"""
LangChain tools for the beauty salon agent.
"""

import structlog
from datetime import datetime, timedelta
from typing import List, Optional

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import Cita, Estilista, HorarioEstilista, InformacionGeneral, ServicioBelleza
from app.services.google_calendar import google_calendar_service
from app.services.redis_cache import redis_cache

logger = structlog.get_logger(__name__)

# Timezone
TZ = pytz.timezone(settings.calendar_timezone)


# ============================================================
# Tool 1: List Services
# ============================================================


@tool
async def list_services() -> str:
    """
    Lista todos los servicios de belleza disponibles en el salón.
    Incluye nombre del servicio, precio, duración en minutos y estilistas que lo ofrecen.
    Usa esta herramienta cuando el cliente pregunte por servicios, precios o qué ofrecemos.
    """
    try:
        # Try cache first
        cached = await redis_cache.get_services()
        if cached:
            services = cached
        else:
            # Fetch from database
            async with get_session_context() as session:
                result = await session.execute(
                    select(ServicioBelleza).where(ServicioBelleza.activo == True)
                )
                services_db = result.scalars().all()
                services = [
                    {
                        "servicio": s.servicio,
                        "descripcion": s.descripcion,
                        "precio": s.precio,
                        "duracion_minutos": s.duracion_minutos,
                        "estilistas_disponibles": s.estilistas_disponibles or [],
                    }
                    for s in services_db
                ]
                # Cache the result
                await redis_cache.set_services(services)

        if not services:
            return "No hay servicios disponibles en este momento."

        # Format response
        lines = ["📋 **Servicios disponibles:**\n"]
        for s in services:
            line = f"• **{s['servicio']}**: ${s['precio']:.2f} ({s['duracion_minutos']} min)"
            if s.get("descripcion"):
                line += f"\n  _{s['descripcion']}_"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error listing services", error=str(e))
        return "Error al obtener la lista de servicios. Por favor intenta más tarde."


# ============================================================
# Tool 2: List Stylists
# ============================================================


@tool
async def list_stylists() -> str:
    """
    Lista todos los estilistas activos del salón.
    Incluye nombre, especialidades y horario de trabajo.
    Usa esta herramienta cuando el cliente pregunte por estilistas disponibles.
    """
    try:
        # Try cache first
        cached = await redis_cache.get_stylists()
        if cached:
            stylists = cached
        else:
            # Fetch from database
            async with get_session_context() as session:
                result = await session.execute(
                    select(Estilista)
                    .where(Estilista.activo == True)
                    .options(selectinload(Estilista.horarios))
                )
                stylists_db = result.scalars().all()
                stylists = []
                for st in stylists_db:
                    horarios = []
                    for h in st.horarios:
                        if h.activo:
                            horarios.append({
                                "dia": h.dia.value,
                                "hora_inicio": h.hora_inicio.strftime("%H:%M"),
                                "hora_fin": h.hora_fin.strftime("%H:%M"),
                            })
                    stylists.append({
                        "id": st.id,
                        "nombre": st.nombre,
                        "especialidades": st.especialidades or [],
                        "horarios": horarios,
                    })
                # Cache the result
                await redis_cache.set_stylists(stylists)

        if not stylists:
            return "No hay estilistas disponibles en este momento."

        # Format response
        lines = ["💇 **Nuestros estilistas:**\n"]
        for st in stylists:
            line = f"• **{st['nombre']}**"
            if st.get("especialidades"):
                line += f"\n  Especialidades: {', '.join(st['especialidades'])}"
            if st.get("horarios"):
                dias = [h["dia"].capitalize() for h in st["horarios"]]
                line += f"\n  Días: {', '.join(dias)}"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error listing stylists", error=str(e))
        return "Error al obtener la lista de estilistas. Por favor intenta más tarde."


# ============================================================
# Tool 3: List Salon Info
# ============================================================


