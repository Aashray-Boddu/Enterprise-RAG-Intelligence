from pathlib import Path
from app.ingestion.extractors import extract_document
from app.ingestion.cleaner import remove_repeated_page_artifacts
from app.ingestion.chunker import chunk_pages
from app.ingestion.embeddings import embed_texts


def process_file(path: Path, file_type: str) -> list[dict]:
    pages = extract_document(path, file_type)
    pages = remove_repeated_page_artifacts(pages)
    chunks = chunk_pages(pages)
    if not chunks:
        raise ValueError("No text chunks were produced from this document.")
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["embedding"] = vector
    return chunks
