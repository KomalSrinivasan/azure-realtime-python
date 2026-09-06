"""Test 3: All streaming APIs - transcript, audio, events."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from azure_realtime_webrtc import RealtimeClient
from azure_realtime_webrtc.types import ApiKeyAuth, SessionConfig


async def test_transcript_stream(client: RealtimeClient):
    print("=" * 50)
    print("TEST: transcript_stream()")
    print("=" * 50)

    async with client.connect() as session:
        session.send_text("Tell me a one-line joke.")

        print("Streaming transcript:\n")
        async for chunk in session.transcript_stream():
            if chunk.role == "assistant":
                if chunk.type == "delta":
                    print(f"  [delta] '{chunk.text}'")
                else:
                    print(f"  [done]  '{chunk.text}'")
                    break

    print("PASSED\n")


async def test_event_stream(client: RealtimeClient):
    print("=" * 50)
    print("TEST: event_stream()")
    print("=" * 50)

    async with client.connect() as session:
        session.send_text("Say hi in one word.")

        print("Streaming events:\n")
        count = 0
        async for event in session.event_stream():
            count += 1
            # Skip noisy audio deltas
            if event.type == "response.audio.delta":
                continue
            print(f"  #{count} {event.type}")
            if event.type == "response.done":
                break

    print(f"\nTotal events: {count}")
    print("PASSED\n")


async def test_on_listener(client: RealtimeClient):
    print("=" * 50)
    print("TEST: on() event listener")
    print("=" * 50)

    async with client.connect() as session:
        events_received = []

        session.on("session.created", lambda e: events_received.append(e.type))
        session.on("response.done", lambda e: events_received.append(e.type))

        session.send_text("Say hello.")

        # Wait for response to complete
        async for event in session.event_stream():
            if event.type == "response.done":
                break

        print(f"  Events via on(): {events_received}")
        assert "session.created" in events_received, "Missing session.created"
        assert "response.done" in events_received, "Missing response.done"

    print("PASSED\n")


async def main():
    resource = os.environ.get("AZURE_RESOURCE", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_DEPLOYMENT", "")

    if not all([resource, api_key, deployment]):
        print("Missing env vars. Copy .env.example to .env and fill in values.")
        sys.exit(1)

    def make_client():
        return RealtimeClient(
            resource=resource,
            deployment=deployment,
            auth=ApiKeyAuth(api_key=api_key),
            session=SessionConfig(instructions="Be extremely brief. One sentence max."),
        )

    await test_transcript_stream(make_client())
    await test_event_stream(make_client())
    await test_on_listener(make_client())

    print("=" * 50)
    print("ALL STREAMING TESTS PASSED")
    print("=" * 50)


asyncio.run(main())
