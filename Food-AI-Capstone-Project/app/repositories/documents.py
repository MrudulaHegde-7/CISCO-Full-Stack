from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document


class SQLAlchemyDocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_named(self, filename: str) -> Document | None:
        query = (
            select(Document)
            .where(Document.filename == filename)
            .order_by(Document.version.desc())
            .limit(1)
        )
        return self.session.scalar(query)

    def add(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def active_documents(self) -> list[Document]:
        return list(
            self.session.scalars(
                select(Document).where(Document.status == "ACTIVE").order_by(Document.filename)
            )
        )

    def by_id(self, document_id: int) -> Document | None:
        return self.session.get(Document, document_id)