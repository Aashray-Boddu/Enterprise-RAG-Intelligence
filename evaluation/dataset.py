from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "id",
    "question",
    "is_answerable",
    "reference_answer",
    "relevant_documents",
    "evidence_phrases",
    "answer_key_terms",
}


class DatasetError(ValueError):
    """Raised when an evaluation dataset is malformed."""


def load_dataset(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise DatasetError(f"Dataset file not found: {path}")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"Invalid JSON on line {line_number}: {exc}") from exc

            if not isinstance(item, dict):
                raise DatasetError(f"Line {line_number} must contain a JSON object.")
            missing = REQUIRED_FIELDS - item.keys()
            if missing:
                raise DatasetError(
                    f"Line {line_number} is missing fields: {', '.join(sorted(missing))}"
                )
            case_id = str(item["id"]).strip()
            question = str(item["question"]).strip()
            if not case_id or not question:
                raise DatasetError(f"Line {line_number}: id and question cannot be empty.")
            if case_id in seen_ids:
                raise DatasetError(f"Duplicate dataset id: {case_id}")
            if not isinstance(item["is_answerable"], bool):
                raise DatasetError(f"Line {line_number}: is_answerable must be boolean.")
            for field in ("relevant_documents", "evidence_phrases", "answer_key_terms"):
                if not isinstance(item[field], list) or not all(
                    isinstance(value, str) for value in item[field]
                ):
                    raise DatasetError(f"Line {line_number}: {field} must be a list of strings.")
            if item["is_answerable"] and not item["relevant_documents"]:
                raise DatasetError(
                    f"Line {line_number}: answerable cases need at least one relevant document."
                )
            if item["is_answerable"] and not str(item["reference_answer"]).strip():
                raise DatasetError(f"Line {line_number}: answerable cases need a reference_answer.")
            if item["is_answerable"] and not item["evidence_phrases"]:
                raise DatasetError(f"Line {line_number}: answerable cases need evidence_phrases for chunk relevance labels.")
            if item["is_answerable"] and not item["answer_key_terms"]:
                raise DatasetError(f"Line {line_number}: answerable cases need answer_key_terms.")
            if not item["is_answerable"] and item["relevant_documents"]:
                raise DatasetError(
                    f"Line {line_number}: unanswerable cases must have an empty relevant_documents list."
                )
            item["id"] = case_id
            item["question"] = question
            seen_ids.add(case_id)
            cases.append(item)

    if not cases:
        raise DatasetError("The evaluation dataset contains no test cases.")
    return cases
