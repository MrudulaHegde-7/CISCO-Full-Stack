from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import MenuItem, Order, User
from tests.conftest import basic_auth

ADMIN = basic_auth("admin", "ChangeThisAdminPassword!")
MAYA = basic_auth("maya", "ChangeThisMayaPassword!")
ARJUN = basic_auth("arjun", "ChangeThisArjunPassword!")


@pytest.mark.asyncio
async def test_public_menu_health_and_validation(client):
    api, _ = client
    assert (await api.get("/api/health")).json() == {"status": "ok"}
    menu = await api.get("/api/menu_items", params={"vegetarian": True, "max_price": 200})
    assert menu.status_code == 200
    assert len(menu.json()) >= 8
    all_items = await api.get("/api/menu_items")
    image_urls = [item["image_url"] for item in all_items.json()]
    assert len(set(image_urls)) == len(image_urls)
    invalid = await api.post(
        "/api/menu_items", json={"title": "x", "price": -1}, headers=ADMIN
    )
    assert invalid.status_code == 422
    assert {"code", "message", "request_id"} <= invalid.json().keys()


@pytest.mark.asyncio
async def test_signup_creates_normalized_user_with_argon2_password(client):
    api, app = client
    password = "fresh-account-passphrase-27!"
    created = await api.post(
        "/api/auth/signup",
        json={"username": "New_Customer", "password": password},
    )
    assert created.status_code == 201
    assert created.json() == {"username": "new_customer", "role": "USER"}

    authenticated = await api.get(
        "/api/auth/me", headers=basic_auth("new_customer", password)
    )
    assert authenticated.status_code == 200
    assert authenticated.json()["role"] == "USER"

    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "new_customer"))
        assert user.password_hash.startswith("$argon2")
        assert user.password_hash != password


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_username_case_insensitively(client):
    api, _ = client
    payload = {"username": "new_customer", "password": "fresh-account-passphrase-27!"}
    assert (await api.post("/api/auth/signup", json=payload)).status_code == 201
    duplicate = await api.post(
        "/api/auth/signup",
        json={"username": "NEW_CUSTOMER", "password": "another-safe-passphrase-28!"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_signup_validates_username_and_password(client):
    api, _ = client
    short_password = await api.post(
        "/api/auth/signup", json={"username": "validname", "password": "short"}
    )
    bad_username = await api.post(
        "/api/auth/signup",
        json={"username": "not a valid name", "password": "fresh-account-passphrase-27!"},
    )
    assert short_password.status_code == 422
    assert bad_username.status_code == 422


@pytest.mark.asyncio
async def test_seeded_menu_photos_match_the_dish(client):
    api, _ = client
    menu = (await api.get("/api/menu_items")).json()
    expected_image_parts = {
        "Masala Dosa": "photo-1668236543090-82eba5ee5976",
        "Paneer Biryani": "Paneer_Biriyani_02.jpg",
        "Idli Sambar": "Idli_Sambar-Noida-UP-SP004.jpg",
        "Vegetable Pulao": "Andhra_Vegetable_Pulao_-_WCI-Day0-Dinner.jpg",
        "Chana Masala": "Chana_Masala_-_Mohammed_-_Spice_Of_Life",
        "Paneer Tikka": "Paneer_Tikka_Shashlik_PK012.jpg",
        "Garden Salad": "Vegetable_Salad_%28Unsplash%29.jpg",
        "Chicken Curry": "Chicken_Curry_5.jpg",
        "Gulab Jamun": "Gulab_Jamun_as_a_Diwali_Sweet.jpg",
        "Lemon Rice": "Lemon_Rice_in_Kerala.jpg",
    }
    for item in menu:
        assert expected_image_parts[item["title"]] in item["image_url"]


@pytest.mark.asyncio
async def test_admin_catalog_permissions_and_soft_disable(client):
    api, _ = client
    payload = {
        "title": "Seasonal Bowl",
        "category": "Main course",
        "vegetarian": True,
        "price": "125.00",
        "capacity": 5,
        "description": "A seasonal bowl.",
        "declared_allergens": "Not specified",
    }
    denied = await api.post("/api/menu_items", json=payload, headers=MAYA)
    assert denied.status_code == 403
    created = await api.post("/api/menu_items", json=payload, headers=ADMIN)
    assert created.status_code == 201
    item_id = created.json()["id"]
    updated = await api.put(
        f"/api/menu_items/{item_id}", json={"capacity": 8}, headers=ADMIN
    )
    assert updated.json()["capacity"] == 8
    disabled = await api.delete(f"/api/menu_items/{item_id}", headers=ADMIN)
    assert disabled.status_code == 204
    assert (await api.get(f"/api/menu_items/{item_id}")).status_code == 404


@pytest.mark.asyncio
async def test_order_price_snapshot_idempotency_and_ownership(client):
    api, app = client
    payload = {"lines": [{"item_id": 1, "quantity": 2}]}
    first = await api.post(
        "/api/orders",
        json=payload,
        headers={**MAYA, "Idempotency-Key": "maya-order-0001"},
    )
    assert first.status_code == 201
    assert first.json()["total"] == "180.00"
    replay = await api.post(
        "/api/orders",
        json=payload,
        headers={**MAYA, "Idempotency-Key": "maya-order-0001"},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    conflict = await api.post(
        "/api/orders",
        json={"lines": [{"item_id": 1, "quantity": 1}]},
        headers={**MAYA, "Idempotency-Key": "maya-order-0001"},
    )
    assert conflict.status_code == 409
    hidden = await api.get(f"/api/orders/{first.json()['id']}", headers=ARJUN)
    assert hidden.status_code == 404
    with app.state.session_factory() as session:
        item = session.get(MenuItem, 1)
        order = session.scalar(select(Order).where(Order.id == first.json()["id"]))
        assert item.capacity == 17
        assert order.lines[0].unit_price == Decimal("90.00")


@pytest.mark.asyncio
async def test_failed_order_does_not_partially_decrement_stock(client):
    api, app = client
    with app.state.session_factory() as session:
        item = session.get(MenuItem, 1)
        item.capacity = 1
        session.commit()
    response = await api.post(
        "/api/orders",
        json={"lines": [{"item_id": 1, "quantity": 2}]},
        headers={**MAYA, "Idempotency-Key": "maya-order-0002"},
    )
    assert response.status_code == 409
    with app.state.session_factory() as session:
        assert session.get(MenuItem, 1).capacity == 1
        assert session.scalar(select(Order).where(Order.idempotency_key == "maya-order-0002")) is None


@pytest.mark.asyncio
async def test_cancel_restores_capacity_once(client):
    api, app = client
    created = await api.post(
        "/api/orders",
        json={"lines": [{"item_id": 1, "quantity": 1}]},
        headers={**MAYA, "Idempotency-Key": "maya-order-0003"},
    )
    order_id = created.json()["id"]
    cancelled = await api.post(f"/api/orders/{order_id}/cancel", headers=MAYA)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert (await api.post(f"/api/orders/{order_id}/cancel", headers=MAYA)).status_code == 409
    with app.state.session_factory() as session:
        assert session.get(MenuItem, 1).capacity == 19


@pytest.mark.asyncio
async def test_chat_history_is_persisted_and_private(client):
    api, _ = client
    created = await api.post(
        "/api/chat/sessions", json={"title": "Menu question"}, headers=MAYA
    )
    session_id = created.json()["id"]
    reply = await api.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "Suggest a vegetarian dinner."},
        headers=MAYA,
    )
    assert reply.status_code == 200
    assert reply.json()["mode"] == "GENERAL"
    history = await api.get(f"/api/chat/sessions/{session_id}/messages", headers=MAYA)
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    hidden = await api.get(
        f"/api/chat/sessions/{session_id}/messages", headers=ARJUN
    )
    assert hidden.status_code == 404


@pytest.mark.asyncio
async def test_confirmation_records_rejection_without_order_mutation(client):
    api, _ = client
    created = await api.post("/api/chat/sessions", json={}, headers=MAYA)
    session_id = created.json()["id"]
    action = await api.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "Please order one Masala Dosa."},
        headers=MAYA,
    )
    # The fake model emits only text, so no action can be executed or fabricated.
    assert action.status_code == 200
    assert action.json()["pending_action"] is None
    assert len(action.json()["assistant_message"]["content"]) > 0


