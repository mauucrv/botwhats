"""
Pydantic schemas for the beauty salon chatbot.
"""

from datetime import datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Chatwoot Webhook Schemas
# ============================================================


class ChatwootMessageType(str, Enum):
    """Chatwoot message types."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    ACTIVITY = "activity"
    TEMPLATE = "template"


class ChatwootEventType(str, Enum):
    """Chatwoot webhook event types."""

    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    CONVERSATION_CREATED = "conversation_created"
    CONVERSATION_STATUS_CHANGED = "conversation_status_changed"
    CONVERSATION_UPDATED = "conversation_updated"
    WEBWIDGET_TRIGGERED = "webwidget_triggered"


class ChatwootAttachment(BaseModel):
    """Chatwoot attachment schema."""

    id: Optional[int] = None
    message_id: Optional[int] = None
    file_type: Optional[str] = None
    account_id: Optional[int] = None
    extension: Optional[str] = None
    data_url: Optional[str] = None
    thumb_url: Optional[str] = None
    file_size: Optional[int] = None


class ChatwootSender(BaseModel):
    """Chatwoot sender schema."""

    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    type: Optional[str] = None  # 'contact' or 'user' (agent)
    avatar_url: Optional[str] = None


class ChatwootContact(BaseModel):
    """Chatwoot contact schema."""

    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    identifier: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


class ChatwootConversation(BaseModel):
    """Chatwoot conversation schema."""

    id: int
    account_id: Optional[int] = None
    inbox_id: Optional[int] = None
    status: Optional[str] = None  # 'open', 'resolved', 'pending', 'snoozed'
    assignee_id: Optional[int] = None
    team_id: Optional[int] = None
    contact: Optional[ChatwootContact] = None
    messages: Optional[List[Dict[str, Any]]] = None
    labels: Optional[List[str]] = None
    additional_attributes: Optional[Dict[str, Any]] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None


class ChatwootMessage(BaseModel):
    """Chatwoot message schema."""

    id: Optional[int] = None
    content: Optional[str] = None
    content_type: Optional[str] = None  # 'text', 'input_select', 'cards', etc.
    content_attributes: Optional[Dict[str, Any]] = None
    message_type: Optional[str] = None  # 'incoming', 'outgoing', 'activity'
    created_at: Optional[datetime] = None
    private: Optional[bool] = False
    sender: Optional[ChatwootSender] = None
    attachments: Optional[List[ChatwootAttachment]] = None
    conversation_id: Optional[int] = None
    account_id: Optional[int] = None
    inbox_id: Optional[int] = None


class ChatwootWebhookPayload(BaseModel):
    """Chatwoot webhook payload schema."""

    event: Optional[str] = None
    id: Optional[int] = None
    content: Optional[str] = None
    content_type: Optional[str] = None
    content_attributes: Optional[Dict[str, Any]] = None
    message_type: Optional[str] = None
    created_at: Optional[datetime] = None
    private: Optional[bool] = False
    sender: Optional[ChatwootSender] = None
    attachments: Optional[List[ChatwootAttachment]] = None
    conversation: Optional[ChatwootConversation] = None
    account: Optional[Dict[str, Any]] = None
    inbox: Optional[Dict[str, Any]] = None

    # For conversation events
    status: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None


# ============================================================
# Service Schemas
# ============================================================


class ServiceBase(BaseModel):
    """Base schema for beauty services."""

    servicio: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = None
    precio: float = Field(..., gt=0)
    duracion_minutos: int = Field(..., gt=0)
    estilistas_disponibles: Optional[List[str]] = None


class ServiceCreate(ServiceBase):
    """Schema for creating a service."""

    pass


class ServiceUpdate(BaseModel):
    """Schema for updating a service."""

    servicio: Optional[str] = Field(None, min_length=1, max_length=100)
    descripcion: Optional[str] = None
    precio: Optional[float] = Field(None, gt=0)
    duracion_minutos: Optional[int] = Field(None, gt=0)
    estilistas_disponibles: Optional[List[str]] = None
    activo: Optional[bool] = None


class ServiceResponse(ServiceBase):
    """Schema for service response."""

    id: int
    activo: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Stylist Schemas
# ============================================================


class StylistBase(BaseModel):
    """Base schema for stylists."""

    nombre: str = Field(..., min_length=1, max_length=100)
    telefono: Optional[str] = None
    email: Optional[str] = None
    especialidades: Optional[List[str]] = None


class StylistCreate(StylistBase):
    """Schema for creating a stylist."""

    pass


class StylistUpdate(BaseModel):
    """Schema for updating a stylist."""

    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    telefono: Optional[str] = None
    email: Optional[str] = None
    especialidades: Optional[List[str]] = None
    activo: Optional[bool] = None


class StylistScheduleBase(BaseModel):
    """Base schema for stylist schedule."""

    dia: str
    hora_inicio: time
    hora_fin: time


class StylistScheduleResponse(StylistScheduleBase):
    """Schema for stylist schedule response."""

    id: int
    estilista_id: int
    activo: bool

    class Config:
        from_attributes = True


class StylistResponse(StylistBase):
    """Schema for stylist response."""

    id: int
    activo: bool
    horarios: Optional[List[StylistScheduleResponse]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Appointment Schemas
# ============================================================


class AppointmentStatus(str, Enum):
    """Appointment status enum."""

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"
    NO_ASISTIO = "no_asistio"


class AppointmentBase(BaseModel):
    """Base schema for appointments."""

    nombre_cliente: str = Field(..., min_length=1, max_length=100)
    telefono_cliente: str = Field(..., min_length=1, max_length=20)
    inicio: datetime
    fin: datetime
    servicios: List[str]
    precio_total: float = Field(..., ge=0)
    estilista_id: Optional[int] = None
    notas: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    """Schema for creating an appointment."""

    @field_validator("inicio", "fin")
    @classmethod
    def validate_datetime(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware")
        return v

    @field_validator("fin")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info) -> datetime:
        if "inicio" in info.data and v <= info.data["inicio"]:
            raise ValueError("End time must be after start time")
        return v


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""

    nombre_cliente: Optional[str] = Field(None, min_length=1, max_length=100)
    telefono_cliente: Optional[str] = Field(None, min_length=1, max_length=20)
    inicio: Optional[datetime] = None
    fin: Optional[datetime] = None
    servicios: Optional[List[str]] = None
    precio_total: Optional[float] = Field(None, ge=0)
    estilista_id: Optional[int] = None
    estado: Optional[AppointmentStatus] = None
    notas: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    """Schema for appointment response."""

    id: int
    id_evento_google: Optional[str] = None
    estado: AppointmentStatus
    recordatorio_enviado: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Availability Schemas
# ============================================================


class AvailabilityCheck(BaseModel):
    """Schema for checking availability."""

    fecha: datetime
    duracion_minutos: int = Field(..., gt=0)
    estilista_id: Optional[int] = None


class TimeSlot(BaseModel):
    """Schema for an available time slot."""

    inicio: datetime
    fin: datetime


class AvailabilityResponse(BaseModel):
    """Schema for availability response."""

    disponible: bool
    slots_disponibles: List[TimeSlot] = []
    mensaje: Optional[str] = None


# ============================================================
# Salon Info Schemas
# ============================================================


class SalonInfoBase(BaseModel):
    """Base schema for salon information."""

    nombre_salon: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    horario: Optional[str] = None
    descripcion: Optional[str] = None
    redes_sociales: Optional[Dict[str, str]] = None
    politicas: Optional[str] = None


class SalonInfoResponse(SalonInfoBase):
    """Schema for salon info response."""

    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Statistics Schemas
# ============================================================


class DailyStatistics(BaseModel):
    """Schema for daily statistics."""

    fecha: datetime
    mensajes_recibidos: int = 0
    mensajes_respondidos: int = 0
    citas_creadas: int = 0
    citas_modificadas: int = 0
    citas_canceladas: int = 0
    transferencias_humano: int = 0
    errores: int = 0
    tiempo_respuesta_promedio_ms: Optional[float] = None


class WeeklyReport(BaseModel):
    """Schema for weekly report."""

    periodo_inicio: datetime
    periodo_fin: datetime
    total_mensajes: int
    total_citas_creadas: int
    total_citas_completadas: int
    total_citas_canceladas: int
    ingresos_estimados: float
    estadisticas_diarias: List[DailyStatistics]