@tool
async def list_info() -> str:
    """
    Obtiene la información general del salón.
    Incluye nombre, dirección, teléfono, horario de atención y políticas.
    Usa esta herramienta cuando el cliente pregunte dónde estamos, horarios, o información del salón.
    """
    try:
        # Try cache first
        cached = await redis_cache.get_info()
        if cached:
            info = cached
        else:
            # Fetch from database
            async with get_session_context() as session:
                result = await session.execute(select(InformacionGeneral).limit(1))
                info_db = result.scalar_one_or_none()

                if info_db:
                    info = {
                        "nombre_salon": info_db.nombre_salon,
                        "direccion": info_db.direccion,
                        "telefono": info_db.telefono,
                        "horario": info_db.horario,
                        "descripcion": info_db.descripcion,
                        "politicas": info_db.politicas,
                    }
                    await redis_cache.set_info(info)
                else:
                    # Use defaults from settings
                    info = {
                        "nombre_salon": settings.salon_name,
                        "direccion": settings.salon_address,
                        "telefono": settings.salon_phone,
                        "horario": settings.salon_hours,
                    }

        # Format response
        lines = [f"🏠 **{info.get('nombre_salon', 'Nuestro Salón')}**\n"]
        if info.get("descripcion"):
            lines.append(f"{info['descripcion']}\n")
        if info.get("direccion"):
            lines.append(f"📍 **Dirección:** {info['direccion']}")
        if info.get("telefono"):
            lines.append(f"📞 **Teléfono:** {info['telefono']}")
        if info.get("horario"):
            lines.append(f"🕐 **Horario:** {info['horario']}")
        if info.get("politicas"):
            lines.append(f"\n📋 **Políticas:** {info['politicas']}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting salon info", error=str(e))
        return "Error al obtener la información del salón. Por favor intenta más tarde."


# ============================================================
# Tool 4: Check Availability (FreeBusy API)
# ============================================================


@tool
async def check_availability(
    fecha: str,
    hora: str,
    duracion_minutos: int = 60,
) -> str:
    """
    Verifica si hay disponibilidad en una fecha y hora específica usando Google Calendar FreeBusy API.
    Si la hora exacta no está disponible, sugiere horarios alternativos.

    Args:
        fecha: Fecha en formato YYYY-MM-DD (ej: 2024-03-15)
        hora: Hora en formato HH:MM (ej: 14:30)
        duracion_minutos: Duración del servicio en minutos (default: 60)
    """
    try:
        # Parse date and time
        try:
            dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            dt = TZ.localize(dt)
        except ValueError:
            return "Formato de fecha/hora inválido. Usa fecha: YYYY-MM-DD y hora: HH:MM"

        # Check if date is in the past
        now = datetime.now(TZ)
        if dt < now:
            return "No puedo verificar disponibilidad para fechas pasadas."

        # Calculate end time
        end_dt = dt + timedelta(minutes=duracion_minutos)

        # Check availability
        result = await google_calendar_service.check_availability(dt, end_dt)

        if result.get("error"):
            return f"Error al verificar disponibilidad: {result['error']}"

        if result["available"]:
            return f"✅ ¡Hay disponibilidad! El horario {fecha} a las {hora} está libre para un servicio de {duracion_minutos} minutos."
        else:
            # Get alternative slots
            day_start = dt.replace(hour=9, minute=0)
            slots = await google_calendar_service.get_available_slots(
                day_start, duracion_minutos
            )

            if slots:
                alternatives = []
                for slot in slots[:5]:  # Show max 5 alternatives
                    slot_time = slot["start"].strftime("%H:%M")
                    alternatives.append(slot_time)

                return (
                    f"❌ El horario {fecha} a las {hora} no está disponible.\n\n"
                    f"Horarios disponibles para ese día:\n• " + "\n• ".join(alternatives)
                )
            else:
                return (
                    f"❌ El horario {fecha} a las {hora} no está disponible "
                    "y no encontré otros horarios libres para ese día."
                )

    except Exception as e:
        logger.error("Error checking availability", error=str(e))
        return "Error al verificar disponibilidad. Por favor intenta más tarde."


# ============================================================
# Tool 5: Check Stylist Availability
# ============================================================


