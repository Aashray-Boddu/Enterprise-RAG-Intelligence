from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.api.dependencies import database_session
from app.core.config import settings
from app.database.models import Document
from app.services.document_service import ingest_upload, list_documents, delete_document, DocumentServiceError

router = APIRouter(prefix="/documents", tags=["documents"])


def serialize_document(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "file_type": document.file_type,
        "status": document.status,
        "created_at": document.created_at.isoformat() if document.created_at else None,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(database_session),
) -> dict:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in settings.allowed_extension_set:
        raise HTTPException(status_code=415, detail="Only PDF, TXT and MD files are supported.")
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    try:
        document = ingest_upload(db, filename, extension, content)
        return {"message": "Document processed successfully.", "document": serialize_document(document)}
    except DocumentServiceError as exc:
        raise HTTPException(status_code=409 if "already been uploaded" in str(exc) else 400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {exc}") from exc
    finally:
        await file.close()


@router.get("")
def get_documents(db: Session = Depends(database_session)) -> dict:
    documents = list_documents(db)
    return {"count": len(documents), "documents": [serialize_document(item) for item in documents]}


@router.delete("/{document_id}")
def remove_document(document_id: str, db: Session = Depends(database_session)) -> dict:
    if not delete_document(db, document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document and associated chunks deleted.", "document_id": document_id}
