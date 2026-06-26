import uuid
import io
from typing import List
from datetime import datetime, timezone

import pypdf
from openrouter import OpenRouter
from pinecone import Pinecone

from core.config import settings

# --- Clients ---
openrouter_client = OpenRouter(api_key=settings.OPENROUTER_API_KEY)
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX_NAME)

EMBED_MODEL = "openai/text-embedding-3-small"
EMBED_DIMENSIONS = 1024  # must match your Pinecone index dimension
CHUNK_SIZE = 500         # characters per chunk
CHUNK_OVERLAP = 50       # overlap between chunks

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
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


# --- Embedding ---

def embed_texts(texts: List[str]) -> List[List[float]]:
    response = openrouter_client.embeddings.generate(
        model=EMBED_MODEL,
        input=texts,
        dimensions=EMBED_DIMENSIONS,
    )
    return [item.embedding for item in response.data]


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
    index.upsert(vectors=vectors)
    return len(vectors)


# --- Main pipeline ---

def process_document(file_bytes: bytes, filename: str, content_type: str, user_id: str, visibility: str = "private") -> dict:
    text = extract_text(file_bytes, content_type)
    if not text.strip():
        raise ValueError("No text could be extracted from the file.")

    chunks = chunk_text(text)
    embeddings = embed_texts(chunks)
    count = store_chunks(chunks, embeddings, filename, user_id, visibility)

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
