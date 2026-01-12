"""
Structured logging configuration.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import Processor

from app.config import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up structlog with JSON output for production
    and colored console output for development.
    """
    # Determine if we're in development mode
    is_development = settings.app_env == "development" or settings.debug

    # Common processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if is_development:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.log_level.upper()),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging configured",
        level=settings.log_level,
        environment=settings.app_env,
    )


def get_request_context(request) -> Dict[str, Any]:
    """
    Extract context from a FastAPI request for logging.

    Args:
        request: The FastAPI request object

    Returns:
        Dictionary with request context
    """
    return {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
