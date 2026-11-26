from __future__ import annotations

from app.events import create_offline_alert
from app.models import (
    AlertResponse,
    DeviceCreate,
    DeviceResponse,
    DeviceStatus,
    DeviceSummary,
)
from app.repositories.contracts import DeviceRepository


class DeviceAlreadyExistsError(Exception):
    pass


class DeviceNotFoundError(Exception):
    pass


class DeviceService:
    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    def register(self, device: DeviceCreate) -> DeviceResponse:
        if self.repository.get_device(device.device_id) is not None:
            raise DeviceAlreadyExistsError(device.device_id)
        return self.repository.add_device(device)

    def list(self) -> list[DeviceResponse]:
        return self.repository.list_devices()

    def get_device_summary(self) -> DeviceSummary:
        devices = self.repository.list_devices()
        statuses = [device.status for device in devices]
        status_counts = {
            status: statuses.count(status) for status in {"online", "offline"}
        }
        device_types = sorted({device.device_type for device in devices})
        return DeviceSummary(
            total_devices=len(devices),
            online_count=status_counts["online"],
            offline_count=status_counts["offline"],
            device_types=device_types,
        )

    def get(self, device_id: str) -> DeviceResponse:
        device = self.repository.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        return device

    def update_status(
        self, device_id: str, status: DeviceStatus
    ) -> DeviceResponse:
        device = self.get(device_id)
        updated_device = self.repository.update_status(device_id, status)
        if updated_device is None:
            raise DeviceNotFoundError(device_id)

        if device.status == "online" and status == "offline":
            create_offline_alert(self.repository, device_id)

        return updated_device

    def list_alerts(self) -> list[AlertResponse]:
        return self.repository.list_alerts()