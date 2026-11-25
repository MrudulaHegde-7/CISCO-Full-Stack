from sqlalchemy import func, select
import pytest

from app.agents.tools import AgentTools
from app.agents.orchestrator import GeminiAgent
from app.models import Order, PendingAction, User
from app.repositories.chat import SQLAlchemyChatRepository
from app.repositories.documents import SQLAlchemyDocumentRepository
from app.services.actions import ActionService
from app.services.chat import ChatService
from app.services.rag import RAGService
from tests.conftest import FakeGemini, basic_auth


@pytest.mark.asyncio
async def test_agent_order_tool_only_stages_pending_action(client, monkeypatch):
    api, app = client
    created = await api.post(
        "/api/chat/sessions",
        json={},
        headers=basic_auth("maya", "ChangeThisMayaPassword!"),
    )
    chat_session_id = created.json()["id"]
    with app.state.session_factory() as session:
        chat = ChatService(SQLAlchemyChatRepository(session))
        rag = RAGService(
            SQLAlchemyDocumentRepository(session),
            app.state.vector_store,
            FakeGemini(),
            session,
        )
        tools = AgentTools(
            session=session,
            chat_service=chat,
            rag_service=rag,
            user_id=2,
            chat_session_id=chat_session_id,
            authorization="Basic trusted-server-forwarded-identity",
            user_message="I want one Masala Dosa.",
        )

        async def live_menu(method, path, **kwargs):
            assert method == "GET"
            assert path == "/api/menu_items/1"
            return {
                "id": 1,
                "title": "Masala Dosa",
                "price": "90.00",
                "capacity": 10,
                "active": True,
            }

        monkeypatch.setattr(tools, "_api", live_menu)
        result = await tools.dispatch(
            "create_order", {"lines": [{"item_id": 1, "quantity": 1}]}
        )
        session.commit()

        assert result["confirmation_required"] is True
        assert result["pending_action"]["action"] == "CREATE_ORDER"
        assert session.scalar(select(func.count(Order.id))) == 3
        assert session.scalar(select(func.count(PendingAction.id))) == 1


@pytest.mark.asyncio
async def test_order_without_portion_count_asks_before_staging_action(client, monkeypatch):
    api, app = client
    created = await api.post(
        "/api/chat/sessions",
        json={},
        headers=basic_auth("maya", "ChangeThisMayaPassword!"),
    )
    chat_session_id = created.json()["id"]
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "maya"))
        chat = ChatService(SQLAlchemyChatRepository(session))
        rag = RAGService(
            SQLAlchemyDocumentRepository(session),
            app.state.vector_store,
            FakeGemini(),
            session,
        )
        tools = AgentTools(
            session=session,
            chat_service=chat,
            rag_service=rag,
            user_id=user.id,
            chat_session_id=chat_session_id,
            authorization="Basic trusted-server-forwarded-identity",
            user_message="I want to order idli.",
        )

        async def live_menu(method, path, **kwargs):
            assert method == "GET"
            assert path == "/api/menu_items/1"
            return {
                "id": 1,
                "title": "Idli Sambar",
                "price": "70.00",
                "capacity": 10,
                "active": True,
            }

        class FakeToolCallingGemini:
            async def generate(self, contents, **kwargs):
                return {"candidates": [{"content": {
                    "role": "model",
                    "parts": [{"functionCall": {
                        "name": "create_order",
                        "args": {"lines": [{"item_id": 1, "quantity": 1}]},
                    }}],
                }}]}

        monkeypatch.setattr(tools, "_api", live_menu)
        before_orders = session.scalar(select(func.count(Order.id)))
        result = await GeminiAgent(FakeToolCallingGemini()).respond(
            [{"role": "user", "content": "I want to order idli."}], tools
        )

        assert result.text == "How many portions of Idli Sambar would you like?"
        assert result.pending_action is None
        assert session.scalar(select(func.count(PendingAction.id))) == 0
        assert session.scalar(select(func.count(Order.id))) == before_orders


@pytest.mark.asyncio
async def test_confirmed_action_is_idempotent_and_saved_to_chat(client, monkeypatch):
    _, app = client
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "maya"))
        chat = ChatService(SQLAlchemyChatRepository(session))
        chat_session = chat.create_session(user.id, "Order help")
        pending = chat.create_pending_action(
            session_id=chat_session.id,
            user_id=user.id,
            action="CREATE_ORDER",
            payload={
                "order": {"lines": [{"item_id": 1, "quantity": 1}]},
                "summary": "Place one Masala Dosa order.",
                "preview": {"total": "90.00"},
            },
        )
        session.commit()
        action_id = pending.id
        calls = []

        class FakeResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"id": 501, "status": "CONFIRMED", "total": "90.00"}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, path, *, json, headers):
                calls.append((path, json, headers))
                return FakeResponse()

        monkeypatch.setattr(
            "app.services.actions.httpx.AsyncClient",
            lambda **kwargs: FakeClient(),
        )
        actions = ActionService(session)
        first = await actions.decide(action_id, user.id, True, "Basic test-identity")
        second = await actions.decide(action_id, user.id, True, "Basic test-identity")

        assert first.status == second.status == "CONFIRMED"
        assert first.result_json["id"] == second.result_json["id"] == 501
        assert len(calls) == 1
        assert calls[0][0] == "/api/orders"
        assert calls[0][2]["Authorization"] == "Basic test-identity"
        assert calls[0][2]["Idempotency-Key"].startswith("chat-action-")
        messages = SQLAlchemyChatRepository(session).messages(chat_session.id)
        assert messages[-1].metadata_json["action_status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_rejected_action_never_calls_business_api(client):
    _, app = client
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "maya"))
        chat = ChatService(SQLAlchemyChatRepository(session))
        chat_session = chat.create_session(user.id, "Cancel question")
        pending = chat.create_pending_action(
            session_id=chat_session.id,
            user_id=user.id,
            action="CANCEL_ORDER",
            payload={"order_id": 1, "summary": "Cancel order #1?", "preview": {}},
        )
        session.commit()

        action = await ActionService(session).decide(
            pending.id, user.id, False, "Basic test-identity"
        )

        assert action.status == "REJECTED"
        assert session.scalar(select(func.count(Order.id))) == 3
        messages = SQLAlchemyChatRepository(session).messages(chat_session.id)
        assert messages[-1].content == "The action was rejected; no order was changed."


