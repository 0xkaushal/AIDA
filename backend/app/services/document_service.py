import uuid
import io
import re
import logging
from typing import List
from datetime import datetime, timezone

logger = logging.getLogger("aida.document_service")

import pypdf
from openrouter import OpenRouter
from pinecone import Pinecone

from core.config import settings # type: ignore

# --- Clients ---
openrouter_client = OpenRouter(api_key=settings.OPENROUTER_API_KEY)
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX_NAME)

EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIMENSIONS = 1024  # must match your Pinecone index dimension
CHUNK_SIZE = 500         # target characters per chunk
CHUNK_OVERLAP = 150      # overlap carried forward; wide enough to hold 1-2 sentences

_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

# --- In-memory document registry ---
_documents: dict[str, dict] = {}


# --- Parsing ---

def parse_pdf(file_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        return parse_pdf(file_bytes)
    return parse_txt(file_bytes)


# --- Chunking ---

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Sentence-aware chunking. Accumulates sentences up to chunk_size, then starts
    a new chunk seeded with the last `overlap` characters of context. Any sentence
    longer than chunk_size is hard-split as a fallback."""
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        slen = len(sentence)

        # Single sentence longer than chunk_size — hard-split it
        if slen > chunk_size:
            if current:
                chunks.append(" ".join(current))
                current, current_len = [], 0
            for start in range(0, slen, chunk_size - overlap):
                chunks.append(sentence[start : start + chunk_size])
            continue

        # Adding this sentence would overflow — flush and carry overlap forward
        if current_len + slen + 1 > chunk_size and current:
            chunks.append(" ".join(current))
            overlap_buf: List[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) + 1 <= overlap:
                    overlap_buf.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break
            current, current_len = overlap_buf, overlap_len

        current.append(sentence)
        current_len += slen + 1

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


# --- Embedding ---

def embed_texts(texts: List[str]) -> List[List[float]]:
    try:
        response = openrouter_client.embeddings.generate(
            model=EMBED_MODEL,
            input=texts,
            dimensions=EMBED_DIMENSIONS,
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower() or "too many requests" in str(e).lower():
            logger.warning("embed_texts_rate_limited chunks=%d", len(texts))
            raise RuntimeError("The AI model is currently rate-limited. Please wait a moment and try again.") from e
        logger.error("embedding_failed chunks=%d error=%s", len(texts), e)
        raise RuntimeError("Embedding service unavailable. Please try again later.") from e


# --- Pinecone upsert ---

def store_chunks(chunks: List[str], embeddings: List[List[float]], filename: str, user_id: str, visibility: str) -> int:
    vectors = [
        {
            "id": str(uuid.uuid4()),
            "values": embedding,
            "metadata": {"text": chunk, "source": filename, "user_id": user_id, "visibility": visibility},
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]
    try:
        index.upsert(vectors=vectors)
    except Exception as e:
        logger.error("pinecone_upsert_failed filename=%s user_id=%s error=%s", filename, user_id, e)
        raise RuntimeError("Vector store unavailable. Please try again later.") from e
    return len(vectors)


# --- Main pipeline ---

def process_document(file_bytes: bytes, filename: str, content_type: str, user_id: str, visibility: str = "private") -> dict:
    logger.info("pipeline_start user_id=%s filename=%s size_bytes=%d visibility=%s", user_id, filename, len(file_bytes), visibility)
    text = extract_text(file_bytes, content_type)
    if not text.strip():
        logger.warning("no_text_extracted user_id=%s filename=%s", user_id, filename)
        raise ValueError("No text could be extracted from the file.")

    chunks = chunk_text(text)
    logger.info("chunked user_id=%s filename=%s chars=%d chunks=%d", user_id, filename, len(text), len(chunks))

    embeddings = embed_texts(chunks)
    logger.info("embedded user_id=%s filename=%s vectors=%d", user_id, filename, len(embeddings))

    count = store_chunks(chunks, embeddings, filename, user_id, visibility)
    logger.info("upserted user_id=%s filename=%s vectors=%d", user_id, filename, count)

    _documents[f"{user_id}:{filename}"] = {
        "filename": filename,
        "chunks_stored": count,
        "characters": len(text),
        "uploaded_at": datetime.now(timezone.utc),
        "user_id": user_id,
        "visibility": visibility,
    }

    return {
        "filename": filename,
        "chunks_stored": count,
        "characters": len(text),
        "visibility": visibility,
    }


def list_documents(user_id: str) -> list[dict]:
    return sorted(
        [d for d in _documents.values() if d["user_id"] == user_id or d["visibility"] == "public"],
        key=lambda d: d["uploaded_at"],
        reverse=True,
    )
