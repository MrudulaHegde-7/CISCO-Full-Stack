import pytest

from app.rag.chunking import chunk_text
from app.rag.loaders import extract_text


def test_chunking_has_overlap_and_source_metadata():
    chunks = chunk_text("word " * 400, page=3, size=750, overlap=100)
    assert len(chunks) > 1
    assert all(chunk.page == 3 for chunk in chunks)
    assert all(len(chunk.text) <= 750 for chunk in chunks)
    assert chunks[0].text[-80:] in chunks[1].text


def test_text_loader_rejects_unsupported_extensions():
    with pytest.raises(ValueError):
        extract_text("secrets.exe", b"not a supported document")


def test_text_loader_reads_utf8_text():
    pages = extract_text("policy.txt", "Policy effective 2026".encode())
    assert pages == [("Policy effective 2026", None, "Document")]