# 💇 Beauty Salon WhatsApp Chatbot

Sistema completo de chatbot de WhatsApp para salón de belleza. Conecta Chatwoot con un agente de IA (LangChain + GPT-4o-mini) para gestionar citas automáticamente usando Google Calendar.

## ✨ Características

### Comunicación
- 📱 Recibe mensajes de Chatwoot via webhook (texto, audio, imágenes)
- 🎤 Transcripción de audios con OpenAI Whisper
- 🖼️ Descripción de imágenes con GPT-4o Vision
- 💬 Respuestas inteligentes con LangChain + GPT-4o-mini

### Gestión de Citas
- 📅 Verificar disponibilidad en Google Calendar (FreeBusy API)
- ✅ Crear, modificar y cancelar citas
- 🔍 Consultar citas de un cliente por teléfono
- 👩‍💼 Información de servicios, estilistas y horarios

### Control del Bot
- 🤖 Pausa automática cuando un agente humano responde
- 🔄 Reactivación automática cuando la conversación se marca como resuelta
- 🚦 Rate limiting por teléfono (30 mensajes/hora)
- ⏱️ Agrupación de mensajes rápidos (espera 3 segundos)

### Jobs Programados
- 📊 Reporte semanal de estadísticas al dueño
- 📢 Recordatorios diarios de citas para el día siguiente
- 💾 Backup diario de PostgreSQL a Google Drive
- 🔄 Sincronización de eventos de Google Calendar

### Cache y Rendimiento
- ⚡ Cache Redis para servicios, estilistas e información del salón
- 🔒 Rate limiting eficiente con Redis
- 📝 Logging estructurado con structlog

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Framework | FastAPI |
| AI/ML | LangChain + OpenAI GPT-4o-mini |
| Base de datos | PostgreSQL 15 + SQLAlchemy 2.0 |
| Migraciones | Alembic |
| Cache | Redis 7 |
| Jobs | APScheduler |
| Validación | Pydantic v2 |
| HTTP Client | httpx |
| Google APIs | google-api-python-client |
| Contenedores | Docker + docker-compose |

## 📁 Estructura del Proyecto

```
botwhats/
├── alembic/                 # Migraciones de base de datos
│   ├── versions/
│   └── env.py
├── app/
│   ├── api/                 # Endpoints API
│   │   ├── health.py
│   │   └── webhooks.py
│   ├── agent/               # Agente IA
│   │   ├── agent.py
│   │   └── tools.py         # 12 herramientas LangChain
│   ├── jobs/                # Jobs programados
│   │   ├── scheduler.py
│   │   ├── reminders.py
│   │   ├── reports.py
│   │   ├── backup.py
│   │   └── sync_calendar.py
│   ├── models/              # Modelos SQLAlchemy
│   ├── schemas/             # Schemas Pydantic
│   ├── services/            # Servicios
│   │   ├── chatwoot.py
│   │   ├── google_calendar.py
│   │   ├── openai_service.py
│   │   ├── redis_cache.py
│   │   └── message_processor.py
│   ├── utils/               # Utilidades
│   ├── config.py
│   ├── database.py
│   └── main.py
├── credentials/             # Credenciales Google (no incluir en git)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── .env.example
```

## 🚀 Instalación y Configuración

### Prerrequisitos

- Docker y Docker Compose
- Cuenta de OpenAI con API key
- Instancia de Chatwoot configurada
- Proyecto de Google Cloud con Calendar API habilitada
- Cuenta de servicio de Google con acceso al calendario

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd botwhats
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Chatwoot
CHATWOOT_BASE_URL=https://your-chatwoot.com
CHATWOOT_API_TOKEN=your-token
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_INBOX_ID=1

# Google Calendar
GOOGLE_CALENDAR_ID=your-calendar@group.calendar.google.com
GOOGLE_DRIVE_FOLDER_ID=folder-id-for-backups

# Teléfono del dueño (para reportes)
OWNER_PHONE_NUMBER=521234567890

