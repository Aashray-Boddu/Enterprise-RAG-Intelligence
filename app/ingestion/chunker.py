from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.ingestion.cleaner import clean_text


def chunk_pages(pages: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )
    chunks: list[dict] = []
    global_index = 0
    for page in pages:
        content = clean_text(page.get("text", ""))
        if not content:
            continue
        for piece in splitter.split_text(content):
            piece = piece.strip()
            if piece:
                chunks.append({
                    "content": piece,
                    "chunk_index": global_index,
                    "page_number": int(page.get("page_number", 1)),
                })
                global_index += 1
    return chunks
