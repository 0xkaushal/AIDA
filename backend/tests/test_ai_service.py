"""
Tests for services/ai_service.py

Covers: Pinecone authorisation filter, score threshold, source deduplication,
        null-metadata safety, in-memory chat history, and error handling (negative tests).
"""
import pytest
from unittest.mock import MagicMock, patch
from services import ai_service  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match(user_id: str, visibility: str, text: str, score: float = 0.8):
    """Build a Pinecone-match-like mock object."""
    m = MagicMock()
    m.metadata = {
        "text": text,
        "source": "doc.pdf",
        "user_id": user_id,
        "visibility": visibility,
    }
    m.score = score
    return m


def _set_results(mock_index, matches):
    result = MagicMock()
    result.matches = matches
    mock_index.query.return_value = result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_index(monkeypatch):
    """Replace the real Pinecone index with a mock for every test in this file."""
    mock_index = MagicMock()
    monkeypatch.setattr(ai_service, "index", mock_index)
    return mock_index


# ---------------------------------------------------------------------------
# Authorisation + score filter
# ---------------------------------------------------------------------------

class TestRetrieveChunks:
    def test_own_private_doc_returned(self, patch_index):
        _set_results(patch_index, [_match("alice", "private", "Alice content")])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert "Alice content" in texts

    def test_other_users_private_doc_blocked(self, patch_index):
        _set_results(patch_index, [_match("bob", "private", "Bob secret")])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert texts == []

    def test_public_doc_from_other_user_accessible(self, patch_index):
        _set_results(patch_index, [_match("bob", "public", "Bob public")])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert "Bob public" in texts

    def test_chunk_below_score_threshold_dropped(self, patch_index):
        _set_results(patch_index, [_match("alice", "private", "Low score", score=0.10)])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert texts == []

    def test_chunk_at_exact_threshold_included(self, patch_index):
        _set_results(patch_index, [_match("alice", "private", "Threshold", score=0.25)])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert "Threshold" in texts

    def test_chunk_above_threshold_included(self, patch_index):
        _set_results(patch_index, [_match("alice", "private", "High score", score=0.99)])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert "High score" in texts

    def test_mixed_matches_filtered_correctly(self, patch_index):
        _set_results(patch_index, [
            _match("alice", "private", "Alice ok",     score=0.9),
            _match("bob",   "private", "Bob blocked",  score=0.9),
            _match("carol", "public",  "Carol public", score=0.6),
            _match("alice", "private", "Alice low",    score=0.05),
        ])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert "Alice ok"     in texts
        assert "Carol public" in texts
        assert "Bob blocked"  not in texts
        assert "Alice low"    not in texts

    def test_match_with_none_metadata_skipped(self, patch_index):
        m = MagicMock()
        m.metadata = None
        m.score = 0.9
        _set_results(patch_index, [m])
        texts, _ = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert texts == []

    def test_sources_are_deduplicated(self, patch_index):
        _set_results(patch_index, [
            _match("alice", "private", "chunk 1", score=0.8),
            _match("alice", "private", "chunk 2", score=0.7),
        ])
        _, sources = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert sources.count("doc.pdf") == 1

    def test_empty_pinecone_result_returns_empty(self, patch_index):
        _set_results(patch_index, [])
        texts, sources = ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert texts == []
        assert sources == []


# ---------------------------------------------------------------------------
# In-memory chat history
# ---------------------------------------------------------------------------

class TestChatHistory:
    def setup_method(self):
        ai_service.clear_history("test-user")

    def test_new_user_has_empty_history(self):
        assert ai_service.get_history("brand-new-user") == []

    def test_append_and_retrieve(self):
        ai_service._append_history("test-user", "user", "Hello")
        ai_service._append_history("test-user", "assistant", "Hi there")
        history = ai_service.get_history("test-user")
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there"}

    def test_clear_removes_history(self):
        ai_service._append_history("test-user", "user", "To be cleared")
        ai_service.clear_history("test-user")
        assert ai_service.get_history("test-user") == []

    def test_clear_nonexistent_user_does_not_raise(self):
        ai_service.clear_history("nobody")  # must not raise

    def test_history_cap_evicts_oldest(self):
        # MAX_HISTORY_TURNS * 2 = 20; adding 22 messages should drop the first 2
        for i in range(22):
            role = "user" if i % 2 == 0 else "assistant"
            ai_service._append_history("test-user", role, f"message {i}")
        history = ai_service.get_history("test-user")
        assert len(history) == 20
        assert history[0]["content"] == "message 2"

    def test_histories_are_isolated_per_user(self):
        ai_service.clear_history("user-a")
        ai_service.clear_history("user-b")
        ai_service._append_history("user-a", "user", "A message")
        assert ai_service.get_history("user-b") == []


