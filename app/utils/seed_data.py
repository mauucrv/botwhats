"""
Seed initial data into the database.
"""

import structlog
from datetime import time

from sqlalchemy import select

from app.config import settings
from app.database import get_session_context
from app.models import (
    Estilista,
    HorarioEstilista,
    InformacionGeneral,
    KeywordHumano,
    ServicioBelleza,
    DiaSemana,
)

logger = structlog.get_logger(__name__)


async def seed_initial_data() -> None:
    """
    Seed initial data into the database.

    This function creates default data if the database is empty:
    - Sample services
    - Sample stylists with schedules
    - Salon information
    - Human handoff keywords
    """
    logger.info("Checking for initial data...")

    async with get_session_context() as session:
        # Check if data already exists
        result = await session.execute(select(ServicioBelleza).limit(1))
        if result.scalar_one_or_none():
            logger.info("Data already exists, skipping seed")
            return

        logger.info("Seeding initial data...")

        # Create services
        services = [
            ServicioBelleza(
                servicio="Corte de cabello",
                descripcion="Corte profesional para dama o caballero",
                precio=150.00,
                duracion_minutos=45,
                estilistas_disponibles=["María García", "Carlos López"],
            ),
            ServicioBelleza(
                servicio="Tinte",
                descripcion="Coloración completa con productos de alta calidad",
                precio=350.00,
                duracion_minutos=90,
                estilistas_disponibles=["María García"],
            ),
            ServicioBelleza(
                servicio="Mechas/Balayage",
                descripcion="Técnica de mechas o balayage para un look natural",
                precio=500.00,
                duracion_minutos=120,
                estilistas_disponibles=["María García"],
            ),
            ServicioBelleza(
                servicio="Peinado",
                descripcion="Peinado para evento especial",
                precio=200.00,
                duracion_minutos=60,
                estilistas_disponibles=["María García", "Ana Martínez"],
            ),
            ServicioBelleza(
                servicio="Manicure",
                descripcion="Manicure tradicional o con esmalte semipermanente",
                precio=120.00,
                duracion_minutos=45,
                estilistas_disponibles=["Ana Martínez"],
            ),
            ServicioBelleza(
                servicio="Pedicure",
                descripcion="Pedicure completo con hidratación",
                precio=150.00,
                duracion_minutos=60,
                estilistas_disponibles=["Ana Martínez"],
            ),
            ServicioBelleza(
                servicio="Tratamiento capilar",
                descripcion="Tratamiento de hidratación profunda",
                precio=250.00,
                duracion_minutos=45,
                estilistas_disponibles=["María García", "Carlos López"],
            ),
            ServicioBelleza(
                servicio="Barba",
                descripcion="Recorte y perfilado de barba",
                precio=80.00,
                duracion_minutos=30,
                estilistas_disponibles=["Carlos López"],
            ),
        ]

        for service in services:
            session.add(service)

        # Create stylists
        stylists_data = [
            {
                "nombre": "María García",
                "telefono": "+52 555 123 4567",
                "email": "maria@salon.com",
                "especialidades": ["Corte", "Color", "Peinados"],
                "horarios": [
                    (DiaSemana.LUNES, time(9, 0), time(18, 0)),
                    (DiaSemana.MARTES, time(9, 0), time(18, 0)),
                    (DiaSemana.MIERCOLES, time(9, 0), time(18, 0)),
                    (DiaSemana.JUEVES, time(9, 0), time(18, 0)),
                    (DiaSemana.VIERNES, time(9, 0), time(18, 0)),
                    (DiaSemana.SABADO, time(9, 0), time(15, 0)),
                ],
            },
            {
                "nombre": "Carlos López",
                "telefono": "+52 555 234 5678",
                "email": "carlos@salon.com",
                "especialidades": ["Corte", "Barba", "Tratamientos"],
                "horarios": [
                    (DiaSemana.LUNES, time(10, 0), time(19, 0)),
                    (DiaSemana.MARTES, time(10, 0), time(19, 0)),
                    (DiaSemana.MIERCOLES, time(10, 0), time(19, 0)),
                    (DiaSemana.JUEVES, time(10, 0), time(19, 0)),
                    (DiaSemana.VIERNES, time(10, 0), time(19, 0)),
                    (DiaSemana.SABADO, time(10, 0), time(16, 0)),
                ],
            },
            {
                "nombre": "Ana Martínez",
                "telefono": "+52 555 345 6789",
                "email": "ana@salon.com",
                "especialidades": ["Manicure", "Pedicure", "Peinados"],
                "horarios": [
                    (DiaSemana.LUNES, time(9, 0), time(17, 0)),
                    (DiaSemana.MARTES, time(9, 0), time(17, 0)),
                    (DiaSemana.MIERCOLES, time(9, 0), time(17, 0)),
                    (DiaSemana.JUEVES, time(9, 0), time(17, 0)),
                    (DiaSemana.VIERNES, time(9, 0), time(17, 0)),
                ],
            },
        ]

        for stylist_data in stylists_data:
            stylist = Estilista(
                nombre=stylist_data["nombre"],
                telefono=stylist_data["telefono"],
                email=stylist_data["email"],
                especialidades=stylist_data["especialidades"],
            )
            session.add(stylist)
            await session.flush()  # Get the stylist ID

            for dia, hora_inicio, hora_fin in stylist_data["horarios"]:
                horario = HorarioEstilista(
                    estilista_id=stylist.id,
                    dia=dia,
                    hora_inicio=hora_inicio,
                    hora_fin=hora_fin,
                )
                session.add(horario)

        # Create salon information
        salon_info = InformacionGeneral(
            nombre_salon=settings.salon_name,
            direccion=settings.salon_address or "Calle Principal #123, Colonia Centro, Ciudad",
            telefono=settings.salon_phone or "+52 555 000 0000",
            horario=settings.salon_hours or "Lunes a Viernes: 9:00 AM - 7:00 PM\nSábados: 9:00 AM - 4:00 PM\nDomingos: Cerrado",
            descripcion="Tu salón de belleza de confianza. Ofrecemos los mejores servicios de belleza con productos de alta calidad y estilistas profesionales.",
            politicas="• Se requiere reservación previa\n• Cancelaciones con mínimo 2 horas de anticipación\n• Se aceptan todas las formas de pago",
            redes_sociales={
                "instagram": "@salon_belleza",
                "facebook": "Salon de Belleza",
            },
        )
        session.add(salon_info)

        # Create human handoff keywords
        keywords = [
            "hablar con humano",
            "hablar con persona",
            "agente humano",
            "quiero hablar con alguien",
            "operador",
            "persona real",
            "atencion al cliente",
            "atención al cliente",
            "queja",
            "reclamación",
            "reclamacion",
            "problema urgente",
            "emergencia",
        ]

        for keyword in keywords:
            session.add(KeywordHumano(keyword=keyword))

        await session.commit()
        logger.info("Initial data seeded successfully")
