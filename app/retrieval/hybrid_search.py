from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.models import DocumentChunk, Document


def full_text_search(db: Session, query: str, limit: int) -> list[dict]:
    # websearch_to_tsquery safely supports ordinary user-entered search syntax.
    statement = text("""
        SELECT c.id AS chunk_id, c.document_id, d.filename, c.content,
               c.page_number, c.chunk_index,
               ts_rank_cd(to_tsvector('english', c.content),
                          websearch_to_tsquery('english', :query)) AS score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.status = 'ready'
          AND to_tsvector('english', c.content) @@ websearch_to_tsquery('english', :query)
        ORDER BY score DESC
        LIMIT :limit
    """)
    rows = db.execute(statement, {"query": query, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def reciprocal_rank_fusion(vector_results: list[dict], text_results: list[dict], limit: int) -> list[dict]:
    fused: dict[str, dict] = {}
    for ranking, results in enumerate((vector_results, text_results)):
        for rank, item in enumerate(results, start=1):
            key = item["chunk_id"]
            if key not in fused:
                fused[key] = {**item, "rrf_score": 0.0, "retrieval_methods": []}
            fused[key]["rrf_score"] += 1.0 / (settings.rrf_k + rank)
            fused[key]["retrieval_methods"].append("vector" if ranking == 0 else "full_text")
    return sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)[:limit]


def hybrid_search(db: Session, query: str, query_embedding: list[float], limit: int | None = None) -> list[dict]:
    top_k = limit or settings.retrieval_top_k
    vector_results = _semantic_search(db, query_embedding)
    text_results = full_text_search(db, query, settings.fulltext_candidate_limit)
    return reciprocal_rank_fusion(vector_results, text_results, top_k)


def _semantic_search(db: Session, embedding: list[float]) -> list[dict]:
    from app.retrieval.vector_search import semantic_search
    return semantic_search(db, embedding, settings.vector_candidate_limit)
