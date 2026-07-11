# AGENTS.md — AIDA

RAG demo app: FastAPI backend + React/Vite frontend + Pinecone (vector store) + OpenRouter (embeddings + LLM). No database; all mutable state (document registry, chat history) is in-memory and lost on backend restart. Pinecone vectors persist across restarts.

---

## Repo layout

```
backend/   FastAPI service (Python 3.11, uv)
frontend/  React 19 + TypeScript 6 SPA (Vite 8, npm)
```

Python package root is `backend/app/`. Imports inside the backend are flat: `from schemas import ...`, `from services.document_service import ...` — not `from app.schemas`. The `backend/app/` directory is added to `sys.path` at test time via `conftest.py`.

---

## Developer commands

**Backend** (run from `backend/`):
```bash
uv sync                                              # install deps (uses uv, not pip)
uv run uvicorn app.main:app --reload --port 8000     # dev server
uv run pytest tests/                                 # run all 44 unit tests
```

**Frontend** (run from `frontend/`):
```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b && vite build
npm run lint       # oxlint (NOT ESLint)
```

**Docker** (run from repo root):
```bash
docker compose up --build
```

---

## Required setup

Copy `backend/.env.example` to `backend/.env` and fill in:
```
OPENROUTER_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...   # must be pre-created: 1024 dims, cosine metric
```

The Pinecone index **must already exist** with 1024 dimensions and cosine metric before the backend starts. The index is not created automatically.

Frontend API URL is controlled by `VITE_API_BASE_URL` (default `http://localhost:8000`, baked at build time). Set in `frontend/.env` for local dev.

---

## Toolchain quirks

- **Python package manager is `uv`**, not pip or poetry. Use `uv sync` / `uv run`. `uv.lock` is the lockfile.
- **Frontend linter is `oxlint`**, not ESLint. Config: `frontend/.oxlintrc.json`. No Prettier.
- **No frontend tests** (no jest/vitest). All 44 tests are backend-only.
- **No CI pipeline** and no Makefile. There is a post-commit hook but it's for `repowise` wiki sync, not linting/tests.
- `package-lock.json` is in the frontend's `.dockerignore` (macOS-generated; causes Linux build issues). Don't rely on it in Docker.
- TypeScript config enforces `noUnusedLocals`, `noUnusedParameters`, and `erasableSyntaxOnly`. Build will fail on unused vars.

---

## Testing

All tests are in `backend/tests/`. External deps (Pinecone, OpenRouter, pypdf, pydantic-settings) are stubbed via `sys.modules` injection in `conftest.py` — no real API keys or network needed.

```bash
# from backend/
uv run pytest tests/
uv run pytest tests/test_ai_service.py          # single file
uv run pytest tests/test_ai_service.py::TestChatHistory  # single class
```

No pytest.ini; no ruff; no mypy. Python has no automated linting beyond what you run manually.

---

## Architecture notes

- **Embedding model must stay consistent**: `EMBED_MODEL = "openai/text-embedding-3-small"` (1024 dims) is used for both indexing and querying. Changing the model makes existing Pinecone vectors unusable without re-indexing everything.
- **Streaming**: The chat UI uses `POST /api/v1/chat/stream` (SSE via native `fetch` + `ReadableStream`). `POST /api/v1/chat/ask` is non-streaming and kept only for Swagger testing.
- **SSE format**: stream sends `{type: "sources"}` first, then `{type: "token"}` per token, then `[DONE]` sentinel. Errors send `{type: "error"}`.
- **Per-user isolation**: enforced twice — Pinecone metadata filter + Python post-filter in `ai_service.py`. Both must pass.
- **Document visibility**: `public` docs are visible to all users; `private` docs are filtered to the owning `user_id` only.
- **In-memory document registry** (`_documents: dict`): keyed by `"{user_id}:{filename}"`. Empty on restart; Pinecone vectors remain.
- **Chat history**: `deque(maxlen=20)` per user, lost on restart. Max 10 turns of context sent to LLM.
- **user_id**: a plain string stored in `localStorage` (`aida_user_id`). No real auth. Valid pattern: `/^[a-zA-Z0-9_-]{3,32}$/`.

