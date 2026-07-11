"""
RAGAS-style evaluation metrics for AIDA.

Three metrics, each returns a float in [0.0, 1.0]:

1. context_recall   — string-based, no LLM needed.
   Measures what fraction of key_facts appear (case-insensitive) in the
   retrieved chunks. A proxy for retrieval quality.

2. faithfulness     — LLM judge.
   Asks the LLM: "Is every claim in the answer supported by the context?"
   Returns the fraction of answer claims that are grounded in context.

3. answer_relevance — LLM judge.
   Asks the LLM: "Does the answer directly address the question?"
   Returns a 0/0.5/1.0 score based on the LLM's verdict.

All LLM calls use the same CHAT_MODEL and OPENROUTER_API_KEY already
configured for the app. No extra dependencies are required.
"""

import json
import logging
from typing import List

import httpx

logger = logging.getLogger("aida.eval.metrics")


def _get_settings():
    from core.config import settings  # noqa: PLC0415
    return settings


def _get_chat_model() -> str:
    from services.ai_service import CHAT_MODEL  # noqa: PLC0415
    return CHAT_MODEL


# ---------------------------------------------------------------------------
# Metric 1: Context recall (no LLM)
# ---------------------------------------------------------------------------

def context_recall(key_facts: List[str], chunks: List[str]) -> float:
    """
    Fraction of key_facts whose text appears (case-insensitive) in any chunk.

    A score of 1.0 means every expected fact was present in the retrieved
    context. A score of 0.0 means nothing matched.

    This is a simple substring check — good enough for known factual nuggets,
    but not suitable for paraphrased or implied facts.
    """
    if not key_facts:
        return 1.0  # nothing expected → trivially satisfied

    combined = " ".join(chunks).lower()
    hits = sum(1 for fact in key_facts if fact.lower() in combined)
    score = hits / len(key_facts)
    logger.debug("context_recall hits=%d total=%d score=%.2f", hits, len(key_facts), score)
    return round(score, 4)


# ---------------------------------------------------------------------------
# Shared LLM helper
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, settings, model: str) -> str:
    """Synchronous LLM call via OpenRouter. Returns the raw response text."""
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0.0,  # deterministic scoring
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Metric 2: Faithfulness (LLM judge)
# ---------------------------------------------------------------------------

_FAITHFULNESS_PROMPT = """\
You are an evaluation assistant. Your job is to check whether an AI-generated \
answer is faithful to a given context — meaning every factual claim in the \
answer is directly supported by the context.

Context (retrieved passages):
{context}

Answer to evaluate:
{answer}

Instructions:
1. List each distinct factual claim in the answer (ignore filler phrases).
2. For each claim, decide: SUPPORTED or NOT_SUPPORTED based on the context alone.
3. Output a JSON object with this exact structure:
{{
  "claims": [
    {{"claim": "<claim text>", "supported": true}},
    {{"claim": "<claim text>", "supported": false}}
  ]
}}
Output ONLY the JSON. No explanation, no markdown fences.
"""


def faithfulness(answer: str, chunks: List[str]) -> float:
    """
    Fraction of answer claims that are directly supported by the retrieved chunks.

    Returns 1.0 if all claims are supported, 0.0 if none are.
    Returns 1.0 if the answer has no checkable claims (e.g. "I don't know").
    """
    if not chunks:
        return 0.0

    settings = _get_settings()
    model = _get_chat_model()
    context = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(chunks))
    prompt = _FAITHFULNESS_PROMPT.format(context=context, answer=answer)

    try:
        raw = _call_llm(prompt, settings, model)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)
        claims = data.get("claims", [])
        if not claims:
            return 1.0
        supported = sum(1 for c in claims if c.get("supported", False))
        score = supported / len(claims)
        logger.debug("faithfulness supported=%d total=%d score=%.2f", supported, len(claims), score)
        return round(score, 4)
    except Exception as e:
        logger.error("faithfulness_metric_failed error=%s raw=%s", e, locals().get("raw", ""))
        return 0.0


# ---------------------------------------------------------------------------
# Metric 3: Answer relevance (LLM judge)
# ---------------------------------------------------------------------------

_RELEVANCE_PROMPT = """\
You are an evaluation assistant. Judge whether the following AI-generated \
answer directly and adequately addresses the user's question.

Question: {question}

Answer: {answer}

Scoring rubric:
- 1.0  The answer directly and completely addresses the question.
- 0.5  The answer partially addresses the question or is vague.
- 0.0  The answer is off-topic, refuses to answer, or is irrelevant.

Output a JSON object with this exact structure:
{{"score": <0.0 | 0.5 | 1.0>, "reason": "<one sentence>"}}
Output ONLY the JSON. No explanation, no markdown fences.
"""


def answer_relevance(question: str, answer: str) -> float:
    """
    LLM-judged score [0.0, 0.5, 1.0] for how well the answer addresses the question.
    """
    settings = _get_settings()
    model = _get_chat_model()
    prompt = _RELEVANCE_PROMPT.format(question=question, answer=answer)

    try:
        raw = _call_llm(prompt, settings, model)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)
        score = float(data.get("score", 0.0))
        score = max(0.0, min(1.0, score))
        logger.debug("answer_relevance score=%.2f reason=%s", score, data.get("reason", ""))
        return round(score, 4)
    except Exception as e:
        logger.error("answer_relevance_metric_failed error=%s raw=%s", e, locals().get("raw", ""))
        return 0.0
