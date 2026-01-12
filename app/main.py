"""
Main FastAPI application for the Beauty Salon Chatbot.
"""

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_db, init_db
from app.api import health_router, webhooks_router
from app.jobs import init_scheduler, shutdown_scheduler
from app.services.redis_cache import redis_cache
from app.utils.logging import setup_logging
from app.utils.seed_data import seed_initial_data

# Setup logging first
setup_logging()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize database, Redis, scheduler, and seed data
    - Shutdown: Clean up resources
    """
    # Startup
    logger.info(
        "Starting application",
        app_name=settings.app_name,
        environment=settings.app_env,
    )

    try:
        # Initialize database
        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialized")

        # Test Redis connection
        logger.info("Testing Redis connection...")
        redis_ok = await redis_cache.ping()
        if redis_ok:
            logger.info("Redis connection successful")
        else:
            logger.warning("Redis connection failed - caching will be disabled")

        # Seed initial data
        await seed_initial_data()

        # Initialize scheduler
        logger.info("Initializing scheduler...")
        init_scheduler()
        logger.info("Scheduler initialized")

        logger.info(
            "Application started successfully",
            port=settings.port,
        )

        yield

    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise

    finally:
        # Shutdown
        logger.info("Shutting down application...")

        # Shutdown scheduler
        shutdown_scheduler()

        # Close Redis connection
        await redis_cache.close()

        # Close database connections
        await close_db()

        logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Beauty Salon Chatbot API",
    description="""
    WhatsApp chatbot for beauty salon appointment management.

    Features:
    - Receive and process messages from Chatwoot
    - AI-powered conversation using LangChain
    - Appointment scheduling via Google Calendar
    - Audio transcription and image description
    - Rate limiting and message grouping
    - Scheduled jobs for reminders, reports, and backups
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Configure CORS
allowed_origins = settings.allowed_origins.split(",") if settings.allowed_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(webhooks_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else "Disabled in production",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