@tool
async def check_stylist_availability(
    estilista_nombre: str,
    fecha: str,
    duracion_minutos: int = 60,
) -> str:
    """
    Verifica la disponibilidad de un estilista específico para una fecha.
    Muestra los horarios libres del estilista ese día.

    Args:
        estilista_nombre: Nombre del estilista
        fecha: Fecha en formato YYYY-MM-DD
        duracion_minutos: Duración del servicio en minutos
    """
    try:
        # Find stylist
        async with get_session_context() as session:
            result = await session.execute(
                select(Estilista)
                .where(Estilista.nombre.ilike(f"%{estilista_nombre}%"))
                .where(Estilista.activo == True)
                .options(selectinload(Estilista.horarios))
            )
            estilista = result.scalar_one_or_none()

            if not estilista:
                return f"No encontré un estilista con el nombre '{estilista_nombre}'."

            # Parse date
            try:
                dt = datetime.strptime(fecha, "%Y-%m-%d")
                dt = TZ.localize(dt)
            except ValueError:
                return "Formato de fecha inválido. Usa: YYYY-MM-DD"

            # Check if date is in the past
            now = datetime.now(TZ)
            if dt.date() < now.date():
                return "No puedo verificar disponibilidad para fechas pasadas."

            # Get day of week
            dias_semana = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
            dia = dias_semana[dt.weekday()]

            # Check if stylist works that day
            horario_dia = None
            for h in estilista.horarios:
                if h.activo and h.dia.value == dia:
                    horario_dia = h
                    break

            if not horario_dia:
                return f"{estilista.nombre} no trabaja los {dia}s."

            # Get available slots
            day_start = dt.replace(
                hour=horario_dia.hora_inicio.hour,
                minute=horario_dia.hora_inicio.minute,
            )
            day_end = dt.replace(
                hour=horario_dia.hora_fin.hour,
                minute=horario_dia.hora_fin.minute,
            )

            # For now, we check calendar availability
            # In a real scenario, you might have a separate calendar per stylist
            result = await google_calendar_service.get_available_slots(
                dt, duracion_minutos,
                start_hour=horario_dia.hora_inicio.hour,
                end_hour=horario_dia.hora_fin.hour,
            )

            if result:
                slots = [s["start"].strftime("%H:%M") for s in result[:8]]
                return (
                    f"📅 **Disponibilidad de {estilista.nombre} el {fecha}:**\n\n"
                    f"Horario de trabajo: {horario_dia.hora_inicio.strftime('%H:%M')} - {horario_dia.hora_fin.strftime('%H:%M')}\n\n"
                    f"Horarios disponibles:\n• " + "\n• ".join(slots)
                )
            else:
                return f"{estilista.nombre} no tiene horarios disponibles el {fecha}."

    except Exception as e:
        logger.error("Error checking stylist availability", error=str(e))
        return "Error al verificar disponibilidad del estilista."


# ============================================================
# Tool 6: Check Stylist Schedule
# ============================================================


@tool
async def check_stylist_schedule(estilista_nombre: str) -> str:
    """
    Obtiene el horario de trabajo semanal de un estilista.

    Args:
        estilista_nombre: Nombre del estilista
    """
    try:
        async with get_session_context() as session:
            result = await session.execute(
                select(Estilista)
                .where(Estilista.nombre.ilike(f"%{estilista_nombre}%"))
                .where(Estilista.activo == True)
                .options(selectinload(Estilista.horarios))
            )
            estilista = result.scalar_one_or_none()

            if not estilista:
                return f"No encontré un estilista con el nombre '{estilista_nombre}'."

            if not estilista.horarios:
                return f"{estilista.nombre} no tiene horario registrado."

            # Format schedule
            lines = [f"📅 **Horario de {estilista.nombre}:**\n"]

            dias_orden = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
            horarios_por_dia = {h.dia.value: h for h in estilista.horarios if h.activo}

            for dia in dias_orden:
                if dia in horarios_por_dia:
                    h = horarios_por_dia[dia]
                    lines.append(
                        f"• {dia.capitalize()}: {h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}"
                    )

            if len(lines) == 1:
                return f"{estilista.nombre} no tiene días de trabajo activos."

            return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting stylist schedule", error=str(e))
        return "Error al obtener el horario del estilista."


# ============================================================
# Tool 7: Check Stylist for Service
# ============================================================


