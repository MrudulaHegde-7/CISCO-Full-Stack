from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, PendingAction


class SQLAlchemyChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_session(self, user_id: int, title: str) -> ChatSession:
        chat_session = ChatSession(user_id=user_id, title=title)
        self.session.add(chat_session)
        self.session.flush()
        return chat_session

    def session_for_owner(
        self, session_id: int, user_id: int, *, for_update: bool = False
    ) -> ChatSession | None:
        query = select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_sessions(self, user_id: int) -> list[ChatSession]:
        query = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(self.session.scalars(query))

    def messages(self, session_id: int, limit: int = 20) -> list[ChatMessage]:
        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.seq_no.desc())
            .limit(limit)
        )
        return list(reversed(self.session.scalars(query).all()))

    def add_message(
        self,
        chat_session: ChatSession,
        role: str,
        content: str,
        *,
        mode: str | None = None,
        metadata: dict | None = None,
        touch_session: bool = True,
    ) -> ChatMessage:
        last_sequence = self.session.scalar(
            select(func.max(ChatMessage.seq_no)).where(
                ChatMessage.session_id == chat_session.id
            )
        ) or 0
        message = ChatMessage(
            session_id=chat_session.id,
            seq_no=last_sequence + 1,
            role=role,
            content=content,
            mode=mode,
            metadata_json=metadata or {},
        )
        if touch_session:
            chat_session.updated_at = datetime.now(timezone.utc)
        self.session.add(message)
        self.session.flush()
        return message

    def add_pending_action(self, action: PendingAction) -> PendingAction:
        self.session.add(action)
        self.session.flush()
        return action

    def pending_action(
        self, action_id: int, user_id: int, *, for_update: bool = False
    ) -> PendingAction | None:
        query = select(PendingAction).where(
            PendingAction.id == action_id, PendingAction.user_id == user_id
        )
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def pending_actions(self, session_id: int, user_id: int) -> list[PendingAction]:
        now = datetime.now(timezone.utc)
        query = select(PendingAction).where(
            PendingAction.session_id == session_id,
            PendingAction.user_id == user_id,
            PendingAction.status.in_(["PENDING", "PROCESSING"]),
            PendingAction.expires_at > now,
        )
        return list(self.session.scalars(query.order_by(PendingAction.created_at.desc())))