"""High-level text chat interface."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ..client import RealtimeClient, RealtimeSession
from ..types import AuthConfig, SessionConfig, ToolRegistration, TranscriptChunk


@dataclass
class ChatMessage:
    id: str
    role: str  # "user" | "assistant"
    content: str
    timestamp: float
    streaming: bool = False


class TextChat:
    """Streaming text chat. No audio complexity.

    Example:
        >>> chat = TextChat(
        ...     resource="my-resource",
        ...     deployment="gpt-4o-realtime-preview",
        ...     auth=ApiKeyAuth(api_key="..."),
        ...     instructions="You are helpful.",
        ... )
        >>>
        >>> async with chat.connect() as session:
        ...     async for msg in session.chat("What is WebRTC?"):
        ...         print(msg.content, end="", flush=True)
    """

    def __init__(
        self,
        resource: str,
        deployment: str,
        auth: AuthConfig | None = None,
        ephemeral_token: str | None = None,
        instructions: str | None = None,
        base_url: str | None = None,
    ) -> None:
        session_config = SessionConfig(instructions=instructions) if instructions else None
        self._client = RealtimeClient(
            resource=resource,
            deployment=deployment,
            auth=auth,
            base_url=base_url,
            session=session_config,
            ephemeral_token=ephemeral_token,
        )
        self._tools: list[ToolRegistration] = []

    def register_tool(self, registration: ToolRegistration) -> "TextChat":
        self._tools.append(registration)
        self._client.register_tool(registration)
        return self

    async def send_and_stream(
        self, session: RealtimeSession, text: str
    ) -> AsyncIterator[ChatMessage]:
        """Send a message and stream the response."""
        msg_id = f"msg_{int(time.time() * 1000)}"
        session.send_text(text)

        current = ""
        async for chunk in session.transcript_stream():
            if chunk.role == "assistant":
                if chunk.type == "delta":
                    current += chunk.text
                    yield ChatMessage(
                        id=msg_id, role="assistant", content=current,
                        timestamp=time.time(), streaming=True,
                    )
                else:
                    yield ChatMessage(
                        id=msg_id, role="assistant", content=chunk.text or current,
                        timestamp=time.time(), streaming=False,
                    )
                    return

    def connect(self) -> "RealtimeClient":
        """Return the underlying client for use with `async with`."""
        return self._client
