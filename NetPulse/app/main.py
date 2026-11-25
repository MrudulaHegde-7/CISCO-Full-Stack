from fastapi import FastAPI

from app.repositories.device_repository import InMemoryDeviceRepository
from app.routes.devices import router
from app.services.device_service import DeviceService


def create_app() -> FastAPI:
    application = FastAPI(title="NetPulse Network Monitoring API")
    repository = InMemoryDeviceRepository()
    application.state.device_service = DeviceService(repository)
    application.include_router(router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()