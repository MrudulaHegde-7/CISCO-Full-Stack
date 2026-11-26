import asyncio

import pytest

from app.models import DeviceCreate
from app.repositories.device_repository import InMemoryDeviceRepository
from app.services.probe import simulate_device_probe
from app.services.device_service import (
    DeviceAlreadyExistsError,
    DeviceNotFoundError,
    DeviceService,
)


@pytest.fixture
def service() -> DeviceService:
    return DeviceService(InMemoryDeviceRepository())


def make_device(
    device_id: str = "RTR-101",
    status: str = "online",
    device_type: str = "router",
) -> DeviceCreate:
    return DeviceCreate(
        device_id=device_id,
        name="Branch Router",
        device_type=device_type,
        ip_address="192.168.10.1",
        status=status,
    )


def test_register_device(service: DeviceService) -> None:
    saved = service.register(make_device())

    assert saved.device_id == "RTR-101"
    assert service.get("RTR-101") == saved


def test_duplicate_registration_raises_error(service: DeviceService) -> None:
    service.register(make_device())

    with pytest.raises(DeviceAlreadyExistsError):
        service.register(make_device())


def test_missing_device_raises_error(service: DeviceService) -> None:
    with pytest.raises(DeviceNotFoundError):
        service.get("missing")

    with pytest.raises(DeviceNotFoundError):
        service.update_status("missing", "offline")


def test_initial_offline_registration_does_not_create_alert(
    service: DeviceService,
) -> None:
    service.register(make_device(status="offline"))

    assert service.list_alerts() == []


def test_online_to_offline_transition_creates_one_alert(
    service: DeviceService,
) -> None:
    service.register(make_device())

    updated = service.update_status("RTR-101", "offline")

    assert updated.status == "offline"
    assert len(service.list_alerts()) == 1
    assert service.list_alerts()[0].device_id == "RTR-101"
    assert service.list_alerts()[0].timestamp.tzinfo is not None


def test_repeated_offline_update_does_not_create_another_alert(
    service: DeviceService,
) -> None:
    service.register(make_device())
    service.update_status("RTR-101", "offline")

    service.update_status("RTR-101", "offline")

    assert len(service.list_alerts()) == 1


def test_empty_device_summary(service: DeviceService) -> None:
    assert service.get_device_summary().model_dump() == {
        "total_devices": 0,
        "online_count": 0,
        "offline_count": 0,
        "device_types": [],
    }


def test_populated_device_summary_counts_and_sorts_types(
    service: DeviceService,
) -> None:
    service.register(make_device(device_type="router"))
    service.register(make_device("SW-102", "offline", "switch"))
    service.register(make_device("RTR-103", device_type="router"))

    summary = service.get_device_summary()

    assert summary.total_devices == 3
    assert summary.online_count == 2
    assert summary.offline_count == 1
    assert summary.device_types == ["router", "switch"]


def test_simulated_probe_returns_deterministic_result() -> None:
    result = asyncio.run(simulate_device_probe("RTR-101"))

    assert result == {
        "device_id": "RTR-101",
        "reachable": True,
        "simulated": True,
    }