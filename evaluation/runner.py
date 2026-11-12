from __future__ import annotations

import argparse
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.database.connection import SessionLocal, initialize_database
from app.database.models import Document, DocumentChunk
from app.ingestion.embeddings import embed_query
from app.llm.generator import generate_answer
from app.retrieval.context_builder import build_context
from app.retrieval.vector_search import semantic_search
from app.retrieval.hybrid_search import full_text_search, hybrid_search
from evaluation.dataset import load_dataset
from evaluation.judge import evaluate_with_llm_judge
from evaluation.metrics import answer_metrics, evidence_match, retrieval_metrics
from evaluation.reporting import write_reports


STRATEGIES = ("vector", "keyword", "hybrid")


def _relevant_chunks(db, case: dict[str, Any]) -> tuple[set[str], str | None]:
    filenames = case["relevant_documents"]
    if not filenames:
        return set(), None
    rows = db.execute(
        select(DocumentChunk.id, DocumentChunk.content, Document.filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.status == "ready", Document.filename.in_(filenames))
    ).all()
    available = {str(row.filename) for row in rows}
    missing = set(filenames) - available
    if missing:
        return set(), f"Expected source document(s) not found in database: {', '.join(sorted(missing))}"
    evidence = case.get("evidence_phrases", [])
    relevant_ids = {
        str(row.id) for row in rows if evidence_match(row.content, evidence)
    }
    if not relevant_ids:
        return set(), "No stored chunks matched this case's evidence_phrases; review the dataset labels or ingest the expected documents."
    return relevant_ids, None


def _retrieve(db, query: str, embedding: list[float], strategy: str, top_k: int) -> list[dict]:
    if strategy == "vector":
        return semantic_search(db, embedding, top_k)
    if strategy == "keyword":
        return full_text_search(db, query, top_k)
    if strategy == "hybrid":
        return hybrid_search(db, query, embedding, top_k)
    raise ValueError(f"Unsupported strategy: {strategy}")


