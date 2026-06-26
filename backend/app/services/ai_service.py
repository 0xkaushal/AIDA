from typing import List, Tuple
from collections import deque

from openrouter import OpenRouter
from pinecone import Pinecone

from core.config import settings
from services.document_service import EMBED_MODEL, EMBED_DIMENSIONS

# --- Clients ---
openrouter_client = OpenRouter(api_key=settings.OPENROUTER_API_KEY)
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX_NAME)

CHAT_MODEL = "openai/gpt-4o-mini"
TOP_K = 5
MAX_HISTORY_TURNS = 10  # keep last 10 user+assistant exchanges

# --- In-memory chat history ---
# {user_id: deque([{"role": "user"|"assistant", "content": str}, ...])}
_chat_history: dict[str, deque] = {}


def get_history(user_id: str) -> list[dict]:
    return list(_chat_history.get(user_id, []))


def _append_history(user_id: str, role: str, content: str) -> None:
    if user_id not in _chat_history:
        _chat_history[user_id] = deque(maxlen=MAX_HISTORY_TURNS * 2)
    _chat_history[user_id].append({"role": role, "content": content})


def clear_history(user_id: str) -> None:
    _chat_history.pop(user_id, None)


def embed_question(question: str) -> List[float]:
    response = openrouter_client.embeddings.generate(
        model=EMBED_MODEL,
        input=[question],
        dimensions=EMBED_DIMENSIONS,
    )
    return response.data[0].embedding


def retrieve_chunks(question_embedding: List[float], user_id: str) -> Tuple[List[str], List[str]]:
    results = index.query(
        vector=question_embedding,
        top_k=TOP_K,
        include_metadata=True,
        filter={"$or": [{"user_id": {"$eq": user_id}}, {"visibility": {"$eq": "public"}}]},
    )
    # Post-filter in Python as a safety net for vectors missing metadata fields
    authorized = [
        m for m in results.matches
        if m.metadata
        and (
            m.metadata.get("visibility") == "public"
            or m.metadata.get("user_id") == user_id
        )
    ]
    texts = [m.metadata["text"] for m in authorized if m.metadata.get("text")]
    sources = list({m.metadata["source"] for m in authorized if m.metadata.get("source")})
    return texts, sources


def build_system_prompt(chunks: List[str]) -> str:
    context = "\n\n".join(chunks)
    return (
        "You are a helpful document assistant. "
        "Answer questions using only the context below. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context}"
    )


def answer_question(question: str, user_id: str) -> dict:
    embedding = embed_question(question)
    chunks, sources = retrieve_chunks(embedding, user_id)

    if not chunks:
        return {"answer": "No relevant documents found for your account.", "sources": []}

    # Build messages: system (RAG context) + history + current question
    messages = [
        {"role": "system", "content": build_system_prompt(chunks)},
        *get_history(user_id),
        {"role": "user", "content": question},
    ]

    response = openrouter_client.chat.send(
        model=CHAT_MODEL,
        messages=messages,
        max_tokens=1024,
    )
    answer = response.choices[0].message.content

    # Persist this exchange
    _append_history(user_id, "user", question)
    _append_history(user_id, "assistant", answer)

    return {"answer": answer, "sources": sources}
