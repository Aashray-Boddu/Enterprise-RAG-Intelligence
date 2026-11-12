from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "what", "when", "where", "which", "with", "does",
    "do", "can", "could", "should", "would", "will", "than", "then", "there",
    "these", "those", "they", "them", "its", "using", "use", "used", "has", "have",
}


def tokens(text: str, *, remove_stopwords: bool = False) -> list[str]:
    result = [match.lower() for match in TOKEN_RE.findall(text or "")]
    if remove_stopwords:
        result = [token for token in result if token not in STOPWORDS]
    return result


def token_prf(prediction: str, reference: str) -> dict[str, float]:
    predicted = Counter(tokens(prediction, remove_stopwords=True))
    expected = Counter(tokens(reference, remove_stopwords=True))
    overlap = sum((predicted & expected).values())
    precision = overlap / sum(predicted.values()) if predicted else 0.0
    recall = overlap / sum(expected.values()) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def evidence_match(chunk_text: str, evidence_phrases: list[str]) -> bool:
    """Heuristic chunk label: exact phrase match or strong token recall + F1 overlap."""
    if not evidence_phrases:
        return True
    chunk_normalized = " ".join(tokens(chunk_text))
    chunk_tokens = set(tokens(chunk_text, remove_stopwords=True))
    for phrase in evidence_phrases:
        phrase_normalized = " ".join(tokens(phrase))
        if phrase_normalized and phrase_normalized in chunk_normalized:
            return True
        expected = set(tokens(phrase, remove_stopwords=True))
        if not expected:
            continue
        overlap = len(expected & chunk_tokens)
        recall = overlap / len(expected)
        precision = overlap / len(chunk_tokens) if chunk_tokens else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if recall >= 0.70 and f1 >= 0.12:
            return True
    return False


def retrieval_metrics(
    retrieved: list[dict[str, Any]],
    relevant_chunk_ids: set[str],
    relevant_documents: set[str],
    k: int,
) -> dict[str, float | int | None]:
    top = retrieved[:k]

    relevant_flags = [
        str(item.get("chunk_id")) in relevant_chunk_ids
        for item in top
    ]

    relevant_retrieved = sum(relevant_flags)

    precision = relevant_retrieved / k if k else 0.0

    recall = (
        relevant_retrieved / len(relevant_chunk_ids)
        if relevant_chunk_ids
        else None
    )

    reciprocal_rank = 0.0
    dcg = 0.0

    for rank, is_relevant in enumerate(relevant_flags, start=1):
        if is_relevant:
            # MRR uses the FIRST relevant result only.
            if reciprocal_rank == 0.0:
                reciprocal_rank = 1.0 / rank

            dcg += 1.0 / math.log2(rank + 1)

    ideal_hits = min(len(relevant_chunk_ids), k)

    ideal_dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )

    ndcg = dcg / ideal_dcg if ideal_dcg else None

    retrieved_docs = {
        str(item.get("filename", ""))
        for item in top
    }

    doc_hits = len(retrieved_docs & relevant_documents)

    doc_precision = (
        doc_hits / len(retrieved_docs)
        if retrieved_docs
        else 0.0
    )

    doc_recall = (
        doc_hits / len(relevant_documents)
        if relevant_documents
        else None
    )

    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "mrr_at_k": reciprocal_rank,
        "ndcg_at_k": ndcg,
        "relevant_chunks_retrieved": relevant_retrieved,
        "relevant_chunks_in_corpus": len(relevant_chunk_ids),
        "document_precision_at_k": doc_precision,
        "document_recall_at_k": doc_recall,
        "relevant_documents_retrieved": doc_hits,
        "retrieved_chunks": len(top),
    }

def is_abstention(answer: str) -> bool:
    """
    Detect a standalone refusal, rather than a refusal phrase appearing
    somewhere inside an otherwise substantive answer.
    """
    if not answer or not answer.strip():
        return True

    # Examine the opening sentence only. This prevents quoted refusal
    # phrases later in a substantive answer from triggering abstention.
    first_sentence = re.split(
        r"(?<=[.!?])\s+|\n+",
        answer.strip(),
        maxsplit=1,
    )[0]

    normalized = " ".join(tokens(first_sentence))

    abstention_phrases = (
        "i cannot answer based on the provided documents",
        "cannot answer based on the provided documents",
        "unable to answer based on the provided documents",
        "insufficient information in the provided documents",
        "not enough information in the provided documents",
    )

    return any(
        normalized == phrase or normalized.startswith(phrase + " ")
        for phrase in abstention_phrases
    )


def answer_metrics(
    answer: str,
    reference_answer: str,
    answer_key_terms: list[str],
    retrieved_context: str,
    citations: list[dict[str, Any]],
    relevant_documents: set[str],
    is_answerable: bool,
) -> dict[str, Any]:
    answer = answer or ""
    prf = token_prf(answer, reference_answer) if reference_answer else {
        "precision": None, "recall": None, "f1": None
    }
    answer_tokens = set(tokens(answer, remove_stopwords=True))
    key_tokens = {token for term in answer_key_terms for token in tokens(term, remove_stopwords=True)}
    keyterm_recall = len(answer_tokens & key_tokens) / len(key_tokens) if key_tokens else None

    context_tokens = set(tokens(retrieved_context, remove_stopwords=True))
    substantive_answer_tokens = {
        token for token in answer_tokens if len(token) > 2 and token not in {"cannot", "answer", "provided", "documents"}
    }
    support_ratio = (
        len(substantive_answer_tokens & context_tokens) / len(substantive_answer_tokens)
        if substantive_answer_tokens and is_answerable else None
    )

    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))
    valid_ids = {str(item.get("source_id")) for item in citations}
    valid_citations = cited_ids & valid_ids
    citation_validity = len(valid_citations) / len(cited_ids) if cited_ids else (1.0 if not is_answerable else 0.0)
    cited_filenames = {
        str(item.get("filename")) for item in citations if str(item.get("source_id")) in valid_citations
    }
    correct_cited_filenames = cited_filenames & relevant_documents
    if is_answerable:
        source_citation_precision = (
            len(correct_cited_filenames) / len(cited_filenames) if cited_filenames else 0.0
        )
        source_citation_recall = (
            len(correct_cited_filenames) / len(relevant_documents) if relevant_documents else None
        )
        correct_doc_citation = source_citation_recall == 1.0
    else:
        source_citation_precision = 1.0 if not cited_filenames else 0.0
        source_citation_recall = None
        correct_doc_citation = not cited_ids

    abstained = is_abstention(answer)
    abstention_correct = (abstained == (not is_answerable))

    return {
        "reference_token_precision": prf["precision"],
        "reference_token_recall": prf["recall"],
        "reference_token_f1": prf["f1"],
        "answer_keyterm_recall": keyterm_recall,
        "context_token_support_proxy": support_ratio,
        "citation_validity": citation_validity,
        "source_citation_precision": source_citation_precision,
        "source_citation_recall": source_citation_recall,
        "correct_document_citation": correct_doc_citation,
        "abstained": abstained,
        "abstention_correct": abstention_correct,
    }


def mean_metric(rows: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return sum(values) / len(values) if values else None
