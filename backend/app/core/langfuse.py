"""
Langfuse client singleton for AIDA.

Provides a single `get_langfuse()` call that returns either:
  - A real `Langfuse` client when LANGFUSE_SECRET_KEY + LANGFUSE_PUBLIC_KEY
    are set in the environment.
  - A `_NoOpLangfuse` stub when keys are absent — the app runs identically
    with zero tracing overhead and no errors.

Langfuse v4 API used here:
  - lf.start_observation(name, as_type, input, metadata)  → span/generation
  - span.start_observation(name, as_type, input)           → child span
  - span.update(output, metadata, model, ...)
  - span.end()
  - lf.flush()   — call at the end of a request to ensure delivery

Span types used:
  - 'span'       — generic timed step
  - 'embedding'  — embedding API call
  - 'retriever'  — vector store query
  - 'generation' — LLM completion call

Test isolation: conftest.py sets LANGFUSE_SECRET_KEY="" which forces the
no-op stub. Unit tests never need real credentials.
"""

import logging
from typing import Any

logger = logging.getLogger("aida.langfuse")


# ---------------------------------------------------------------------------
# No-op stub — used when Langfuse is not configured
# ---------------------------------------------------------------------------

class _NoOpSpan:
    """Silent stub for a Langfuse span/generation."""
    trace_id: str = "noop"

    def start_observation(self, **_: Any) -> "_NoOpSpan":
        return _NoOpSpan()

    def end(self, **_: Any) -> "_NoOpSpan":
        return self

    def update(self, **_: Any) -> "_NoOpSpan":
        return self

    def set_trace_io(self, **_: Any) -> "_NoOpSpan":
        return self

    def score(self, **_: Any) -> None: ...
    def score_trace(self, **_: Any) -> None: ...


class _NoOpLangfuse:
    """Silent stub for the Langfuse client."""
    def start_observation(self, **_: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def flush(self) -> None: ...


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_client: Any = None
_enabled: bool = False


def get_langfuse() -> Any:
    """
    Return the Langfuse client (or a silent no-op stub if not configured).

    Initialised once on first call and reused for the process lifetime.
    """
    global _client, _enabled

    if _client is not None:
        return _client

    try:
        from core.config import settings  # noqa: PLC0415

        if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
            logger.info(
                "langfuse_disabled: LANGFUSE_SECRET_KEY or LANGFUSE_PUBLIC_KEY not set — "
                "tracing is off. Set both keys in .env to enable."
            )
            _client = _NoOpLangfuse()
            _enabled = False
            return _client

        from langfuse import Langfuse  # noqa: PLC0415

        _client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST,
        )
        _enabled = True
        logger.info("langfuse_enabled host=%s", settings.LANGFUSE_HOST)

    except Exception as e:
        logger.warning("langfuse_init_failed error=%s — falling back to no-op", e)
        _client = _NoOpLangfuse()
        _enabled = False

    return _client


def is_enabled() -> bool:
    """Return True if a real Langfuse client is active."""
    get_langfuse()
    return _enabled
