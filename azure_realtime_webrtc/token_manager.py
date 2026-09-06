"""Token management for Azure OpenAI Realtime API."""

from __future__ import annotations

import json
from typing import Any

import aiohttp

from .errors import AuthenticationError, NegotiationError
from .types import AuthConfig, ApiKeyAuth, EntraAuth

TOKEN_PATH = "/openai/v1/realtime/client_secrets"
CALLS_PATH = "/openai/v1/realtime/calls"
FETCH_TIMEOUT = 30


class TokenManager:
    """Handles ephemeral token acquisition and SDP negotiation.

    Example:
        >>> tm = TokenManager(
        ...     base_url="https://my-resource.openai.azure.com",
        ...     auth=ApiKeyAuth(api_key="..."),
        ...     session_body={"session": {"type": "realtime", "model": "gpt-4o-realtime-preview"}},
        ... )
        >>> token = await tm.get_ephemeral_token()
    """

    def __init__(
        self,
        base_url: str,
        auth: AuthConfig,
        session_body: dict[str, Any],
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.session_body = session_body

    async def _get_auth_headers(self) -> dict[str, str]:
        if isinstance(self.auth, ApiKeyAuth):
            return {"api-key": self.auth.api_key}

        token = self.auth.get_token
        if callable(token):
            token = await token()

        return {"Authorization": f"Bearer {token}"}

    async def get_ephemeral_token(self) -> str:
        """Fetch an ephemeral token from /openai/v1/realtime/client_secrets."""
        url = f"{self.base_url}{TOKEN_PATH}"
        headers = await self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=self.session_body) as resp:
                if resp.status in (401, 403):
                    raise AuthenticationError(
                        f"Authentication failed: {resp.status} {resp.reason}"
                    )
                if not resp.ok:
                    body = await resp.text()
                    raise AuthenticationError(
                        f"Token request failed: {resp.status} {resp.reason} - {body}"
                    )

                data = await resp.json()
                token = data.get("value", "")
                if not token:
                    raise AuthenticationError("Invalid token response: missing 'value' field")
                return token

    async def negotiate(
        self,
        sdp_offer: str,
        ephemeral_token: str,
        webrtc_filter: bool = False,
    ) -> tuple[str, str]:
        """Post SDP offer and return (sdp_answer, call_id)."""
        url = f"{self.base_url}{CALLS_PATH}"
        if webrtc_filter:
            url += "?webrtcfilter=on"

        headers = {
            "Authorization": f"Bearer {ephemeral_token}",
            "Content-Type": "application/sdp",
        }

        timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, data=sdp_offer) as resp:
                if not resp.ok and resp.status != 201:
                    body = await resp.text()
                    raise NegotiationError(
                        f"SDP negotiation failed: {resp.status} - {body}",
                        status=resp.status,
                    )

                sdp_answer = await resp.text()
                location = resp.headers.get("Location", "")
                call_id = location.split("/")[-1] if location else ""
                return sdp_answer, call_id
