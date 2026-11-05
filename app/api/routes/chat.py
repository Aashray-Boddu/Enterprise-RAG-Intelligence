from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies import database_session
from app.services.chat_service import answer_question, ChatServiceError

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


class Citation(BaseModel):
    source_id: str
    filename: str
    page_number: int
    chunk_id: str
    retrieval_score: float | None = None
    retrieval_methods: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: int


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(database_session)) -> dict:
    try:
        return answer_question(db, request.question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ChatServiceError as exc:
        raise HTTPException(status_code=503, detail=f"Question answering service unavailable: {exc}") from exc
