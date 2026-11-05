# Enterprise RAG Intelligence Platform

A modular Retrieval-Augmented Generation application using FastAPI, PostgreSQL + pgvector, Sentence Transformers, Ollama/OpenAI, and Streamlit.

## Architecture

1. Upload a PDF, TXT, or Markdown file through Streamlit or the REST API.
2. Extract page-aware text (PyMuPDF for PDFs), clean it, and split it into overlapping chunks.
3. Generate normalized 384-dimensional embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
4. Store document metadata and vectors in PostgreSQL.
5. Retrieve candidate passages using cosine distance and PostgreSQL full-text search.
6. Fuse ranked results using Reciprocal Rank Fusion (RRF, k=60).
7. Construct source-aware context and ask the configured LLM to answer only from that context.

## Requirements

- Python 3.12
- PostgreSQL 16 with the pgvector extension (or Docker)
- Ollama locally with a chat model downloaded, or an OpenAI API key
- The embedding model is downloaded from Hugging Face on first use.

## Local setup (Windows PowerShell)

```powershell
# From the project root
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

Copy-Item .env.example .env
```

Start PostgreSQL with pgvector. One option is to run only the database service:

```powershell
docker compose up -d db
```

For Ollama installed on the host, start Ollama and download the configured model:

```powershell
ollama pull llama3.2
```

Edit `.env` if required. For a host-installed Ollama and Docker-hosted database, use:
`DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db`
and `OLLAMA_BASE_URL=http://localhost:11434`.

Run the API in terminal 1:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run Streamlit in terminal 2:

```powershell
streamlit run frontend/streamlit_app.py
```

Open:
- Streamlit: http://localhost:8501
- FastAPI Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Full Docker setup

Copy `.env.example` to `.env`, then run:

```powershell
docker compose up --build -d
docker compose exec ollama ollama pull llama3.2
```

The API container uses the Compose service hostname `db` for PostgreSQL and `ollama` for Ollama. The frontend is at http://localhost:8501.

To inspect logs:

```powershell
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f db
```

To stop:

```powershell
docker compose down
```

To remove database, model, and uploaded-file volumes as well:

```powershell
docker compose down -v
```

## OpenAI provider

Set these values in `.env`:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4o-mini
```

Restart the API. Embeddings remain local; only answer generation uses OpenAI.

## REST API

### Upload

`POST /api/v1/documents/upload` as multipart form data with field `file`.

### List

`GET /api/v1/documents`

### Delete

`DELETE /api/v1/documents/{document_id}`

### Chat

`POST /api/v1/chat`

```json
{
  "question": "What does the policy say about data retention?"
}
```

Response contains `answer`, `citations`, and `retrieved_chunks`. Citations include filename, page, chunk identifier, retrieval methods, and RRF score.

## Important implementation notes

- Ingestion currently runs synchronously in the API request. For large-scale production deployments, move ingestion to a durable background queue (for example Celery/RQ) and add retry/dead-letter handling.
- The app creates the pgvector extension and SQLAlchemy tables on startup. Production deployments should use Alembic migrations and a controlled migration process.
- The upload directory is local persistent storage. For multi-instance production deployments, use object storage and store object keys in PostgreSQL.
- Add authentication, authorization, tenant isolation, malware scanning, rate limiting, audit logging, encryption/key management, backup/restore tests, and observability before exposing this service to untrusted users.
- PDF extraction is text-based; scanned/image-only PDFs require OCR, which is not included.
- Full-text search uses PostgreSQL's English text configuration. Adjust language configuration for multilingual corpora.
- The citation list reports retrieved evidence. The LLM is instructed to cite source IDs, but output citation correctness should be evaluated and enforced in production with structured generation and validation.
