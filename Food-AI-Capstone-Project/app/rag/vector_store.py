from pathlib import Path
from typing import Any

import chromadb

from app.config import settings
from app.rag.chunking import TextChunk


class ChromaVectorStore:
    def __init__(self, path: Path | None = None) -> None:
        storage_path = path or settings.chroma_path
        storage_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(storage_path))
        self.collection = self.client.get_or_create_collection(
            name="restaurant_knowledge",
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_document(
        self,
        *,
        document_id: int,
        version: int,
        filename: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Each document chunk requires one embedding")
        ids = [f"doc-{document_id}-v{version}-c{chunk.index}" for chunk in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "version": version,
                "filename": filename,
                "page": chunk.page or 0,
                "section": chunk.section or "",
                "chunk_id": ids[index],
                "active": True,
            }
            for index, chunk in enumerate(chunks)
        ]
        if ids:
            self.collection.upsert(
                ids=ids,
                documents=[chunk.text for chunk in chunks],
                embeddings=embeddings,
                metadatas=metadatas,
            )

    def deactivate_document(self, document_id: int) -> None:
        existing = self.collection.get(where={"document_id": document_id})
        if existing["ids"]:
            self.collection.update(
                ids=existing["ids"],
                metadatas=[{**metadata, "active": False} for metadata in existing["metadatas"]],
            )

    def search(self, embedding: list[float], limit: int = 4) -> list[dict[str, Any]]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where={"active": True},
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {"text": text, "metadata": metadata, "distance": distance}
            for text, metadata, distance in zip(documents, metadatas, distances, strict=False)
        ]