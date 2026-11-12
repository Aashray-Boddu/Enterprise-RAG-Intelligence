from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.metrics import mean_metric


AGGREGATE_METRICS = [
    "precision_at_k",
    "recall_at_k",
    "mrr_at_k",
    "ndcg_at_k",
    "document_precision_at_k",
    "document_recall_at_k",
    "reference_token_precision",
    "reference_token_recall",
    "reference_token_f1",
    "answer_keyterm_recall",
    "context_token_support_proxy",
    "citation_validity",
    "source_citation_precision",
    "source_citation_recall",
    "correct_document_citation",
    "abstention_correct",
    "judge_correctness",
    "judge_faithfulness",
    "judge_relevance",
]



def percentile(values: list[float], quantile: float) -> float | None:
    """Linearly interpolated percentile for a non-empty list of numeric values."""
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

def build_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    strategies = sorted({row["strategy"] for row in case_results})
    summary: dict[str, Any] = {}
    for strategy in strategies:
        rows = [row for row in case_results if row["strategy"] == strategy]
        successful_generation_rows = [
            row for row in rows
            if row.get("llm_generation_succeeded")
            and isinstance(row.get("generation_latency_ms"), (int, float))
        ]
        failed_generation_rows = [
            row for row in rows
            if row.get("llm_generation_failed")
            and isinstance(row.get("generation_latency_ms"), (int, float))
        ]
        successful_generation_latencies = [
            float(row["generation_latency_ms"]) for row in successful_generation_rows
        ]
        generation_attempts = sum(bool(row.get("llm_generation_attempted")) for row in rows)
        strategy_summary: dict[str, Any] = {
            "cases": len(rows),
            "llm_generation_attempts": generation_attempts,
            "answer_generation_successes": len(successful_generation_rows),
            "answer_generation_failures": sum(bool(row.get("llm_generation_failed")) for row in rows),
            "generation_exceptions": sum(bool(row.get("answer_error")) for row in rows),
            "answers_returned_including_fallback": sum(bool(row.get("answer_generated")) for row in rows),
            "judge_failures": sum(bool(row.get("judge_error")) for row in rows),
            "mean_embedding_latency_ms": mean_metric(rows, "embedding_latency_ms"),
            "mean_retrieval_latency_ms": mean_metric(rows, "retrieval_latency_ms"),
            "mean_generation_latency_ms": (
                sum(successful_generation_latencies) / len(successful_generation_latencies)
                if successful_generation_latencies else None
            ),
            "median_generation_latency_ms": percentile(successful_generation_latencies, 0.50),
            "p95_generation_latency_ms": percentile(successful_generation_latencies, 0.95),
            "mean_failed_generation_latency_ms": mean_metric(failed_generation_rows, "generation_latency_ms"),
            "generation_success_rate": (
                len(successful_generation_rows) / generation_attempts if generation_attempts else None
            ),
            "unanswerable_cases": sum(not row["is_answerable"] for row in rows),
            "mean_unanswerable_retrieved_chunks": mean_metric(
                [row for row in rows if not row["is_answerable"]], "retrieved_chunks"
            ),
            "unanswerable_retrieval_empty_rate": mean_metric(
                [row for row in rows if not row["is_answerable"]], "unanswerable_retrieval_empty"
            ),
        }
        for metric in AGGREGATE_METRICS:
            strategy_summary[metric] = mean_metric(rows, metric)
        summary[strategy] = strategy_summary
    return summary


