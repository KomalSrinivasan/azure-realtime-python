"""WebSocket client for Azure OpenAI Realtime API."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Callable, Awaitable

import websockets
from websockets.asyncio.client import ClientConnection

from .errors import ConnectionError as RTCConnectionError, RealtimeError
from .token_manager import TokenManager
from .types import (
    AuthConfig,
    ApiKeyAuth,
    EntraAuth,
    AudioChunk,
    ClientEvent,
    ConversationItem,
    ServerEvent,
    SessionConfig,
    ToolDefinition,
    ToolRegistration,
    TranscriptChunk,
)

WS_PATH = "/openai/v1/realtime"

# Both reference + GA WebRTC event names for transcript
_TRANSCRIPT_DELTA_EVENTS = {
    "response.audio_transcript.delta",
    "response.output_audio_transcript.delta",
    "response.text.delta",
    "response.output_text.delta",
}

_TRANSCRIPT_DONE_EVENTS = {
    "response.audio_transcript.done",
    "response.output_audio_transcript.done",
}

_TEXT_DONE_EVENTS = {
    "response.text.done",
    "response.output_text.done",
}

_USER_TRANSCRIPT_EVENT = "conversation.item.input_audio_transcription.completed"


class RealtimeSession:
    """An active WebSocket session with the Azure OpenAI Realtime API.

    Use via `async with client.connect() as session:`.
    """

    def __init__(self, ws: ClientConnection, tools: dict[str, ToolRegistration]) -> None:
        self._ws = ws
        self._tools = tools
        self._listeners: dict[str, list[Callable[..., Any]]] = {}
        self._event_queue: asyncio.Queue[ServerEvent] = asyncio.Queue()
        self._receive_task: asyncio.Task[None] | None = None
        self._closed = False

    async def _start_receiving(self) -> None:
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        try:
            async for message in self._ws:
                if self._closed:
                    break
                try:
                    raw = json.loads(message)
                except (json.JSONDecodeError, TypeError):
                    continue

                if not isinstance(raw, dict) or "type" not in raw:
                    continue

                event = ServerEvent(
                    type=raw["type"],
                    event_id=raw.get("event_id", ""),
                    data=raw,
                )

                # Dispatch to listeners
                for handler in self._listeners.get(event.type, []):
                    try:
                        result = handler(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass

                for handler in self._listeners.get("*", []):
                    try:
                        result = handler(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass

                # Auto-handle tool calls
                if event.type == "response.function_call_arguments.done":
                    await self._handle_tool_call(event)

                # Push to event queue for iterators
                await self._event_queue.put(event)

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            pass

    async def _handle_tool_call(self, event: ServerEvent) -> None:
        name = event.data.get("name", "")
        reg = self._tools.get(name)
        if not reg:
            return

        try:
            args = json.loads(event.data.get("arguments", "{}"))
            result = reg.handler(args)
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as e:
            result = json.dumps({"error": str(e)})

        call_id = event.data.get("call_id", "")
        self.send(ClientEvent(type="conversation.item.create", data={
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result if isinstance(result, str) else json.dumps(result),
            }
        }))
        self.send(ClientEvent(type="response.create"))

    def on(self, event_type: str, handler: Callable[..., Any]) -> Callable[[], None]:
        """Subscribe to an event type. Returns an unsubscribe function."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)
        return lambda: self._listeners[event_type].remove(handler)

    def send(self, event: ClientEvent) -> None:
        """Send a client event."""
        if self._closed:
            raise RTCConnectionError("Session is closed")
        asyncio.ensure_future(self._ws.send(json.dumps(event.to_dict())))

    def send_text(self, text: str) -> None:
        """Send a text message and trigger a response."""
        self.send(ClientEvent(type="conversation.item.create", data={
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            }
        }))
        self.send(ClientEvent(type="response.create"))

    def add_item(self, item: ConversationItem) -> None:
        """Add a conversation item."""
        self.send(ClientEvent(type="conversation.item.create", data={
            "item": item.to_dict(),
        }))

    def create_response(self, **kwargs: Any) -> None:
        """Trigger a model response."""
        data: dict[str, Any] = {}
        if kwargs:
            data["response"] = kwargs
        self.send(ClientEvent(type="response.create", data=data))

    def update_session(self, **kwargs: Any) -> None:
        """Update session configuration."""
        self.send(ClientEvent(type="session.update", data={"session": kwargs}))

    async def transcript_stream(self) -> AsyncIterator[TranscriptChunk]:
        """Async iterator of transcript chunks (user + assistant).

        Example:
            async for chunk in session.transcript_stream():
                if chunk.type == "delta":
                    print(chunk.text, end="", flush=True)
                elif chunk.type == "done":
                    print(f"\\n[{chunk.role}] {chunk.text}")
        """
        while not self._closed:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if event.type in _TRANSCRIPT_DELTA_EVENTS:
                yield TranscriptChunk(
                    type="delta",
                    text=event.data.get("delta", ""),
                    role="assistant",
                    response_id=event.data.get("response_id"),
                    item_id=event.data.get("item_id"),
                    timestamp=time.time(),
                )
            elif event.type in _TRANSCRIPT_DONE_EVENTS:
                yield TranscriptChunk(
                    type="done",
                    text=event.data.get("transcript", ""),
                    role="assistant",
                    response_id=event.data.get("response_id"),
                    item_id=event.data.get("item_id"),
                    timestamp=time.time(),
                )
            elif event.type in _TEXT_DONE_EVENTS:
                yield TranscriptChunk(
                    type="done",
                    text=event.data.get("text", ""),
                    role="assistant",
                    response_id=event.data.get("response_id"),
                    item_id=event.data.get("item_id"),
                    timestamp=time.time(),
                )
            elif event.type == _USER_TRANSCRIPT_EVENT:
                yield TranscriptChunk(
                    type="done",
                    text=event.data.get("transcript", ""),
                    role="user",
                    item_id=event.data.get("item_id"),
                    timestamp=time.time(),
                )

    async def audio_stream(self) -> AsyncIterator[AudioChunk]:
        """Async iterator of audio data chunks."""
        while not self._closed:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if event.type == "response.audio.delta":
                yield AudioChunk(
                    data=event.data.get("delta", ""),
                    response_id=event.data.get("response_id", ""),
                    item_id=event.data.get("item_id", ""),
                    done=False,
                    timestamp=time.time(),
                )
            elif event.type == "response.audio.done":
                yield AudioChunk(
                    data="",
                    response_id=event.data.get("response_id", ""),
                    item_id=event.data.get("item_id", ""),
                    done=True,
                    timestamp=time.time(),
                )

    async def event_stream(self) -> AsyncIterator[ServerEvent]:
        """Async iterator of all server events."""
        while not self._closed:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            yield event

    async def close(self) -> None:
        """Close the session."""
        self._closed = True
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except (asyncio.CancelledError, Exception):
                pass
        await self._ws.close()


