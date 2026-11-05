from sqlalchemy.orm import Session
from app.ingestion.embeddings import embed_query
from app.retrieval.hybrid_search import hybrid_search
from app.retrieval.context_builder import build_context
from app.llm.generator import generate_answer
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatServiceError(Exception):
    pass


def answer_question(db: Session, question: str) -> dict:
    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty.")
    try:
        embedding = embed_query(question)
        results = hybrid_search(db, question, embedding)
        context, citations = build_context(results)
        if not results:
            return {
                "answer": "I cannot answer based on the provided documents.",
                "citations": [],
                "retrieved_chunks": 0,
            }
        answer = generate_answer(question, context)
        return {"answer": answer, "citations": citations, "retrieved_chunks": len(results)}
    except Exception as exc:
        logger.exception("Question answering failed.")
        raise ChatServiceError(str(exc)) from exc
