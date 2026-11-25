from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models import User
from app.repositories.documents import SQLAlchemyDocumentRepository
from app.schemas import DocumentResponse
from app.security.auth import require_admin
from app.services.rag import RAGService

router = APIRouter(prefix="/api/documents", tags=["knowledge base"])


def get_rag_service(request: Request, session: Session) -> RAGService:
    return RAGService(
        SQLAlchemyDocumentRepository(session),
        request.app.state.vector_store,
        request.app.state.gemini,
        session,
    )


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DocumentResponse:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise AppError("UPLOAD_TOO_LARGE", "Document exceeds the upload size limit", 413)
    service = get_rag_service(request, session)
    return await service.index_document(file.filename or "upload.txt", data, admin.id)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    request: Request,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[DocumentResponse]:
    return SQLAlchemyDocumentRepository(session).active_documents()


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    document_id: int,
    request: Request,
    session: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DocumentResponse:
    service = get_rag_service(request, session)
    return await service.reindex_document(document_id, admin.id)