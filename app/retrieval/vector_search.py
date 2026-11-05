from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import Document, DocumentChunk


def semantic_search(db: Session, query_embedding: list[float], limit: int) -> list[dict]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    statement = (
        select(DocumentChunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.status == "ready")
        .order_by(distance.asc())
        .limit(limit)
    )
    rows = db.execute(statement).all()
    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "filename": filename,
            "content": chunk.content,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "distance": float(distance_value),
        }
        for chunk, filename, distance_value in rows
    ]