---

## API surface

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/health` | liveness check |
| GET | `/api/v1/documents/?user_id=` | list docs for user |
| POST | `/api/v1/documents/upload?user_id=&visibility=` | PDF/TXT, ≤10 MB |
| GET | `/api/v1/chat/history?user_id=` | returns `{role, content}[]` — no `sources` field |
| POST | `/api/v1/chat/ask` | non-streaming, for Swagger |
| POST | `/api/v1/chat/stream` | SSE streaming — primary UI endpoint |
| DELETE | `/api/v1/chat/history?user_id=` | clears in-memory history |

---

## Evaluation framework

Two separate eval implementations live side by side. Both run against **live** Pinecone + OpenRouter and share the same dataset (`backend/eval/dataset.py`).

### Naive eval — `backend/eval/`

Custom LLM-judge implementation using raw `httpx` calls. No extra dependencies.

```bash
# from backend/
uv run python -m eval.run_eval --user_id <eval_user_id>
uv run python -m eval.run_eval --user_id eval_user --tags factual
uv run python -m eval.run_eval --user_id eval_user --skip-llm-metrics   # context_recall only
uv run python -m eval.run_eval --user_id eval_user --output eval/results/my_run.json
```

Three metrics — all return `[0.0, 1.0]`:
- **context_recall** — string match (no LLM): fraction of `key_facts` found in retrieved chunks
- **faithfulness** — LLM judge: fraction of answer claims supported by context
- **answer_relevance** — LLM judge: does the answer address the question?

Results: `backend/eval/results/run_<timestamp>.json` (gitignored).

To add test cases: edit `backend/eval/dataset.py` — add `EvalCase` entries with `question`, `ground_truth`, `key_facts`, and optionally `expected_sources` and `tags`.

### RAGAS eval — `backend/eval_ragas/`

Same pipeline, scoring powered by **RAGAS 0.4.x**. Requires extra deps: `ragas`, `langchain-openai`, `langchain-google-vertexai` (already in `pyproject.toml`). Shares `eval/dataset.py` — no separate dataset needed.

```bash
# from backend/
uv run python -m eval_ragas.run_eval --user_id <eval_user_id>
uv run python -m eval_ragas.run_eval --user_id eval_user --tags factual
uv run python -m eval_ragas.run_eval --user_id eval_user --skip-llm-metrics
uv run python -m eval_ragas.run_eval --user_id eval_user --output eval_ragas/results/my_run.json
```

Three metrics (RAGAS): **faithfulness**, **answer_relevancy**, **context_recall** — all `[0.0, 1.0]`.

Results: `backend/eval_ragas/results/run_<timestamp>.json` (gitignored). Exit code 1 if avg faithfulness or answer_relevancy < 0.7, or if any case errored.

**RAGAS wiring quirk**: RAGAS 0.4.3 has a broken import (`langchain_community.chat_models.vertexai`). On fresh install, patch `.venv/lib/python3.11/site-packages/ragas/llms/base.py` lines 12-13 to import from `langchain_google_vertexai` instead. The metrics use `_Faithfulness`, `_ResponseRelevancy`, `_LLMContextRecall` (underscore-prefixed classes) — these are the stable `Metric` subclasses that work with `evaluate()`. The non-underscore versions in `ragas.metrics.collections` use a different base class and are incompatible with `evaluate()`.

---

## Error handling conventions (backend)

- 400 — bad request (wrong file type, duplicate, etc.)
- 413 — file too large (>10 MB)
- 422 — validation error (Pydantic)
- 503 — downstream service unavailable (Pinecone or OpenRouter unreachable)
- All exceptions are chained: `raise RuntimeError("...") from e`
- Rate-limit (429) from OpenRouter is caught and reported with a specific message
