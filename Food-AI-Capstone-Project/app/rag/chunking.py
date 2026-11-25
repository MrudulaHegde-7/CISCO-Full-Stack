from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    page: int | None
    section: str | None
    index: int


def chunk_text(
    text: str,
    *,
    page: int | None = None,
    section: str | None = None,
    size: int = 750,
    overlap: int = 100,
) -> list[TextChunk]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if size <= overlap or overlap < 0:
        raise ValueError("Chunk size must be greater than overlap")

    chunks: list[TextChunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        content = normalized[start:end].strip()
        if content:
            chunks.append(TextChunk(content, page, section, len(chunks)))
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks