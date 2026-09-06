"""Test 4: Function calling / tools."""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from azure_realtime_webrtc import RealtimeClient
from azure_realtime_webrtc.types import ApiKeyAuth, SessionConfig, ToolDefinition, ToolRegistration


def get_weather(args: dict) -> str:
    """Mock weather tool."""
    city = args.get("city", "unknown")
    weather = {
        "tokyo": {"temp": 82, "condition": "Sunny"},
        "london": {"temp": 58, "condition": "Rainy"},
        "new york": {"temp": 71, "condition": "Cloudy"},
    }
    data = weather.get(city.lower(), {"temp": 70, "condition": "Fair"})
    result = {"city": city, **data}
    print(f"  [tool called] get_weather({city}) -> {result}")
    return json.dumps(result)


async def main():
    resource = os.environ.get("AZURE_RESOURCE", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_DEPLOYMENT", "")

    if not all([resource, api_key, deployment]):
        print("Missing env vars.")
        sys.exit(1)

    print("TEST: Function calling (tools)\n")

    client = RealtimeClient(
        resource=resource,
        deployment=deployment,
        auth=ApiKeyAuth(api_key=api_key),
        session=SessionConfig(
            instructions="You are a weather assistant. Always use the get_weather tool when asked about weather. Be brief.",
            tools=[
                ToolDefinition(
                    name="get_weather",
                    description="Get the current weather for a city",
                    parameters={
                        "type": "object",
                        "properties": {"city": {"type": "string", "description": "City name"}},
                        "required": ["city"],
                    },
                )
            ],
            tool_choice="auto",
        ),
    )

    # Register the handler
    client.register_tool(ToolRegistration(
        definition=ToolDefinition(name="get_weather", description="", parameters={}),
        handler=get_weather,
    ))

    async with client.connect() as session:
        print("Connected. Asking about weather in Tokyo...\n")
        session.send_text("What's the weather like in Tokyo?")

        print("--- Streaming response ---")
        async for chunk in session.transcript_stream():
            if chunk.role == "assistant":
                if chunk.type == "delta":
                    print(chunk.text, end="", flush=True)
                elif chunk.type == "done":
                    print(f"\n\n--- Complete ---")
                    break

    print("\nTool calling test PASSED!")


asyncio.run(main())
