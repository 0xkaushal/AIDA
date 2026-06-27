# AIDA — AI Document Assistant

AIDA is a full-stack Retrieval-Augmented Generation (RAG) application. Upload your documents, and ask questions about them in natural language. AIDA finds the most relevant passages and uses a large language model to generate grounded, accurate answers — citing the source documents it used.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [Running with Docker Compose](#running-with-docker-compose)
  - [Running Locally (Development)](#running-locally-development)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Model Selection](#model-selection)
- [Key Technical Decisions](#key-technical-decisions)
- [Engineering Standards](#engineering-standards)
- [AI Tools in Development](#ai-tools-in-development)
- [What I'd Do Differently](#what-id-do-differently)
- [Features](#features)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│   React + TypeScript + Vite  (port 80 / 5173 dev)      │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP (Axios)
┌───────────────────────▼─────────────────────────────────┐
│               FastAPI Backend  (port 8000)               │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  /documents  │  │    /chat     │  │   /health    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘  │
│         │                 │                             │
│  ┌──────▼───────────────────────────────────────────┐   │
│  │            document_service / ai_service         │   │
│  └──────┬───────────────────────────┬───────────────┘   │
└─────────┼───────────────────────────┼───────────────────┘
          │                           │
┌─────────▼──────────┐   ┌────────────▼──────────────────┐
│  Pinecone (vectors)│   │   OpenRouter API              │
│  - user_id filter  │   │   - text-embedding-3-small    │
│  - visibility flag │   │   - gpt-4o-mini               │
└────────────────────┘   └───────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend framework | React 19 + TypeScript 6 |
| Build tool | Vite 8 |
| Routing | React Router DOM 7 |
| HTTP client | Axios |
| Backend framework | FastAPI |
| ASGI server | Uvicorn |
| Package manager | uv |
| PDF parsing | pypdf |
| Embeddings + LLM | OpenRouter (`text-embedding-3-small`, `gpt-4o-mini`) |
| Vector database | Pinecone |
| Containerisation | Docker + Docker Compose |
| Production web server | Nginx (Alpine) |

---

## Project Structure

```
AIDA/
├── docker-compose.yml
├── README.md
├── FEATURES.md
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py               # FastAPI app, CORS, router registration
│       ├── core/
│       │   └── config.py         # Pydantic Settings (env vars)
│       ├── schemas/
│       │   └── __init__.py       # Pydantic request/response models
│       ├── services/
│       │   ├── document_service.py  # Parse, chunk, embed, store
│       │   └── ai_service.py        # Retrieve, RAG prompt, chat history
│       └── api/routes/
│           ├── health.py
│           ├── documents.py
│           └── chat.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx               # Shell, navbar, routing
        ├── index.css             # Design system (CSS custom properties)
        ├── components/
        │   └── UserIdGate.tsx    # First-load user ID prompt
        ├── pages/
        │   ├── UploadPage.tsx    # File upload + document list
        │   └── ChatPage.tsx      # Chat thread UI
        ├── services/
        │   └── api.ts            # All Axios API calls
        └── types/
            └── index.ts          # TypeScript interfaces
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker + Docker Compose)
- A [Pinecone](https://www.pinecone.io/) account with an index created
  - Index dimensions: **1024**
  - Metric: **cosine**
- An [OpenRouter](https://openrouter.ai/) API key

---

## Getting Started

### Running with Docker Compose

1. **Clone the repo**

```bash
git clone <repo-url>
cd AIDA
```

2. **Create the backend environment file**

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in your keys:

```env
OPENROUTER_API_KEY=sk-or-...
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=your-index-name
```

3. **Build and start**

```bash
docker compose up --build
```

4. **Open the app**

| Service | URL |
|---|---|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

> On subsequent starts (no code changes) use `docker compose up` — images are cached.

---

### Running Locally (Development)

**Backend:**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev          # starts on http://localhost:5173
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | ✅ | OpenRouter API key for embeddings and LLM |
| `PINECONE_API_KEY` | ✅ | Pinecone API key |
| `PINECONE_INDEX_NAME` | ✅ | Name of your Pinecone index (must have 1024 dimensions) |
| `CORS_ORIGINS` | optional | Comma-separated list of allowed origins (default: `localhost:5173`, `localhost`) |

### Frontend (Docker build arg)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL baked into the frontend at build time |

---

## API Reference

### Health

```
GET /api/v1/health
→ { status, app, version }
```

### Documents

```
GET  /api/v1/documents/?user_id=<id>
→ { documents: [{ filename, chunks_stored, characters, uploaded_at, visibility }] }

POST /api/v1/documents/upload?user_id=<id>&visibility=private|public
Body: multipart/form-data  { file }
Accepted types: application/pdf, text/plain
→ { message, filename, chunks_stored, characters, visibility }
```

### Chat

```
GET    /api/v1/chat/history?user_id=<id>
→ { messages: [{ role: "user"|"assistant", content }] }

POST   /api/v1/chat/ask
Body:  { question: string, user_id: string }
→ { answer: string, sources: string[] }

DELETE /api/v1/chat/history?user_id=<id>
→ { message }
```

---

## How It Works

### Document Ingestion

```
File upload
    └─► extract text (pypdf / UTF-8 decode)
            └─► chunk into 500-char windows (50-char overlap)
                    └─► embed each chunk (text-embedding-3-small, 1024 dims)
                            └─► upsert to Pinecone
                                  metadata: { text, source, user_id, visibility }
```

### Question Answering

```
User question
    └─► embed question (same model, 1024 dims)
            └─► query Pinecone
                  filter: user_id == me  OR  visibility == "public"
                  top_k: 5
                    └─► Python post-filter (safety net for old vectors)
                            └─► build messages:
                                  [system: RAG context]
                                  [... chat history (last 10 turns)]
                                  [user: question]
                                    └─► call gpt-4o-mini via OpenRouter
                                            └─► return answer + source filenames
                                                  store in per-user deque (max 20 msgs)
```

---

## Model Selection

### Embedding — `openai/text-embedding-3-small`

The embedding model converts text chunks and user questions into vectors so Pinecone can find semantically similar content. I chose `text-embedding-3-small` for three reasons:

- **Best cost-to-quality ratio for RAG.** It significantly outperforms the older `ada-002` on retrieval benchmarks while costing less. The `large` variant is higher quality but ~5× more expensive per token — the improvement is not worth it at this scale.
- **Flexible dimensions.** The model supports truncated dimensions (256–1536). I use 1024, which balances vector quality with Pinecone storage size. Using all 1536 dims would increase storage and query cost with diminishing returns.
- **Same model for indexing and querying.** A critical constraint: the model used to embed document chunks at upload time must be identical to the model used to embed questions at query time. If these differ, similarity scores are meaningless. Keeping it as a single named constant (`EMBED_MODEL`) makes this impossible to accidentally break.

Alternatives I considered:
- `text-embedding-ada-002` — older, slightly weaker on MTEB benchmarks, no dimension flexibility. Ruled out.
- Local models (`nomic-embed-text`, `bge-large-en`) — free but require self-hosting infrastructure. Not justified for a POC.

---

### LLM — `openai/gpt-4o-mini`

The LLM receives the retrieved context passages and the user's question, and generates a grounded natural-language answer. I chose `gpt-4o-mini` for these reasons:

- **Instruction following.** The system prompt explicitly tells the model to answer only from the provided context and to say "I couldn't find that" when the answer is absent. `gpt-4o-mini` respects this constraint reliably. Weaker models hallucinate beyond the context even with explicit instructions.
- **128K token context window.** Injecting 8 retrieved chunks plus chat history fits comfortably. There is no risk of hitting context limits for normal documents.
- **Cost and speed.** At ~$0.15 per million input tokens it is among the cheapest capable models. Streaming responses mean the user sees tokens immediately, making latency less of a concern.
- **Available via OpenRouter without a direct OpenAI account.** OpenRouter acts as a proxy, which also makes it easy to swap models (e.g. to `anthropic/claude-haiku`) by changing a single constant if needed.

Alternatives I considered:
- `openai/gpt-4o` — noticeably better reasoning but ~20× more expensive. The quality gain is not justified for a document Q&A use case where retrieval quality matters more than reasoning depth.
- Self-hosted (`llama-3`, `mistral`) — removes data egress concerns but requires GPU infrastructure. Not viable for a POC.

---

## Key Technical Decisions

**1. `uv` as the package manager**
I used `uv` instead of `pip` or `poetry` because it is significantly faster, lightweight, and gives you a single tool for both virtual environment management and dependency resolution. The `uv.lock` lockfile ensures fully reproducible installs across local dev and Docker builds.

**2. In-memory state for document registry and chat history**
Both `_documents` and `_chat_history` are Python dicts/deques that live in process memory. I made this call deliberately to keep the build simple and get the core RAG functionality working quickly. The trade-off is that restarting the container wipes the document list and all chat history — the vectors in Pinecone persist but the metadata does not. For a production setup I would use a cloud-hosted database like Supabase (Postgres) or even SQLite as a first step. I've documented this in `PRODUCTION.md`.

**3. SSE streaming instead of WebSockets**
The chat response flow is strictly one-directional: server streams tokens to the client. SSE (Server-Sent Events) is the right tool for this — it's simpler to implement, works over standard HTTP, and has native browser support via `EventSource`. WebSockets add bidirectional complexity that isn't needed here. If I later wanted real-time features like server-pushed notifications, I'd revisit WebSockets.

**4. OpenRouter as the LLM gateway**
I personally prefer not managing separate API keys for every model provider. OpenRouter gives a single key and endpoint that proxies to OpenAI, Anthropic, Google, and others. More importantly, switching from `gpt-4o-mini` to `claude-haiku` or any other model is a one-line constant change — no SDK swaps, no auth changes. Any LLM gateway (AWS Bedrock, Azure AI) would serve the same purpose; OpenRouter was the quickest to set up for a POC.

---

## Engineering Standards

**Followed:**
- Type hints throughout the Python backend
- Pydantic validation at every API boundary — request bodies, query params, response models
- CORS configured explicitly with an allowlist, not wildcard
- Docker layer caching — `pyproject.toml` and `uv.lock` copied before source so deps are cached between builds
- Secrets in `.env` file, never in code or baked into Docker images
- Structured logging with `key=value` pairs parseable by log aggregators
- 44 unit tests covering positive and negative cases for both services, zero network calls

**Skipped (and why):**
- **Real authentication** — the current `user_id` is a self-reported string from localStorage. Implementing proper JWT auth would require a full auth service and was out of scope for a POC. Documented as a P0 requirement in `PRODUCTION.md`
- **Database persistence** — in-memory state resets on restart. Acceptable for a demo; SQLite or Supabase would be the next step
- **Prometheus metrics / distributed tracing** — logs give enough signal at this scale. Metrics and tracing are documented as next steps
- **CI/CD pipeline** — no GitHub Actions setup. Would add automated test runs on PR and deploy-on-merge before going to production
- **Integration tests against live Pinecone** — require real API keys and network access; the unit test suite covers the logic with mocks

---

## AI Tools in Development

I used **GitHub Copilot** throughout this project. Honestly, this is mostly a vibe-coded application — I leaned on Copilot heavily for boilerplate, and it saved a lot of time.

**What I used it for:**
- Generating boilerplate: route handlers, Pydantic schemas, Dockerfiles, test scaffolding
- Asking questions on how to improve both technically (chunking strategy, score thresholds, error handling patterns) and functionally (streaming UX, duplicate detection, visibility controls)
- CSS design system structure and component patterns

**Where I reviewed carefully rather than accepting blindly:**
- The authorisation filter logic in `retrieve_chunks` — I read this line by line because a mistake here would silently expose one user's private documents to another
- Error handling and exception chaining — Copilot's first suggestion was a bare `except Exception: pass` pattern; I rewrote this properly
- The system prompt wording — the initial suggestion was generic; I tightened the grounding instruction and the fallback phrase myself

**My do's and don'ts with AI coding assistants:**
- ✅ Use for repetitive structure and boilerplate where the pattern is well-understood
- ✅ Use to explore options and ask "what are the trade-offs here"
- ✅ Use to generate test cases — it's good at covering edge cases I'd miss
- ❌ Never accept security-sensitive code without reading it carefully
- ❌ Never let it write the reasoning sections of docs — those must reflect your own thinking, not a summarised version of it

---

## Features

See [FEATURES.md](FEATURES.md) for a full breakdown of every feature with implementation details.
AI Document Assistant
