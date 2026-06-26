from typing import List, Tuple

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
        filter={"user_id": {"$eq": user_id}},
    )
    texts = [match.metadata["text"] for match in results.matches]
    sources = list({match.metadata["source"] for match in results.matches})
    return texts, sources


def build_prompt(question: str, chunks: List[str]) -> str:
    context = "\n\n".join(chunks)
    return (
        f"You are a helpful document assistant. "
        f"Answer the question using only the context below. "
        f"If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )


def answer_question(question: str, user_id: str) -> dict:
    embedding = embed_question(question)
    chunks, sources = retrieve_chunks(embedding, user_id)

    if not chunks:
        return {"answer": "No relevant documents found for your account.", "sources": []}

    prompt = build_prompt(question, chunks)
    response = openrouter_client.chat.send(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    answer = response.choices[0].message.content
    return {"answer": answer, "sources": sources}
