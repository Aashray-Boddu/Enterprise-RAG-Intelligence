<div align="center">

# Enterprise RAG Intelligence Platform

**A source-aware document intelligence workspace built with FastAPI, PostgreSQL + pgvector, local embeddings, hybrid retrieval, and LLM-based answer generation.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/Vector%20Search-pgvector-315C46)](https://github.com/pgvector/pgvector)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Containers-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

</div>

---

## Overview

Enterprise RAG Intelligence is a modular Retrieval-Augmented Generation (RAG) application that turns uploaded business documents into a searchable knowledge base. Users can upload PDF, TXT, and Markdown files, ask natural-language questions, and inspect the document/page references returned with an answer.

The project focuses on the engineering around RAG—not only the LLM call. It includes a page-aware ingestion pipeline, deterministic text chunking, local embedding generation, relational document metadata, vector persistence, lexical and semantic retrieval, Reciprocal Rank Fusion (RRF), a grounded generation prompt, REST endpoints, and a Streamlit interface.

## Product walkthrough

The interface uses a restrained, nature-inspired visual system: warm ivory surfaces, forest-green actions, sage supporting tones, and muted terracotta accents. The aim is to feel like a practical knowledge-management workspace rather than a generic AI demo.

### 1. Document intake

Upload a PDF, TXT, or Markdown file and send it to the ingestion API for extraction, chunking, embedding, and persistence.

![Document intake screen](Uploading%20Docs.png)

### 2. Knowledge library

Review indexed documents, processing status, file metadata, and remove a document together with its associated chunks.

![Uploaded documents screen](Uploaded%20Docs.png)

### 3. Research assistant

Ask questions against the indexed collection and expand the evidence panel to inspect source filenames, page references, and retrieval methods.

![Knowledge assistant screen](Knowledge%20Assistant.png)


## Key capabilities

| Area | Implementation |
|---|---|
| Document intake | Multipart upload endpoint for PDF, TXT, and Markdown |
| PDF extraction | PyMuPDF extracts text page by page so PDF page references can be retained |
| Text preparation | Unicode normalization, whitespace cleanup, and repeated page-edge artifact filtering |
| Chunking | Recursive character splitting, configured at 900 characters with 150-character overlap |
| Embeddings | Local `sentence-transformers/all-MiniLM-L6-v2` model; normalized 384-dimensional vectors |
| Vector retrieval | pgvector cosine-distance ordering |
| Lexical retrieval | PostgreSQL full-text search with `websearch_to_tsquery` and `ts_rank_cd` |
| Hybrid ranking | Reciprocal Rank Fusion with smoothing constant `k = 60` |
| Answer generation | Ollama-hosted Llama 3.2 by default, with an OpenAI provider option |
| Grounding | System instructions require context-only answers and source IDs; insufficient evidence should trigger a fixed fallback response |
| Persistence | SQLAlchemy 2.0 models over PostgreSQL; document/chunk relationship supports cascading deletion |
| User interface | Streamlit tabs for document intake, library management, and question answering |
| Local deployment | Docker Compose for PostgreSQL + pgvector, Ollama, API, and frontend |

## Architecture

```mermaid
flowchart TD
    U[User] --> UI[Streamlit UI]
    UI --> API[FastAPI REST API]
    API --> DS[Document Service]
    DS --> EX[PyMuPDF / Text Extraction]
    EX --> CL[Cleaner]
    CL --> CH[Recursive Chunker]
    CH --> EM[Sentence Transformer Embeddings]
    EM --> DB[(PostgreSQL + pgvector)]

    UI --> CHAT[Chat Endpoint]
    CHAT --> QE[Query Embedding]
    QE --> VS[Vector Search]
    CHAT --> FTS[PostgreSQL Full-Text Search]
    VS --> RRF[Reciprocal Rank Fusion]
    FTS --> RRF
    RRF --> CTX[Context Builder + Source Metadata]
    CTX --> LLM[Ollama / OpenAI Provider]
    LLM --> ANS[Grounded Answer + Citations]
    ANS --> UI
```

### End-to-end request lifecycle

1. **Upload:** the Streamlit frontend sends a multipart request to `POST /api/v1/documents/upload`.
2. **Validate and fingerprint:** the document service checks the extension and configured size limit, computes a SHA-256 digest, and rejects a duplicate content hash.
3. **Extract and clean:** PDFs are read page by page with PyMuPDF. TXT and Markdown files are read as UTF-8. Text is normalized and repeated short page-edge lines are filtered when they appear across multiple PDF pages.
4. **Chunk and embed:** cleaned page text is split into overlapping passages. Sentence Transformers generates one normalized vector per passage.
5. **Persist:** document metadata and its chunks are committed to PostgreSQL. Each chunk stores its document ID, chunk index, page number, content, and 384-dimensional vector.
6. **Retrieve:** a chat question is embedded. The system independently obtains a vector-ranked candidate list and a full-text-ranked candidate list.
7. **Fuse and answer:** RRF combines the two rankings. The context builder labels retrieved passages with source IDs, filenames, page numbers, and chunk indexes. The configured LLM receives the question and context under a grounding-focused system prompt.

## Retrieval design

### Semantic retrieval

The query is encoded with the same embedding model used during ingestion. pgvector calculates cosine distance between the query vector and stored chunk vectors. Lower cosine distance indicates a closer vector match. The implementation fetches a candidate set before final ranking.

### Lexical retrieval

PostgreSQL full-text search tokenizes and normalizes the query and chunk text. `websearch_to_tsquery` provides a user-friendly query parser, while `ts_rank_cd` ranks matching passages based on term evidence. This channel is useful when exact terminology, policy names, identifiers, or uncommon words matter.

### Reciprocal Rank Fusion

The two retrieval channels return ranked lists with scores that are not directly comparable. RRF combines their positions rather than attempting to normalize the original scores:

\[
RRF(d) = \sum_{r \in \{vector, lexical\}} \frac{1}{k + rank_r(d)}
\]

The configured smoothing constant is `k = 60`. A passage appearing near the top of both lists accumulates evidence from both channels and can rise in the combined ranking. The final context is limited by `RETRIEVAL_TOP_K`.

## Technology choices

| Technology | Why it is used here |
|---|---|
| FastAPI | Defines typed HTTP endpoints, validates request bodies, and exposes interactive OpenAPI documentation. It keeps the API layer separate from the interface and core services. |
| Uvicorn | Runs the FastAPI application as an ASGI server during local development and container execution. |
| PostgreSQL | Stores durable document metadata and chunk records in a relational database. |
| pgvector | Stores fixed-dimension embeddings alongside relational data and exposes distance operators for vector retrieval. |
| SQLAlchemy 2.0 | Defines the ORM models and manages database sessions and transactions. |
| psycopg 3 | Provides the PostgreSQL driver used by SQLAlchemy. |
| Sentence Transformers | Produces text embeddings locally, avoiding a paid embedding API call for every uploaded passage and query. |
| all-MiniLM-L6-v2 | A compact general-purpose sentence embedding model that outputs 384-dimensional vectors; selected for a practical local semantic-search baseline. |
| PyMuPDF | Extracts PDF text page by page, preserving the page number needed for citations. |
| LangChain text splitters | Supplies a recursive splitter that tries paragraph, line, sentence-like, and character boundaries while maintaining overlap. The project uses the splitter only; it does not depend on a LangChain RAG chain. |
| Ollama + Llama 3.2 | Provides a locally served chat model for experimentation without sending document context to a hosted generation API. The default Ollama `llama3.2` tag maps to the 3B text model; it is a relatively small local model, not a guarantee of high-end answer quality. |
| OpenAI API option | Offers an alternative hosted generation provider when local model quality or hardware constraints require it. |
| Streamlit | Builds the Python-native user interface without maintaining a separate JavaScript frontend. |
| Docker Compose | Starts the database and, optionally, the full multi-service stack with declared ports, dependencies, and persistent volumes. |

## Repository structure

```text
Enterprise-RAG-Intelligence/
├── app/
│   ├── api/                 # FastAPI routes and dependency injection
│   ├── core/                # Settings and logging
│   ├── database/            # SQLAlchemy models and engine/session setup
│   ├── ingestion/           # Extraction, cleaning, chunking, embeddings
│   ├── retrieval/           # Vector search, full-text search, RRF, context
│   ├── llm/                 # Provider abstraction, prompts, generation
│   ├── services/            # Document and chat orchestration
│   └── main.py              # FastAPI application and lifespan startup
├── frontend/
│   └── streamlit_app.py     # Streamlit interface
├── Uploading Docs.png
├── Uploaded Docs.png
├── Knowledge Assitant.png
├── .streamlit/              # Streamlit theme
│   └── config.toml          # Configuration template
├── .env.example             
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Run locally on Windows

### Prerequisites

- Python 3.12
- Docker Desktop with Docker Compose
- Ollama for Windows, with the `llama3.2` model pulled
- Git

### 1. Create and activate the virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure the application

```powershell
Copy-Item .env.example .env
```

For the local Windows setup, retain the default host URLs in `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### 3. Start PostgreSQL and Ollama

```powershell
docker compose up -d db
ollama pull llama3.2
```

Ensure the Ollama application is running on the host.

### 4. Start the API

In terminal 1:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Start the frontend

In terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run frontend/streamlit_app.py
```

Open the application at **http://localhost:8501**. The API documentation is at **http://localhost:8000/docs**, and the health endpoint is **http://localhost:8000/health**.

## Full Docker Compose setup

The Compose file can run the database, Ollama, API, and Streamlit frontend together:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec ollama ollama pull llama3.2
```

Then open **http://localhost:8501**. In this mode, the API uses Docker service hostnames (`db` and `ollama`), not `localhost`, to reach the other containers.

Useful commands:

```powershell
docker compose ps
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f db
docker compose down
```

`docker compose down` preserves named volumes. `docker compose down -v` also deletes the persistent database, model, and upload volumes; use it only when you intend to reset application data.

## API reference

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Reports application and database health |
| `POST` | `/api/v1/documents/upload` | Uploads and synchronously processes a PDF, TXT, or Markdown file |
| `GET` | `/api/v1/documents` | Lists stored document metadata and status |
| `DELETE` | `/api/v1/documents/{document_id}` | Deletes a document and cascades its chunk records |
| `POST` | `/api/v1/chat` | Embeds a question, retrieves passages, and generates an answer |

Example chat request:

```json
{
  "question": "What is the employee expense reimbursement deadline?"
}
```

The response includes an answer, a list of citations (source ID, filename, page, chunk ID, RRF score, and retrieval methods), and the number of retrieved chunks.

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | local PostgreSQL URL | SQLAlchemy connection URL using psycopg 3 |
| `UPLOAD_DIR` | `./data/uploads` | Local path for uploaded source files |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum accepted upload size |
| `ALLOWED_EXTENSIONS` | `pdf,txt,md` | Accepted file extensions |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local text embedding model |
| `EMBEDDING_DIMENSION` | `384` | Expected vector dimension |
| `CHUNK_SIZE` | `900` | Recursive splitter target chunk size in characters |
| `CHUNK_OVERLAP` | `150` | Character overlap between adjacent chunks |
| `RETRIEVAL_TOP_K` | `8` | Number of fused chunks sent to context construction |
| `VECTOR_CANDIDATE_LIMIT` | `30` | Candidate count from vector search |
| `FULLTEXT_CANDIDATE_LIMIT` | `30` | Candidate count from lexical search |
| `RRF_K` | `60` | RRF smoothing constant |
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model tag |
| `OPENAI_API_KEY` | empty | Required only for the OpenAI provider |

## Manual validation scenarios

These are useful checks to run against a small, known dataset. They are manual validation scenarios, not an automated test suite bundled with the repository.

| Scenario | What to verify |
|---|---|
| Upload a PDF | It is accepted, page-aware chunks are persisted, and status becomes `ready` |
| Upload TXT or Markdown | Text is extracted and associated with page number 1 |
| Upload identical contents again | Duplicate SHA-256 content is rejected |
| Ask a direct factual question | The answer matches the source and cites the expected filename/page |
| Ask using different wording | Semantic retrieval can surface a relevant passage even with fewer exact keyword matches |
| Ask a terminology-heavy question | PostgreSQL full-text retrieval can contribute lexical matches |
| Ask across multiple documents | Evidence from multiple sources can appear in the same context |
| Ask an unsupported question | The system should respond that it cannot answer from the provided documents |
| Delete a document | Document metadata and associated chunks are removed |

## Engineering trade-offs and current limitations

The project is intentionally a local, single-tenant demonstrator of a complete RAG workflow. The following limitations are explicit and should be addressed before public or production use:

- **Synchronous ingestion:** extraction, chunking, embedding, and database writes happen during the upload request. A production system should move this work to a durable background queue with retries, job state, and dead-letter handling.
- **No OCR:** image-only or scanned PDFs do not yield usable text through the current extraction path. An OCR stage is needed for those documents.
- **No authentication or tenant isolation:** endpoints are not protected by user identity or authorization. Do not expose the service publicly with sensitive documents.
- **No managed migration history:** tables are created during application startup. Add Alembic migrations and a controlled schema deployment process.
- **Local file storage:** uploaded files are stored on the API host/container volume. Multi-instance deployments should use object storage and durable object keys.
- **Citation enforcement:** the model is prompted to cite supplied source IDs, but the response is not parsed against an allow-list of retrieved IDs. Add structured output and citation validation.
- **Retrieval evaluation:** there is no automated benchmark for recall@k, MRR, answer faithfulness, or citation precision in the repository. Add a labelled evaluation set before tuning chunk sizes or retrieval weights.
- **Vector indexing:** the current schema stores pgvector embeddings but does not create an HNSW or IVFFlat index. Exact vector ordering is simpler for a small corpus; add and benchmark an approximate index as the collection grows.
- **Language configuration:** lexical retrieval uses PostgreSQL's English text-search configuration. Multilingual collections need language-aware processing and evaluation.
- **No reranker:** RRF merges two rankings but does not use a cross-encoder to rerank the fused candidates. A reranker is a possible quality improvement if evaluation shows it is needed.

## Security notes

- Keep `.env` out of version control. Commit `.env.example` with non-secret defaults only.
- Do not upload customer, employer, or other confidential documents to a public repository or unprotected demo.
- Use authentication, authorization, tenant-level access controls, rate limiting, upload scanning, encrypted storage, secret management, audit logs, and tested backups before production deployment.
- The default database credentials in the example configuration are development credentials and must be changed outside local development.

## Further technical documentation

- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Uvicorn documentation](https://www.uvicorn.org/)
- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [pgvector](https://github.com/pgvector/pgvector)
- [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/)
- [Psycopg 3 documentation](https://www.psycopg.org/psycopg3/docs/)
- [Sentence Transformers documentation](https://www.sbert.net/)
- [PyMuPDF documentation](https://pymupdf.readthedocs.io/)
- [LangChain text splitters](https://python.langchain.com/docs/concepts/text_splitters/)
- [Ollama model library: Llama 3.2](https://ollama.com/library/llama3.2)
- [Streamlit documentation](https://docs.streamlit.io/)
- [Docker Compose documentation](https://docs.docker.com/compose/)

