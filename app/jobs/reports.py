"""
Weekly statistics report job.
"""

import structlog
from datetime import datetime, timedelta

from sqlalchemy import select, func
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import Cita, EstadisticasBot
from app.services.chatwoot import chatwoot_service

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)


async def send_weekly_report() -> None:
    """
    Send weekly statistics report to the salon owner.

    This job runs once a week and sends a summary of:
    - Messages received and responded
    - Appointments created, completed, and cancelled
    - Revenue from completed appointments
    - Bot performance metrics
    """
    logger.info("Starting weekly report job")

    if not settings.owner_phone_number:
        logger.warning("Owner phone number not configured, skipping report")
        return

    try:
        now = datetime.now(TZ)
        week_start = (now - timedelta(days=7)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        async with get_session_context() as session:
            # Get statistics for the week
            result = await session.execute(
                select(EstadisticasBot)
                .where(EstadisticasBot.fecha >= week_start)
                .where(EstadisticasBot.fecha <= week_end)
            )
            stats_records = result.scalars().all()

            # Aggregate statistics
            total_mensajes_recibidos = sum(s.mensajes_recibidos for s in stats_records)
            total_mensajes_respondidos = sum(s.mensajes_respondidos for s in stats_records)
            total_citas_creadas = sum(s.citas_creadas for s in stats_records)
            total_citas_modificadas = sum(s.citas_modificadas for s in stats_records)
            total_citas_canceladas = sum(s.citas_canceladas for s in stats_records)
            total_transferencias = sum(s.transferencias_humano for s in stats_records)
            total_errores = sum(s.errores for s in stats_records)

            # Calculate average response time
            response_times = [
                s.tiempo_respuesta_promedio_ms
                for s in stats_records
                if s.tiempo_respuesta_promedio_ms
            ]
            avg_response_time = (
                sum(response_times) / len(response_times)
                if response_times
                else 0
            )

            # Get appointment statistics from the appointments table
            result = await session.execute(
                select(Cita)
                .where(Cita.inicio >= week_start)
                .where(Cita.inicio <= week_end)
            )
            appointments = result.scalars().all()

            completadas = [a for a in appointments if a.estado == "completada"]
            canceladas = [a for a in appointments if a.estado == "cancelada"]
            no_asistio = [a for a in appointments if a.estado == "no_asistio"]

            # Calculate revenue
            ingresos = sum(a.precio_total for a in completadas)

            # Get most popular services
            all_services = []
            for a in appointments:
                all_services.extend(a.servicios)

            service_counts = {}
            for service in all_services:
                service_counts[service] = service_counts.get(service, 0) + 1

            top_services = sorted(
                service_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]

        # Format report message
        fecha_inicio = week_start.strftime("%d/%m/%Y")
        fecha_fin = week_end.strftime("%d/%m/%Y")

        message = (
            f"📊 *Reporte Semanal - {settings.salon_name}*\n"
            f"Período: {fecha_inicio} - {fecha_fin}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*💬 Mensajes*\n"
            f"• Recibidos: {total_mensajes_recibidos}\n"
            f"• Respondidos: {total_mensajes_respondidos}\n"
            f"• Transferencias a humano: {total_transferencias}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*📅 Citas*\n"
            f"• Agendadas: {len(appointments)}\n"
            f"• Completadas: {len(completadas)}\n"
            f"• Canceladas: {len(canceladas)}\n"
            f"• No asistieron: {len(no_asistio)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*💰 Ingresos*\n"
            f"• Total estimado: ${ingresos:,.2f}\n\n"
        )

        if top_services:
            message += (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"*🌟 Servicios más solicitados*\n"
            )
            for service, count in top_services:
                message += f"• {service}: {count}\n"
            message += "\n"

        if avg_response_time > 0:
            message += (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"*⚡ Rendimiento del Bot*\n"
                f"• Tiempo de respuesta promedio: {avg_response_time:.0f}ms\n"
                f"• Errores: {total_errores}\n"
            )

        # Send report
        result = await chatwoot_service.send_message_to_phone(
            settings.owner_phone_number,
            message,
        )

        if result:
            logger.info(
                "Weekly report sent",
                messages=total_mensajes_recibidos,
                appointments=len(appointments),
                revenue=ingresos,
            )
        else:
            logger.error("Failed to send weekly report")

    except Exception as e:
        logger.error("Error in weekly report job", error=str(e))
