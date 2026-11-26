from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.repositories.device_repository import InMemoryDeviceRepository
from app.routes.devices import router
from app.services.device_service import (
    DeviceAlreadyExistsError,
    DeviceNotFoundError,
    DeviceService,
)


def create_app() -> FastAPI:
    application = FastAPI(title="NetPulse Network Monitoring API")
    repository = InMemoryDeviceRepository()
    application.state.device_service = DeviceService(repository)
    application.include_router(router)

    @application.exception_handler(DeviceAlreadyExistsError)
    async def device_already_exists_handler(
        request: Request, exc: DeviceAlreadyExistsError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": f"Device '{exc}' already exists."},
        )

    @application.exception_handler(DeviceNotFoundError)
    async def device_not_found_handler(
        request: Request, exc: DeviceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Device '{exc}' was not found."},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()