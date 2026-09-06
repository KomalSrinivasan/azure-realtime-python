"""FastAPI middleware for token server."""

from __future__ import annotations

from typing import Any

from ..token_manager import TokenManager
from ..types import AuthConfig


def create_fastapi_router(
    resource: str,
    deployment: str,
    auth: AuthConfig,
    session: dict[str, Any] | None = None,
    prefix: str = "/api/realtime",
) -> Any:
    """Create a FastAPI router with token and health endpoints.

    Example:
        >>> from fastapi import FastAPI
        >>> from azure_realtime_webrtc.server import create_fastapi_router
        >>> from azure_realtime_webrtc.types import ApiKeyAuth
        >>>
        >>> app = FastAPI()
        >>> router = create_fastapi_router(
        ...     resource="my-resource",
        ...     deployment="gpt-4o-realtime-preview",
        ...     auth=ApiKeyAuth(api_key="..."),
        ... )
        >>> app.include_router(router)
    """
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter(prefix=prefix)

    base_url = f"https://{resource}.openai.azure.com"
    session_body: dict[str, Any] = {
        "session": {"type": "realtime", "model": deployment, **(session or {})}
    }
    tm = TokenManager(base_url, auth, session_body)

    @router.post("/token")
    async def get_token() -> JSONResponse:
        try:
            token = await tm.get_ephemeral_token()
            return JSONResponse(
                content={"token": token},
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            content={"status": "ok", "resource": resource, "deployment": deployment}
        )

    return router