# ---------------------------------------------------------------------------
# Negative tests — error handling
# ---------------------------------------------------------------------------

class TestEmbedQuestionErrors:
    def test_openrouter_failure_raises_runtime_error(self, monkeypatch):
        mock_client = MagicMock()
        mock_client.embeddings.generate.side_effect = Exception("API down")
        monkeypatch.setattr(ai_service, "openrouter_client", mock_client)
        with pytest.raises(RuntimeError, match="Embedding service unavailable"):
            ai_service.embed_question("what is this?")

    def test_original_exception_is_chained(self, monkeypatch):
        mock_client = MagicMock()
        original = Exception("network error")
        mock_client.embeddings.generate.side_effect = original
        monkeypatch.setattr(ai_service, "openrouter_client", mock_client)
        with pytest.raises(RuntimeError) as exc_info:
            ai_service.embed_question("question")
        assert exc_info.value.__cause__ is original


class TestRetrieveChunksErrors:
    def test_pinecone_failure_raises_runtime_error(self, monkeypatch):
        mock_index = MagicMock()
        mock_index.query.side_effect = Exception("pinecone timeout")
        monkeypatch.setattr(ai_service, "index", mock_index)
        with pytest.raises(RuntimeError, match="Vector store unavailable"):
            ai_service.retrieve_chunks([0.0] * 1024, "alice")

    def test_pinecone_original_exception_is_chained(self, monkeypatch):
        mock_index = MagicMock()
        original = Exception("connection reset")
        mock_index.query.side_effect = original
        monkeypatch.setattr(ai_service, "index", mock_index)
        with pytest.raises(RuntimeError) as exc_info:
            ai_service.retrieve_chunks([0.0] * 1024, "alice")
        assert exc_info.value.__cause__ is original


class TestAnswerQuestionErrors:
    def test_embed_failure_propagates(self, monkeypatch):
        mock_client = MagicMock()
        mock_client.embeddings.generate.side_effect = Exception("embed down")
        monkeypatch.setattr(ai_service, "openrouter_client", mock_client)
        with pytest.raises(RuntimeError, match="Embedding service unavailable"):
            ai_service.answer_question("a question", "alice")

    def test_pinecone_failure_propagates(self, monkeypatch):
        mock_client = MagicMock()
        embed_resp = MagicMock()
        embed_resp.data = [MagicMock(embedding=[0.1] * 1024)]
        mock_client.embeddings.generate.return_value = embed_resp
        monkeypatch.setattr(ai_service, "openrouter_client", mock_client)
        mock_index = MagicMock()
        mock_index.query.side_effect = Exception("pinecone down")
        monkeypatch.setattr(ai_service, "index", mock_index)
        with pytest.raises(RuntimeError, match="Vector store unavailable"):
            ai_service.answer_question("a question", "alice")

    def test_llm_failure_raises_runtime_error(self, monkeypatch, patch_index):
        # Pinecone returns a valid result
        result = MagicMock()
        m = MagicMock()
        m.metadata = {"text": "content", "source": "doc.pdf", "user_id": "alice", "visibility": "private"}
        m.score = 0.9
        result.matches = [m]
        patch_index.query.return_value = result
        # Embedding succeeds
        mock_client = MagicMock()
        embed_resp = MagicMock()
        embed_resp.data = [MagicMock(embedding=[0.1] * 1024)]
        mock_client.embeddings.generate.return_value = embed_resp
        # LLM fails
        mock_client.chat.send.side_effect = Exception("LLM timeout")
        monkeypatch.setattr(ai_service, "openrouter_client", mock_client)
        with pytest.raises(RuntimeError, match="Language model unavailable"):
            ai_service.answer_question("a question", "alice")