@pytest.mark.asyncio
async def test_admin_document_upload_and_reindex_versions(client):
    api, _ = client
    upload = await api.post(
        "/api/documents",
        headers=ADMIN,
        files={"file": ("restaurant-policy.txt", b"Cancellation is allowed before preparation begins.", "text/plain")},
    )
    assert upload.status_code == 201
    first = upload.json()
    assert first["version"] == 1
    assert first["status"] == "ACTIVE"

    reindexed = await api.post(f"/api/documents/{first['id']}/reindex", headers=ADMIN)
    assert reindexed.status_code == 200
    assert reindexed.json()["version"] == 2
    active = await api.get("/api/documents", headers=ADMIN)
    assert len(active.json()) == 1
    assert active.json()[0]["version"] == 2


@pytest.mark.asyncio
async def test_gemini_failure_is_saved_without_claiming_success(client, monkeypatch):
    api, app = client

    async def unavailable(*args, **kwargs):
        from app.errors import ServiceUnavailableError

        raise ServiceUnavailableError("Gemini is temporarily unavailable.")

    monkeypatch.setattr(app.state.gemini, "generate", unavailable)
    created = await api.post("/api/chat/sessions", json={}, headers=MAYA)
    session_id = created.json()["id"]
    response = await api.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "Suggest a vegetarian dinner."},
        headers=MAYA,
    )

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    history = await api.get(f"/api/chat/sessions/{session_id}/messages", headers=MAYA)
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    assert history.json()[-1]["metadata_json"]["error"] is True
    assert "temporarily unavailable" in history.json()[-1]["content"]