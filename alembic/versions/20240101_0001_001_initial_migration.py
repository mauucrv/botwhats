"""Initial migration - Create all tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    estado_cita_enum = sa.Enum(
        "pendiente",
        "confirmada",
        "en_progreso",
        "completada",
        "cancelada",
        "no_asistio",
        name="estadocita",
    )
    dia_semana_enum = sa.Enum(
        "lunes",
        "martes",
        "miercoles",
        "jueves",
        "viernes",
        "sabado",
        "domingo",
        name="diasemana",
    )

    # Create servicios_belleza table
    op.create_table(
        "servicios_belleza",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("servicio", sa.String(length=100), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("precio", sa.Float(), nullable=False),
        sa.Column("duracion_minutos", sa.Integer(), nullable=False),
        sa.Column("estilistas_disponibles", sa.JSON(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=True, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("servicio"),
    )

    # Create estilistas table
    op.create_table(
        "estilistas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("especialidades", sa.JSON(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=True, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create horarios_estilistas table
    op.create_table(
        "horarios_estilistas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("estilista_id", sa.Integer(), nullable=False),
        sa.Column("dia", dia_semana_enum, nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=True, default=True),
        sa.ForeignKeyConstraint(
            ["estilista_id"], ["estilistas.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create citas table
    op.create_table(
        "citas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre_cliente", sa.String(length=100), nullable=False),
        sa.Column("telefono_cliente", sa.String(length=20), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id_evento_google", sa.String(length=255), nullable=True),
        sa.Column("servicios", sa.JSON(), nullable=False),
        sa.Column("precio_total", sa.Float(), nullable=False),
        sa.Column("estilista_id", sa.Integer(), nullable=True),
        sa.Column("estado", estado_cita_enum, nullable=True, default="pendiente"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("recordatorio_enviado", sa.Boolean(), nullable=True, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["estilista_id"], ["estilistas.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id_evento_google"),
    )
    op.create_index(
        op.f("ix_citas_telefono_cliente"), "citas", ["telefono_cliente"], unique=False
    )

    # Create informacion_general table
    op.create_table(
        "informacion_general",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre_salon", sa.String(length=200), nullable=False),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("telefono", sa.String(length=50), nullable=True),
        sa.Column("horario", sa.Text(), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("redes_sociales", sa.JSON(), nullable=True),
        sa.Column("politicas", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create conversaciones_chatwoot table
    op.create_table(
        "conversaciones_chatwoot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chatwoot_conversation_id", sa.Integer(), nullable=False),
        sa.Column("chatwoot_contact_id", sa.Integer(), nullable=True),
        sa.Column("telefono_cliente", sa.String(length=20), nullable=False),
        sa.Column("nombre_cliente", sa.String(length=100), nullable=True),
        sa.Column("bot_activo", sa.Boolean(), nullable=True, default=True),
        sa.Column("motivo_pausa", sa.String(length=255), nullable=True),
        sa.Column("pausado_por", sa.String(length=100), nullable=True),
        sa.Column("pausado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_mensaje_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mensajes_pendientes", sa.JSON(), nullable=True),
        sa.Column("contexto_conversacion", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chatwoot_conversation_id"),
    )
    op.create_index(
        op.f("ix_conversaciones_chatwoot_chatwoot_conversation_id"),
        "conversaciones_chatwoot",
        ["chatwoot_conversation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_conversaciones_chatwoot_telefono_cliente"),
        "conversaciones_chatwoot",
        ["telefono_cliente"],
        unique=False,
    )

    # Create keywords_humano table
    op.create_table(
        "keywords_humano",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keyword", sa.String(length=100), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=True, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keyword"),
    )

    # Create estadisticas_bot table
    op.create_table(
        "estadisticas_bot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mensajes_recibidos", sa.Integer(), nullable=True, default=0),
        sa.Column("mensajes_respondidos", sa.Integer(), nullable=True, default=0),
        sa.Column("citas_creadas", sa.Integer(), nullable=True, default=0),
        sa.Column("citas_modificadas", sa.Integer(), nullable=True, default=0),
        sa.Column("citas_canceladas", sa.Integer(), nullable=True, default=0),
        sa.Column("transferencias_humano", sa.Integer(), nullable=True, default=0),
        sa.Column("errores", sa.Integer(), nullable=True, default=0),
        sa.Column("tiempo_respuesta_promedio_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_estadisticas_bot_fecha"),
        "estadisticas_bot",
        ["fecha"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_estadisticas_bot_fecha"), table_name="estadisticas_bot")
    op.drop_table("estadisticas_bot")
    op.drop_table("keywords_humano")
    op.drop_index(
        op.f("ix_conversaciones_chatwoot_telefono_cliente"),
        table_name="conversaciones_chatwoot",
    )
    op.drop_index(
        op.f("ix_conversaciones_chatwoot_chatwoot_conversation_id"),
        table_name="conversaciones_chatwoot",
    )
    op.drop_table("conversaciones_chatwoot")
    op.drop_table("informacion_general")
    op.drop_index(op.f("ix_citas_telefono_cliente"), table_name="citas")
    op.drop_table("citas")
    op.drop_table("horarios_estilistas")
    op.drop_table("estilistas")
    op.drop_table("servicios_belleza")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS estadocita")
    op.execute("DROP TYPE IF EXISTS diasemana")
