# RAG Evaluation Framework

This package benchmarks the production retrieval implementations in `app/retrieval/` without changing the live FastAPI chat route or database schema.

## What it measures

- **Vector-only retrieval:** calls `app.retrieval.vector_search.semantic_search`.
- **Keyword-only retrieval:** calls `app.retrieval.hybrid_search.full_text_search`.
- **Hybrid retrieval:** calls the existing `app.retrieval.hybrid_search.hybrid_search` implementation (vector + PostgreSQL full-text + RRF).
- **Chunk retrieval:** Precision@K, Recall@K, MRR@K, and nDCG@K using evidence phrases in the labelled dataset.
- **Document selection:** document Precision@K and Recall@K using expected source filenames.
- **Answer evaluation:** reference token precision/recall/F1, answer key-term recall, citation-ID validity, source-document citation precision/recall, and unanswerable-query abstention accuracy.
- **Context-support proxy:** lexical overlap between answer terms and retrieved context. This is explicitly a heuristic and must not be described as semantic faithfulness.
- **Optional model judge:** correctness, faithfulness, and relevance scores using the configured LLM provider (`--llm-judge`). This is a model-based estimate, not ground truth. The default setting uses the same provider configured for answer generation; for independent judging, configure a separate evaluator in a future extension. Abstention correctness is calculated deterministically from the dataset's `is_answerable` label and the returned answer; it is not delegated to the judge model.

## 1. Prepare the application

Run commands from the repository root in the same Python environment used by the application:

```powershell
.\.venv\Scripts\Activate.ps1
```

If the virtual environment does not exist yet:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from `.env.example` if it does not already exist, then start PostgreSQL:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db
```

Ensure Ollama is running and the configured model is available if you plan to generate answers:

```powershell
ollama pull llama3.2
```

The evaluation runner uses your existing `DATABASE_URL`, `EMBEDDING_MODEL`, `LLM_PROVIDER`, and retrieval settings. It does not reset the database or modify existing documents.

## 2. Ingest the included benchmark documents

The included JSONL dataset is grounded in the three Markdown files under `sample data/`. To make those labelled sources available in PostgreSQL, run:

```powershell
python -m evaluation.ingest_sample_docs
```

The helper is idempotent: it checks the existing document SHA-256 hash and skips files already ingested. It adds the sample documents; it does not delete or overwrite other documents.

If you prefer to evaluate your own knowledge base, edit `evaluation/datasets/sample_rag_dataset.jsonl` and replace each `relevant_documents`, `evidence_phrases`, `reference_answer`, and `answer_key_terms` with labels grounded in files already stored in the database. `relevant_documents` must use the exact stored filename.

## 3. Run a quick retrieval-only smoke test

This skips LLM answer generation and checks all three retrieval strategies against the first five questions:

```powershell
python -m evaluation.runner --retrieval-only --max-cases 5 --top-k 5
```

## 4. Run the complete benchmark

Runs all dataset questions through vector-only, keyword-only, and hybrid RRF retrieval, then generates one answer for each strategy/case pair:

```powershell
python -m evaluation.runner --top-k 5
```

This is 18 questions × 3 retrieval methods = up to 54 answer-generation calls. It can take several minutes depending on the configured model and hardware.

Optional model-based evaluation (additional LLM calls):

```powershell
python -m evaluation.runner --top-k 5 --llm-judge
```

Other useful options:

```powershell
# Only benchmark hybrid retrieval
python -m evaluation.runner --strategies hybrid --top-k 5

# Run a short generation-enabled smoke test
python -m evaluation.runner --max-cases 3 --top-k 5

# Use a different labelled JSONL dataset
python -m evaluation.runner --dataset evaluation/datasets/my_dataset.jsonl --top-k 5
```

## 5. Outputs

Every run creates timestamped files under `evaluation/results/`:

- `.json`: run metadata, each test case, retrieved filenames/chunk IDs and ranking metadata, citations, generated answers, latency, and metrics.
- `.csv`: one row per case and retrieval strategy for spreadsheet analysis.
- `.md`: compact comparison table and warnings.

Keep the JSON/CSV/Markdown reports together with the Git commit and dataset version used for the run. The JSON metadata records the corpus document/chunk counts and a SHA-256 hash of the dataset. The same scores are only directly comparable when the corpus contents, dataset, embedding model, LLM, prompts, retrieval settings, and top-K are held constant. Any other ready documents in the database participate in retrieval and can compete with the labelled benchmark sources; keep the corpus stable between runs.

## Metric interpretation and limitations

- Retrieval labels are derived from the dataset's expected source filenames and evidence phrases. Review any `ground_truth_warning` in the JSON output; an answerable case without matching stored evidence should not be interpreted as a retrieval failure until its labels/corpus are checked.
- Precision@K uses K as the denominator even when fewer than K chunks are returned.
- Recall@K is calculated against all stored chunks in expected source documents that match the evidence phrases.
- Document Recall@K is based on whether each expected filename appears among the top K retrieved chunks. Document Precision@K divides the number of expected unique documents retrieved by the number of unique documents returned in the top K chunks.
- Reference token F1 is a deterministic lexical baseline. It does not fully recognise paraphrases or semantic equivalence.
- Context token support is a lexical proxy. It is not an entailment/faithfulness metric.
- Model-judge scores are subjective estimates. Inspect rationales and manually review representative successes and failures. If the same model both answers and judges, expect correlated bias.
- Judge faithfulness scores claims in the generated answer; irrelevant extra passages in the retrieved context should not lower faithfulness unless the answer relies on them or makes unsupported claims.
- Generation mean, median, and p95 latency include successful LLM calls only. Failed calls are counted separately, with their mean elapsed time reported separately. Deterministic fallback responses are not counted as LLM generations.
- `answer_generation_successes` counts non-empty successful LLM responses; `answer_generation_failures` includes exceptions and empty model outputs. `generation_exceptions` isolates thrown errors. `answers_returned_including_fallback` also counts the deterministic no-retrieval fallback.
- The included test set is a starter benchmark, not a statistically representative evaluation suite. Expand it with questions from your actual use cases before making broad quality claims.
- The benchmark tests the current retrieval implementation. It does not add reranking or alter production retrieval behaviour.

## Tests

The metric and dataset tests use Python's standard library `unittest` and do not require a live database or LLM. The evaluation runner calls the same idempotent schema initializer used by the API, so you do not need to start FastAPI first:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
