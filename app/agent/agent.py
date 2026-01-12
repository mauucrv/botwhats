"""
LangChain agent for the beauty salon chatbot.
"""

import structlog
from datetime import datetime
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
import pytz

from app.config import settings
from app.agent.tools import get_salon_tools

logger = structlog.get_logger(__name__)

# Timezone
TZ = pytz.timezone(settings.calendar_timezone)

# System prompt for the salon agent
SYSTEM_PROMPT = """Eres el asistente virtual de {salon_name}, un salón de belleza.
Tu trabajo es ayudar a los clientes de manera amable y profesional.

INFORMACIÓN IMPORTANTE:
- Fecha y hora actual: {current_datetime}
- Zona horaria: {timezone}

TUS RESPONSABILIDADES:
1. Responder preguntas sobre servicios, precios y horarios
2. Ayudar a agendar, modificar o cancelar citas
3. Proporcionar información sobre los estilistas
4. Dar información general del salón

REGLAS IMPORTANTES:
- Siempre sé amable y profesional
- Confirma todos los detalles antes de crear o modificar una cita
- Si el cliente quiere una cita, necesitas: nombre, teléfono, servicio(s), fecha y hora
- Si no tienes el teléfono del cliente, pregúntalo antes de buscar o crear citas
- Sugiere horarios alternativos si el solicitado no está disponible
- No inventes información - usa las herramientas para obtener datos reales
- Responde siempre en español
- Mantén las respuestas concisas pero completas
- Si algo no está claro, pregunta para aclarar

FLUJO DE CONVERSACIÓN PARA CITAS:
1. El cliente expresa interés en una cita
2. Pregunta qué servicio(s) desea
3. Muestra los servicios disponibles si es necesario
4. Pregunta fecha y hora preferida
5. Verifica disponibilidad
6. Pregunta nombre y teléfono si no los tienes
7. Confirma todos los detalles
8. Crea la cita solo después de confirmación

FORMATO DE RESPUESTA:
- Usa emojis moderadamente para hacer la conversación más amigable
- Usa formato de lista cuando sea apropiado
- Mantén las respuestas organizadas y fáciles de leer

Recuerda: eres la primera impresión del salón, ¡haz que sea excelente!
"""


class SalonAgent:
    """AI Agent for the beauty salon chatbot."""

    def __init__(self):
        """Initialize the salon agent."""
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
        )
        self.tools = get_salon_tools()
        self.agent_executor = self._create_agent()

    def _create_agent(self) -> AgentExecutor:
        """Create the agent executor."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_tools_agent(self.llm, self.tools, prompt)

        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=settings.debug,
            handle_parsing_errors=True,
            max_iterations=10,
        )

    def _get_current_datetime(self) -> str:
        """Get current datetime formatted for the agent."""
        now = datetime.now(TZ)
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        dia = dias[now.weekday()]
        return now.strftime(f"{dia}, %d de %B de %Y, %H:%M")

    def _format_chat_history(
        self, history: Optional[List[dict]]
    ) -> List:
        """Format chat history for the agent."""
        if not history:
            return []

        messages = []
        for msg in history[-10:]:  # Keep last 10 messages for context
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        return messages

    async def process_message(
        self,
        message: str,
        chat_history: Optional[List[dict]] = None,
        client_phone: Optional[str] = None,
        client_name: Optional[str] = None,
    ) -> str:
        """
        Process a message and return the agent's response.

        Args:
            message: The user's message
            chat_history: Previous messages in the conversation
            client_phone: The client's phone number (if known)
            client_name: The client's name (if known)

        Returns:
            The agent's response
        """
        try:
            # Add context about the client if available
            context_prefix = ""
            if client_name:
                context_prefix = f"[Cliente: {client_name}] "
            if client_phone:
                context_prefix += f"[Tel: {client_phone}] "

            full_message = context_prefix + message if context_prefix else message

            # Format chat history
            formatted_history = self._format_chat_history(chat_history)

            # Prepare inputs
            inputs = {
                "input": full_message,
                "chat_history": formatted_history,
                "salon_name": settings.salon_name,
                "current_datetime": self._get_current_datetime(),
                "timezone": settings.calendar_timezone,
            }

            # Run the agent
            result = await self.agent_executor.ainvoke(inputs)

            response = result.get("output", "Lo siento, hubo un error al procesar tu mensaje.")

            logger.info(
                "Agent processed message",
                message_length=len(message),
                response_length=len(response),
            )

            return response

        except Exception as e:
            logger.error("Error processing message with agent", error=str(e))
            return (
                "Lo siento, hubo un problema al procesar tu mensaje. "
                "Por favor intenta de nuevo o contacta al salón directamente."
            )


# Singleton instance
_agent_instance: Optional[SalonAgent] = None


def get_salon_agent() -> SalonAgent:
    """Get or create the salon agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SalonAgent()
        logger.info("Salon agent initialized")
    return _agent_instance
