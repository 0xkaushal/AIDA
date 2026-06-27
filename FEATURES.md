# AIDA — Feature Reference

Complete documentation of every feature in the application.

---

## Table of Contents

1. [User Identity & Session](#1-user-identity--session)
2. [Document Upload](#2-document-upload)
3. [Document Visibility (Public / Private)](#3-document-visibility-public--private)
4. [Duplicate File Detection](#4-duplicate-file-detection)
5. [Document List](#5-document-list)
6. [RAG Question Answering](#6-rag-question-answering)
7. [Per-User Document Isolation](#7-per-user-document-isolation)
8. [Chat History (In-Memory)](#8-chat-history-in-memory)
9. [Source Attribution](#9-source-attribution)
10. [Chat Thread UI](#10-chat-thread-ui)
11. [Typing Indicator / Streaming](#11-typing-indicator--streaming)
12. [Light / Dark Mode](#12-light--dark-mode)
13. [Responsive Layout](#13-responsive-layout)
14. [Sticky Navbar with Active Links](#14-sticky-navbar-with-active-links)
15. [Docker Compose Deployment](#15-docker-compose-deployment)
16. [Health Check Endpoint](#16-health-check-endpoint)
17. [SPA Routing](#17-spa-routing)
18. [Onboarding Tour](#18-onboarding-tour)

---

## 1. User Identity & Session

### What it does
On first load, the app prompts the user to enter a user ID before they can access any page. The ID is validated and persisted in `localStorage` so the user is not asked again on subsequent visits. A "Switch" button in the navbar lets the user clear the ID and re-enter a different one.

### How it works
- **Component**: `UserIdGate.tsx`
- **Storage**: `localStorage` key `aida_user_id`
- **Validation**: regex `/^[a-zA-Z0-9_-]{3,32}$/` — 3 to 32 characters, letters, numbers, hyphen, underscore
- **App.tsx** reads the stored ID on startup via `getUserId()`. If `null`, renders `<UserIdGate>` fullscreen instead of the app shell.
- Once confirmed, `userId` is passed as a prop to all pages and included in every API call.

### User experience
- Centered card with AIDA logo, welcome message, and input field
- Inline validation error shown beneath the input
- Small footer note explaining the ID is stored locally and re-used

---

## 2. Document Upload

### What it does
Users can upload PDF or TXT files. The file is parsed, split into overlapping text chunks, embedded into 1024-dimensional vectors, and stored in Pinecone. The full pipeline runs server-side.

### How it works

**Frontend** (`UploadPage.tsx`, `api.ts`):
- Click-to-open or drag-and-drop file zone (`<input type="file">` overlaid with a styled div)
- Accepts `.pdf`, `.docx`, `.txt` (MIME-validated server-side: `application/pdf`, `text/plain`)
- `uploadDocument(file, userId, visibility)` sends `multipart/form-data` via `POST /api/v1/documents/upload?user_id=&visibility=`

**Backend** (`documents.py`, `document_service.py`):

| Step | Detail |
|---|---|
| Parse | PDF → `pypdf.PdfReader`, TXT → `bytes.decode("utf-8")` |
| Chunk | 500-character sentence-aware sliding window, 150-character overlap |
| Embed | `openrouter.embeddings.generate`, model `openai/text-embedding-3-small`, 1024 dimensions |
| Store | `pinecone.Index.upsert` — one vector per chunk with metadata: `{ text, source, user_id, visibility }` |
| Register | In-memory `_documents` dict updated with upload stats |

**Response fields**: `filename`, `chunks_stored`, `characters`, `visibility`

### User experience
- Upload zone highlights on hover and when a file is selected
- Shows filename and file size (KB) once selected
- Button shows "⏳ Processing…" during upload
- Success alert shows chunk count, character count, and visibility after completion
- Error alert shows the server's error message on failure

---

## 3. Document Visibility (Public / Private)

### What it does
When uploading, the user chooses whether the document is **Private** (only they can query it) or **Public** (any user can query it). The choice is enforced at both the Pinecone query filter level and in a Python post-filter.

### How it works

**Upload**:
- A two-button toggle ("🔒 Private" / "🌐 Public") appears after a file is selected
- Default is **Private**
- `visibility` is sent as a query parameter: `?visibility=private|public`
- Stored in Pinecone vector metadata: `{ visibility: "private" | "public" }`

**Query filter** (in `ai_service.py`):
```python
filter={
    "$or": [
        {"user_id": {"$eq": user_id}},
        {"visibility": {"$eq": "public"}}
    ]
}
```

**Python post-filter** (safety net for vectors missing metadata):
```python
authorized = [
    m for m in results.matches
    if m.metadata
    and (
        m.metadata.get("visibility") == "public"
        or m.metadata.get("user_id") == user_id
    )
]
```

**Document list**: Shows own documents + all public documents from any user.

**Visibility badge**: Each document in the list shows 🌐 Public or 🔒 Private.

---

## 4. Duplicate File Detection

### What it does
Before uploading, the frontend checks whether a file with the same name already exists in the user's document list. If it does, it intercepts the upload and shows a warning instead of proceeding immediately.

### How it works
- `isDuplicate(file)` checks `documents.some(d => d.filename === file.name)`
- `handleUploadClick()` calls `isDuplicate` before uploading; sets `confirmDuplicate = true` if matched
- When `confirmDuplicate` is true, an inline warning banner replaces the normal flow

### Warning banner contains
- ⚠️ title and the duplicate filename
- Explanation that re-uploading adds duplicate chunks to the Pinecone index
- **"Upload anyway"** button — proceeds with the upload
- **"Cancel"** button — clears file selection and dismisses the warning

### Reset behaviour
- Selecting a new file resets `confirmDuplicate` to `false` and clears the warning

---

## 5. Document List

### What it does
Below the upload card, a second card lists all documents the current user has access to — their own uploads (any visibility) and any public documents uploaded by others. The list refreshes automatically after each successful upload.

### How it works

**Backend** (`GET /api/v1/documents/?user_id=`):
- Reads from `_documents` in-memory registry
- Filters: `doc["user_id"] == user_id OR doc["visibility"] == "public"`
- Sorted by `uploaded_at` descending (newest first)
- Returns `DocumentInfo` objects: `{ filename, chunks_stored, characters, uploaded_at, visibility }`

**Frontend**:
- Fetched on component mount via `listDocuments(userId)`
- Re-fetched after every successful upload via `fetchDocuments()`
- Shows a count badge next to "Uploaded Documents" heading
- "Loading…" placeholder while fetching
- "No documents uploaded yet." empty state

### Each document row shows
- 📄 file icon
- Filename (truncated with ellipsis if too long)
- Chunks stored · characters extracted · upload timestamp · 🌐 Public / 🔒 Private

### Persistence note
The document list is backed by an in-memory Python dict. It resets when the backend restarts. The underlying vectors in Pinecone are permanent — the AI can still answer questions about previously uploaded documents even if the list appears empty.

---

## 6. RAG Question Answering

### What it does
The core feature. The user asks a question in natural language. The backend embeds the question, searches Pinecone for the most semantically relevant document chunks the user is authorised to access, injects those chunks into an LLM prompt as context, and returns a grounded answer.

### Pipeline (end-to-end)

```
Question
  └─► embed (text-embedding-3-small, 1024 dims)
        └─► Pinecone query
              filter: user's docs + public docs
              top_k: 8  (over-fetch; low-score results pruned below)
              └─► Python post-filter:
                    authorisation check + score >= 0.25
                    └─► build messages:
                          [system: numbered context passages]
                          [chat history: last 10 turns]
                          [user: question]
                          └─► gpt-4o-mini (streamed via SSE)
                                └─► answer + source filenames
```

### Key parameters
| Parameter | Value |
|---|---|
| Embedding model | `openai/text-embedding-3-small` |
| Embedding dimensions | 1024 |
| Retrieval top-k | 8 (over-fetch) |
| Score threshold | 0.25 (cosine similarity) |
| LLM model | `openai/gpt-4o-mini` |
| Chat history window | Last 10 turns (20 messages) |

### Prompt design
The system prompt instructs the model to answer **only from the provided context** (passages are numbered `[1]`, `[2]`… so the model can cite them) and to say "I couldn't find that in the uploaded documents." if the answer is absent. This prevents hallucination beyond the uploaded documents.

### No-results handling
If Pinecone returns zero authorised chunks, the API returns `"No relevant documents found for your account."` without calling the LLM.

---

## 7. Per-User Document Isolation

### What it does
Each user can only retrieve answers derived from documents they uploaded (private) or documents explicitly shared as public. One user cannot access another user's private documents.

### How it works
- Every vector in Pinecone stores `user_id` in its metadata
- Every `index.query()` call includes a metadata filter: `$or [{user_id: me}, {visibility: "public"}]`
- A Python post-filter provides a second layer of enforcement
- The `user_id` comes from the request body/query param, which the frontend always populates from `localStorage`

---

## 8. Chat History (In-Memory)

### What it does
The backend keeps a per-user chat history in memory. History is included in every LLM call so the model has conversational context. Follow-up questions like "expand on that" or "what about his education?" work correctly.

### How it works

**Storage**:
```python
_chat_history: dict[str, deque] = {}
# deque with maxlen = MAX_HISTORY_TURNS * 2  (default: 20)
```

- `deque(maxlen=20)` automatically evicts the oldest messages once the limit is reached
- Keyed by `user_id`
- Each entry: `{ role: "user" | "assistant", content: str }`

**On each `answer_question()` call**:
1. Retrieve existing history with `get_history(user_id)`
2. Build messages: `[system prompt] + [history] + [current user message]`
3. Call LLM
4. Append user message and assistant reply to the deque

**Reset behaviour**: History is lost when the backend process restarts (container restart / `docker compose down`). This is intentional — the chat window starts clean on next session.

**API endpoints**:
- `GET /api/v1/chat/history?user_id=` — returns stored messages
- `DELETE /api/v1/chat/history?user_id=` — clears history

### History loading in UI
On `ChatPage` mount, the frontend calls `getChatHistory(userId)` and renders existing messages in the thread. If the backend was restarted, it returns `[]` and the chat starts empty. Backend role `"assistant"` is mapped to frontend role `"ai"`.

---

## 9. Source Attribution

### What it does
After answering a question, the UI shows which document files the answer was derived from, as pill badges beneath the AI's message bubble.

### How it works
- `retrieve_chunks()` collects `source` (filename) from each authorised Pinecone match
- De-duplicated via `list({m.metadata["source"] for m in authorized})`
- Returned in the API response as `sources: string[]`
- Frontend renders each source as a `<span>` badge with accent colour styling

---

## 10. Chat Thread UI

### What it does
The chat page renders a full-height scrollable conversation thread with distinct message bubbles for the user and the AI, matching the style of modern chat applications.

### Layout
- Full viewport height minus the navbar (56 px)
- Scrollable message area (`flex: 1`, `overflow-y: auto`)
- Fixed input bar at the bottom

### Message bubbles
| | User | AI |
|---|---|---|
| Position | Right-aligned | Left-aligned |
| Background | Accent purple | Surface (white / dark) |
| Text colour | White | Primary text |
| Border radius | Rounded, flat bottom-right | Rounded, flat bottom-left |
| Avatar | "You" pill | "AI" pill |

### Input bar
- Auto-expanding `<textarea>` (min 44 px, max 140 px)
- **Enter** → send message
- **Shift + Enter** → insert newline
- Send button disabled when input is empty or a response is loading
- Input field is re-focused after each response

### Auto-scroll
`useEffect` watches `messages` and `loading`; calls `bottomRef.current?.scrollIntoView({ behavior: "smooth" })` after every change.

---

## 11. Typing Indicator / Streaming

### What it does
Chat responses stream token-by-token from the backend. Tokens appear live in the AI bubble as they arrive — no waiting for the full response. While the first token is still in transit, a pulsing three-dot animation is shown.

### How it works

**Backend** (`POST /api/v1/chat/stream`):
- `stream_answer_question()` is an `async` generator that first yields a `{type: "sources"}` SSE event, then yields `{type: "token"}` events for each streamed token from the OpenRouter API
- FastAPI's `StreamingResponse` sends this as `text/event-stream` with headers `X-Accel-Buffering: no` and `Cache-Control: no-cache`

**Frontend** (`ChatPage.tsx`, `api.ts`):
- `streamQuestion()` uses the Fetch API's `ReadableStream` to consume SSE events incrementally
- `onSources` callback fires on the first event; `onToken` callback fires for each token
- `streamingContent` and `streamingSources` React state are updated on every token — the bubble re-renders live
- On completion, the assembled message is moved into the `messages` array and streaming state is cleared
- Typing dots (`@keyframes bounce`, 0ms / 200ms / 400ms stagger) are shown only before the first token arrives

**SSE event format**:
```
data: {"type": "sources", "sources": ["report.pdf"]}
data: {"type": "token",   "token":   "The "}
data: {"type": "token",   "token":   "answer is..."}
```

---

## 12. Light / Dark Mode

### What it does
The UI automatically switches between a light and dark colour scheme based on the user's OS preference.

### How it works
- All colours are defined as CSS custom properties on `:root`
- `@media (prefers-color-scheme: dark)` overrides the same custom properties
- No JavaScript required — purely CSS

### Custom properties include
`--bg`, `--surface`, `--text`, `--text-h`, `--border`, `--accent`, `--accent-hover`, `--accent-bg`, `--accent-border`, `--user-bubble`, `--ai-bubble`, `--nav-bg`, `--shadow`, `--success-*`, `--error-*`, `--radius`, `--radius-sm`, `--radius-full`

---

## 13. Responsive Layout

### What it does
The app renders cleanly on both desktop and mobile screens.

### How it works
- `max-width` constraints on cards (560 px upload, 760 px chat)
- Padding collapses on small screens
- Navbar uses `flex` layout; long user IDs truncate with the `overflow: hidden` pattern
- Upload zone, buttons, and alerts all use `width: 100%` within their containers
- Visibility toggle uses `display: flex` with `flex: 1` buttons that share available space equally

---

## 14. Sticky Navbar with Active Links

### What it does
The navigation bar stays fixed at the top of the screen while scrolling and highlights the currently active route.

### How it works
- `position: sticky; top: 0; z-index: 100` on `.navbar`
- React Router's `<NavLink>` provides an `isActive` callback used to conditionally apply the `active` CSS class
- Active link receives `color: var(--accent)` and a subtle accent background pill

### Navbar contents
- **AIDA logo** (purple square badge with "A") — links to `/`
- **Upload** nav link → `/`
- **Chat** nav link → `/chat`
- **User identity** section (right side): `👤 <userId>` + **Switch** button
  - "Switch" calls `clearUserId()` and resets `userId` state to `null`, re-showing the gate

---

## 15. Docker Compose Deployment

### What it does
A single `docker compose up --build` command builds and starts both services — no manual steps required.

### Services

| Service | Image | Port |
|---|---|---|
| `backend` | `python:3.11-slim` + uv | 8000 |
| `frontend` | `node:22-alpine` (build) → `nginx:alpine` | 80 |

### Backend image
- Uses [`uv`](https://github.com/astral-sh/uv) copied from the official `ghcr.io/astral-sh/uv:latest` image
- `uv sync --frozen --no-dev` installs exact locked dependencies, skipping dev tools
- Fast builds: `pyproject.toml` + `uv.lock` copied first (Docker layer cache)

### Frontend image
- Multi-stage: Node 22 Alpine builds the React app with `npm run build`
- `VITE_API_BASE_URL` is injected as a build-time `ARG` (default `http://localhost:8000`)
- Nginx Alpine serves the compiled `dist/` directory
- `package-lock.json` excluded from Docker context (was generated on macOS; causes version issues in Linux containers)

### Compose configuration
- `env_file: ./backend/.env` — secrets never baked into the image
- `depends_on: backend` — frontend container waits for backend to be created
- `restart: unless-stopped` — both services recover from crashes automatically but don't respawn after a manual `docker compose down`

---

## 16. Health Check Endpoint

### What it does
A lightweight endpoint to verify the backend is running.

### Details
```
GET /api/v1/health
→ { "status": "ok", "app": "AIDA - AI Document Assistant", "version": "0.1.0" }
```

Used by monitoring tools, load balancers, or a simple browser check.

---

## 17. SPA Routing

### What it does
Navigating directly to `/chat` (or refreshing on that route) returns the React app instead of a 404.

### How it works
- React Router DOM handles `/` and `/chat` client-side
- In development: Vite's dev server handles all routes
- In production (Docker): the frontend Nginx container's default config has `try_files $uri $uri/ /index.html` enabled by default, so any unmatched path falls back to `index.html` and React Router takes over

---

## 18. Onboarding Tour

### What it does
First-time users see a 3-step guided tour immediately after entering their user ID. The tour introduces AIDA, then points to the Upload and Chat nav buttons with a visual arrow and pulsing highlight.

### How it works
- **Component**: `OnboardingTour.tsx`
- **Trigger**: `App.tsx` checks `hasTourBeenSeen()` (reads `aida_tour_seen` from `localStorage`) when the user confirms their ID. If not seen, `showTour` state is set to `true` and the tour overlay is rendered.
- **Persistence**: On dismiss ("Got it" or "Skip"), `localStorage.setItem("aida_tour_seen", "1")` is written. Returning users never see the tour again.

### Steps
| Step | Content | Arrow |
|---|---|---|
| 1 | Welcome — what AIDA does | None (centered modal) |
| 2 | Upload a document | Upward triangle arrow pointing at **Upload** nav link + pulse highlight |
| 3 | Ask questions | Upward triangle arrow pointing at **Chat** nav link + pulse highlight |

### Arrow & highlight mechanism
- For steps 2 and 3 the tour card is positioned in the top-left corner directly below the navbar
- A CSS `border-trick` triangle (`width: 0; height: 0; border-left/right/bottom`) sits at the top of the card, offset by `arrowLeft` to align with the target button
- A `body` class (`tour-highlight-upload` / `tour-highlight-chat`) is added via `useEffect` while that step is active; CSS selectors on the actual `<NavLink>` elements apply a pulsing `outline` animation

---

## Memory & Persistence Summary

| Data | Storage | Survives restart? |
|---|---|---|
| Document vectors + text chunks | Pinecone | ✅ Permanent |
| User ID | `localStorage` | ✅ (until cleared) |
| Document registry (list) | Python `dict` (in-memory) | ❌ |
| Chat history | Python `deque` (in-memory) | ❌ |
| UI state (messages, loading…) | React `useState` | ❌ (page refresh) |
