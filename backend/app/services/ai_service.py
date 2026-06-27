from typing import List, Tuple, AsyncGenerator
from collections import deque
import json
import logging

logger = logging.getLogger("aida.ai_service")

import httpx
from openrouter import OpenRouter
from pinecone import Pinecone

from core.config import settings
from services.document_service import EMBED_MODEL, EMBED_DIMENSIONS

# --- Clients ---
openrouter_client = OpenRouter(api_key=settings.OPENROUTER_API_KEY)
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX_NAME)

CHAT_MODEL = "openai/gpt-4o-mini"
TOP_K = 8              # over-fetch; low-score results are pruned below
SCORE_THRESHOLD = 0.25 # drop chunks with cosine similarity below this
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
    try:
        response = openrouter_client.embeddings.generate(
            model=EMBED_MODEL,
            input=[question],
            dimensions=EMBED_DIMENSIONS,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("embed_question_failed error=%s", e)
        raise RuntimeError("Embedding service unavailable. Please try again later.") from e


def retrieve_chunks(question_embedding: List[float], user_id: str) -> Tuple[List[str], List[str]]:
    try:
        results = index.query(
            vector=question_embedding,
            top_k=TOP_K,
            include_metadata=True,
            filter={"$or": [{"user_id": {"$eq": user_id}}, {"visibility": {"$eq": "public"}}]},
        )
    except Exception as e:
        logger.error("pinecone_query_failed user_id=%s error=%s", user_id, e)
        raise RuntimeError("Vector store unavailable. Please try again later.") from e
    # Post-filter: authorisation AND relevance score threshold
    authorized = [
        m for m in results.matches
        if m.metadata
        and (
            m.metadata.get("visibility") == "public"
            or m.metadata.get("user_id") == user_id
        )
        and m.score is not None
        and m.score >= SCORE_THRESHOLD
    ]
    logger.info(
        "retrieve user_id=%s candidates=%d authorized=%d",
        user_id, len(results.matches), len(authorized),
    )
    texts = [m.metadata["text"] for m in authorized if m.metadata.get("text")]
    sources = list({m.metadata["source"] for m in authorized if m.metadata.get("source")})
    return texts, sources


def build_system_prompt(chunks: List[str]) -> str:
    numbered = "\n\n".join(f"[{i+1}] {chunk}" for i, chunk in enumerate(chunks))
    return (
        "You are AIDA, a helpful document assistant.\n"
        "Answer the user's question using ONLY the context passages below.\n"
        "If the answer is not contained in the passages, say: "
        "\"I couldn't find that in the uploaded documents.\"\n"
        "Do not make up information or use prior knowledge.\n"
        "Be concise. When helpful, reference the passage number (e.g. 'According to [2]...').\n\n"
        f"Context passages:\n{numbered}"
    )


def answer_question(question: str, user_id: str) -> dict:
    logger.info("answer_start user_id=%s question_len=%d", user_id, len(question))
    embedding = embed_question(question)
    chunks, sources = retrieve_chunks(embedding, user_id)

    if not chunks:
        logger.warning("no_chunks_found user_id=%s", user_id)
        return {"answer": "No relevant documents found for your account.", "sources": []}

    # Build messages: system (RAG context) + history + current question
    messages = [
        {"role": "system", "content": build_system_prompt(chunks)},
        *get_history(user_id),
        {"role": "user", "content": question},
    ]

    try:
        response = openrouter_client.chat.send(
            model=CHAT_MODEL,
            messages=messages,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error("llm_call_failed user_id=%s error=%s", user_id, e)
        raise RuntimeError("Language model unavailable. Please try again later.") from e
    answer = response.choices[0].message.content
    logger.info("answer_done user_id=%s answer_len=%d sources=%s", user_id, len(answer), sources)

    # Persist this exchange
    _append_history(user_id, "user", question)
    _append_history(user_id, "assistant", answer)

    return {"answer": answer, "sources": sources}


async def stream_answer_question(
    question: str, user_id: str
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE-formatted strings for a streaming response."""
    logger.info("stream_start user_id=%s question_len=%d", user_id, len(question))
    embedding = embed_question(question)
    chunks, sources = retrieve_chunks(embedding, user_id)

    if not chunks:
        logger.warning("stream_no_chunks user_id=%s", user_id)
        yield f'data: {json.dumps({"type": "error", "message": "No relevant documents found for your account."})}\n\n'
        yield "data: [DONE]\n\n"
        return

    # Send sources immediately so the UI can render them before tokens arrive
    yield f'data: {json.dumps({"type": "sources", "sources": sources})}\n\n'

    messages = [
        {"role": "system", "content": build_system_prompt(chunks)},
        *get_history(user_id),
        {"role": "user", "content": question},
    ]

    full_answer = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CHAT_MODEL,
                    "messages": messages,
                    "max_tokens": 1024,
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:]  # strip "data: " prefix
                    if raw == "[DONE]":
                        break
                    try:
                        payload = json.loads(raw)
                        token = payload["choices"][0]["delta"].get("content", "")
                        if token:
                            full_answer += token
                            yield f'data: {json.dumps({"type": "token", "token": token})}\n\n'
                    except (KeyError, json.JSONDecodeError):
                        continue
    except httpx.TimeoutException:
        logger.error("stream_timeout user_id=%s", user_id)
        yield f'data: {json.dumps({"type": "error", "message": "The request timed out. Please try again."})}\n\n'
        yield "data: [DONE]\n\n"
        return
    except Exception as e:
        logger.error("stream_llm_failed user_id=%s error=%s", user_id, e)
        yield f'data: {json.dumps({"type": "error", "message": "Language model unavailable. Please try again later."})}\n\n'
        yield "data: [DONE]\n\n"
        return

    # Persist the full exchange after streaming completes
    _append_history(user_id, "user", question)
    _append_history(user_id, "assistant", full_answer)

    yield "data: [DONE]\n\n"
