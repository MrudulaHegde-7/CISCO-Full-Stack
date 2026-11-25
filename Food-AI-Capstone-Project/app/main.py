from collections import defaultdict, deque
from contextlib import asynccontextmanager
import logging
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.menu import router as menu_router
from app.api.orders import router as orders_router
from app.config import PROJECT_ROOT, settings
from app.db import Base, build_engine, build_session_factory
from app.errors import AppError
from app.models import *  # noqa: F403
from app.rag.vector_store import ChromaVectorStore
from app.seed import seed_demo_data
from app.services.gemini import GeminiClient

logger = logging.getLogger("food_assistant")
_rate_lock = threading.Lock()
_rate_events: dict[str, deque[float]] = defaultdict(deque)


def create_app(
    database_url: str | None = None,
    *,
    initialize_database: bool = True,
    vector_store: ChromaVectorStore | None = None,
    gemini: GeminiClient | None = None,
) -> FastAPI:
    engine = build_engine(database_url or settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if initialize_database:
            try:
                Base.metadata.create_all(bind=engine)
                with session_factory() as session:
                    seed_demo_data(session)
            except SQLAlchemyError as exc:
                logger.error("Database startup failed; check DATABASE_URL and MySQL availability")
                raise RuntimeError(
                    "Unable to initialize MySQL. Check DATABASE_URL, create the database, and retry."
                ) from exc
        yield
        engine.dispose()

    application = FastAPI(
        title="Bowl & Bloom Food Assistant",
        version="1.0.0",
        description="MySQL-backed restaurant ordering, document retrieval, and Gemini assistant.",
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.vector_store = vector_store or ChromaVectorStore()
    application.state.gemini = gemini or GeminiClient()

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        now = time.monotonic()
        window, limit = (60.0, 20) if request.url.path.startswith("/api/chat") else (3600.0, 8)
        limited_path = (
            request.url.path.startswith("/api/chat")
            or request.url.path == "/api/documents"
            or request.url.path == "/api/auth/signup"
        )
        if limited_path:
            client_ip = request.client.host if request.client else "unknown"
            key = f"{client_ip}:{request.url.path.split('/')[2]}"
            with _rate_lock:
                events = _rate_events[key]
                while events and events[0] <= now - window:
                    events.popleft()
                if len(events) >= limit:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "code": "RATE_LIMITED",
                            "message": "Request rate limit exceeded; try again shortly.",
                            "request_id": request_id,
                        },
                        headers={"X-Request-ID": request_id},
                    )
                events.append(now)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": getattr(request.state, "request_id", "unknown"),
            },
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": str(exc.detail),
                "request_id": getattr(request.state, "request_id", "unknown"),
            },
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "fields": fields,
                "request_id": getattr(request.state, "request_id", "unknown"),
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled request failure request_id=%s error_type=%s",
            request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            },
        )

    application.include_router(auth_router)
    application.include_router(menu_router)
    application.include_router(orders_router)
    application.include_router(documents_router)
    application.include_router(chat_router)

    @application.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    frontend = PROJECT_ROOT / "app" / "frontend"
    application.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(frontend / "index.html")

    return application


app = create_app()