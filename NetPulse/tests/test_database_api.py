from collections.abc import Generator, Iterator
from contextlib import contextmanager
import json
from pathlib import Path
import re

import pytest
import structlog
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.logging_config import configure_logging
from app.main import create_app
from app.repositories.sqlalchemy_device_repository import SQLAlchemyDeviceRepository


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    with _client_for_database(
        database_url,
        log_file=tmp_path / "test.jsonl",
    ) as test_client:
        yield test_client


@contextmanager
def _client_for_database(
    database_url: str,
    raise_server_exceptions: bool = True,
    log_file: Path | None = None,
) -> Iterator[TestClient]:
    if log_file is None:
        database_path = Path(database_url.removeprefix("sqlite:///"))
        log_file = database_path.with_suffix(".jsonl")
    application = create_app(database_url, log_file=log_file)

    def override_get_session() -> Generator[Session, None, None]:
        session = application.state.session_factory()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    application.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(
            application,
            raise_server_exceptions=raise_server_exceptions,
        ) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def device_payload(device_id: str = "RTR-101") -> dict[str, str]:
    return {
        "device_id": device_id,
        "name": "Branch Router",
        "device_type": "router",
        "ip_address": "192.168.10.1",
        "status": "online",
    }


def read_log_events(log_file: Path) -> list[dict[str, object]]:
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text().splitlines()]


def test_api_preserves_create_read_update_errors_and_validation(
    client: TestClient,
) -> None:
    created = client.post("/devices", json=device_payload())
    assert created.status_code == 201
    assert client.get("/devices/RTR-101").json()["device_id"] == "RTR-101"
    assert client.post("/devices", json=device_payload()).status_code == 409
    assert client.get("/devices/missing").status_code == 404
    assert client.post(
        "/devices", json={**device_payload("RTR-BAD"), "ip_address": "not-ip"}
    ).status_code == 422


def test_data_persists_across_app_restarts(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'restart.db'}"
    with _client_for_database(database_url) as first_client:
        assert first_client.post("/devices", json=device_payload()).status_code == 201

    with _client_for_database(database_url) as restarted_client:
        response = restarted_client.get("/devices/RTR-101")
        assert response.json()["device_id"] == "RTR-101"


def test_offline_transition_persists_exactly_one_alert_and_probe_is_read_only(
    client: TestClient,
) -> None:
    assert client.post("/devices", json=device_payload()).status_code == 201

    first_update = client.patch(
        "/devices/RTR-101/status", json={"status": "offline"}
    )
    assert first_update.status_code == 200
    assert first_update.json()["status"] == "offline"
    assert len(client.get("/alerts").json()) == 1

    assert client.patch(
        "/devices/RTR-101/status", json={"status": "offline"}
    ).status_code == 200
    assert len(client.get("/alerts").json()) == 1

    summary = client.get("/devices/summary").json()
    assert summary["total_devices"] == 1
    assert summary["offline_count"] == 1
    assert client.get("/devices/RTR-101/probe").json()["simulated"] is True
    assert client.get("/devices/RTR-101").json()["status"] == "offline"
    assert len(client.get("/alerts").json()) == 1


def test_status_and_alert_roll_back_together_on_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.post("/devices", json=device_payload()).status_code == 201
    save_alert = SQLAlchemyDeviceRepository.save_alert

    def save_then_fail(
        repository: SQLAlchemyDeviceRepository, alert
    ):
        save_alert(repository, alert)
        raise RuntimeError("injected test failure")

    monkeypatch.setattr(SQLAlchemyDeviceRepository, "save_alert", save_then_fail)

    with pytest.raises(RuntimeError, match="injected test failure"):
        client.patch("/devices/RTR-101/status", json={"status": "offline"})

    assert client.get("/devices/RTR-101").json()["status"] == "online"
    assert client.get("/alerts").json() == []


def test_request_ids_are_generated_accepted_and_validated(client: TestClient) -> None:
    generated = client.get("/health").headers["x-request-id"]
    assert re.fullmatch(r"[a-f0-9]{32}", generated)

    supplied = client.get(
        "/health", headers={"X-Request-ID": "lab-trace-101"}
    ).headers["x-request-id"]
    assert supplied == "lab-trace-101"

    invalid = client.get(
        "/health", headers={"X-Request-ID": "unsafe request id"}
    ).headers["x-request-id"]
    assert re.fullmatch(r"[a-f0-9]{32}", invalid)
    assert invalid != "unsafe request id"