# Base de datos
POSTGRES_PASSWORD=your-secure-password
```

### 3. Configurar credenciales de Google

1. Crea un proyecto en Google Cloud Console
2. Habilita Calendar API y Drive API
3. Crea una cuenta de servicio
4. Descarga el archivo JSON de credenciales
5. Colócalo en `credentials/google_service_account.json`
6. Comparte el calendario con la cuenta de servicio

### 4. Iniciar con Docker Compose

```bash
docker-compose up -d
```

### 5. Ejecutar migraciones

```bash
docker-compose exec app alembic upgrade head
```

### 6. Configurar webhook en Chatwoot

En la configuración de tu inbox de Chatwoot, agrega el webhook:

```
URL: https://your-domain.com/api/webhooks/chatwoot
Events: message_created, conversation_status_changed
```

## 🔧 Herramientas del Agente IA

El agente tiene acceso a 12 herramientas especializadas:

| # | Herramienta | Descripción |
|---|-------------|-------------|
| 1 | `list_services` | Lista todos los servicios disponibles con precios |
| 2 | `list_stylists` | Lista los estilistas activos y sus especialidades |
| 3 | `list_info` | Información del salón (dirección, horario, etc.) |
| 4 | `check_availability` | Verifica disponibilidad usando FreeBusy API |
| 5 | `check_stylist_availability` | Disponibilidad de un estilista específico |
| 6 | `check_stylist_schedule` | Horario semanal de un estilista |
| 7 | `check_stylist_for_service` | Qué estilistas realizan un servicio |
| 8 | `get_stylist_info` | Información detallada de un estilista |
| 9 | `create_booking` | Crear una nueva cita |
| 10 | `update_booking` | Modificar una cita existente |
| 11 | `cancel_booking` | Cancelar una cita |
| 12 | `get_appointments` | Consultar citas de un cliente |

## 📊 Base de Datos

### Tablas principales

```sql
-- Servicios de belleza
servicios_belleza (servicio, precio, duracion_minutos, estilistas_disponibles)

-- Estilistas
estilistas (nombre, telefono, email, especialidades, activo)

-- Horarios de estilistas
horarios_estilistas (estilista_id, dia, hora_inicio, hora_fin)

-- Citas
citas (nombre, telefono, inicio, fin, id_evento, servicios, precio_total, estado)

-- Información del salón
informacion_general (nombre_salon, direccion, telefono, horario)

-- Conversaciones de Chatwoot
conversaciones_chatwoot (chatwoot_conversation_id, telefono, bot_activo, motivo_pausa)

-- Keywords para transferir a humano
keywords_humano (keyword, activo)

-- Estadísticas del bot
estadisticas_bot (fecha, mensajes_recibidos, citas_creadas, ...)
```

## 📅 Formato de Eventos en Google Calendar

Los eventos se crean con el siguiente formato:

```
Summary: "Corte, Tinte - María López"
Description:
  Número de teléfono: +521234567890
  Servicios: Corte, Tinte
  Precio Total: $500.00
  Estilista: Ana García
```

## 🔐 Seguridad

- Rate limiting por teléfono (configurable)
- Verificación de firma de webhooks (opcional)
- Usuario no-root en Docker
- Variables de entorno para secretos
- Logs sin datos sensibles

## 📈 Monitoreo

### Endpoints de salud

```bash
# Básico
GET /health

# Listo (verifica DB y Redis)
GET /health/ready

# Vivo
GET /health/live

# Información de la app
GET /info
```

### Logs

Los logs están estructurados en formato JSON (producción) o colorizado (desarrollo):

```json
{
  "event": "Message processed",
  "conversation_id": 123,
  "processing_time_ms": 450,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🛡️ Variables de Entorno

Ver `.env.example` para la lista completa. Variables críticas:

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `OPENAI_API_KEY` | API key de OpenAI | ✅ |
| `CHATWOOT_BASE_URL` | URL de Chatwoot | ✅ |
| `CHATWOOT_API_TOKEN` | Token de API de Chatwoot | ✅ |
| `GOOGLE_CALENDAR_ID` | ID del calendario | ✅ |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | ✅ |
| `OWNER_PHONE_NUMBER` | Teléfono para reportes | ⚠️ |

## 🔄 Jobs Programados

| Job | Horario Default | Descripción |
|-----|-----------------|-------------|
| Recordatorios | 18:00 diario | Envía recordatorios de citas de mañana |
| Reporte semanal | Lunes 9:00 | Estadísticas de la semana al dueño |
| Backup | 03:00 diario | Backup de DB a Google Drive |
| Sync calendario | Cada 15 min | Sincroniza eventos con la DB |

## 🧪 Desarrollo Local

### Sin Docker

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
uvicorn app.main:app --reload
```

### Con Docker (desarrollo)

```bash
# Construir y ejecutar
docker-compose up --build

# Ver logs
docker-compose logs -f app

# Ejecutar migraciones
docker-compose exec app alembic upgrade head

# Crear nueva migración
docker-compose exec app alembic revision --autogenerate -m "description"
```

## 📝 Licencia

MIT License

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

## 📞 Soporte

Para reportar bugs o solicitar funcionalidades, abre un issue en el repositorio.
