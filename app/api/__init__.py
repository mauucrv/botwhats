"""
API endpoints module.
"""

from app.api.webhooks import router as webhooks_router
from app.api.health import router as health_router

__all__ = ["webhooks_router", "health_router"]