@tool
async def check_stylist_for_service(servicio_nombre: str) -> str:
    """
    Encuentra qué estilistas pueden realizar un servicio específico.

    Args:
        servicio_nombre: Nombre del servicio
    """
    try:
        async with get_session_context() as session:
            # Find service
            result = await session.execute(
                select(ServicioBelleza)
                .where(ServicioBelleza.servicio.ilike(f"%{servicio_nombre}%"))
                .where(ServicioBelleza.activo == True)
            )
            servicio = result.scalar_one_or_none()

            if not servicio:
                return f"No encontré un servicio llamado '{servicio_nombre}'."

            estilistas_disponibles = servicio.estilistas_disponibles or []

            if not estilistas_disponibles:
                # If no specific stylists, all active stylists can do it
                result = await session.execute(
                    select(Estilista).where(Estilista.activo == True)
                )
                estilistas = result.scalars().all()
                nombres = [e.nombre for e in estilistas]
            else:
                nombres = estilistas_disponibles

            if not nombres:
                return f"No hay estilistas disponibles para {servicio.servicio}."

            return (
                f"💇 **Estilistas que realizan {servicio.servicio}:**\n\n"
                f"• " + "\n• ".join(nombres) + "\n\n"
                f"Precio: ${servicio.precio:.2f}\n"
                f"Duración: {servicio.duracion_minutos} minutos"
            )

    except Exception as e:
        logger.error("Error checking stylist for service", error=str(e))
        return "Error al buscar estilistas para el servicio."


# ============================================================
# Tool 8: Get Stylist Info
# ============================================================


@tool
async def get_stylist_info(estilista_nombre: str) -> str:
    """
    Obtiene información detallada de un estilista.

    Args:
        estilista_nombre: Nombre del estilista
    """
    try:
        async with get_session_context() as session:
            result = await session.execute(
                select(Estilista)
                .where(Estilista.nombre.ilike(f"%{estilista_nombre}%"))
                .where(Estilista.activo == True)
                .options(selectinload(Estilista.horarios))
            )
            estilista = result.scalar_one_or_none()

            if not estilista:
                return f"No encontré un estilista con el nombre '{estilista_nombre}'."

            lines = [f"💇 **{estilista.nombre}**\n"]

            if estilista.especialidades:
                lines.append(f"Especialidades: {', '.join(estilista.especialidades)}")

            if estilista.horarios:
                lines.append("\nHorario de trabajo:")
                for h in estilista.horarios:
                    if h.activo:
                        lines.append(
                            f"• {h.dia.value.capitalize()}: "
                            f"{h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}"
                        )

            return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting stylist info", error=str(e))
        return "Error al obtener información del estilista."


# ============================================================
# Tool 9: Create Booking
# ============================================================


