"""
SQLAlchemy database models for the beauty salon chatbot.
"""

from datetime import datetime, time
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EstadoCita(str, PyEnum):
    """Appointment status enum."""

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"
    NO_ASISTIO = "no_asistio"


class DiaSemana(str, PyEnum):
    """Day of week enum."""

    LUNES = "lunes"
    MARTES = "martes"
    MIERCOLES = "miercoles"
    JUEVES = "jueves"
    VIERNES = "viernes"
    SABADO = "sabado"
    DOMINGO = "domingo"


class ServicioBelleza(Base):
    """Beauty services table."""

    __tablename__ = "servicios_belleza"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    servicio: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    precio: Mapped[float] = mapped_column(Float, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    estilistas_disponibles: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ServicioBelleza(id={self.id}, servicio='{self.servicio}', precio={self.precio})>"


class Estilista(Base):
    """Stylists table."""

    __tablename__ = "estilistas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    especialidades: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    horarios: Mapped[List["HorarioEstilista"]] = relationship(
        "HorarioEstilista", back_populates="estilista", cascade="all, delete-orphan"
    )
    citas: Mapped[List["Cita"]] = relationship("Cita", back_populates="estilista")

    def __repr__(self) -> str:
        return f"<Estilista(id={self.id}, nombre='{self.nombre}')>"


class HorarioEstilista(Base):
    """Stylist schedules table."""

    __tablename__ = "horarios_estilistas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estilista_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("estilistas.id", ondelete="CASCADE"), nullable=False
    )
    dia: Mapped[DiaSemana] = mapped_column(Enum(DiaSemana), nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    estilista: Mapped["Estilista"] = relationship(
        "Estilista", back_populates="horarios"
    )

    def __repr__(self) -> str:
        return f"<HorarioEstilista(estilista_id={self.estilista_id}, dia='{self.dia}')>"


class Cita(Base):
    """Appointments table."""

    __tablename__ = "citas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_cliente: Mapped[str] = mapped_column(String(100), nullable=False)
    telefono_cliente: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_evento_google: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True
    )
    servicios: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    precio_total: Mapped[float] = mapped_column(Float, nullable=False)
    estilista_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("estilistas.id", ondelete="SET NULL"), nullable=True
    )
    estado: Mapped[EstadoCita] = mapped_column(
        Enum(EstadoCita), default=EstadoCita.PENDIENTE
    )
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recordatorio_enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    estilista: Mapped[Optional["Estilista"]] = relationship(
        "Estilista", back_populates="citas"
    )

    def __repr__(self) -> str:
        return f"<Cita(id={self.id}, cliente='{self.nombre_cliente}', inicio='{self.inicio}')>"


class InformacionGeneral(Base):
    """General salon information table."""

    __tablename__ = "informacion_general"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_salon: Mapped[str] = mapped_column(String(200), nullable=False)
    direccion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    horario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    redes_sociales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    politicas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<InformacionGeneral(nombre_salon='{self.nombre_salon}')>"


class ConversacionChatwoot(Base):
    """Chatwoot conversations tracking table."""

    __tablename__ = "conversaciones_chatwoot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatwoot_conversation_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True
    )
    chatwoot_contact_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    telefono_cliente: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    nombre_cliente: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bot_activo: Mapped[bool] = mapped_column(Boolean, default=True)
    motivo_pausa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pausado_por: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pausado_en: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_mensaje_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mensajes_pendientes: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    contexto_conversacion: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ConversacionChatwoot(id={self.chatwoot_conversation_id}, telefono='{self.telefono_cliente}')>"


class KeywordHumano(Base):
    """Keywords that trigger human agent handoff."""

    __tablename__ = "keywords_humano"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<KeywordHumano(keyword='{self.keyword}')>"


class EstadisticasBot(Base):
    """Bot statistics for reporting."""

    __tablename__ = "estadisticas_bot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    mensajes_recibidos: Mapped[int] = mapped_column(Integer, default=0)
    mensajes_respondidos: Mapped[int] = mapped_column(Integer, default=0)
    citas_creadas: Mapped[int] = mapped_column(Integer, default=0)
    citas_modificadas: Mapped[int] = mapped_column(Integer, default=0)
    citas_canceladas: Mapped[int] = mapped_column(Integer, default=0)
    transferencias_humano: Mapped[int] = mapped_column(Integer, default=0)
    errores: Mapped[int] = mapped_column(Integer, default=0)
    tiempo_respuesta_promedio_ms: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<EstadisticasBot(fecha='{self.fecha}')>"
