"""
OpenAI service for transcription and image description.
"""

import base64
import structlog
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings

logger = structlog.get_logger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API."""

    def __init__(self):
        """Initialize the OpenAI service."""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.whisper_model = settings.openai_whisper_model
        self.vision_model = settings.openai_vision_model

    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
        language: str = "es",
    ) -> Optional[str]:
        """
        Transcribe audio using OpenAI Whisper.

        Args:
            audio_data: The audio file as bytes
            filename: The filename (used to determine format)
            language: The language of the audio

        Returns:
            The transcribed text or None if failed
        """
        try:
            # Create a file-like object from bytes
            audio_file = (filename, audio_data)

            response = await self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                language=language,
                response_format="text",
            )

            logger.info(
                "Audio transcribed successfully",
                filename=filename,
                text_length=len(response) if response else 0,
            )

            return response

        except Exception as e:
            logger.error(
                "Error transcribing audio",
                filename=filename,
                error=str(e),
            )
            return None

    async def describe_image(
        self,
        image_data: bytes,
        prompt: Optional[str] = None,
        detail: str = "auto",
    ) -> Optional[str]:
        """
        Describe an image using GPT-4o Vision.

        Args:
            image_data: The image file as bytes
            prompt: Optional custom prompt for the description
            detail: Image detail level ('low', 'high', 'auto')

        Returns:
            The image description or None if failed
        """
        try:
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # Determine image type (assume jpeg if unknown)
            if image_data[:8] == b"\x89PNG\r\n\x1a\n":
                media_type = "image/png"
            elif image_data[:2] == b"\xff\xd8":
                media_type = "image/jpeg"
            elif image_data[:4] == b"GIF8":
                media_type = "image/gif"
            elif image_data[:4] == b"RIFF":
                media_type = "image/webp"
            else:
                media_type = "image/jpeg"

            # Default prompt for salon context
            if not prompt:
                prompt = """Describe esta imagen de manera concisa y útil en el contexto de un salón de belleza.
Si es una imagen de un peinado, color de cabello, estilo de uñas u otro servicio de belleza,
descríbelo de manera que ayude a entender lo que el cliente desea.
Si no es relevante para un salón de belleza, simplemente describe lo que ves brevemente."""

            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{base64_image}",
                                    "detail": detail,
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )

            description = response.choices[0].message.content

            logger.info(
                "Image described successfully",
                description_length=len(description) if description else 0,
            )

            return description

        except Exception as e:
            logger.error(
                "Error describing image",
                error=str(e),
            )
            return None

    async def describe_image_from_url(
        self,
        image_url: str,
        prompt: Optional[str] = None,
        detail: str = "auto",
    ) -> Optional[str]:
        """
        Describe an image from URL using GPT-4o Vision.

        Args:
            image_url: The URL of the image
            prompt: Optional custom prompt for the description
            detail: Image detail level ('low', 'high', 'auto')

        Returns:
            The image description or None if failed
        """
        try:
            # Default prompt for salon context
            if not prompt:
                prompt = """Describe esta imagen de manera concisa y útil en el contexto de un salón de belleza.
Si es una imagen de un peinado, color de cabello, estilo de uñas u otro servicio de belleza,
descríbelo de manera que ayude a entender lo que el cliente desea.
Si no es relevante para un salón de belleza, simplemente describe lo que ves brevemente."""

            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": detail,
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )

            description = response.choices[0].message.content

            logger.info(
                "Image from URL described successfully",
                url=image_url[:50],
                description_length=len(description) if description else 0,
            )

            return description

        except Exception as e:
            logger.error(
                "Error describing image from URL",
                url=image_url[:50],
                error=str(e),
            )
            return None


# Singleton instance
openai_service = OpenAIService()