@pytest.mark.asyncio
async def test_unreturned_action_is_rolled_back_when_gemini_fails(client, monkeypatch):
    api, app = client
    created = await api.post(
        "/api/chat/sessions",
        json={},
        headers=basic_auth("maya", "ChangeThisMayaPassword!"),
    )
    session_id = created.json()["id"]
    calls = 0

    async def fail_after_tool(contents, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "candidates": [{
                    "content": {
                        "role": "model",
                        "parts": [{"functionCall": {
                            "name": "create_order",
                            "args": {"lines": [{"item_id": 1, "quantity": 1}]},
                        }}],
                    }
                }]
            }
        from app.errors import ServiceUnavailableError

        raise ServiceUnavailableError("Gemini failed after preparing the preview")

    async def live_menu(self, method, path, **kwargs):
        return {"id": 1, "title": "Masala Dosa", "price": "90.00", "capacity": 10}

    monkeypatch.setattr(app.state.gemini, "generate", fail_after_tool)
    monkeypatch.setattr(AgentTools, "_api", live_menu)
    response = await api.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "Order a dosa."},
        headers=basic_auth("maya", "ChangeThisMayaPassword!"),
    )

    assert response.status_code == 503
    actions = await api.get(f"/api/chat/sessions/{session_id}/actions", headers=basic_auth("maya", "ChangeThisMayaPassword!"))
    assert actions.json() == []


@pytest.mark.asyncio
async def test_gemini_policy_tool_returns_rag_mode_and_citation(client):
    _, app = client
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "maya"))
        chat = ChatService(SQLAlchemyChatRepository(session))
        chat_session = chat.create_session(user.id, "Policy help")

        class FakeRag:
            async def retrieve(self, question):
                return (
                    [{"text": "Cancellation is allowed before preparation.", "metadata": {}}],
                    [{"filename": "Restaurant_Policy.txt", "page": None, "section": "Document", "chunk_id": "doc-1-v1-c0"}],
                )

        class FunctionCallingGemini:
            def __init__(self):
                self.calls = 0

            async def generate(self, contents, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return {"candidates": [{"content": {
                        "role": "model",
                        "parts": [{"functionCall": {
                            "name": "retrieve_policy",
                            "args": {"question": "When can I cancel?"},
                        }}],
                    }}]}
                assert contents[-1]["parts"][0]["functionResponse"]["name"] == "retrieve_policy"
                return {"candidates": [{"content": {
                    "role": "model",
                    "parts": [{"text": "The policy allows cancellation before preparation."}],
                }}]}

        tools = AgentTools(
            session=session,
            chat_service=chat,
            rag_service=FakeRag(),
            user_id=user.id,
            chat_session_id=chat_session.id,
            authorization="Basic trusted-identity",
        )
        result = await GeminiAgent(FunctionCallingGemini()).respond(
            [{"role": "user", "content": "When can I cancel?"}], tools
        )

        assert result.mode == "RAG"
        assert result.citations[0]["filename"] == "Restaurant_Policy.txt"
        assert "before preparation" in result.text


@pytest.mark.asyncio
async def test_agent_business_tools_use_current_app_origin(client, monkeypatch):
    _, app = client
    observed_bases = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return []

    class FakeClient:
        def __init__(self, *, base_url, **kwargs):
            observed_bases.append(str(base_url).rstrip("/"))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.agents.tools.httpx.AsyncClient", FakeClient)
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "maya"))
        chat = ChatService(SQLAlchemyChatRepository(session))
        chat_session = chat.create_session(user.id, "Origin check")
        tools = AgentTools(
            session=session,
            chat_service=chat,
            rag_service=object(),
            user_id=user.id,
            chat_session_id=chat_session.id,
            authorization="Basic trusted-identity",
            api_base_url="http://food-app.test:8003/",
        )

        result = await tools.dispatch("search_menu_items", {"keyword": "idli"})

        assert result == {"ok": True, "items": []}
        assert observed_bases == ["http://food-app.test:8003"]