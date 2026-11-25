from base64 import b64encode

import httpx
import pytest_asyncio
from sqlalchemy import select

from app.db import Base
from app.main import create_app
from app.models import MenuItem
from app.seed import seed_demo_data


class FakeVectorStore:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def upsert_document(self, **kwargs) -> None:
        self.records.append(kwargs)

    def deactivate_document(self, document_id: int) -> None:
        return None

    def search(self, embedding: list[float], limit: int = 4) -> list[dict]:
        return []


class FakeGemini:
    async def generate(self, contents, **kwargs):
        return {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "I can help with the menu and restaurant policies."}],
                    }
                }
            ]
        }

    async def embed(self, text: str, *, task_type: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def basic_auth(username: str, password: str) -> dict[str, str]:
    token = b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest_asyncio.fixture
async def client(tmp_path):
    database_path = tmp_path / "food-assistant-test.db"
    app = create_app(
        f"sqlite:///{database_path}",
        vector_store=FakeVectorStore(),
        gemini=FakeGemini(),
    )
    Base.metadata.create_all(bind=app.state.engine)
    with app.state.session_factory() as session:
        seed_demo_data(session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client, app
    app.state.engine.dispose()


@pytest_asyncio.fixture
async def menu_item(client):
    _, app = client
    with app.state.session_factory() as session:
        return session.scalar(select(MenuItem).where(MenuItem.title == "Masala Dosa"))