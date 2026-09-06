"""Azure OpenAI Realtime API SDK for Python.

Provides WebSocket client, streaming iterators, SDK classes, and server middleware
for Flask and FastAPI.

Usage:
    from azure_realtime_webrtc import RealtimeClient, TokenManager

    client = RealtimeClient(
        resource="my-resource",
        deployment="gpt-4o-realtime-preview",
        auth={"type": "api-key", "api_key": "..."},
    )

    async with client.connect() as session:
        session.send_text("Hello!")
        async for chunk in session.transcript_stream():
            print(chunk.text, end="", flush=True)
"""

from .client import RealtimeClient
from .token_manager import TokenManager
from .types import (
    AuthConfig,
    SessionConfig,
    TranscriptChunk,
    AudioChunk,
    ClientEvent,
    ServerEvent,
    ToolDefinition,
    ToolRegistration,
    ConversationItem,
)
from .errors import (
    RealtimeError,
    AuthenticationError,
    ConnectionError as RealtimeConnectionError,
    NegotiationError,
)

__version__ = "0.2.0"

__all__ = [
    "RealtimeClient",
    "TokenManager",
    "AuthConfig",
    "SessionConfig",
    "TranscriptChunk",
    "AudioChunk",
    "ClientEvent",
    "ServerEvent",
    "ToolDefinition",
    "ToolRegistration",
    "ConversationItem",
    "RealtimeError",
    "AuthenticationError",
    "RealtimeConnectionError",
    "NegotiationError",
]
