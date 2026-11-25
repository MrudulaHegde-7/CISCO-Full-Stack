from datetime import datetime, timedelta, timezone
import uuid

from app.errors import NotFoundError
from app.models import ChatMessage, ChatSession, PendingAction
from app.repositories.protocols import ChatRepository


class ChatService:
    def __init__(self, repository: ChatRepository) -> None:
        self.repository = repository

    def create_session(self, user_id: int, title: str) -> ChatSession:
        return self.repository.create_session(user_id, title.strip() or "New conversation")

    def list_sessions(self, user_id: int) -> list[ChatSession]:
        return self.repository.list_sessions(user_id)

    def get_session(self, session_id: int, user_id: int) -> ChatSession:
        chat_session = self.repository.session_for_owner(session_id, user_id)
        if chat_session is None:
            raise NotFoundError("Chat session not found")
        return chat_session

    def list_messages(self, session_id: int, user_id: int) -> list[ChatMessage]:
        self.get_session(session_id, user_id)
        return self.repository.messages(session_id)

    def list_pending_actions(self, session_id: int, user_id: int) -> list[PendingAction]:
        self.get_session(session_id, user_id)
        return self.repository.pending_actions(session_id, user_id)

    def add_message(
        self,
        session_id: int,
        user_id: int,
        role: str,
        content: str,
        *,
        mode: str | None = None,
        metadata: dict | None = None,
    ) -> ChatMessage:
        chat_session = self.repository.session_for_owner(
            session_id, user_id, for_update=True
        )
        if chat_session is None:
            raise NotFoundError("Chat session not found")
        return self.repository.add_message(
            chat_session, role, content, mode=mode, metadata=metadata
        )

    def create_pending_action(
        self,
        *,
        session_id: int,
        user_id: int,
        action: str,
        payload: dict,
    ) -> PendingAction:
        pending = PendingAction(
            session_id=session_id,
            user_id=user_id,
            action=action,
            payload=payload,
            idempotency_key=f"chat-action-{uuid.uuid4().hex}",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        return self.repository.add_pending_action(pending)