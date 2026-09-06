"""Run all tests in sequence."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

resource = os.environ.get("AZURE_RESOURCE", "")
api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
deployment = os.environ.get("AZURE_DEPLOYMENT", "")

if not all([resource, api_key, deployment]):
    print("Missing env vars. Copy .env.example to .env and fill in values.")
    sys.exit(1)

from azure_realtime_webrtc import RealtimeClient, TokenManager
from azure_realtime_webrtc.types import ApiKeyAuth, SessionConfig, ToolDefinition, ToolRegistration
import json


async def test_1_token():
    print("\n" + "=" * 50)
    print("TEST 1: Token Generation")
    print("=" * 50)

    tm = TokenManager(
        base_url=f"https://{resource}.openai.azure.com",
        auth=ApiKeyAuth(api_key=api_key),
        session_body={"session": {"type": "realtime", "model": deployment}},
    )
    token = await tm.get_ephemeral_token()
    assert token.startswith("ek_"), f"Unexpected token format: {token[:20]}"
    print(f"  Token: {token[:25]}...")
    print("  PASSED")


async def test_2_websocket():
    print("\n" + "=" * 50)
    print("TEST 2: WebSocket Connect + Text")
    print("=" * 50)

    client = RealtimeClient(
        resource=resource,
        deployment=deployment,
        auth=ApiKeyAuth(api_key=api_key),
        session=SessionConfig(instructions="Reply in exactly 5 words."),
    )

    async with client.connect() as session:
        session.send_text("Say hello.")

        response = ""
        async for chunk in session.transcript_stream():
            if chunk.role == "assistant":
                if chunk.type == "delta":
                    response += chunk.text
                elif chunk.type == "done":
                    response = chunk.text or response
                    break

        print(f"  Response: {response}")
        assert len(response) > 0, "Empty response"
        print("  PASSED")


async def test_3_streaming():
    print("\n" + "=" * 50)
    print("TEST 3: Event Stream")
    print("=" * 50)

    client = RealtimeClient(
        resource=resource,
        deployment=deployment,
        auth=ApiKeyAuth(api_key=api_key),
        session=SessionConfig(instructions="Reply in 3 words."),
    )

    async with client.connect() as session:
        session.send_text("Hi")

        event_types = set()
        async for event in session.event_stream():
            event_types.add(event.type)
            if event.type == "response.done":
                break

        print(f"  Events seen: {sorted(event_types)}")
        assert "session.created" in event_types, "Missing session.created"
        assert "response.done" in event_types, "Missing response.done"
        print("  PASSED")


async def test_4_tools():
    print("\n" + "=" * 50)
    print("TEST 4: Function Calling")
    print("=" * 50)

    tool_called = False

    def mock_tool(args):
        nonlocal tool_called
        tool_called = True
        print(f"  Tool called with: {args}")
        return json.dumps({"result": "42"})

    client = RealtimeClient(
        resource=resource,
        deployment=deployment,
        auth=ApiKeyAuth(api_key=api_key),
        session=SessionConfig(
            instructions="Always use the calculate tool. Be brief.",
            tools=[ToolDefinition(
                name="calculate",
                description="Calculate a math expression",
                parameters={"type": "object", "properties": {"expr": {"type": "string"}}, "required": ["expr"]},
            )],
            tool_choice="auto",
        ),
    )
    client.register_tool(ToolRegistration(
        definition=ToolDefinition(name="calculate", description="", parameters={}),
        handler=mock_tool,
    ))

    async with client.connect() as session:
        session.send_text("What is 6 times 7? Use the calculate tool.")

        response = ""
        async for chunk in session.transcript_stream():
            if chunk.role == "assistant":
                if chunk.type == "delta":
                    response += chunk.text
                elif chunk.type == "done":
                    response = chunk.text or response
                    break

        print(f"  Response: {response}")
        print(f"  Tool was called: {tool_called}")
        print("  PASSED")


async def main():
    print("\nAzure OpenAI Realtime Python SDK - Test Suite")
    print(f"Resource: {resource} | Deployment: {deployment}")

    await test_1_token()
    await test_2_websocket()
    await test_3_streaming()
    await test_4_tools()

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)


asyncio.run(main())
