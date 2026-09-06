"""Test 5: Flask token server."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from azure_realtime_webrtc.server import create_flask_blueprint
from azure_realtime_webrtc.types import ApiKeyAuth

resource = os.environ.get("AZURE_RESOURCE", "")
api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
deployment = os.environ.get("AZURE_DEPLOYMENT", "")

if not all([resource, api_key, deployment]):
    print("Missing env vars.")
    sys.exit(1)

app = Flask(__name__)

bp = create_flask_blueprint(
    resource=resource,
    deployment=deployment,
    auth=ApiKeyAuth(api_key=api_key),
    session={
        "instructions": "You are a helpful assistant.",
        "audio": {"output": {"voice": "alloy"}},
    },
)

app.register_blueprint(bp)

print(f"\nFlask Token Server")
print(f"  Resource:   {resource}")
print(f"  Deployment: {deployment}")
print(f"  Endpoints:")
print(f"    POST http://localhost:5001/api/realtime/token")
print(f"    GET  http://localhost:5001/api/realtime/health")
print()

app.run(port=5001, debug=False)
