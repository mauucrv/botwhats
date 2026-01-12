"""
Health check endpoints.
"""

import structlog
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine
from app.services.redis_cache import redis_cache
import pytz

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

TZ = pytz.timezone(settings.calendar_timezone)


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.
    Returns 200 if the application is running.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "app": settings.app_name,
            "timestamp": datetime.now(TZ).isoformat(),
        },
    )


@router.get("/health/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness check endpoint.
    Verifies database and Redis connections.
    """
    checks: Dict[str, Any] = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        checks["database"] = str(e)

    # Check Redis
    try:
        checks["redis"] = await redis_cache.ping()
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        checks["redis"] = str(e)

    # Determine overall status
    all_healthy = all(v is True for v in checks.values())

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(TZ).isoformat(),
        },
    )


@router.get("/health/live")
async def liveness_check() -> JSONResponse:
    """
    Liveness check endpoint.
    Simple check that the application is responding.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "alive",
            "timestamp": datetime.now(TZ).isoformat(),
        },
    )


@router.get("/info")
async def app_info() -> JSONResponse:
    """
    Application information endpoint.
    """
    return JSONResponse(
        status_code=200,
        content={
            "app": settings.app_name,
            "version": "1.0.0",
            "environment": settings.app_env,
            "debug": settings.debug,
            "timezone": settings.calendar_timezone,
        },
    )
