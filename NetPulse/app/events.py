from datetime import datetime, timezone

import structlog

from app.logging_config import safe_device_id
from app.models import AlertResponse
from app.repositories.contracts import DeviceRepository

logger = structlog.get_logger("netpulse.events")


def create_offline_alert(repository: DeviceRepository, device_id: str) -> None:
    alert = AlertResponse(
        device_id=device_id,
        message=f"Device {device_id} changed from online to offline.",
        timestamp=datetime.now(timezone.utc),
    )
    repository.save_alert(alert)
    logger.info(
        "offline_alert_created",
        device_id=safe_device_id(device_id),
    )