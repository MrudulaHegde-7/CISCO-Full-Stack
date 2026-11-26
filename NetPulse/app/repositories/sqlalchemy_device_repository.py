from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AlertRow, DeviceRow
from app.models import AlertResponse, DeviceCreate, DeviceResponse, DeviceStatus


class SQLAlchemyDeviceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_device(self, device: DeviceCreate) -> DeviceResponse:
        row = DeviceRow(**device.model_dump())
        self.session.add(row)
        self.session.flush()
        return self._device_response(row)

    def list_devices(self) -> list[DeviceResponse]:
        rows = self.session.scalars(select(DeviceRow)).all()
        return [self._device_response(row) for row in rows]

    def get_device(self, device_id: str) -> DeviceResponse | None:
        row = self.session.get(DeviceRow, device_id)
        return self._device_response(row) if row is not None else None

    def update_status(
        self, device_id: str, status: DeviceStatus
    ) -> DeviceResponse | None:
        row = self.session.get(DeviceRow, device_id)
        if row is None:
            return None

        row.status = status
        self.session.flush()
        return self._device_response(row)

    def save_alert(self, alert: AlertResponse) -> AlertResponse:
        row = AlertRow(**alert.model_dump())
        self.session.add(row)
        self.session.flush()
        return self._alert_response(row)

    def list_alerts(self) -> list[AlertResponse]:
        rows = self.session.scalars(select(AlertRow).order_by(AlertRow.id)).all()
        return [self._alert_response(row) for row in rows]

    @staticmethod
    def _device_response(row: DeviceRow) -> DeviceResponse:
        return DeviceResponse(
            device_id=row.device_id,
            name=row.name,
            device_type=row.device_type,
            ip_address=row.ip_address,
            status=row.status,
        )

    @staticmethod
    def _alert_response(row: AlertRow) -> AlertResponse:
        timestamp = row.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return AlertResponse(
            device_id=row.device_id,
            message=row.message,
            timestamp=timestamp,
        )