class RealtimeClient:
    """WebSocket client for Azure OpenAI Realtime API.

    Example:
        >>> client = RealtimeClient(
        ...     resource="my-resource",
        ...     deployment="gpt-4o-realtime-preview",
        ...     auth=ApiKeyAuth(api_key=os.environ["AZURE_OPENAI_API_KEY"]),
        ... )
        >>>
        >>> async with client.connect() as session:
        ...     session.send_text("Hello!")
        ...     async for chunk in session.transcript_stream():
        ...         print(chunk.text, end="", flush=True)
    """

    def __init__(
        self,
        resource: str,
        deployment: str,
        auth: AuthConfig | None = None,
        base_url: str | None = None,
        session: SessionConfig | None = None,
        ephemeral_token: str | None = None,
    ) -> None:
        self.resource = resource
        self.deployment = deployment
        self.auth = auth
        self.base_url = (base_url or f"https://{resource}.openai.azure.com").rstrip("/")
        self.session_config = session
        self.ephemeral_token = ephemeral_token
        self._tools: dict[str, ToolRegistration] = {}

    def register_tool(self, registration: ToolRegistration) -> "RealtimeClient":
        """Register a tool the AI can call."""
        self._tools[registration.definition.name] = registration
        return self

    def _build_session_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": "realtime",
            "model": self.deployment,
        }
        if self.session_config:
            if self.session_config.instructions:
                body["instructions"] = self.session_config.instructions
            if self.session_config.audio:
                audio: dict[str, Any] = {}
                if self.session_config.audio.output:
                    out: dict[str, Any] = {}
                    if self.session_config.audio.output.voice:
                        out["voice"] = self.session_config.audio.output.voice
                    if self.session_config.audio.output.format:
                        out["format"] = self.session_config.audio.output.format
                    audio["output"] = out
                if self.session_config.audio.input:
                    inp: dict[str, Any] = {}
                    if self.session_config.audio.input.format:
                        inp["format"] = self.session_config.audio.input.format
                    if self.session_config.audio.input.transcription:
                        inp["transcription"] = self.session_config.audio.input.transcription
                    if self.session_config.audio.input.turn_detection:
                        td = self.session_config.audio.input.turn_detection
                        td_dict: dict[str, Any] = {"type": td.type}
                        if td.threshold is not None:
                            td_dict["threshold"] = td.threshold
                        if td.prefix_padding_ms is not None:
                            td_dict["prefix_padding_ms"] = td.prefix_padding_ms
                        if td.silence_duration_ms is not None:
                            td_dict["silence_duration_ms"] = td.silence_duration_ms
                        if td.create_response is not None:
                            td_dict["create_response"] = td.create_response
                        inp["turn_detection"] = td_dict
                    audio["input"] = inp
                body["audio"] = audio
            if self.session_config.tools:
                body["tools"] = [
                    {"type": t.type, "name": t.name, "description": t.description, "parameters": t.parameters}
                    for t in self.session_config.tools
                ]
            if self.session_config.tool_choice:
                body["tool_choice"] = self.session_config.tool_choice
            if self.session_config.temperature is not None:
                body["temperature"] = self.session_config.temperature
            if self.session_config.modalities:
                body["modalities"] = self.session_config.modalities
        return {"session": body}

    @asynccontextmanager
    async def connect(self, call_id: str | None = None) -> AsyncIterator[RealtimeSession]:
        """Connect and yield a RealtimeSession.

        Args:
            call_id: Optional call ID to observe an existing WebRTC session.

        Example:
            async with client.connect() as session:
                session.send_text("Hello!")
                async for chunk in session.transcript_stream():
                    print(chunk.text, end="", flush=True)
        """
        # Get token if needed
        token = self.ephemeral_token
        if not token and self.auth:
            tm = TokenManager(self.base_url, self.auth, self._build_session_body())
            token = await tm.get_ephemeral_token()

        # Build WebSocket URL
        ws_base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        params = f"model={self.deployment}"
        if call_id:
            params += f"&call_id={call_id}"
        ws_url = f"{ws_base}{WS_PATH}?{params}"

        # Auth headers
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif self.auth and isinstance(self.auth, ApiKeyAuth):
            headers["api-key"] = self.auth.api_key

        ws = await websockets.connect(ws_url, additional_headers=headers)

        session = RealtimeSession(ws, self._tools)
        await session._start_receiving()

        try:
            yield session
        finally:
            await session.close()
