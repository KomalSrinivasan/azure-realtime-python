"""Test 6: FastAPI token server."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

resource = os.environ.get("AZURE_RESOURCE", "")
api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
deployment = os.environ.get("AZURE_DEPLOYMENT", "")

if not all([resource, api_key, deployment]):
    print("Missing env vars.")
    sys.exit(1)

from fastapi import FastAPI
from azure_realtime_webrtc.server import create_fastapi_router
from azure_realtime_webrtc.types import ApiKeyAuth

app = FastAPI(title="Azure Realtime Token Server")

router = create_fastapi_router(
    resource=resource,
    deployment=deployment,
    auth=ApiKeyAuth(api_key=api_key),
    session={
        "instructions": "You are a helpful assistant.",
        "audio": {"output": {"voice": "alloy"}},
    },
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    print(f"\nFastAPI Token Server")
    print(f"  Resource:   {resource}")
    print(f"  Deployment: {deployment}")
    print(f"  Endpoints:")
    print(f"    POST http://localhost:5002/api/realtime/token")
    print(f"    GET  http://localhost:5002/api/realtime/health")
    print(f"    GET  http://localhost:5002/docs  (Swagger UI)")
    print()

    uvicorn.run(app, host="0.0.0.0", port=5002)
