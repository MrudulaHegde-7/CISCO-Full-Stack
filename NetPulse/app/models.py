from datetime import datetime
from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DeviceType = Literal["router", "switch", "server"]
DeviceStatus = Literal["online", "offline"]


class DeviceCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "RTR-101",
                "name": "Branch Router",
                "device_type": "router",
                "ip_address": "192.168.10.1",
                "status": "online",
            }
        }
    )

    device_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    device_type: DeviceType
    ip_address: str
    status: DeviceStatus = "online"

    @field_validator("ip_address")
    @classmethod
    def validate_ipv4(cls, value: str) -> str:
        try:
            IPv4Address(value)
        except ValueError as exc:
            raise ValueError("ip_address must be a valid IPv4 address") from exc
        return value


class DeviceResponse(DeviceCreate):
    pass


class DeviceSummary(BaseModel):
    total_devices: int
    online_count: int
    offline_count: int
    device_types: list[DeviceType]


class StatusUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "offline"}}
    )

    status: DeviceStatus


class AlertResponse(BaseModel):
    device_id: str
    message: str
    timestamp: datetime