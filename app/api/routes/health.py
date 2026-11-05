from fastapi import APIRouter
from sqlalchemy import text
from app.database.connection import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    database = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"
    return {"status": "ok" if database == "ok" else "degraded", "database": database}
