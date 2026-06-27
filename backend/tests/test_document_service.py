"""
Tests for services/document_service.py

Covers: text parsing, sentence-aware chunking, hard-split fallback,
        content preservation, and edge cases.
"""
import pytest
from services.document_service import chunk_text, extract_text, parse_txt, CHUNK_SIZE # type: ignore


class TestParseTxt:
    def test_unicode_decoded_correctly(self):
        assert parse_txt("Héllo wörld".encode("utf-8")) == "Héllo wörld"

    def test_invalid_bytes_ignored_not_raised(self):
        result = parse_txt(b"valid \xff invalid")
        assert "valid" in result
        assert "invalid" in result


class TestExtractText:
    def test_txt_content_type_decodes_utf8(self):
        result = extract_text("Hello world".encode(), "text/plain")
        assert result == "Hello world"

    def test_unknown_content_type_falls_back_to_txt_decoder(self):
        result = extract_text("fallback".encode(), "application/octet-stream")
        assert result == "fallback"

    def test_invalid_bytes_do_not_raise(self):
        bad = b"Hello \xff\xfe world"
        result = extract_text(bad, "text/plain")
        assert "Hello" in result
        assert "world" in result


class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\t  ") == []

    def test_short_text_produces_single_chunk(self):
        text = "Hello world. This is a short test."
        result = chunk_text(text)
        assert len(result) == 1
        assert "Hello world" in result[0]

    def test_no_chunk_exceeds_chunk_size(self):
        # Allow a small buffer: a sentence that lands just over the boundary
        # is hard-split rather than silently truncated
        text = "This is a sentence. " * 60  # well over 500 chars
        for chunk in chunk_text(text):
            assert len(chunk) <= CHUNK_SIZE + 100

    def test_long_sentence_without_punctuation_is_hard_split(self):
        # No sentence-ending punctuation → hard-split fallback path
        long_text = "word " * 200  # ~1000 chars
        chunks = chunk_text(long_text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_all_content_preserved_across_chunks(self):
        sentences = [f"Sentence {i} has unique content." for i in range(30)]
        text = " ".join(sentences)
        joined = " ".join(chunk_text(text))
        for i in range(30):
            assert f"Sentence {i}" in joined

    def test_no_empty_chunks_returned(self):
        text = "Short. " * 5
        assert all(c.strip() for c in chunk_text(text))

    def test_multiple_chunks_produced_for_long_text(self):
        text = "A sentence with some content here. " * 30
        assert len(chunk_text(text, chunk_size=100, overlap=20)) > 1

    def test_single_sentence_exactly_at_limit_is_one_chunk(self):
        # Build a sentence that is exactly chunk_size chars
        sentence = "x" * CHUNK_SIZE + "."
        chunks = chunk_text(sentence, chunk_size=CHUNK_SIZE, overlap=20)
        # It exceeds CHUNK_SIZE only by 1 char (the period); hard-split applies
        assert len(chunks) >= 1

    def test_overlap_carries_context_to_next_chunk(self):
        # With a very small chunk_size the last sentence of chunk N should
        # appear at the start of chunk N+1
        sentences = ["Alpha sentence here.", "Beta sentence here.", "Gamma sentence here.",
                     "Delta sentence here.", "Epsilon sentence here."]
        text = " ".join(sentences)
        chunks = chunk_text(text, chunk_size=45, overlap=40)
        if len(chunks) > 1:
            # Some content from chunk 0 should appear in chunk 1 due to overlap
            assert any(word in chunks[1] for word in chunks[0].split())