@tool
async def create_booking(
    nombre_cliente: str,
    telefono_cliente: str,
    servicios: str,
    fecha: str,
    hora: str,
    estilista_nombre: Optional[str] = None,
    notas: Optional[str] = None,
) -> str:
    """
    Crea una nueva cita en el calendario y la base de datos.
    IMPORTANTE: Confirma todos los detalles con el cliente antes de crear la cita.

    Args:
        nombre_cliente: Nombre completo del cliente
        telefono_cliente: Teléfono del cliente
        servicios: Lista de servicios separados por coma (ej: "Corte, Tinte")
        fecha: Fecha en formato YYYY-MM-DD
        hora: Hora en formato HH:MM
        estilista_nombre: Nombre del estilista preferido (opcional)
        notas: Notas adicionales (opcional)
    """
    try:
        # Parse services
        servicios_lista = [s.strip() for s in servicios.split(",")]

        # Find services in database and calculate duration/price
        async with get_session_context() as session:
            total_duracion = 0
            total_precio = 0.0
            servicios_encontrados = []

            for servicio_nombre in servicios_lista:
                result = await session.execute(
                    select(ServicioBelleza)
                    .where(ServicioBelleza.servicio.ilike(f"%{servicio_nombre}%"))
                    .where(ServicioBelleza.activo == True)
                )
                servicio = result.scalar_one_or_none()

                if servicio:
                    total_duracion += servicio.duracion_minutos
                    total_precio += servicio.precio
                    servicios_encontrados.append(servicio.servicio)
                else:
                    return f"No encontré el servicio '{servicio_nombre}'. Por favor verifica el nombre."

            if not servicios_encontrados:
                return "No se encontraron servicios válidos."

            # Find stylist if specified
            estilista_id = None
            estilista_nombre_real = None
            if estilista_nombre:
                result = await session.execute(
                    select(Estilista)
                    .where(Estilista.nombre.ilike(f"%{estilista_nombre}%"))
                    .where(Estilista.activo == True)
                )
                estilista = result.scalar_one_or_none()
                if estilista:
                    estilista_id = estilista.id
                    estilista_nombre_real = estilista.nombre

            # Parse date and time
            try:
                dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
                dt = TZ.localize(dt)
            except ValueError:
                return "Formato de fecha/hora inválido. Usa fecha: YYYY-MM-DD y hora: HH:MM"

            # Check if date is in the past
            now = datetime.now(TZ)
            if dt < now:
                return "No puedo crear citas para fechas pasadas."

            end_dt = dt + timedelta(minutes=total_duracion)

            # Check availability
            availability = await google_calendar_service.check_availability(dt, end_dt)
            if not availability["available"]:
                return (
                    f"El horario {fecha} a las {hora} no está disponible. "
                    "Por favor elige otro horario."
                )

            # Create Google Calendar event
            summary = f"{', '.join(servicios_encontrados)} - {nombre_cliente}"
            description = (
                f"Número de teléfono: {telefono_cliente}\n"
                f"Servicios: {', '.join(servicios_encontrados)}\n"
                f"Precio Total: ${total_precio:.2f}\n"
                f"Estilista: {estilista_nombre_real or 'Por asignar'}"
            )
            if notas:
                description += f"\nNotas: {notas}"

            event = await google_calendar_service.create_event(
                summary=summary,
                description=description,
                start_time=dt,
                end_time=end_dt,
            )

            if not event:
                return "Error al crear la cita en el calendario. Por favor intenta más tarde."

            # Save to database
            cita = Cita(
                nombre_cliente=nombre_cliente,
                telefono_cliente=telefono_cliente,
                inicio=dt,
                fin=end_dt,
                id_evento_google=event.get("id"),
                servicios=servicios_encontrados,
                precio_total=total_precio,
                estilista_id=estilista_id,
                notas=notas,
            )
            session.add(cita)
            await session.commit()

            # Format confirmation
            return (
                f"✅ **¡Cita agendada exitosamente!**\n\n"
                f"📅 Fecha: {fecha}\n"
                f"🕐 Hora: {hora}\n"
                f"⏱️ Duración: {total_duracion} minutos\n"
                f"💇 Servicios: {', '.join(servicios_encontrados)}\n"
                f"💰 Precio total: ${total_precio:.2f}\n"
                + (f"👤 Estilista: {estilista_nombre_real}\n" if estilista_nombre_real else "")
                + f"\n¡Te esperamos!"
            )

    except Exception as e:
        logger.error("Error creating booking", error=str(e))
        return "Error al crear la cita. Por favor intenta más tarde."


# ============================================================
# Tool 10: Update Booking
# ============================================================


