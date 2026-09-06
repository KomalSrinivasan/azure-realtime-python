<p align="center">
  <strong>azure-realtime-webrtc</strong><br/>
  <em>Python SDK for Azure OpenAI Realtime API — async streaming, tools, Flask & FastAPI</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/azure-realtime-webrtc/"><img src="https://img.shields.io/pypi/v/azure-realtime-webrtc?style=flat-square&color=10A37F" alt="pypi version"/></a>
  <a href="https://pypi.org/project/azure-realtime-webrtc/"><img src="https://img.shields.io/pypi/dm/azure-realtime-webrtc?style=flat-square&color=D97757" alt="downloads"/></a>
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="license"/>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-green?style=flat-square" alt="python"/>
  <img src="https://img.shields.io/badge/typed-py.typed-blue?style=flat-square" alt="typed"/>
  <img src="https://img.shields.io/badge/async-first-brightgreen?style=flat-square" alt="async"/>
</p>

---

**azure-realtime-webrtc** is the Python companion to the [npm package](https://www.npmjs.com/package/azure-realtime-webrtc). It provides an async WebSocket client, streaming iterators, function calling, and server middleware for Flask & FastAPI — so you can build real-time AI voice/text applications in Python.

```python
from azure_realtime_webrtc import RealtimeClient
from azure_realtime_webrtc.types import ApiKeyAuth

client = RealtimeClient(
    resource="my-resource",
    deployment="gpt-4o-realtime-preview",
    auth=ApiKeyAuth(api_key=os.environ["AZURE_OPENAI_API_KEY"]),
)

async with client.connect() as session:
    session.send_text("Hello!")
    async for chunk in session.transcript_stream():
        print(chunk.text, end="", flush=True)
```

## What's Inside

| Module | Purpose |
|--------|---------|
| `azure_realtime_webrtc` | Async WebSocket client, token manager, typed events |
| `azure_realtime_webrtc.sdk` | High-level classes: **TextChat**, **ToolAgent** |
| `azure_realtime_webrtc.server` | Flask blueprint & FastAPI router for token server |
| `azure_realtime_webrtc.types` | All dataclass types with full type hints |

## Features

| Feature | Details |
|---------|---------|
| **Async WebSocket Client** | Full duplex communication with Azure OpenAI Realtime API |
| **Streaming Iterators** | `async for chunk in session.transcript_stream()` |
| **Function Calling** | `register_tool()` with automatic call → execute → respond cycle |
| **SDK: TextChat** | Streaming text chat with message history |
| **SDK: ToolAgent** | Autonomous multi-step tool calling with execution trace |
| **Flask Middleware** | `create_flask_blueprint()` — drop-in token server |
| **FastAPI Middleware** | `create_fastapi_router()` — async token server with Swagger UI |
| **Entra ID Auth** | Microsoft Entra ID support via `azure-identity` |
| **Fully Typed** | `py.typed` marker, dataclasses, full type hints |

## Install

```bash
pip install azure-realtime-webrtc
```

With Flask:
```bash
pip install azure-realtime-webrtc[flask]
```

With FastAPI:
```bash
pip install azure-realtime-webrtc[fastapi]
```

With Entra ID:
```bash
pip install azure-realtime-webrtc[azure]
```

Everything:
```bash
pip install azure-realtime-webrtc[all]
```

## Prerequisites

You need three things from the [Azure Portal](https://portal.azure.com):

| Value | Where to find it | Example |
|-------|-------------------|---------|
| **Resource name** | Your Azure OpenAI resource URL: `https://<THIS>.openai.azure.com` | `my-openai-resource` |
| **API Key** | Azure Portal → Your OpenAI resource → Keys and Endpoint | `abc123...` |
| **Deployment name** | Azure AI Foundry → Deployments (must be a **realtime** model) | `gpt-4o-realtime-preview` |

> Deployment must be in **East US 2** or **Sweden Central**.

---

## Quick Start

### 1. WebSocket Client (Async Streaming)

```python
import asyncio
import os
from azure_realtime_webrtc import RealtimeClient
from azure_realtime_webrtc.types import ApiKeyAuth, SessionConfig, AudioConfig, AudioOutputConfig

client = RealtimeClient(
    resource=os.environ["AZURE_RESOURCE"],
    deployment=os.environ["AZURE_DEPLOYMENT"],
    auth=ApiKeyAuth(api_key=os.environ["AZURE_OPENAI_API_KEY"]),
    session=SessionConfig(
        instructions="You are a helpful assistant. Be concise.",
        audio=AudioConfig(output=AudioOutputConfig(voice="alloy")),
    ),
)

async def main():
    async with client.connect() as session:
        session.send_text("What are three facts about WebRTC?")

        async for chunk in session.transcript_stream():
            if chunk.type == "delta":
                print(chunk.text, end="", flush=True)
            elif chunk.type == "done":
                print(f"\n\n[{chunk.role}] Complete.")
                break

asyncio.run(main())
```

### 2. Function Calling (Tools)

```python
import json
from azure_realtime_webrtc.types import ToolDefinition, ToolRegistration

def get_weather(args: dict) -> str:
    city = args.get("city", "unknown")
    return json.dumps({"city": city, "temp": 72, "condition": "Sunny"})

client.register_tool(ToolRegistration(
    definition=ToolDefinition(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    ),
    handler=get_weather,
))

async with client.connect() as session:
    session.send_text("What's the weather in Tokyo?")
    # Tool calls are handled automatically!
    async for chunk in session.transcript_stream():
        if chunk.role == "assistant":
            print(chunk.text, end="", flush=True)
            if chunk.type == "done":
                break
```

### 3. Flask Token Server

```python
import os
from flask import Flask
from azure_realtime_webrtc.server import create_flask_blueprint
from azure_realtime_webrtc.types import ApiKeyAuth

app = Flask(__name__)

bp = create_flask_blueprint(
    resource=os.environ["AZURE_RESOURCE"],
    deployment=os.environ["AZURE_DEPLOYMENT"],
    auth=ApiKeyAuth(api_key=os.environ["AZURE_OPENAI_API_KEY"]),
    session={
        "instructions": "You are a helpful assistant.",
        "audio": {"output": {"voice": "alloy"}},
    },
)

app.register_blueprint(bp)
app.run(port=3001)
# POST /api/realtime/token → {"token": "ek_..."}
# GET  /api/realtime/health → {"status": "ok"}
```

### 4. FastAPI Token Server

```python
import os
from fastapi import FastAPI
from azure_realtime_webrtc.server import create_fastapi_router
from azure_realtime_webrtc.types import ApiKeyAuth

app = FastAPI(title="Realtime Token Server")

router = create_fastapi_router(
    resource=os.environ["AZURE_RESOURCE"],
    deployment=os.environ["AZURE_DEPLOYMENT"],
    auth=ApiKeyAuth(api_key=os.environ["AZURE_OPENAI_API_KEY"]),
)

app.include_router(router)
# Run: uvicorn server:app --port 3001
# Swagger UI at http://localhost:3001/docs
```

### 5. Tool Agent (Multi-Step Autonomous)

```python
import json
from azure_realtime_webrtc.sdk import ToolAgent
from azure_realtime_webrtc.types import ApiKeyAuth, ToolDefinition, ToolRegistration

agent = ToolAgent(
    resource="my-resource",
    deployment="gpt-4o-realtime-preview",
    auth=ApiKeyAuth(api_key="..."),
    instructions="You are a research assistant. Use tools to find information.",
    max_tool_rounds=10,
)

agent.register_tool(ToolRegistration(
    definition=ToolDefinition(
        name="search", description="Search the web",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ),
    handler=lambda args: json.dumps(search_web(args["query"])),
))

async with agent.connect().connect() as session:
    result = await agent.run(session, "Find the latest WebRTC news")
    print(f"Response: {result.response}")
    print(f"Tool calls: {result.tool_call_count}")
    for step in result.steps:
        print(f"  [{step.type}] {step.content[:100]}")
```

### 6. Text Chat (Streaming)

```python
from azure_realtime_webrtc.sdk import TextChat
from azure_realtime_webrtc.types import ApiKeyAuth

chat = TextChat(
    resource="my-resource",
    deployment="gpt-4o-realtime-preview",
    auth=ApiKeyAuth(api_key="..."),
    instructions="You are customer support.",
)

async with chat.connect().connect() as session:
    async for msg in chat.send_and_stream(session, "How do I reset my password?"):
        if msg.streaming:
            print(f"\r{msg.content}", end="", flush=True)
        else:
            print(f"\n{msg.content}")
```

---

## Streaming

Streaming is built into `RealtimeSession` — no extra imports needed:

```python
async with client.connect() as session:
    session.send_text("Tell me a story.")

    # Transcript stream (user + assistant text, word by word)
    async for chunk in session.transcript_stream():
        if chunk.type == "delta":
            print(chunk.text, end="", flush=True)
        elif chunk.type == "done":
            print(f"\n[{chunk.role}] Complete")
            break

    # Audio stream (base64 audio data chunks)
    async for chunk in session.audio_stream():
        if not chunk.done:
            save_audio(base64.b64decode(chunk.data))

    # All events stream
    async for event in session.event_stream():
        print(f"Event: {event.type}")
        if event.type == "response.done":
            break
```

### Event Listener Pattern

```python
async with client.connect() as session:
    session.on("session.created", lambda e: print("Session ready!"))
    session.on("error", lambda e: print(f"Error: {e.data['error']['message']}"))
    session.on("*", lambda e: print(f"[{e.type}]"))  # wildcard

    session.send_text("Hello!")
    async for event in session.event_stream():
        if event.type == "response.done":
            break
```

---

## API Reference

### `RealtimeClient`

```python
client = RealtimeClient(
    resource="my-resource",           # Azure resource name (required)
    deployment="gpt-4o-realtime",     # Model deployment name (required)
    auth=ApiKeyAuth(api_key="..."),   # Or EntraAuth(get_token=...)
    session=SessionConfig(...),        # Optional session config
    base_url="https://...",           # Optional URL override
    ephemeral_token="ek_...",         # Optional pre-fetched token
)
client.register_tool(ToolRegistration(...))
```

### `RealtimeSession`

| Method | Returns | Description |
|--------|---------|-------------|
| `send(event)` | — | Send any `ClientEvent` |
| `send_text(text)` | — | Send text + trigger response |
| `add_item(item)` | — | Add a conversation item |
| `create_response()` | — | Trigger model response |
| `update_session(**kwargs)` | — | Update session config |
| `transcript_stream()` | `AsyncIterator[TranscriptChunk]` | User + AI text stream |
| `audio_stream()` | `AsyncIterator[AudioChunk]` | Audio data stream |
| `event_stream()` | `AsyncIterator[ServerEvent]` | All events stream |
| `on(event, handler)` | `() -> None` | Subscribe (returns unsubscribe fn) |
| `close()` | — | Close the session |

### Server Middleware

| Function | Framework | Endpoints |
|----------|-----------|-----------|
| `create_flask_blueprint(...)` | Flask | `POST /api/realtime/token` · `GET /api/realtime/health` |
| `create_fastapi_router(...)` | FastAPI | `POST /api/realtime/token` · `GET /api/realtime/health` |

### SDK Classes

| Class | Method | Description |
|-------|--------|-------------|
| `TextChat` | `send_and_stream(session, text)` | `AsyncIterator[ChatMessage]` with streaming |
| `ToolAgent` | `run(session, task)` | `AgentRunResult` with full execution trace |

---

## Session Configuration

```python
from azure_realtime_webrtc.types import (
    SessionConfig, AudioConfig, AudioInputConfig, AudioOutputConfig, TurnDetectionConfig
)

session = SessionConfig(
    instructions="You are a helpful assistant.",
    audio=AudioConfig(
        output=AudioOutputConfig(voice="alloy", format="pcm16"),
        input=AudioInputConfig(
            format="pcm16",
            transcription={"model": "whisper-1"},
            turn_detection=TurnDetectionConfig(
                threshold=0.5,
                prefix_padding_ms=300,
                silence_duration_ms=200,
                create_response=True,
            ),
        ),
    ),
    modalities=["audio", "text"],
    temperature=0.8,
    max_response_output_tokens=4096,
    tools=[ToolDefinition(name="...", description="...", parameters={...})],
    tool_choice="auto",
)
```

**Voices:** `alloy` · `ash` · `ballad` · `coral` · `echo` · `sage` · `shimmer` · `verse` · `marin`

## Supported Models

| Model | Version |
|-------|---------|
| `gpt-4o-mini-realtime-preview` | 2024-12-17 |
| `gpt-4o-realtime-preview` | 2024-12-17 |
| `gpt-realtime` | 2025-08-28 |
| `gpt-realtime-mini` | 2025-10-06, 2025-12-15 |
| `gpt-realtime-1.5` | 2026-02-23 |

> Regions: **East US 2** and **Sweden Central** only.

## Security

| Measure | Details |
|---------|---------|
| **Token isolation** | API keys stay server-side — only ephemeral tokens sent to clients |
| **Security headers** | `Cache-Control: no-store` · `X-Content-Type-Options: nosniff` |
| **CORS** | Enabled by default on Flask blueprint |
| **No eval** | All JSON parsed with `json.loads` — no `exec()` or `eval()` |
| **Typed** | `py.typed` marker for mypy / pyright static analysis |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Token request 500 | Use nested format: `audio.output.voice` not flat `voice` |
| No transcript | Listen for BOTH `response.audio_transcript.delta` AND `response.output_audio_transcript.delta` (SDK handles this automatically) |
| Import error | `pip install azure-realtime-webrtc[all]` |
| Async errors | Use `async with client.connect()` — the client is async-first |
| Flask blocking | Token generation uses `asyncio.run()` internally — works in sync Flask |

## npm Companion

This is the Python companion to the npm package. Use them together:

| Package | Registry | Install | Adds |
|---------|----------|---------|------|
| `azure-realtime-webrtc` | **npm** | `npm install azure-realtime-webrtc` | WebRTC browser client, VoiceAssistant, ReadableStreams, SSE, Express middleware |
| `azure-realtime-webrtc` | **PyPI** | `pip install azure-realtime-webrtc` | WebSocket client, Flask/FastAPI middleware, TextChat, ToolAgent |

## Author & Maintainer

**Komal Vardhan Lolugu**
Lead Product Engineer — Agentic AI & Generative Models

| Platform | Link |
|----------|------|
| Portfolio | [komalsrinivas.vercel.app](https://komalsrinivas.vercel.app/) |
| LinkedIn | [linkedin.com/in/komalvardhanlolugu](https://www.linkedin.com/in/komalvardhanlolugu/) |
| GitHub | [github.com/komalSrinivasan](https://github.com/komalSrinivasan) |
| Medium | [komalvardhan.medium.com](https://komalvardhan.medium.com/) |
| Topmate | [topmate.io/komal_vardhan_lolugu](https://topmate.io/komal_vardhan_lolugu) |

For bugs, questions, or collaboration — reach out via [LinkedIn](https://www.linkedin.com/in/komalvardhanlolugu/) or open an issue.

## License

MIT
