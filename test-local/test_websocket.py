"""Test 2: WebSocket client - connect, send text, stream response."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from azure_realtime_webrtc import RealtimeClient
from azure_realtime_webrtc.types import ApiKeyAuth, SessionConfig, AudioConfig, AudioOutputConfig


async def main():
    resource = os.environ.get("AZURE_RESOURCE", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_DEPLOYMENT", "")

    if not all([resource, api_key, deployment]):
        print("Missing env vars. Copy .env.example to .env and fill in values.")
        sys.exit(1)

    print(f"Connecting to {resource}/{deployment} via WebSocket...\n")

    client = RealtimeClient(
        resource=resource,
        deployment=deployment,
        auth=ApiKeyAuth(api_key=api_key),
        session=SessionConfig(
            instructions="You are a helpful assistant. Keep responses to 2 sentences max.",
        ),
    )

    async with client.connect() as session:
        print("Connected!\n")

        # Send a text message
        print("Sending: 'What are 3 facts about WebRTC?'\n")
        session.send_text("What are 3 facts about WebRTC?")

        # Stream the transcript
        print("--- Streaming response ---")
        full_text = ""
        async for chunk in session.transcript_stream():
            if chunk.role == "assistant":
                if chunk.type == "delta":
                    print(chunk.text, end="", flush=True)
                    full_text += chunk.text
                elif chunk.type == "done":
                    print(f"\n\n--- Complete ---")
                    print(f"Full response ({len(chunk.text)} chars): {chunk.text[:200]}...")
                    break

    print("\nDisconnected. Test passed!")


asyncio.run(main())
