import logging
import re
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

SENSITIVE_FIELDS = {"password", "token", "api_key", "authorization", "secret"}
_DEVICE_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_DEFAULT_LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "netpulse.jsonl"
_structlog_configured = False


def safe_device_id(device_id: str) -> str:
    return device_id if _DEVICE_ID_PATTERN.fullmatch(device_id) else "***"


def redact_sensitive_fields(logger, method_name, event_dict):
    for key in event_dict:
        if key.lower() in SENSITIVE_FIELDS:
            event_dict[key] = "***"
    return event_dict


def _safe_exception_fields(logger, method_name, event_dict):
    exc_info = event_dict.pop("exc_info", None)
    if not exc_info:
        return event_dict

    if exc_info is True:
        exc_info = sys.exc_info()
    elif isinstance(exc_info, BaseException):
        exc_info = (type(exc_info), exc_info, exc_info.__traceback__)

    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        exception_type, _, traceback_object = exc_info
        event_dict.setdefault("error_type", exception_type.__name__)
        event_dict["stack_trace"] = [
            {
                "file": frame.filename,
                "line": frame.lineno,
                "function": frame.name,
            }
            for frame in traceback.extract_tb(traceback_object)
        ]
    return event_dict


def configure_logging(log_file: str | Path | None = None) -> None:
    global _structlog_configured

    log_path = Path(log_file) if log_file is not None else _DEFAULT_LOG_FILE
    log_path = log_path.resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
        _safe_exception_fields,
        redact_sensitive_fields,
    ]

    application_logger = logging.getLogger("netpulse")
    application_logger.setLevel(logging.INFO)
    application_logger.propagate = False
    file_handlers = [
        handler
        for handler in application_logger.handlers
        if getattr(handler, "_netpulse_json_handler", False)
    ]
    matching_handler = next(
        (
            handler
            for handler in file_handlers
            if Path(handler.baseFilename).resolve() == log_path
        ),
        None,
    )
    for handler in file_handlers:
        if handler is not matching_handler:
            application_logger.removeHandler(handler)
            handler.close()

    if matching_handler is None:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(),
                foreign_pre_chain=shared_processors,
            )
        )
        handler._netpulse_json_handler = True
        application_logger.addHandler(handler)

    if not _structlog_configured:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        _structlog_configured = True