def run_evaluation(
    dataset_path: Path,
    output_dir: Path,
    top_k: int = 5,
    strategies: tuple[str, ...] = STRATEGIES,
    retrieval_only: bool = False,
    include_llm_judge: bool = False,
    max_cases: int | None = None,
) -> dict[str, Any]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    if max_cases is not None and max_cases < 1:
        raise ValueError("max_cases must be at least 1 when supplied.")
    if retrieval_only and include_llm_judge:
        raise ValueError("--llm-judge requires answer generation; do not combine it with --retrieval-only.")
    if len(set(strategies)) != len(strategies):
        raise ValueError("Each retrieval strategy may be selected only once.")
    if not strategies:
        raise ValueError("Select at least one retrieval strategy.")
    unknown = set(strategies) - set(STRATEGIES)
    if unknown:
        raise ValueError(f"Unknown retrieval strategy: {', '.join(sorted(unknown))}")
    dataset = load_dataset(dataset_path)
    if max_cases is not None:
        dataset = dataset[:max_cases]
    if not dataset:
        raise ValueError("No test cases selected.")

    initialize_database()
    db = SessionLocal()
    case_results: list[dict[str, Any]] = []
    try:
        ready_count = db.scalar(select(Document.id).where(Document.status == "ready").limit(1))
        if not ready_count:
            raise RuntimeError(
                "No ready documents found in the database. Run `python -m evaluation.ingest_sample_docs` first."
            )

        ready_document_count = db.scalar(
            select(func.count(Document.id)).where(Document.status == "ready")
        ) or 0
        ready_chunk_count = db.scalar(
            select(func.count(DocumentChunk.id))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.status == "ready")
        ) or 0

        for case_number, case in enumerate(dataset, start=1):
            print(f"[{case_number}/{len(dataset)}] {case['id']}: {case['question']}")
            relevant_ids, ground_truth_warning = _relevant_chunks(db, case)
            relevant_docs = set(case["relevant_documents"])
            embedding_started = time.perf_counter()
            query_embedding = embed_query(case["question"])
            embedding_ms = (time.perf_counter() - embedding_started) * 1000

            for strategy in strategies:
                retrieval_started = time.perf_counter()
                retrieved = _retrieve(db, case["question"], query_embedding, strategy, top_k)
                retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
                context, citations = build_context(retrieved)
                retrieval_scores = retrieval_metrics(retrieved, relevant_ids, relevant_docs, top_k)
                if not case["is_answerable"] or ground_truth_warning:
                    # P/R metrics have no valid positive denominator for unanswerable or unlabelled cases.
                    for metric_name in (
                        "precision_at_k", "recall_at_k", "mrr_at_k", "ndcg_at_k",
                        "document_precision_at_k", "document_recall_at_k",
                    ):
                        retrieval_scores[metric_name] = None

                answer = ""
                answer_error = None
                generation_ms = None
                llm_generation_attempted = False
                llm_generation_succeeded = False
                llm_generation_failed = False
                judge_scores = {}
                if not retrieval_only:
                    if not retrieved:
                        # The fixed fallback is a deterministic abstention, not an LLM call.
                        answer = "I cannot answer based on the provided documents."
                    else:
                        llm_generation_attempted = True
                        generation_started = time.perf_counter()
                        try:
                            answer = generate_answer(case["question"], context)
                            llm_generation_succeeded = bool(answer and answer.strip())
                        except Exception as exc:  # Continue so one model failure does not discard the benchmark.
                            answer_error = f"{type(exc).__name__}: {exc}"
                        finally:
                            # Preserve elapsed time for failed calls, but report it separately.
                            generation_ms = (time.perf_counter() - generation_started) * 1000
                        llm_generation_failed = not llm_generation_succeeded

                    if answer_error is None:
                        answer_scores = answer_metrics(
                            answer=answer,
                            reference_answer=case.get("reference_answer", ""),
                            answer_key_terms=case.get("answer_key_terms", []),
                            retrieved_context=context,
                            citations=citations,
                            relevant_documents=relevant_docs,
                            is_answerable=case["is_answerable"],
                        )
                        if include_llm_judge:
                            try:
                                judge_scores = evaluate_with_llm_judge(
                                    question=case["question"],
                                    answer=answer,
                                    reference_answer=case.get("reference_answer", ""),
                                    context=context,
                                    is_answerable=case["is_answerable"],
                                )
                            except Exception as exc:
                                judge_scores = {"judge_error": f"{type(exc).__name__}: {exc}"}
                    else:
                        answer_scores = {}
                else:
                    answer_scores = {}

                row: dict[str, Any] = {
                    "case_id": case["id"],
                    "strategy": strategy,
                    "question": case["question"],
                    "is_answerable": case["is_answerable"],
                    "expected_documents": case["relevant_documents"],
                    "retrieved_documents": list(dict.fromkeys(item.get("filename") for item in retrieved)),
                    "retrieved_chunk_ids": [str(item.get("chunk_id")) for item in retrieved],
                    "retrieved_chunk_details": [
                        {
                            "chunk_id": str(item.get("chunk_id")),
                            "filename": item.get("filename"),
                            "page_number": item.get("page_number"),
                            "chunk_index": item.get("chunk_index"),
                            "score": item.get("score"),
                            "distance": item.get("distance"),
                            "rrf_score": item.get("rrf_score"),
                            "retrieval_methods": item.get("retrieval_methods", []),
                        }
                        for item in retrieved
                    ],
                    "citations": citations,
                    "reference_answer": case.get("reference_answer", ""),
                    "answer_key_terms": case.get("answer_key_terms", []),
                    "retrieved_chunks": len(retrieved),
                    "unanswerable_retrieval_empty": (not retrieved) if not case["is_answerable"] else None,
                    "retrieval_latency_ms": round(retrieval_ms, 3),
                    "embedding_latency_ms": round(embedding_ms, 3),
                    "ground_truth_warning": ground_truth_warning,
                    "answer_generated": bool(answer) if not retrieval_only else False,
                    "llm_generation_attempted": llm_generation_attempted,
                    "llm_generation_succeeded": llm_generation_succeeded,
                    "llm_generation_failed": llm_generation_failed,
                    "answer": answer,
                    "answer_error": answer_error,
                    "generation_latency_ms": round(generation_ms, 3) if generation_ms is not None else None,
                    **retrieval_scores,
                    **answer_scores,
                    **judge_scores,
                }
                case_results.append(row)

    finally:
        db.close()

    run_id = datetime.now(timezone.utc).strftime("rag_eval_%Y%m%dT%H%M%S_%fZ")
    metadata = {
        "dataset_path": str(dataset_path),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "case_count": len(dataset),
        "ready_document_count": int(ready_document_count),
        "ready_chunk_count": int(ready_chunk_count),
        "top_k": top_k,
        "strategies": list(strategies),
        "retrieval_only": retrieval_only,
        "llm_judge_enabled": include_llm_judge,
        "llm_provider": settings.llm_provider,
        "ollama_model": settings.ollama_model if settings.llm_provider.lower() == "ollama" else None,
        "openai_model": settings.openai_model if settings.llm_provider.lower() == "openai" else None,
        "embedding_model": settings.embedding_model,
        "rrf_k": settings.rrf_k,
        "vector_candidate_limit": settings.vector_candidate_limit,
        "fulltext_candidate_limit": settings.fulltext_candidate_limit,
    }
    paths = write_reports(output_dir, run_id, metadata, case_results)
    return {"run_id": run_id, "summary": paths, "case_count": len(case_results), "metadata": metadata}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark vector, keyword, and RRF hybrid retrieval.")
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/datasets/sample_rag_dataset.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--strategies", default="vector,keyword,hybrid", help="Comma-separated: vector,keyword,hybrid")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip LLM answer generation; useful for a quick retrieval smoke test.")
    parser.add_argument("--llm-judge", action="store_true", help="Add optional model-based correctness/faithfulness/relevance scores.")
    parser.add_argument("--max-cases", type=int, default=None, help="Run only the first N dataset cases.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    strategies = tuple(item.strip() for item in args.strategies.split(",") if item.strip())
    result = run_evaluation(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        top_k=args.top_k,
        strategies=strategies,
        retrieval_only=args.retrieval_only,
        include_llm_judge=args.llm_judge,
        max_cases=args.max_cases,
    )
    print("\nEvaluation completed.")
    print(f"Run ID: {result['run_id']}")
    for kind, path in result["summary"].items():
        print(f"{kind.upper()} report: {path}")
    print("\nOpen the Markdown and CSV reports to inspect strategy comparisons and per-question results.")


if __name__ == "__main__":
    main()
