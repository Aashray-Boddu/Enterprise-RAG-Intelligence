from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.database.connection import SessionLocal, initialize_database
from app.database.models import Document
from app.services.document_service import ingest_upload, sha256_file

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "sample data"
SAMPLE_FILES = [
    SAMPLE_DIR / "k8s_architecture.md",
    SAMPLE_DIR / "k8s_pods_and_workloads.md",
    SAMPLE_DIR / "k8s_troubleshooting_cheatsheet.md",
]


def main() -> None:
    missing = [path.name for path in SAMPLE_FILES if not path.is_file()]
    if missing:
        raise SystemExit(f"Sample files missing: {', '.join(missing)}")

    initialize_database()
    db = SessionLocal()
    try:
        for path in SAMPLE_FILES:
            digest = sha256_file(path)
            existing = db.scalar(select(Document).where(Document.file_hash == digest))
            if existing:
                print(f"SKIP already ingested: {path.name} (document ID: {existing.id})")
                continue
            document = ingest_upload(
                db=db,
                filename=path.name,
                file_type="md",
                content=path.read_bytes(),
            )
            print(f"INGESTED: {document.filename} (document ID: {document.id})")
    finally:
        db.close()

    print("\nSample evaluation documents are ready. Existing documents were not deleted or modified.")


if __name__ == "__main__":
    main()
