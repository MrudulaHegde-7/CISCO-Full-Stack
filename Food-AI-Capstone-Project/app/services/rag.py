import hashlib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.errors import ConflictError, ServiceUnavailableError
from app.models import Document
from app.rag.chunking import TextChunk, chunk_text
from app.rag.loaders import extract_text
from app.rag.vector_store import ChromaVectorStore
from app.repositories.protocols import DocumentRepository, GeminiGateway, VectorStore
from app.services.gemini import GeminiClient

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class RAGService:
    def __init__(
        self,
        repository: DocumentRepository,
        vector_store: VectorStore,
        gemini: GeminiGateway,
        session: Session,
    ) -> None:
        self.repository = repository
        self.vector_store = vector_store
        self.gemini = gemini
        self.session = session

    async def index_document(self, filename: str, data: bytes, uploader_id: int) -> Document:
        safe_name = Path(filename).name
        extension = Path(safe_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ConflictError("Upload a PDF, DOCX, or TXT file")
        if not data or len(data) > settings.max_upload_bytes:
            raise ConflictError("Document is empty or exceeds the upload size limit")

        try:
            pages = extract_text(safe_name, data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ConflictError("The uploaded document could not be read") from exc
        chunks: list[TextChunk] = []
        for page_text, page, section in pages:
            chunks.extend(chunk_text(page_text, page=page, section=section))
        if not chunks:
            raise ConflictError("The uploaded document contains no extractable text")
        if len(chunks) > 100:
            raise ConflictError("The document has too many text chunks to index in one upload")

        prior = self.repository.latest_named(safe_name)
        version = (prior.version + 1) if prior else 1
        document = self.repository.add(
            Document(
                filename=safe_name,
                sha256=hashlib.sha256(data).hexdigest(),
                version=version,
                status="INDEXING",
                uploaded_by=uploader_id,
            )
        )
        self.session.commit()

        stored_name = f"{document.id}-{uuid.uuid4().hex}{extension}"
        settings.document_path.mkdir(parents=True, exist_ok=True)
        target = settings.document_path / stored_name
        target.write_bytes(data)

        try:
            embeddings = [
                await self.gemini.embed(chunk.text, task_type="RETRIEVAL_DOCUMENT")
                for chunk in chunks
            ]
            self.vector_store.upsert_document(
                document_id=document.id,
                version=version,
                filename=safe_name,
                chunks=chunks,
                embeddings=embeddings,
            )
            if prior is not None:
                prior.status = "REPLACED"
                self.vector_store.deactivate_document(prior.id)
            document.status = "ACTIVE"
            document.storage_key = stored_name
            document.sha256 = hashlib.sha256(data).hexdigest()
            self.session.commit()
            return document
        except Exception as exc:
            self.session.rollback()
            failed = self.session.get(Document, document.id)
            if failed is not None:
                failed.status = "FAILED"
                self.session.commit()
            target.unlink(missing_ok=True)
            if isinstance(exc, ServiceUnavailableError):
                raise
            raise ServiceUnavailableError("Document indexing failed; no active version was changed") from exc

    async def reindex_document(self, document_id: int, uploader_id: int) -> Document:
        document = self.repository.by_id(document_id)
        if document is None or not document.storage_key:
            raise ConflictError("Document source is not available for re-indexing")
        root = settings.document_path.resolve()
        source = (root / document.storage_key).resolve()
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise ConflictError("Document storage key is invalid") from exc
        if not source.is_file():
            raise ConflictError("Stored document file is missing")
        return await self.index_document(document.filename, source.read_bytes(), uploader_id)

    async def retrieve(self, question: str) -> tuple[list[dict], list[dict]]:
        embedding = await self.gemini.embed(question, task_type="RETRIEVAL_QUERY")
        try:
            matches = self.vector_store.search(embedding, limit=4)
        except Exception as exc:
            raise ServiceUnavailableError("The policy index is temporarily unavailable") from exc
        grounded = [match for match in matches if match["distance"] <= 0.72]
        citations = [
            {
                "filename": match["metadata"]["filename"],
                "page": match["metadata"].get("page") or None,
                "section": match["metadata"].get("section") or None,
                "chunk_id": match["metadata"]["chunk_id"],
            }
            for match in grounded
        ]
        return grounded, citations