from fastapi import APIRouter, Depends, Request, status

from app.models import (
    AlertResponse,
    DeviceCreate,
    DeviceResponse,
    DeviceSummary,
    StatusUpdate,
)
from app.services.probe import simulate_device_probe
from app.services.device_service import (
    DeviceService,
)

router = APIRouter()


def get_device_service(request: Request) -> DeviceService:
    return request.app.state.device_service


@router.post(
    "/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "A device with this ID already exists."}},
)
def register_device(
    device: DeviceCreate,
    service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
    return service.register(device)


@router.get("/devices", response_model=list[DeviceResponse])
def list_devices(
    service: DeviceService = Depends(get_device_service),
) -> list[DeviceResponse]:
    return service.list()


@router.get("/devices/summary", response_model=DeviceSummary)
def get_device_summary(
    service: DeviceService = Depends(get_device_service),
) -> DeviceSummary:
    return service.get_device_summary()


@router.get(
    "/devices/{device_id}/probe",
    responses={404: {"description": "Device not found."}},
)
async def probe_device(
    device_id: str,
    service: DeviceService = Depends(get_device_service),
) -> dict[str, str | bool]:
    service.get(device_id)
    return await simulate_device_probe(device_id)


@router.get(
    "/devices/{device_id}",
    response_model=DeviceResponse,
    responses={404: {"description": "Device not found."}},
)
def get_device(
    device_id: str,
    service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
    return service.get(device_id)


@router.patch(
    "/devices/{device_id}/status",
    response_model=DeviceResponse,
    responses={404: {"description": "Device not found."}},
)
def update_device_status(
    device_id: str,
    update: StatusUpdate,
    service: DeviceService = Depends(get_device_service),
) -> DeviceResponse:
    return service.update_status(device_id, update.status)


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    service: DeviceService = Depends(get_device_service),
) -> list[AlertResponse]:
    return service.list_alerts()