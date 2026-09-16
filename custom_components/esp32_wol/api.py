"""HTTP client for the ESP32-S3 WoL bridge firmware."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import DEFAULT_TIMEOUT


class WolBridgeError(Exception):
    """Base error for the bridge client."""


class WolBridgeAuthError(WolBridgeError):
    """The bridge rejected the token."""


class WolBridgeConnectionError(WolBridgeError):
    """The bridge could not be reached."""


class WolBridgeClient:
    """Small async wrapper around the bridge's HTTP API."""

    def __init__(self, session: aiohttp.ClientSession, host: str, token: str | None = None) -> None:
        self._session = session
        self._host = host.strip()
        self._token = (token or "").strip()

    @property
    def base_url(self) -> str:
        """Return the base URL of the bridge."""
        return f"http://{self._host}"

    async def _get(self, path: str, params: dict[str, str] | None = None) -> aiohttp.ClientResponse:
        params = dict(params or {})
        if self._token:
            params["token"] = self._token
        try:
            response = await self._session.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
            raise WolBridgeConnectionError(f"Cannot reach bridge at {self._host}: {err}") from err
        if response.status == 401:
            raise WolBridgeAuthError("Bridge rejected the token")
        return response

    async def async_get_status(self) -> dict[str, Any]:
        """Return the JSON from /status."""
        response = await self._get("/status")
        if response.status != 200:
            raise WolBridgeError(f"Unexpected status code {response.status} from /status")
        try:
            data = await response.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise WolBridgeError("Bridge returned invalid JSON") from err
        if not isinstance(data, dict):
            raise WolBridgeError("Bridge returned unexpected status payload")
        return data

    async def async_wake(self, mac: str | None = None) -> str:
        """Ask the bridge to send a magic packet. Empty mac uses the firmware default."""
        params: dict[str, str] = {}
        if mac:
            params["mac"] = mac
        response = await self._get("/wake", params)
        text = (await response.text()).strip()
        if response.status != 200:
            raise WolBridgeError(f"Wake failed ({response.status}): {text or 'no details'}")
        return text
