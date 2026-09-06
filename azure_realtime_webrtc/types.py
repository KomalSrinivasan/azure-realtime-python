"""Type definitions for Azure OpenAI Realtime API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Union


# ── Auth ─────────────────────────────────────────────────

@dataclass
class ApiKeyAuth:
    type: Literal["api-key"] = "api-key"
    api_key: str = ""


@dataclass
class EntraAuth:
    type: Literal["entra"] = "entra"
    get_token: Union[str, Callable[[], Awaitable[str]]] = ""


AuthConfig = Union[ApiKeyAuth, EntraAuth]


# ── Session Config ───────────────────────────────────────

@dataclass
class TurnDetectionConfig:
    type: Literal["server_vad"] = "server_vad"
    threshold: float | None = None
    prefix_padding_ms: int | None = None
    silence_duration_ms: int | None = None
    create_response: bool | None = None


@dataclass
class AudioInputConfig:
    format: str | None = None
    transcription: dict[str, str] | None = None
    turn_detection: TurnDetectionConfig | None = None


@dataclass
class AudioOutputConfig:
    voice: str | None = None
    format: str | None = None


@dataclass
class AudioConfig:
    input: AudioInputConfig | None = None
    output: AudioOutputConfig | None = None


@dataclass
class ToolDefinition:
    type: Literal["function"] = "function"
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionConfig:
    model: str = ""
    instructions: str | None = None
    audio: AudioConfig | None = None
    modalities: list[str] | None = None
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict[str, str] | None = None
    temperature: float | None = None
    max_response_output_tokens: int | str | None = None


# ── Tools ────────────────────────────────────────────────

ToolHandler = Callable[..., Awaitable[str] | str]


@dataclass
class ToolRegistration:
    definition: ToolDefinition
    handler: ToolHandler


# ── Events ───────────────────────────────────────────────

@dataclass
class ServerEvent:
    type: str
    event_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name in self.data:
            return self.data[name]
        raise AttributeError(f"ServerEvent has no attribute '{name}'")


@dataclass
class ClientEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {"type": self.type, **self.data}
        return result


# ── Conversation Items ───────────────────────────────────

@dataclass
class ContentPart:
    type: str
    text: str | None = None
    audio: str | None = None
    transcript: str | None = None


@dataclass
class ConversationItem:
    type: str  # "message" | "function_call" | "function_call_output"
    role: str | None = None
    content: list[ContentPart] | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: str | None = None
    output: str | None = None
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.id:
            d["id"] = self.id
        if self.role:
            d["role"] = self.role
        if self.content:
            d["content"] = [
                {k: v for k, v in vars(c).items() if v is not None} for c in self.content
            ]
        if self.call_id:
            d["call_id"] = self.call_id
        if self.name:
            d["name"] = self.name
        if self.arguments:
            d["arguments"] = self.arguments
        if self.output:
            d["output"] = self.output
        return d


# ── Streaming Chunks ─────────────────────────────────────

@dataclass
class TranscriptChunk:
    type: Literal["delta", "done"]
    text: str
    role: Literal["user", "assistant"]
    response_id: str | None = None
    item_id: str | None = None
    timestamp: float = 0.0


@dataclass
class AudioChunk:
    data: str  # base64
    response_id: str = ""
    item_id: str = ""
    done: bool = False
    timestamp: float = 0.0
