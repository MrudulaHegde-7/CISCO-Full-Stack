from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.agents.orchestrator import GeminiAgent
from app.agents.tools import AgentTools
from app.db import get_db
from app.errors import NotFoundError, ServiceUnavailableError
from app.models import ChatMessage, ToolRun, User
from app.repositories.chat import SQLAlchemyChatRepository
from app.repositories.documents import SQLAlchemyDocumentRepository
from app.schemas import (
    ActionDecision,
    ActionResult,
    ChatMessageResponse,
    ChatReply,
    ChatRequest,
    ChatSessionCreate,
    ChatSessionResponse,
)
from app.security.auth import get_current_user
from app.services.actions import ActionService
from app.services.chat import ChatService
from app.services.rag import RAGService

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_chat_service(session: Session = Depends(get_db)) -> ChatService:
    return ChatService(SQLAlchemyChatRepository(session))


def get_rag_service(request: Request, session: Session = Depends(get_db)) -> RAGService:
    return RAGService(
        SQLAlchemyDocumentRepository(session),
        request.app.state.vector_store,
        request.app.state.gemini,
        session,
    )


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    data: ChatSessionCreate,
    service: ChatService = Depends(get_chat_service),
    user: User = Depends(get_current_user),
) -> ChatSessionResponse:
    return service.create_session(user.id, data.title)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_chat_sessions(
    service: ChatService = Depends(get_chat_service),
    user: User = Depends(get_current_user),
) -> list[ChatSessionResponse]:
    return service.list_sessions(user.id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_chat_messages(
    session_id: int,
    service: ChatService = Depends(get_chat_service),
    user: User = Depends(get_current_user),
) -> list[ChatMessageResponse]:
    return service.list_messages(session_id, user.id)


@router.get("/sessions/{session_id}/actions")
def list_pending_actions(
    session_id: int,
    service: ChatService = Depends(get_chat_service),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return [
        {
            "id": action.id,
            "action": action.action,
            "status": action.status,
            "summary": action.payload["summary"],
            "expires_at": action.expires_at,
        }
        for action in service.list_pending_actions(session_id, user.id)
    ]


@router.post("/sessions/{session_id}/messages", response_model=ChatReply)
async def send_chat_message(
    session_id: int,
    data: ChatRequest,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatReply:
    chat_service = ChatService(SQLAlchemyChatRepository(session))
    chat_session = chat_service.get_session(session_id, user.id)
    user_message = chat_service.add_message(session_id, user.id, "user", data.message)
    if chat_session.title == "New conversation":
        chat_session.title = data.message[:60]
    session.commit()

    authorization = request.headers.get("authorization", "")
    rag_service = get_rag_service(request, session)
    tools = AgentTools(
        session=session,
        chat_service=chat_service,
        rag_service=rag_service,
        user_id=user.id,
        chat_session_id=session_id,
        authorization=authorization,
        api_base_url=str(request.base_url).rstrip("/"),
        user_message=data.message,
    )
    history = [
        {"role": message.role, "content": message.content}
        for message in SQLAlchemyChatRepository(session).messages(session_id, limit=12)
    ]
    try:
        result = await GeminiAgent(request.app.state.gemini).respond(history, tools)
    except ServiceUnavailableError as exc:
        session.rollback()
        chat_service.add_message(
            session_id,
            user.id,
            "assistant",
            "The assistant is temporarily unavailable. Your message is saved; please try again.",
            mode="GENERAL",
            metadata={"error": True},
        )
        session.commit()
        raise exc
    except Exception as exc:
        session.rollback()
        chat_service.add_message(
            session_id,
            user.id,
            "assistant",
            "The assistant is temporarily unavailable. Your message is saved; please try again.",
            mode="GENERAL",
            metadata={"error": True},
        )
        session.commit()
        raise ServiceUnavailableError("The assistant is temporarily unavailable") from exc

    assistant_message = chat_service.add_message(
        session_id,
        user.id,
        "assistant",
        result.text,
        mode=result.mode,
        metadata={
            "citations": result.citations,
            "pending_action": (
                {
                    "id": result.pending_action.id,
                    "action": result.pending_action.action,
                    "status": result.pending_action.status,
                    "summary": result.pending_action.payload["summary"],
                    "expires_at": result.pending_action.expires_at.isoformat(),
                }
                if result.pending_action is not None
                else None
            ),
        },
    )
    for run in result.tool_runs:
        session.add(
            ToolRun(
                message_id=assistant_message.id,
                tool_name=run["tool_name"],
                args_json=run["args"],
                result_json=run["result"],
                status="SUCCESS" if run["result"].get("ok", True) else "ERROR",
            )
        )
    session.commit()
    pending = result.pending_action
    pending_response = None
    if pending is not None:
        pending_response = {
            "id": pending.id,
            "action": pending.action,
            "summary": pending.payload["summary"],
            "expires_at": pending.expires_at,
        }
    return ChatReply(
        user_message=ChatMessageResponse.model_validate(user_message),
        assistant_message=ChatMessageResponse.model_validate(assistant_message),
        mode=result.mode,
        citations=result.citations,
        pending_action=pending_response,
    )


@router.post("/actions/{action_id}/confirm", response_model=ActionResult)
async def decide_pending_action(
    action_id: int,
    decision: ActionDecision,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ActionResult:
    authorization = request.headers.get("authorization", "")
    action = await ActionService(
        session, api_base_url=str(request.base_url).rstrip("/")
    ).decide(
        action_id, user.id, decision.confirm, authorization
    )
    return ActionResult(id=action.id, status=action.status, result=action.result_json)