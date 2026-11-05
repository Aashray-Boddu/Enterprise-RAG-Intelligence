from pathlib import Path
from uuid import uuid4
import hashlib
import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.database.models import Document, DocumentChunk
from app.ingestion.pipeline import process_file
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentServiceError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_upload(db: Session, filename: str, file_type: str, content: bytes) -> Document:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise DocumentServiceError("Invalid filename.")
    extension = Path(safe_name).suffix.lower().lstrip(".")
    if extension not in settings.allowed_extension_set or extension != file_type.lower():
        raise DocumentServiceError("File extension is not allowed.")
    if not content:
        raise DocumentServiceError("Uploaded file is empty.")
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise DocumentServiceError(f"File exceeds {settings.max_upload_size_mb} MB limit.")

    temporary_path = settings.upload_dir / f".{uuid4().hex}.upload"
    stored_path = settings.upload_dir / f"{uuid4().hex}_{safe_name}"
    try:
        temporary_path.write_bytes(content)
        file_hash = sha256_file(temporary_path)
        existing = db.scalar(select(Document).where(Document.file_hash == file_hash))
        if existing:
            raise DocumentServiceError(f"This file has already been uploaded (document ID: {existing.id}).")
        os.replace(temporary_path, stored_path)

        document = Document(
            filename=safe_name,
            file_type=extension,
            file_hash=file_hash,
            storage_path=str(stored_path.resolve()),
            status="processing",
        )
        db.add(document)
        db.flush()

        chunks = process_file(stored_path, extension)
        db.add_all([
            DocumentChunk(
                document_id=document.id,
                content=chunk["content"],
                chunk_index=chunk["chunk_index"],
                page_number=chunk["page_number"],
                embedding=chunk["embedding"],
            )
            for chunk in chunks
        ])
        document.status = "ready"
        db.commit()
        db.refresh(document)
        logger.info("Ingested %s (%s chunks).", safe_name, len(chunks))
        return document
    except Exception:
        db.rollback()
        temporary_path.unlink(missing_ok=True)
        # A failed ingestion should not leave an orphaned uploaded file.
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        raise


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())).all())


def delete_document(db: Session, document_id: str) -> bool:
    document = db.get(Document, document_id)
    if not document:
        return False
    stored_path = Path(document.storage_path)
    db.delete(document)
    db.commit()
    stored_path.unlink(missing_ok=True)
    return True