@tool
async def update_booking(
    telefono_cliente: str,
    nueva_fecha: Optional[str] = None,
    nueva_hora: Optional[str] = None,
    nuevos_servicios: Optional[str] = None,
    nuevo_estilista: Optional[str] = None,
) -> str:
    """
    Modifica una cita existente. Busca la próxima cita del cliente por teléfono.
    Solo modifica los campos proporcionados.

    Args:
        telefono_cliente: Teléfono del cliente para buscar la cita
        nueva_fecha: Nueva fecha en formato YYYY-MM-DD (opcional)
        nueva_hora: Nueva hora en formato HH:MM (opcional)
        nuevos_servicios: Nuevos servicios separados por coma (opcional)
        nuevo_estilista: Nuevo estilista (opcional)
    """
    try:
        async with get_session_context() as session:
            # Find the next appointment for this phone
            now = datetime.now(TZ)
            result = await session.execute(
                select(Cita)
                .where(Cita.telefono_cliente.contains(telefono_cliente[-10:]))
                .where(Cita.inicio > now)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .order_by(Cita.inicio)
            )
            cita = result.scalar_one_or_none()

            if not cita:
                return f"No encontré citas pendientes para el teléfono {telefono_cliente}."

            # Track changes
            cambios = []

            # Update date/time if provided
            if nueva_fecha or nueva_hora:
                fecha = nueva_fecha or cita.inicio.strftime("%Y-%m-%d")
                hora = nueva_hora or cita.inicio.strftime("%H:%M")

                try:
                    nuevo_inicio = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
                    nuevo_inicio = TZ.localize(nuevo_inicio)
                except ValueError:
                    return "Formato de fecha/hora inválido."

                if nuevo_inicio < now:
                    return "No puedo reagendar para una fecha pasada."

                # Calculate duration from current appointment
                duracion = (cita.fin - cita.inicio).total_seconds() / 60
                nuevo_fin = nuevo_inicio + timedelta(minutes=duracion)

                # Check availability
                availability = await google_calendar_service.check_availability(
                    nuevo_inicio, nuevo_fin
                )

                # Exclude current event from availability check
                if not availability["available"]:
                    return (
                        f"El nuevo horario {fecha} a las {hora} no está disponible. "
                        "Por favor elige otro horario."
                    )

                cita.inicio = nuevo_inicio
                cita.fin = nuevo_fin
                cambios.append(f"Fecha/hora: {fecha} a las {hora}")

            # Update services if provided
            if nuevos_servicios:
                servicios_lista = [s.strip() for s in nuevos_servicios.split(",")]
                total_duracion = 0
                total_precio = 0.0
                servicios_encontrados = []

                for servicio_nombre in servicios_lista:
                    result = await session.execute(
                        select(ServicioBelleza)
                        .where(ServicioBelleza.servicio.ilike(f"%{servicio_nombre}%"))
                        .where(ServicioBelleza.activo == True)
                    )
                    servicio = result.scalar_one_or_none()

                    if servicio:
                        total_duracion += servicio.duracion_minutos
                        total_precio += servicio.precio
                        servicios_encontrados.append(servicio.servicio)

                if servicios_encontrados:
                    cita.servicios = servicios_encontrados
                    cita.precio_total = total_precio
                    cita.fin = cita.inicio + timedelta(minutes=total_duracion)
                    cambios.append(f"Servicios: {', '.join(servicios_encontrados)}")

            # Update stylist if provided
            if nuevo_estilista:
                result = await session.execute(
                    select(Estilista)
                    .where(Estilista.nombre.ilike(f"%{nuevo_estilista}%"))
                    .where(Estilista.activo == True)
                )
                estilista = result.scalar_one_or_none()
                if estilista:
                    cita.estilista_id = estilista.id
                    cambios.append(f"Estilista: {estilista.nombre}")

            if not cambios:
                return "No se especificaron cambios para realizar."

            # Update Google Calendar event
            if cita.id_evento_google:
                summary = f"{', '.join(cita.servicios)} - {cita.nombre_cliente}"
                description = (
                    f"Número de teléfono: {cita.telefono_cliente}\n"
                    f"Servicios: {', '.join(cita.servicios)}\n"
                    f"Precio Total: ${cita.precio_total:.2f}"
                )

                await google_calendar_service.update_event(
                    event_id=cita.id_evento_google,
                    summary=summary,
                    description=description,
                    start_time=cita.inicio,
                    end_time=cita.fin,
                )

            await session.commit()

            return (
                f"✅ **Cita modificada exitosamente**\n\n"
                f"Cambios realizados:\n• " + "\n• ".join(cambios) + "\n\n"
                f"📅 Nueva fecha: {cita.inicio.strftime('%Y-%m-%d')}\n"
                f"🕐 Nueva hora: {cita.inicio.strftime('%H:%M')}\n"
                f"💰 Precio total: ${cita.precio_total:.2f}"
            )

    except Exception as e:
        logger.error("Error updating booking", error=str(e))
        return "Error al modificar la cita. Por favor intenta más tarde."


# ============================================================
# Tool 11: Cancel Booking
# ============================================================


