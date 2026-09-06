"""Test 1: Token generation - verify Azure credentials work."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from azure_realtime_webrtc import TokenManager
from azure_realtime_webrtc.types import ApiKeyAuth


async def main():
    resource = os.environ.get("AZURE_RESOURCE", "")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_DEPLOYMENT", "")

    if not all([resource, api_key, deployment]):
        print("Missing env vars. Copy .env.example to .env and fill in values.")
        sys.exit(1)

    print(f"Resource:   {resource}")
    print(f"Deployment: {deployment}")
    print(f"API Key:    ****{api_key[-4:]}")
    print()

    tm = TokenManager(
        base_url=f"https://{resource}.openai.azure.com",
        auth=ApiKeyAuth(api_key=api_key),
        session_body={
            "session": {
                "type": "realtime",
                "model": deployment,
            }
        },
    )

    print("Fetching ephemeral token...")
    token = await tm.get_ephemeral_token()
    print(f"SUCCESS: {token[:25]}...")
    print(f"Token length: {len(token)} chars")


asyncio.run(main())
