from functools import lru_cache
from threading import Lock
import numpy as np
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_model_lock = Lock()


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    logger.info("Loading embedding model: %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)
    if model.get_sentence_embedding_dimension() != settings.embedding_dimension:
        raise RuntimeError("Configured embedding dimension does not match the model output.")
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    with _model_lock:
        vectors = _load_model().encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[1] != settings.embedding_dimension:
        raise RuntimeError(f"Unexpected embedding shape: {vectors.shape}")
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
