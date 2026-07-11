"""
RAGAS metric setup for AIDA.

Provides a pre-configured set of RAGAS metrics wired to OpenRouter via
LangchainLLMWrapper (ChatOpenAI) and LangchainEmbeddingsWrapper (OpenAIEmbeddings).

Three metrics:
  - _Faithfulness      : are answer claims grounded in retrieved context?
  - _ResponseRelevancy : does the answer address the question?
  - _LLMContextRecall  : did retrieval surface the information needed to answer?

All three use openai/gpt-4o-mini as the judge LLM and
openai/text-embedding-3-small (1024 dims) for embedding-based scoring —
the same models the app already uses, so no extra cost model is introduced.

RAGAS wiring notes (0.4.3):
  - Use underscore-prefixed classes (_Faithfulness, etc.) — these are the
    stable Metric subclasses compatible with evaluate(). The non-underscore
    versions in ragas.metrics.collections use a different base class and
    are incompatible with evaluate().
  - ragas/llms/base.py has a broken import on fresh install. Patch it:
      sed -i '' 's/from langchain_community.chat_models.vertexai import ChatVertexAI/from langchain_google_vertexai import ChatVertexAI/' \
        .venv/lib/python3.11/site-packages/ragas/llms/base.py
      sed -i '' 's/from langchain_community.llms import VertexAI/from langchain_google_vertexai import VertexAI/' \
        .venv/lib/python3.11/site-packages/ragas/llms/base.py

Usage:
    from eval_ragas.metrics import get_metrics
    faithfulness_m, relevancy_m, recall_m = get_metrics()
"""

import sys
from pathlib import Path

# Make backend/app/ importable
_APP = Path(__file__).resolve().parent.parent / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from core.config import settings  # noqa: E402

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import (  # noqa: E402
    _Faithfulness,
    _LLMContextRecall,
    _ResponseRelevancy,
)


def get_metrics() -> tuple[_Faithfulness, _ResponseRelevancy, _LLMContextRecall]:
    """
    Build and return RAGAS metric objects wired to OpenRouter.

    Call once per eval run — the returned objects are stateless scorers,
    so you can reuse them across multiple evaluate() calls.
    """
    llm = LangchainLLMWrapper(
        ChatOpenAI(
            model="openai/gpt-4o-mini",
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            max_tokens=512,
        )
    )
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model="openai/text-embedding-3-small",
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            dimensions=1024,
        )
    )
    return (
        _Faithfulness(llm=llm),
        _ResponseRelevancy(llm=llm, embeddings=embeddings),
        _LLMContextRecall(llm=llm),
    )