def test_registration_and_status_events_share_request_id(
    client: TestClient,
    tmp_path,
) -> None:
    request_id = "lab-trace-201"
    response = client.post(
        "/devices",
        json=device_payload(),
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 201
    assert response.headers["x-request-id"] == request_id

    registration_events = [
        event
        for event in read_log_events(tmp_path / "test.jsonl")
        if event.get("request_id") == request_id
    ]
    for event_name in ("device_registration_requested", "device_registered"):
        event = next(
            event
            for event in registration_events
            if event["event"] == event_name
        )
        assert event["device_id"] == "RTR-101"
        assert event["request_id"] == request_id
        assert event["level"] == "info"
        assert event["timestamp"]

    response = client.patch(
        "/devices/RTR-101/status",
        json={"status": "offline"},
        headers={"X-Request-ID": request_id},
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id

    status_events = [
        event
        for event in read_log_events(tmp_path / "test.jsonl")
        if event.get("request_id") == request_id
        and event.get("event") not in {
            "device_registration_requested",
            "device_registered",
        }
    ]
    correlated_events = {
        event["event"]: event
        for event in status_events
        if event.get("event") in {"device_status_changed", "offline_alert_created"}
    }
    assert set(correlated_events) == {"device_status_changed", "offline_alert_created"}
    assert all(event["request_id"] == request_id for event in correlated_events.values())
    assert any(
        event["event"] == "request_completed" and event["status_code"] == 200
        for event in status_events
    )

    assert client.patch(
        "/devices/RTR-101/status",
        json={"status": "offline"},
        headers={"X-Request-ID": request_id},
    ).status_code == 200
    assert len(client.get("/alerts").json()) == 1


def test_domain_not_found_logs_one_warning_and_completion(
    client: TestClient,
    tmp_path,
) -> None:
    response = client.get(
        "/devices/UNKNOWN-404",
        headers={"X-Request-ID": "lab-trace-404"},
    )
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "lab-trace-404"

    events = [
        event
        for event in read_log_events(tmp_path / "test.jsonl")
        if event.get("request_id") == "lab-trace-404"
    ]
    warnings = [event for event in events if event["level"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["event"] == "device_not_found"
    assert warnings[0]["error_type"] == "DeviceNotFoundError"
    assert warnings[0]["device_id"] == "UNKNOWN-404"
    completion = next(event for event in events if event["event"] == "request_completed")
    assert completion["status_code"] == 404
    assert "?" not in completion["path"]


def test_domain_conflict_logs_one_warning(
    client: TestClient,
    tmp_path,
) -> None:
    assert client.post("/devices", json=device_payload()).status_code == 201

    response = client.post(
        "/devices",
        json=device_payload(),
        headers={"X-Request-ID": "lab-trace-409"},
    )
    assert response.status_code == 409
    assert response.headers["x-request-id"] == "lab-trace-409"

    events = [
        event
        for event in read_log_events(tmp_path / "test.jsonl")
        if event.get("request_id") == "lab-trace-409"
    ]
    warnings = [event for event in events if event["level"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["event"] == "device_already_exists"
    assert warnings[0]["error_type"] == "DeviceAlreadyExistsError"
    assert warnings[0]["device_id"] == "RTR-101"
    assert any(
        event["event"] == "request_completed" and event["status_code"] == 409
        for event in events
    )


def test_sensitive_fields_are_redacted_in_rendered_json(
    tmp_path,
) -> None:
    log_file = tmp_path / "redaction.jsonl"
    configure_logging(log_file)
    logger = structlog.get_logger("netpulse.tests.redaction")
    logger.info(
        "redaction_demo",
        token="DEMO-DO-NOT-USE",
        PASSWORD="DEMO-PASSWORD-DO-NOT-USE",
        Api_Key="DEMO-API-KEY-DO-NOT-USE",
        Authorization="DEMO-AUTH-DO-NOT-USE",
        SeCrEt="DEMO-SECRET-DO-NOT-USE",
        device_id="RTR-TEST",
    )

    output = log_file.read_text()
    for fake_secret in (
        "DEMO-DO-NOT-USE",
        "DEMO-PASSWORD-DO-NOT-USE",
        "DEMO-API-KEY-DO-NOT-USE",
        "DEMO-AUTH-DO-NOT-USE",
        "DEMO-SECRET-DO-NOT-USE",
    ):
        assert fake_secret not in output
    assert '"token": "***"' in output
    assert '"PASSWORD": "***"' in output
    assert '"Api_Key": "***"' in output
    assert '"Authorization": "***"' in output
    assert '"SeCrEt": "***"' in output
    assert '"device_id": "RTR-TEST"' in output


def test_unexpected_error_is_safely_logged_and_correlated(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'error.db'}"
    log_file = tmp_path / "error.jsonl"

    def fail_list_devices(repository: SQLAlchemyDeviceRepository):
        raise RuntimeError("secret-value-must-not-be-logged")

    monkeypatch.setattr(
        SQLAlchemyDeviceRepository,
        "list_devices",
        fail_list_devices,
    )
    with _client_for_database(
        database_url,
        raise_server_exceptions=False,
        log_file=log_file,
    ) as error_client:
        response = error_client.get(
            "/devices",
            headers={"X-Request-ID": "lab-trace-500"},
        )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "lab-trace-500"
    output = log_file.read_text()
    assert "secret-value-must-not-be-logged" not in output
    events = [json.loads(line) for line in output.splitlines()]
    error_events = [event for event in events if event["event"] == "request_failed"]
    assert len(error_events) == 1
    assert error_events[0]["level"] == "error"
    assert error_events[0]["error_type"] == "RuntimeError"
    assert error_events[0]["stack_trace"]
    assert error_events[0]["request_id"] == "lab-trace-500"
    completions = [event for event in events if event["event"] == "request_completed"]
    assert len(completions) == 1
    assert completions[0]["status_code"] == 500