from io import BytesIO
from pathlib import Path

import pymupdf
from docx import Document as WordDocument


def extract_text(filename: str, data: bytes) -> list[tuple[str, int | None, str | None]]:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                return [(page.get_text("text"), index + 1, None) for index, page in enumerate(pdf)]
        if suffix == ".docx":
            doc = WordDocument(BytesIO(data))
            paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
            return [("\n".join(paragraphs), None, "Document")]
        if suffix == ".txt":
            return [(data.decode("utf-8-sig"), None, "Document")]
    except Exception as exc:
        raise ValueError("The uploaded document could not be parsed") from exc
    raise ValueError("Only PDF, DOCX, and TXT documents are supported")