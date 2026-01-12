"""
Webhook endpoints for Chatwoot integration.
"""

import hashlib
import hmac
import structlog
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import ChatwootWebhookPayload
from app.services.message_processor import message_processor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify the webhook signature from Chatwoot.

    Args:
        payload: The raw request body
        signature: The signature from the X-Chatwoot-Signature header

    Returns:
        True if valid, False otherwise
    """
    if not settings.chatwoot_webhook_secret:
        # If no secret configured, skip verification
        return True

    expected_signature = hmac.new(
        settings.chatwoot_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@router.post("/chatwoot")
async def chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_chatwoot_signature: str = Header(None, alias="X-Chatwoot-Signature"),
) -> JSONResponse:
    """
    Handle incoming webhooks from Chatwoot.

    This endpoint receives all webhook events from Chatwoot including:
    - message_created: New message in a conversation
    - conversation_created: New conversation started
    - conversation_status_changed: Conversation status updated
    - conversation_updated: Conversation details updated

    The webhook is processed asynchronously in the background.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature if configured
        if settings.chatwoot_webhook_secret and x_chatwoot_signature:
            if not verify_webhook_signature(body, x_chatwoot_signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse payload
        try:
            payload_dict = await request.json()
            payload = ChatwootWebhookPayload(**payload_dict)
        except Exception as e:
            logger.error("Failed to parse webhook payload", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid payload")

        logger.info(
            "Webhook received",
            event=payload.event,
            message_type=payload.message_type,
            conversation_id=payload.conversation.id if payload.conversation else None,
        )

        # Process webhook in background
        background_tasks.add_task(process_webhook_background, payload)

        return JSONResponse(
            status_code=200,
            content={"status": "accepted", "event": payload.event},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error handling webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_webhook_background(payload: ChatwootWebhookPayload) -> None:
    """Process webhook in background."""
    try:
        result = await message_processor.process_webhook(payload)
        logger.info("Webhook processed", result=result)
    except Exception as e:
        logger.error("Error processing webhook in background", error=str(e))


@router.post("/chatwoot/test")
async def test_webhook(payload: Dict[str, Any]) -> JSONResponse:
    """
    Test endpoint for webhook payloads.
    Only available in debug mode.
    """
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    logger.info("Test webhook received", payload=payload)

    return JSONResponse(
        status_code=200,
        content={"status": "received", "payload": payload},
    )
