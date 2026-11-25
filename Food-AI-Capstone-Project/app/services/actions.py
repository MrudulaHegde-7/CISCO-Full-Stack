from datetime import datetime, timezone
import logging

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.models import PendingAction
from app.repositories.chat import SQLAlchemyChatRepository

logger = logging.getLogger(__name__)


class ActionService:
    def __init__(self, session: Session, api_base_url: str | None = None) -> None:
        self.session = session
        self.repository = SQLAlchemyChatRepository(session)
        self.api_base_url = (api_base_url or settings.internal_api_base_url).rstrip("/")

    async def decide(
        self,
        action_id: int,
        user_id: int,
        confirm: bool,
        authorization: str,
    ) -> PendingAction:
        action = self.repository.pending_action(action_id, user_id, for_update=True)
        if action is None:
            raise NotFoundError("Pending action not found")
        if action.status in {"CONFIRMED", "REJECTED", "EXPIRED"}:
            if confirm and action.status == "CONFIRMED":
                return action
            raise ConflictError(f"This action is already {action.status.lower()}")
        if action.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            action.status = "EXPIRED"
            self.session.commit()
            raise ConflictError("This confirmation has expired")
        if not confirm:
            if action.status == "PROCESSING":
                raise ConflictError("This action is already being processed")
            action.status = "REJECTED"
            action.result_json = {"message": "The action was rejected; no order was changed."}
            self.session.commit()
            self._record_outcome_best_effort(action, action.result_json["message"])
            return action

        if action.action not in {"CREATE_ORDER", "CANCEL_ORDER"}:
            raise ConflictError("Unsupported pending action")
        action.status = "PROCESSING"
        self.session.commit()

        try:
            async with httpx.AsyncClient(
                base_url=self.api_base_url,
                timeout=httpx.Timeout(10.0, connect=2.0),
                follow_redirects=False,
            ) as client:
                headers = {"Authorization": authorization}
                if action.action == "CREATE_ORDER":
                    headers["Idempotency-Key"] = action.idempotency_key
                    response = await client.post(
                        "/api/orders", json=action.payload["order"], headers=headers
                    )
                else:
                    current = await client.get(
                        f"/api/orders/{action.payload['order_id']}", headers=headers
                    )
                    if current.status_code >= 400:
                        response = current
                    elif current.json().get("status") == "CANCELLED":
                        action.result_json = current.json()
                        action.status = "CONFIRMED"
                        self.session.commit()
                        self._record_outcome_best_effort(
                            action, f"Order #{action.payload['order_id']} was cancelled."
                        )
                        return action
                    else:
                        response = await client.post(
                            f"/api/orders/{action.payload['order_id']}/cancel",
                            headers=headers,
                        )
                if response.status_code >= 400:
                    action.status = "PENDING"
                    self.session.commit()
                    detail = "The business API rejected this action."
                    try:
                        detail = response.json().get("message", detail)
                    except ValueError:
                        pass
                    raise ConflictError(detail)
                action.result_json = response.json()
                action.status = "CONFIRMED"
                result_id = action.result_json.get("id", action.payload.get("order_id", ""))
                self.session.commit()
                self._record_outcome_best_effort(
                    action, f"Confirmed action completed for order #{result_id}."
                )
                return action
        except ConflictError:
            raise
        except httpx.HTTPError as exc:
            action.status = "PENDING"
            self.session.commit()
            raise ServiceUnavailableError(
                "The action result is uncertain; retry confirmation to safely reconcile it."
            ) from exc

    def _record_outcome(self, action: PendingAction, text: str) -> None:
        chat_session = self.repository.session_for_owner(action.session_id, action.user_id)
        if chat_session is None:
            return
        self.repository.add_message(
            chat_session,
            "assistant",
            text,
            mode="AGENT",
            metadata={"pending_action_id": action.id, "action_status": action.status},
            touch_session=False,
        )

    def _record_outcome_best_effort(self, action: PendingAction, text: str) -> None:
        try:
            self._record_outcome(action, text)
            self.session.commit()
        except Exception:
            self.session.rollback()
            logger.warning(
                "Could not append action outcome to chat transcript for action_id=%s",
                action.id,
            )