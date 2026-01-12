"""
Chatwoot service for sending messages and managing conversations.
"""

import structlog
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = structlog.get_logger(__name__)


class ChatwootService:
    """Service for interacting with Chatwoot API."""

    def __init__(self):
        """Initialize the Chatwoot service."""
        self.base_url = settings.chatwoot_base_url.rstrip("/")
        self.api_token = settings.chatwoot_api_token
        self.account_id = settings.chatwoot_account_id
        self.inbox_id = settings.chatwoot_inbox_id

        self.headers = {
            "api_access_token": self.api_token,
            "Content-Type": "application/json",
        }

    def _get_api_url(self, endpoint: str) -> str:
        """Get the full API URL for an endpoint."""
        return f"{self.base_url}/api/v1/accounts/{self.account_id}/{endpoint}"

    async def send_message(
        self,
        conversation_id: int,
        message: str,
        private: bool = False,
        content_type: str = "text",
        content_attributes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a message to a Chatwoot conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            message: The message content
            private: Whether the message is private (internal note)
            content_type: The content type (text, input_select, etc.)
            content_attributes: Additional content attributes

        Returns:
            The message response or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/messages")

        payload = {
            "content": message,
            "message_type": "outgoing",
            "private": private,
            "content_type": content_type,
        }

        if content_attributes:
            payload["content_attributes"] = content_attributes

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "Message sent to Chatwoot",
                    conversation_id=conversation_id,
                    message_id=result.get("id"),
                )
                return result
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to send message to Chatwoot",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            return None
        except Exception as e:
            logger.error(
                "Error sending message to Chatwoot",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def get_conversation(
        self, conversation_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The Chatwoot conversation ID

        Returns:
            The conversation data or None if not found
        """
        url = self._get_api_url(f"conversations/{conversation_id}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get conversation",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error getting conversation",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def get_contact(self, contact_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a contact by ID.

        Args:
            contact_id: The Chatwoot contact ID

        Returns:
            The contact data or None if not found
        """
        url = self._get_api_url(f"contacts/{contact_id}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get contact",
                contact_id=contact_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error getting contact",
                contact_id=contact_id,
                error=str(e),
            )
            return None

    async def update_conversation_status(
        self, conversation_id: int, status: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update conversation status.

        Args:
            conversation_id: The Chatwoot conversation ID
            status: The new status ('open', 'resolved', 'pending', 'snoozed')

        Returns:
            The updated conversation or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}")

        payload = {"status": status}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(
                    "Conversation status updated",
                    conversation_id=conversation_id,
                    status=status,
                )
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to update conversation status",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error updating conversation status",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def add_labels(
        self, conversation_id: int, labels: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Add labels to a conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            labels: List of labels to add

        Returns:
            The updated conversation or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/labels")

        payload = {"labels": labels}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(
                    "Labels added to conversation",
                    conversation_id=conversation_id,
                    labels=labels,
                )
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to add labels",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error adding labels",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def assign_agent(
        self, conversation_id: int, agent_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Assign an agent to a conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            agent_id: The agent ID to assign

        Returns:
            The updated conversation or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/assignments")

        payload = {"assignee_id": agent_id}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(
                    "Agent assigned to conversation",
                    conversation_id=conversation_id,
                    agent_id=agent_id,
                )
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to assign agent",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error assigning agent",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def get_messages(
        self, conversation_id: int, before: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: The Chatwoot conversation ID
            before: Get messages before this message ID

        Returns:
            List of messages or None if failed
        """
        url = self._get_api_url(f"conversations/{conversation_id}/messages")

        params = {}
        if before:
            params["before"] = before

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json().get("payload", [])
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get messages",
                conversation_id=conversation_id,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error getting messages",
                conversation_id=conversation_id,
                error=str(e),
            )
            return None

    async def download_attachment(self, attachment_url: str) -> Optional[bytes]:
        """
        Download an attachment from Chatwoot.

        Args:
            attachment_url: The URL of the attachment

        Returns:
            The attachment content as bytes or None if failed
        """
        try:
            # Handle relative URLs
            if attachment_url.startswith("/"):
                attachment_url = f"{self.base_url}{attachment_url}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    attachment_url, headers={"api_access_token": self.api_token}
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(
                "Error downloading attachment",
                url=attachment_url,
                error=str(e),
            )
            return None

    async def search_contacts(
        self, query: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Search for contacts.

        Args:
            query: Search query (name, email, phone)

        Returns:
            List of matching contacts or None if failed
        """
        url = self._get_api_url("contacts/search")

        params = {"q": query}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json().get("payload", [])
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to search contacts",
                query=query,
                status_code=e.response.status_code,
            )
            return None
        except Exception as e:
            logger.error(
                "Error searching contacts",
                query=query,
                error=str(e),
            )
            return None

    async def send_message_to_phone(
        self, phone_number: str, message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Send a message to a phone number (creates conversation if needed).

        Args:
            phone_number: The phone number to message
            message: The message content

        Returns:
            The message response or None if failed
        """
        # First, search for existing contact
        contacts = await self.search_contacts(phone_number)

        if contacts and len(contacts) > 0:
            contact_id = contacts[0]["id"]
        else:
            # Create new contact
            contact = await self._create_contact(phone_number)
            if not contact:
                return None
            contact_id = contact["id"]

        # Get or create conversation
        conversation = await self._get_or_create_conversation(contact_id)
        if not conversation:
            return None

        # Send message
        return await self.send_message(conversation["id"], message)

    async def _create_contact(
        self, phone_number: str, name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new contact."""
        url = self._get_api_url("contacts")

        payload = {
            "inbox_id": self.inbox_id,
            "phone_number": phone_number,
        }

        if name:
            payload["name"] = name

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json().get("payload", {}).get("contact")
        except Exception as e:
            logger.error(
                "Error creating contact",
                phone_number=phone_number,
                error=str(e),
            )
            return None

    async def _get_or_create_conversation(
        self, contact_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get or create a conversation for a contact."""
        url = self._get_api_url("conversations")

        payload = {
            "source_id": str(contact_id),
            "inbox_id": self.inbox_id,
            "contact_id": contact_id,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(
                "Error creating conversation",
                contact_id=contact_id,
                error=str(e),
            )
            return None


# Singleton instance
chatwoot_service = ChatwootService()
