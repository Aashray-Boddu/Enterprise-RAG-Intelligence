from pathlib import Path
import fitz


class ExtractionError(Exception):
    pass


def extract_pdf(path: Path) -> list[dict]:
    pages: list[dict] = []
    try:
        with fitz.open(path) as pdf:
            if pdf.is_encrypted:
                raise ExtractionError("Encrypted PDFs are not supported.")
            for index, page in enumerate(pdf, start=1):
                pages.append({"page_number": index, "text": page.get_text("text") or ""})
    except (fitz.FileDataError, RuntimeError, OSError) as exc:
        raise ExtractionError(f"Unable to read PDF: {exc}") from exc
    if not any(item["text"].strip() for item in pages):
        raise ExtractionError("The PDF contains no extractable text.")
    return pages


def extract_text(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as exc:
        raise ExtractionError(f"Unable to read text file as UTF-8: {exc}") from exc
    return [{"page_number": 1, "text": text}]


def extract_document(path: Path, file_type: str) -> list[dict]:
    extension = file_type.lower().lstrip(".")
    if extension == "pdf":
        return extract_pdf(path)
    if extension in {"txt", "md"}:
        return extract_text(path)
    raise ExtractionError(f"Unsupported file type: {extension}")
