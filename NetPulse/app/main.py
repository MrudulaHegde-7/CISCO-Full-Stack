from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.db.database import (
    DATABASE_URL,
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from app.logging_config import configure_logging, safe_device_id
from app.routes.devices import router
from app.services.device_service import DeviceAlreadyExistsError, DeviceNotFoundError

_SAFE_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
logger = structlog.get_logger("netpulse.request")


def create_app(
    database_url: str = DATABASE_URL,
    log_file: str | Path | None = None,
) -> FastAPI:
    engine = create_database_engine(database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(log_file)
        initialize_database(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="NetPulse Network Monitoring API",
        lifespan=lifespan,
    )
    application.state.session_factory = create_session_factory(engine)
    application.include_router(router)

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        clear_contextvars()
        supplied_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_id
            if _SAFE_REQUEST_ID_PATTERN.fullmatch(supplied_id)
            else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        bind_contextvars(request_id=request_id)
        started_at = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            logger.exception(
                "request_failed",
                error_type=type(exc).__name__,
            )
            raise
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            logger.info(
                "request_completed",
                method=request.method,
                path=path,
                status_code=status_code,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            )
            clear_contextvars()

    @application.exception_handler(DeviceAlreadyExistsError)
    async def device_already_exists_handler(
        request: Request, exc: DeviceAlreadyExistsError
    ) -> JSONResponse:
        logger.warning(
            "device_already_exists",
            error_type=type(exc).__name__,
            device_id=safe_device_id(str(exc)),
        )
        return JSONResponse(
            status_code=409,
            content={"detail": f"Device '{exc}' already exists."},
        )

    @application.exception_handler(DeviceNotFoundError)
    async def device_not_found_handler(
        request: Request, exc: DeviceNotFoundError
    ) -> JSONResponse:
        logger.warning(
            "device_not_found",
            error_type=type(exc).__name__,
            device_id=safe_device_id(str(exc)),
        )
        return JSONResponse(
            status_code=404,
            content={"detail": f"Device '{exc}' was not found."},
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exc: Exception
    ) -> PlainTextResponse:
        return PlainTextResponse(
            "Internal Server Error",
            status_code=500,
            headers={"X-Request-ID": request.state.request_id},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()