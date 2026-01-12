"""
Appointment reminder job.
"""

import structlog
from datetime import datetime, timedelta

from sqlalchemy import select, update
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import Cita
from app.services.chatwoot import chatwoot_service

logger = structlog.get_logger(__name__)

TZ = pytz.timezone(settings.calendar_timezone)


async def send_appointment_reminders() -> None:
    """
    Send reminders for appointments scheduled for tomorrow.

    This job runs daily and sends WhatsApp messages to clients
    with appointments scheduled for the next day.
    """
    logger.info("Starting appointment reminders job")

    try:
        now = datetime.now(TZ)
        tomorrow_start = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tomorrow_end = tomorrow_start + timedelta(days=1)

        async with get_session_context() as session:
            # Get tomorrow's appointments that haven't had a reminder sent
            result = await session.execute(
                select(Cita)
                .where(Cita.inicio >= tomorrow_start)
                .where(Cita.inicio < tomorrow_end)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .where(Cita.recordatorio_enviado == False)
            )
            appointments = result.scalars().all()

            if not appointments:
                logger.info("No appointments to remind")
                return

            sent_count = 0
            failed_count = 0

            for appointment in appointments:
                try:
                    # Format reminder message
                    hora = appointment.inicio.strftime("%H:%M")
                    servicios = ", ".join(appointment.servicios)

                    message = (
                        f"📅 *Recordatorio de cita*\n\n"
                        f"Hola {appointment.nombre_cliente}!\n\n"
                        f"Te recordamos que tienes una cita mañana:\n\n"
                        f"🕐 Hora: {hora}\n"
                        f"💇 Servicios: {servicios}\n"
                        f"💰 Total: ${appointment.precio_total:.2f}\n\n"
                        f"¡Te esperamos en {settings.salon_name}!\n\n"
                        f"Si necesitas cancelar o modificar tu cita, "
                        f"responde a este mensaje."
                    )

                    # Send reminder via Chatwoot
                    result = await chatwoot_service.send_message_to_phone(
                        appointment.telefono_cliente,
                        message,
                    )

                    if result:
                        # Mark reminder as sent
                        appointment.recordatorio_enviado = True
                        sent_count += 1
                        logger.info(
                            "Reminder sent",
                            appointment_id=appointment.id,
                            phone=appointment.telefono_cliente[-4:],
                        )
                    else:
                        failed_count += 1
                        logger.warning(
                            "Failed to send reminder",
                            appointment_id=appointment.id,
                        )

                except Exception as e:
                    failed_count += 1
                    logger.error(
                        "Error sending reminder",
                        appointment_id=appointment.id,
                        error=str(e),
                    )

            await session.commit()

            logger.info(
                "Appointment reminders job completed",
                total=len(appointments),
                sent=sent_count,
                failed=failed_count,
            )

    except Exception as e:
        logger.error("Error in appointment reminders job", error=str(e))
