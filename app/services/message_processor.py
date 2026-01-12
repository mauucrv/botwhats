"""
Message processor service with rate limiting and message grouping.
"""

import asyncio
import structlog
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import ConversacionChatwoot, EstadisticasBot, KeywordHumano
from app.services.chatwoot import chatwoot_service
from app.services.openai_service import openai_service
from app.services.redis_cache import redis_cache
from app.agent import get_salon_agent
from app.schemas import ChatwootWebhookPayload

logger = structlog.get_logger(__name__)

# Timezone
TZ = pytz.timezone(settings.calendar_timezone)


class MessageProcessor:
    """Service for processing incoming messages."""

    def __init__(self):
        """Initialize the message processor."""
        self.message_delay = settings.message_group_delay
        self.rate_limit_max = settings.rate_limit_max_messages
        self.rate_limit_window = settings.rate_limit_window_seconds
        self._processing_tasks: Dict[int, asyncio.Task] = {}

    async def process_webhook(self, payload: ChatwootWebhookPayload) -> Dict[str, Any]:
        """
        Process an incoming Chatwoot webhook.

        Args:
            payload: The webhook payload

        Returns:
            Processing result
        """
        event = payload.event

        if event == "message_created":
            return await self._handle_message_created(payload)
        elif event == "conversation_status_changed":
            return await self._handle_conversation_status_changed(payload)
        elif event == "conversation_created":
            return await self._handle_conversation_created(payload)
        else:
            logger.debug("Ignoring webhook event", event=event)
            return {"status": "ignored", "event": event}

    async def _handle_message_created(
        self, payload: ChatwootWebhookPayload
    ) -> Dict[str, Any]:
        """Handle a new message webhook."""
        # Skip outgoing messages and private notes
        if payload.message_type != "incoming":
            return {"status": "skipped", "reason": "not_incoming"}

        if payload.private:
            return {"status": "skipped", "reason": "private_message"}

        # Check if sender is an agent (human)
        if payload.sender and payload.sender.type == "user":
            # Human agent responded - pause the bot
            await self._pause_bot_for_conversation(
                payload.conversation.id,
                reason="Agente humano respondió",
                paused_by=payload.sender.name or "Agente",
            )
            return {"status": "skipped", "reason": "human_agent_message"}

        conversation = payload.conversation
        if not conversation:
            return {"status": "error", "reason": "no_conversation"}

        conversation_id = conversation.id
        contact = conversation.contact

        # Extract phone number
        phone_number = None
        if contact:
            phone_number = contact.phone_number or contact.identifier

        if not phone_number:
            # Try to extract from conversation meta
            meta = conversation.meta or {}
            sender_info = meta.get("sender", {})
            phone_number = sender_info.get("phone_number")

        if not phone_number:
            logger.warning("No phone number found", conversation_id=conversation_id)
            phone_number = f"unknown_{conversation_id}"

        # Get or create conversation record
        conv_record = await self._get_or_create_conversation(
            conversation_id=conversation_id,
            phone_number=phone_number,
            contact_name=contact.name if contact else None,
            contact_id=contact.id if contact else None,
        )

        # Check if bot is active for this conversation
        if not conv_record.bot_activo:
            logger.info(
                "Bot paused for conversation",
                conversation_id=conversation_id,
                reason=conv_record.motivo_pausa,
            )
            return {"status": "skipped", "reason": "bot_paused"}

        # Check rate limit
        is_allowed, msg_count = await redis_cache.check_rate_limit(
            phone_number, self.rate_limit_max, self.rate_limit_window
        )

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                phone=phone_number[-4:],
                count=msg_count,
            )
            await chatwoot_service.send_message(
                conversation_id,
                "Has enviado muchos mensajes. Por favor espera un momento antes de continuar.",
            )
            return {"status": "rate_limited", "count": msg_count}

        # Process message content
        message_content = await self._extract_message_content(payload)

        if not message_content:
            return {"status": "skipped", "reason": "no_content"}

        # Check for human keywords
        if await self._check_human_keywords(message_content):
            await self._pause_bot_for_conversation(
                conversation_id,
                reason="Cliente solicitó agente humano",
            )
            await chatwoot_service.send_message(
                conversation_id,
                "Entendido. Un agente humano te atenderá pronto. Por favor espera.",
            )
            return {"status": "transferred", "reason": "human_keyword"}

        # Add message to pending queue and schedule processing
        message_data = {
            "content": message_content,
            "timestamp": datetime.now(TZ).isoformat(),
            "message_id": payload.id,
        }

        await redis_cache.add_pending_message(
            conversation_id, message_data, ttl=60
        )

        # Schedule delayed processing
        await self._schedule_processing(
            conversation_id, phone_number, contact.name if contact else None
        )

        return {"status": "queued", "conversation_id": conversation_id}

    async def _schedule_processing(
        self,
        conversation_id: int,
        phone_number: str,
        client_name: Optional[str],
    ) -> None:
        """Schedule message processing after a delay."""
        # Cancel existing task if any
        if conversation_id in self._processing_tasks:
            task = self._processing_tasks[conversation_id]
            if not task.done():
                task.cancel()

        # Create new task
        task = asyncio.create_task(
            self._delayed_process(conversation_id, phone_number, client_name)
        )
        self._processing_tasks[conversation_id] = task

    async def _delayed_process(
        self,
        conversation_id: int,
        phone_number: str,
        client_name: Optional[str],
    ) -> None:
        """Process messages after a delay to group quick messages."""
        try:
            # Wait for message grouping delay
            await asyncio.sleep(self.message_delay)

            # Try to acquire processing lock
            if not await redis_cache.set_processing_lock(conversation_id):
                logger.debug("Processing lock not acquired", conversation_id=conversation_id)
                return

            try:
                # Get all pending messages
                pending = await redis_cache.get_pending_messages(conversation_id)
                if not pending:
                    return

                # Clear pending messages
                await redis_cache.clear_pending_messages(conversation_id)

                # Combine messages
                combined_message = " ".join([m["content"] for m in pending])

                # Get conversation context
                context = await redis_cache.get_conversation_context(conversation_id)

                # Process with AI agent
                start_time = datetime.now()
                agent = get_salon_agent()
                response = await agent.process_message(
                    message=combined_message,
                    chat_history=context,
                    client_phone=phone_number,
                    client_name=client_name,
                )
                processing_time = (datetime.now() - start_time).total_seconds() * 1000

                # Send response
                await chatwoot_service.send_message(conversation_id, response)

                # Update conversation context
                new_context = (context or []) + [
                    {"role": "user", "content": combined_message},
                    {"role": "assistant", "content": response},
                ]
                # Keep only last 20 messages
                new_context = new_context[-20:]
                await redis_cache.set_conversation_context(conversation_id, new_context)

                # Update statistics
                await self._update_statistics(
                    messages_received=len(pending),
                    messages_responded=1,
                    response_time_ms=processing_time,
                )

                logger.info(
                    "Messages processed",
                    conversation_id=conversation_id,
                    message_count=len(pending),
                    processing_time_ms=processing_time,
                )

            finally:
                await redis_cache.release_processing_lock(conversation_id)

        except asyncio.CancelledError:
            logger.debug("Processing cancelled", conversation_id=conversation_id)
        except Exception as e:
            logger.error(
                "Error processing messages",
                conversation_id=conversation_id,
                error=str(e),
            )
            await self._update_statistics(errores=1)

    async def _extract_message_content(
        self, payload: ChatwootWebhookPayload
    ) -> Optional[str]:
        """Extract and process message content from payload."""
        parts = []

        # Process text content
        if payload.content:
            parts.append(payload.content)

        # Process attachments
        if payload.attachments:
            for attachment in payload.attachments:
                if not attachment.data_url:
                    continue

                file_type = attachment.file_type or ""

                # Handle audio
                if file_type.startswith("audio") or attachment.extension in [
                    "ogg", "mp3", "wav", "m4a", "opus"
                ]:
                    audio_data = await chatwoot_service.download_attachment(
                        attachment.data_url
                    )
                    if audio_data:
                        transcription = await openai_service.transcribe_audio(
                            audio_data,
                            filename=f"audio.{attachment.extension or 'ogg'}",
                        )
                        if transcription:
                            parts.append(f"[Audio transcrito]: {transcription}")

                # Handle images
                elif file_type.startswith("image") or attachment.extension in [
                    "jpg", "jpeg", "png", "gif", "webp"
                ]:
                    image_data = await chatwoot_service.download_attachment(
                        attachment.data_url
                    )
                    if image_data:
                        description = await openai_service.describe_image(image_data)
                        if description:
                            parts.append(f"[Imagen adjunta]: {description}")

        return " ".join(parts) if parts else None

    async def _handle_conversation_status_changed(
        self, payload: ChatwootWebhookPayload
    ) -> Dict[str, Any]:
        """Handle conversation status change webhook."""
        conversation = payload.conversation
        if not conversation:
            return {"status": "error", "reason": "no_conversation"}

        new_status = payload.status or conversation.status

        # If conversation is resolved, reactivate bot
        if new_status == "resolved":
            await self._reactivate_bot_for_conversation(conversation.id)
            return {"status": "bot_reactivated", "conversation_id": conversation.id}

        return {"status": "ok", "new_status": new_status}

    async def _handle_conversation_created(
        self, payload: ChatwootWebhookPayload
    ) -> Dict[str, Any]:
        """Handle new conversation webhook."""
        conversation = payload.conversation
        if not conversation:
            return {"status": "error", "reason": "no_conversation"}

        contact = conversation.contact
        phone_number = None
        if contact:
            phone_number = contact.phone_number or contact.identifier

        if not phone_number:
            phone_number = f"unknown_{conversation.id}"

        # Create conversation record
        await self._get_or_create_conversation(
            conversation_id=conversation.id,
            phone_number=phone_number,
            contact_name=contact.name if contact else None,
            contact_id=contact.id if contact else None,
        )

        return {"status": "created", "conversation_id": conversation.id}

    async def _get_or_create_conversation(
        self,
        conversation_id: int,
        phone_number: str,
        contact_name: Optional[str] = None,
        contact_id: Optional[int] = None,
    ) -> ConversacionChatwoot:
        """Get or create a conversation record."""
        async with get_session_context() as session:
            result = await session.execute(
                select(ConversacionChatwoot).where(
                    ConversacionChatwoot.chatwoot_conversation_id == conversation_id
                )
            )
            conv = result.scalar_one_or_none()

            if conv:
                # Update last message timestamp
                conv.ultimo_mensaje_at = datetime.now(TZ)
                if contact_name and not conv.nombre_cliente:
                    conv.nombre_cliente = contact_name
                await session.commit()
                return conv

            # Create new record
            conv = ConversacionChatwoot(
                chatwoot_conversation_id=conversation_id,
                chatwoot_contact_id=contact_id,
                telefono_cliente=phone_number,
                nombre_cliente=contact_name,
                bot_activo=True,
                ultimo_mensaje_at=datetime.now(TZ),
            )
            session.add(conv)
            await session.commit()
            await session.refresh(conv)

            logger.info(
                "Conversation record created",
                conversation_id=conversation_id,
                phone=phone_number[-4:] if phone_number else None,
            )

            return conv

    async def _pause_bot_for_conversation(
        self,
        conversation_id: int,
        reason: str,
        paused_by: Optional[str] = None,
    ) -> None:
        """Pause the bot for a conversation."""
        async with get_session_context() as session:
            await session.execute(
                update(ConversacionChatwoot)
                .where(ConversacionChatwoot.chatwoot_conversation_id == conversation_id)
                .values(
                    bot_activo=False,
                    motivo_pausa=reason,
                    pausado_por=paused_by,
                    pausado_en=datetime.now(TZ),
                )
            )
            await session.commit()

        # Clear conversation context
        await redis_cache.clear_conversation_context(conversation_id)

        logger.info(
            "Bot paused",
            conversation_id=conversation_id,
            reason=reason,
        )

        # Update statistics
        await self._update_statistics(transferencias_humano=1)

    async def _reactivate_bot_for_conversation(self, conversation_id: int) -> None:
        """Reactivate the bot for a conversation."""
        async with get_session_context() as session:
            await session.execute(
                update(ConversacionChatwoot)
                .where(ConversacionChatwoot.chatwoot_conversation_id == conversation_id)
                .values(
                    bot_activo=True,
                    motivo_pausa=None,
                    pausado_por=None,
                    pausado_en=None,
                )
            )
            await session.commit()

        # Clear old conversation context
        await redis_cache.clear_conversation_context(conversation_id)

        logger.info("Bot reactivated", conversation_id=conversation_id)

    async def _check_human_keywords(self, message: str) -> bool:
        """Check if message contains keywords that trigger human handoff."""
        # Get keywords from cache or database
        keywords = await redis_cache.get_keywords()

        if keywords is None:
            async with get_session_context() as session:
                result = await session.execute(
                    select(KeywordHumano).where(KeywordHumano.activo == True)
                )
                keyword_records = result.scalars().all()
                keywords = [k.keyword.lower() for k in keyword_records]
                await redis_cache.set_keywords(keywords)

        # Check message against keywords
        message_lower = message.lower()
        for keyword in keywords:
            if keyword in message_lower:
                logger.info("Human keyword detected", keyword=keyword)
                return True

        return False

    async def _update_statistics(
        self,
        mensajes_recibidos: int = 0,
        mensajes_respondidos: int = 0,
        citas_creadas: int = 0,
        citas_modificadas: int = 0,
        citas_canceladas: int = 0,
        transferencias_humano: int = 0,
        errores: int = 0,
        response_time_ms: Optional[float] = None,
    ) -> None:
        """Update daily statistics."""
        try:
            async with get_session_context() as session:
                today = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)

                result = await session.execute(
                    select(EstadisticasBot).where(EstadisticasBot.fecha == today)
                )
                stats = result.scalar_one_or_none()

                if stats:
                    stats.mensajes_recibidos += mensajes_recibidos
                    stats.mensajes_respondidos += mensajes_respondidos
                    stats.citas_creadas += citas_creadas
                    stats.citas_modificadas += citas_modificadas
                    stats.citas_canceladas += citas_canceladas
                    stats.transferencias_humano += transferencias_humano
                    stats.errores += errores

                    if response_time_ms:
                        if stats.tiempo_respuesta_promedio_ms:
                            # Calculate running average
                            total = stats.mensajes_respondidos
                            stats.tiempo_respuesta_promedio_ms = (
                                (stats.tiempo_respuesta_promedio_ms * (total - 1) + response_time_ms)
                                / total
                            )
                        else:
                            stats.tiempo_respuesta_promedio_ms = response_time_ms
                else:
                    stats = EstadisticasBot(
                        fecha=today,
                        mensajes_recibidos=mensajes_recibidos,
                        mensajes_respondidos=mensajes_respondidos,
                        citas_creadas=citas_creadas,
                        citas_modificadas=citas_modificadas,
                        citas_canceladas=citas_canceladas,
                        transferencias_humano=transferencias_humano,
                        errores=errores,
                        tiempo_respuesta_promedio_ms=response_time_ms,
                    )
                    session.add(stats)

                await session.commit()

        except Exception as e:
            logger.error("Error updating statistics", error=str(e))


# Singleton instance
message_processor = MessageProcessor()
