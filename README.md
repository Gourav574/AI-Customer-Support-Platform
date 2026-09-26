# SupportIQ — AI Customer Support & Ticket Intelligence

SupportIQ is a full-stack portfolio project for customer support operations. Customers create and track requests; agents work a routed queue and use source-backed knowledge assistance; managers review measured operational analytics, agent/team workload, document sources, and editable routing rules.

## What it does

- Customer registration, login, private ticket history, replies, close/reopen, and safe attachment upload/download.
- Agent ticket queue, analysis panel, reply/status/priority changes, escalation, reassignment, and response drafts that agents edit and send themselves.
- Manager analytics, user/team views, routing-rule management, knowledge document lifecycle, and role management for admins.
- Local scikit-learn ticket classifiers, confidence estimates, language detection, workload-based routing, document retrieval, and FastAPI OpenAPI docs.
- PostgreSQL-first SQLAlchemy schema, Alembic migrations, Docker Compose, reproducible training/evaluation, and automated tests.

## AI/ML Architecture

### Ticket intelligence

`backend/app/ai/` normalizes the ticket subject and description, then runs independent TF-IDF + logistic-regression models for category, intent, priority, and sentiment. Probability for each predicted class is averaged into the displayed confidence score; it is a model score, not a calibrated probability. Lightweight offline language detection handles common scripts and a few common languages. The classifier uses explicit rules only when an artifact is missing or a model cannot load.

The labeled training sample is [data/sample/tickets.csv](data/sample/tickets.csv). Run `python scripts/train_models.py` to make a deterministic 75/25 split (`random_state=42`), fit each model, calculate accuracy and macro precision/recall/F1 on the holdout, and write the fitted `.joblib` models plus the actual measured report to `backend/app/ai/artifacts/`. The included artifacts and `evaluation.json` were produced by that script. The sample is intentionally small and is a reproducibility demo, not a claim of production model quality. `/api/ml/evaluation` exposes the stored measurements to managers.

### Knowledge retrieval and response assistant

Knowledge ingestion extracts text from PDF (PyMuPDF), TXT, and DOCX, normalizes and chunks the text, computes vectors, then stores both each passage and its embedding in PostgreSQL. Retrieval ranks normalized vectors by cosine similarity. FAISS inner-product search is used when `faiss-cpu` is available; otherwise NumPy performs the same cosine ranking over stored vectors.

The default provider is a small sklearn character n-gram hashing vectorizer. It requires no model downloads and supports fully local operation; its subword similarity is a fallback, not a transformer semantic model. For transformer semantic retrieval, install the optional Sentence Transformers/FAISS dependencies in `requirements-semantic.txt`, explicitly cache `sentence-transformers/all-MiniLM-L6-v2` using `scripts/cache_embedding_model.py`, then run `POST /api/knowledge/reindex`. Model weights are not downloaded at app startup. Each result exposes its document, filename, passage index, text, cosine score, and provider.

The response assistant uses the ticket subject, category, intent, and sentiment to create an editable professional draft. It includes retrieved passages and source references when available. With no relevant result, the draft says the knowledge base did not answer the question and avoids making a policy promise. It never sends a message automatically and requires no paid LLM API.

OCR is an opt-in fallback. Install `requirements-ocr.txt`, install the Tesseract executable separately, and set `OCR_ENABLED=true`; normal installation and startup do not require OCR libraries.

## Architecture and structure

```text
backend/app/
  main.py                 FastAPI factory, app lifecycle, development seed
  config.py database.py models.py schemas.py security.py
  routers/                auth, tickets, users/routing, analytics, knowledge, attachments
  ai/                     preprocessors, classifier, sentiment, language, routing, response assistant
  rag/                    extraction/chunking, embedding providers, vector store, retriever
alembic/                  Alembic environment and initial/legacy upgrade migration
data/sample/tickets.csv   labeled model-training data
data/knowledge_base/      sample policy documents for the seed command
scripts/                  model training, model-cache, demo-data commands
frontend/                 responsive HTML/CSS/vanilla JavaScript + Chart.js
tests/                    API, security, AI, RAG, routing, analytics, and migration tests
```

PostgreSQL is the intended production database. SQLite is used by tests and supports local smoke runs. Tables include users, teams, routing rules, tickets, assignments, analyses, messages, status history, escalations, attachments, knowledge documents, and knowledge chunks. Foreign keys, check constraints, uniqueness rules, indexes, and SQLAlchemy relationships are defined in `backend/app/models.py`.

## Install and run locally

Use Python 3.12. From the project root in PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a private `SECRET_KEY` and a PostgreSQL `DATABASE_URL` in `.env`. Create the database itself once (tables are created by the migration, not by hand):

