"""Flask middleware for token server."""

from __future__ import annotations

import asyncio
from typing import Any

from ..token_manager import TokenManager
from ..types import AuthConfig


def create_flask_blueprint(
    resource: str,
    deployment: str,
    auth: AuthConfig,
    session: dict[str, Any] | None = None,
    prefix: str = "/api/realtime",
) -> Any:
    """Create a Flask blueprint with token and health endpoints.

    Example:
        >>> from flask import Flask
        >>> from azure_realtime_webrtc.server import create_flask_blueprint
        >>> from azure_realtime_webrtc.types import ApiKeyAuth
        >>>
        >>> app = Flask(__name__)
        >>> bp = create_flask_blueprint(
        ...     resource="my-resource",
        ...     deployment="gpt-4o-realtime-preview",
        ...     auth=ApiKeyAuth(api_key="..."),
        ... )
        >>> app.register_blueprint(bp)
    """
    from flask import Blueprint, jsonify, request

    bp = Blueprint("realtime", __name__)

    base_url = f"https://{resource}.openai.azure.com"
    session_body: dict[str, Any] = {
        "session": {"type": "realtime", "model": deployment, **(session or {})}
    }
    tm = TokenManager(base_url, auth, session_body)

    def _run_async(coro: Any) -> Any:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result()
        except RuntimeError:
            pass
        return asyncio.run(coro)

    @bp.route(f"{prefix}/token", methods=["POST"])
    def get_token() -> Any:
        try:
            token = _run_async(tm.get_ephemeral_token())
            return jsonify({"token": token})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route(f"{prefix}/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "ok", "resource": resource, "deployment": deployment})

    @bp.after_request
    def add_headers(response: Any) -> Any:
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    return bp
