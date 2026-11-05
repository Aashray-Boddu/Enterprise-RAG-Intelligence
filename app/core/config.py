from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Enterprise RAG Intelligence Platform"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_size_mb: int = 25
    allowed_extensions: str = "pdf,txt,md"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    chunk_size: int = 900
    chunk_overlap: int = 150

    retrieval_top_k: int = 8
    vector_candidate_limit: int = 30
    fulltext_candidate_limit: int = 30
    rrf_k: int = 60

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 120.0
    llm_temperature: float = 0.1

    @property
    def allowed_extension_set(self) -> set[str]:
        return {item.strip().lower().lstrip(".") for item in self.allowed_extensions.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