```powershell
createdb -U postgres customer_support_db
```

Then migrate, optionally seed the local demo accounts/data, and run the web server:

```powershell
alembic upgrade head
python scripts/seed_demo.py
uvicorn backend.app.main:app --reload
```

The app is at <http://127.0.0.1:8000>; Swagger is at <http://127.0.0.1:8000/docs>. The frontend is served by FastAPI; there is no Node build step. To start without sample data, skip `seed_demo.py` and register a customer. Create agents/managers through a development seed or with the admin role-management endpoint after provisioning an admin account.

### Existing MVP databases

The first migration detects the unversioned schema from the previous SupportIQ MVP. It adds team/routing and embedding columns while preserving the existing ticket and customer records. Back up the database before migration. For a new database, the same migration creates the complete schema.

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL; e.g. `postgresql+psycopg2://postgres:password@localhost:5432/customer_support_db` |
| `SECRET_KEY` | JWT signing key; replace the example value |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB` | Local attachment storage and size limit |
| `SEED_DEMO` | Seed sample users, tickets, teams and policy documents at app startup |
| `EMBEDDING_MODEL` | Optional Sentence Transformer model name |
| `EMBEDDING_DOWNLOAD_MODEL` | Explicitly permit model download when indexing; default `false` |
| `OCR_ENABLED` | Attempt optional OCR on PDFs with no extractable text |

`.env` is ignored by Git. Do not commit credentials.

## Demo accounts and data

Run `python scripts/seed_demo.py` after migration. This creates synthetic demo records and sample policy files only. All demo accounts use `SupportDemo123!`:

- `customer@example.com`
- `agent@example.com`
- `sam@example.com`
- `manager@example.com`

The password is deliberately development-only. Do not reuse it outside a local demo.

## Training and retrieval maintenance

```powershell
python scripts/train_models.py
```

The command replaces the four model artifacts and writes metrics calculated from the included holdout set. For actual transformer embeddings, install the optional extras, then explicitly cache model weights:

```powershell
pip install -r requirements-semantic.txt
$env:EMBEDDING_DOWNLOAD_MODEL = "true"
python scripts/cache_embedding_model.py
```

Restart the app with `EMBEDDING_DOWNLOAD_MODEL=false` and click **Rebuild embeddings** in the manager Knowledge Base page or call `POST /api/knowledge/reindex`. OCR support setup is described above; `requirements-ocr.txt` alone does not install the Tesseract program.

## Docker Compose

Docker Compose starts PostgreSQL, runs Alembic migrations, and launches the API. The default compose seed is for local demonstration only. Set strong `POSTGRES_PASSWORD` and `SECRET_KEY` values in `.env` before exposing services.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Visit <http://localhost:8000> and <http://localhost:8000/docs>. Set `SEED_DEMO=false` to start with an empty database.

## API highlights

- Auth: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- Tickets: `GET/POST /api/tickets`, `GET/PUT /api/tickets/{id}`, message/attachment/analyze/escalate/suggest-response routes
- Routing: `GET /api/teams`, `GET/PUT /api/routing-rules/{category}`, `PUT /api/tickets/{id}/assign`
- Knowledge: `GET /api/knowledge`, `POST /api/knowledge/upload`, `/search`, `/reindex`, `DELETE /api/knowledge/{id}`
- Analytics: `GET /api/analytics/overview`, `/tickets`, `/agents`; manager-only measured ML metrics at `/api/ml/evaluation`

All API routes are documented in Swagger. Ticket search is filtered server-side and paginated using `limit` and `offset`. Customers only see their own tickets; agents can see their assigned or unassigned queue, and cannot read tickets assigned to another agent; managers/admins have operational visibility.

## Tests

```powershell
pytest -q
```

Tests use an isolated SQLite database. They cover password hashing, registration/login/JWT, role and ticket isolation, ticket lifecycle, trained inference, sentiment, workload routing, editable routing rules, document ingestion/vector search, cited response suggestions, analytics, and upgrading an unversioned MVP database. A live PostgreSQL server is not needed by the test suite.

## Known limits and next steps

The training corpus is a small hand-labeled example set; gather a reviewed domain dataset and evaluate it before operational use. Without optional Sentence Transformers, the app uses char n-gram vector similarity rather than contextual embeddings. Language detection is lightweight, and the response assistant uses grounded templates instead of an LLM. OCR requires external Tesseract installation. Metrics such as customer satisfaction are not shown because no satisfaction data is collected. Add production rate limiting, object storage, malware scanning, audit retention, and a larger PostgreSQL integration test environment before deployment.