def write_reports(output_dir: Path, run_id: str, metadata: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(cases)
    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "summary": summary,
        "cases": cases,
        "metric_notes": {
            "reference_token_f1": "Deterministic lexical overlap with the reference answer; not semantic correctness.",
            "answer_keyterm_recall": "Fraction of manually defined answer key terms present in the generated answer.",
            "context_token_support_proxy": "Lexical overlap proxy only; it is not a substitute for semantic faithfulness evaluation.",
            "judge_metrics": "Optional model-based scores; inspect rationales and manually review samples.",
            "abstention_accuracy": "Deterministic comparison of the answer's abstention state with the dataset is_answerable label; not an LLM-judge opinion.",
            "generation_latency": "Mean, median, and p95 use successful non-empty LLM responses only; failed call latency is reported separately and fallback responses are excluded.",
            "retrieval_relevance": "Relevant chunks are labelled using the dataset's evidence phrases and relevant document filenames.",
        },
    }

    json_path = output_dir / f"{run_id}.json"
    csv_path = output_dir / f"{run_id}.csv"
    md_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_fields = [
        "case_id", "strategy", "question", "is_answerable", "retrieved_chunks",
        "embedding_latency_ms", "retrieval_latency_ms", "generation_latency_ms", "llm_generation_attempted", "llm_generation_succeeded", "llm_generation_failed", "answer_generated", "answer_error",
        "precision_at_k", "recall_at_k", "mrr_at_k", "ndcg_at_k",
        "document_precision_at_k", "document_recall_at_k",
        "reference_token_precision", "reference_token_recall", "reference_token_f1",
        "answer_keyterm_recall", "context_token_support_proxy", "citation_validity",
        "source_citation_precision", "source_citation_recall", "correct_document_citation",
        "abstained", "abstention_correct",
        "judge_correctness", "judge_faithfulness", "judge_relevance", "judge_rationale",
        "unanswerable_retrieval_empty",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for row in cases:
            flat = {key: row.get(key) for key in csv_fields}
            flat["case_id"] = row.get("case_id")
            writer.writerow(flat)

    lines = [
        f"# RAG Evaluation Report — {run_id}",
        "",
        f"Generated: {payload['generated_at']}",
        f"Dataset: {metadata.get('dataset_path')}",
        f"Test cases: {metadata.get('case_count')}",
        f"Ready documents / chunks: {metadata.get('ready_document_count')} / {metadata.get('ready_chunk_count')}",
        f"Top-K: {metadata.get('top_k')}",
        "",
        "> Metrics are benchmark evidence for this dataset and database snapshot, not a universal quality score.",
        "",
        "## Retrieval and answer comparison",
        "",
        "| Strategy | P@K | Recall@K | MRR@K | nDCG@K | Doc P@K | Doc Recall@K | Answer Token F1 | Abstention Accuracy | Unanswerable Empty Rate | Retrieval ms | Generation mean / median / p95 ms | Gen success / attempts / failures |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    def fmt(value: Any) -> str:
        return "—" if value is None else f"{float(value):.3f}"
    for strategy, values in summary.items():
        lines.append(
            f"| {strategy} | {fmt(values.get('precision_at_k'))} | {fmt(values.get('recall_at_k'))} "
            f"| {fmt(values.get('mrr_at_k'))} | {fmt(values.get('ndcg_at_k'))} "
            f"| {fmt(values.get('document_precision_at_k'))} | {fmt(values.get('document_recall_at_k'))} "
            f"| {fmt(values.get('reference_token_f1'))} "
            f"| {fmt(values.get('abstention_correct'))} | {fmt(values.get('unanswerable_retrieval_empty_rate'))} "
            f"| {fmt(values.get('mean_retrieval_latency_ms'))} "
            f"| {fmt(values.get('mean_generation_latency_ms'))} / {fmt(values.get('median_generation_latency_ms'))} / {fmt(values.get('p95_generation_latency_ms'))} "
            f"| {values.get('answer_generation_successes', 0)} / {values.get('llm_generation_attempts', 0)} / {values.get('answer_generation_failures', 0)} |"
        )
    if any(values.get("judge_correctness") is not None for values in summary.values()):
        lines += [
            "",
            "## Optional LLM-judge scores",
            "",
            "| Strategy | Correctness | Faithfulness | Relevance |",
            "|---|---:|---:|---:|",
        ]
        for strategy, values in summary.items():
            lines.append(
                f"| {strategy} | {fmt(values.get('judge_correctness'))} "
                f"| {fmt(values.get('judge_faithfulness'))} | {fmt(values.get('judge_relevance'))} |"
            )
    lines += [
        "",
        "## Interpretation notes",
        "",
        "- P@K, Recall@K, MRR@K and nDCG@K are computed using evidence-phrase-labelled relevant chunks.",
        "- Document recall measures whether expected source filenames were retrieved within the first K chunks.",
        "- Reference token F1 is lexical overlap, so semantically equivalent paraphrases may score lower.",
        "- Source citation precision/recall check whether generated source IDs map to the expected source documents.",
        "- Context token support is a lexical proxy, not a semantic faithfulness score.",
        "- Model-judge scores are subjective estimates. Abstention accuracy is computed deterministically from answerability labels; the LLM judge does not score abstention.",
        "- Generation mean/median/p95 include successful LLM calls only. Failed calls are counted separately and their mean elapsed time is reported separately; fallback responses are not counted as LLM generations.",
        "- If LLM judge metrics are missing, rerun with `--llm-judge` to add model-based review scores.",
        "- Review individual case rows and manually inspect misses before drawing conclusions.",
        "",
        "## Cases with retrieval or generation errors",
        "",
    ]
    errors = [
        row for row in cases
        if row.get("answer_error") or row.get("ground_truth_warning")
        or row.get("judge_error") or row.get("llm_generation_failed")
    ]
    if not errors:
        lines.append("No recorded retrieval-ground-truth or answer-generation errors.")
    else:
        for row in errors:
            detail = (
                row.get("answer_error")
                or row.get("ground_truth_warning")
                or row.get("judge_error")
                or "LLM returned an empty response."
            )
            lines.append(f"- `{row['case_id']}` / {row['strategy']}: {detail}")
    lines += ["", "## Reproducibility", "", "The JSON report includes run metadata and per-case results. Keep it with the source revision, dataset version, and model configuration used for the run.", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}