@tool
async def cancel_booking(
    telefono_cliente: str,
    motivo: Optional[str] = None,
) -> str:
    """
    Cancela la próxima cita de un cliente. Busca por teléfono.
    IMPORTANTE: Confirma con el cliente antes de cancelar.

    Args:
        telefono_cliente: Teléfono del cliente
        motivo: Motivo de la cancelación (opcional)
    """
    try:
        async with get_session_context() as session:
            # Find the next appointment for this phone
            now = datetime.now(TZ)
            result = await session.execute(
                select(Cita)
                .where(Cita.telefono_cliente.contains(telefono_cliente[-10:]))
                .where(Cita.inicio > now)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .order_by(Cita.inicio)
            )
            cita = result.scalar_one_or_none()

            if not cita:
                return f"No encontré citas pendientes para el teléfono {telefono_cliente}."

            # Store appointment details for confirmation message
            fecha = cita.inicio.strftime("%Y-%m-%d")
            hora = cita.inicio.strftime("%H:%M")
            servicios = ", ".join(cita.servicios)

            # Delete from Google Calendar
            if cita.id_evento_google:
                await google_calendar_service.delete_event(cita.id_evento_google)

            # Update status in database
            cita.estado = "cancelada"
            if motivo:
                cita.notas = f"{cita.notas or ''}\nMotivo cancelación: {motivo}".strip()

            await session.commit()

            return (
                f"✅ **Cita cancelada**\n\n"
                f"📅 Fecha: {fecha}\n"
                f"🕐 Hora: {hora}\n"
                f"💇 Servicios: {servicios}\n"
                + (f"📝 Motivo: {motivo}\n" if motivo else "")
                + "\nEsperamos verte pronto."
            )

    except Exception as e:
        logger.error("Error canceling booking", error=str(e))
        return "Error al cancelar la cita. Por favor intenta más tarde."


# ============================================================
# Tool 12: Get Appointments
# ============================================================


@tool
async def get_appointments(telefono_cliente: str) -> str:
    """
    Consulta las citas de un cliente por su número de teléfono.
    Muestra citas pendientes y las últimas citas completadas.

    Args:
        telefono_cliente: Teléfono del cliente
    """
    try:
        async with get_session_context() as session:
            now = datetime.now(TZ)

            # Get upcoming appointments
            result = await session.execute(
                select(Cita)
                .where(Cita.telefono_cliente.contains(telefono_cliente[-10:]))
                .where(Cita.inicio > now)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .order_by(Cita.inicio)
            )
            proximas = result.scalars().all()

            # Get past appointments (last 3)
            result = await session.execute(
                select(Cita)
                .where(Cita.telefono_cliente.contains(telefono_cliente[-10:]))
                .where(Cita.inicio <= now)
                .order_by(Cita.inicio.desc())
                .limit(3)
            )
            pasadas = result.scalars().all()

            if not proximas and not pasadas:
                return f"No encontré citas para el teléfono {telefono_cliente}."

            lines = [f"📋 **Citas para {telefono_cliente}**\n"]

            if proximas:
                lines.append("**Próximas citas:**")
                for cita in proximas:
                    status_emoji = "✅" if cita.estado == "confirmada" else "🕐"
                    lines.append(
                        f"{status_emoji} {cita.inicio.strftime('%Y-%m-%d %H:%M')} - "
                        f"{', '.join(cita.servicios)} (${cita.precio_total:.2f})"
                    )
                lines.append("")

            if pasadas:
                lines.append("**Últimas citas:**")
                for cita in pasadas:
                    status = "✓" if cita.estado == "completada" else "✗"
                    lines.append(
                        f"{status} {cita.inicio.strftime('%Y-%m-%d')} - "
                        f"{', '.join(cita.servicios)}"
                    )

            return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting appointments", error=str(e))
        return "Error al consultar las citas. Por favor intenta más tarde."


# ============================================================
# Export all tools
# ============================================================


def get_salon_tools() -> List:
    """Get all salon tools for the agent."""
    return [
        list_services,
        list_stylists,
        list_info,
        check_availability,
        check_stylist_availability,
        check_stylist_schedule,
        check_stylist_for_service,
        get_stylist_info,
        create_booking,
        update_booking,
        cancel_booking,
        get_appointments,
    ]
