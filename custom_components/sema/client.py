"""Async read-only client; caller owns the shared aiohttp session."""

import json
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import NoReturn

import aiohttp
from yarl import URL

from .const import INFO_PATH, STATE_PATH
from .protocol import (
    DeviceInfo,
    DeviceState,
    ProtocolError,
    SemaError,
    UnsupportedVersion,
    parse_info,
    parse_state,
)

MAX_RESPONSE_BYTES = 65536


class AuthenticationError(SemaError):
    """Invalid, revoked or disabled HA credentials."""


class CommunicationError(SemaError):
    """Transport failure or server unavailable."""


class RateLimitError(SemaError):
    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("Device rate limit; retry later")
        self.retry_after_seconds = retry_after_seconds


def normalize_base_url(value: str) -> str:
    try:
        url = URL(value.strip())
        if (
            url.scheme not in ("http", "https")
            or not url.host
            or url.user is not None
            or url.password is not None
            or url.query_string
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError
        _ = url.port
        return str(url.with_path("").with_query(None).with_fragment(None))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(
            "Expected HTTP(S) device base URL without credentials or path"
        ) from None


def _retry_after(value: str | None) -> float:
    if value is None:
        return 30
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
    except (ValueError, TypeError):
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is not None:
            return max(0, (when - datetime.now(UTC)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        pass
    return 30


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError


class SemaClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 10,
    ) -> None:
        self._base_url = normalize_base_url(base_url)
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise ValueError("Invalid HA token format")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Invalid request timeout")
        self._token = token
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._retry_at = 0.0

    async def async_get_info(self) -> DeviceInfo:
        return parse_info(await self._get(INFO_PATH))

    async def async_get_state(self, info: DeviceInfo) -> DeviceState:
        return parse_state(await self._get(STATE_PATH), info)

    async def _get(self, path: str) -> object:
        remaining = self._retry_at - time.monotonic()
        if remaining > 0:
            raise RateLimitError(remaining)
        try:
            async with self._session.get(
                self._base_url + path,
                headers={
                    "Authorization": "Bearer " + self._token,
                    "Accept": "application/json",
                },
                timeout=self._timeout,
                allow_redirects=False,
                raise_for_status=False,
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError("HA authentication failed")
                if response.status == 404:
                    raise UnsupportedVersion("Device API endpoint unavailable")
                if response.status == 429:
                    seconds = _retry_after(response.headers.get("Retry-After"))
                    self._retry_at = time.monotonic() + seconds
                    raise RateLimitError(seconds)
                if response.status >= 500:
                    raise CommunicationError("Device server unavailable")
                if response.status != 200:
                    raise ProtocolError("Unexpected HTTP response")
                if response.content_type != "application/json":
                    raise ProtocolError("Expected JSON response")
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ProtocolError("Response exceeds size limit")
                try:
                    parsed: object = json.loads(body, parse_constant=_reject_constant)
                    return parsed
                except (ValueError, UnicodeError, RecursionError):
                    raise ProtocolError("Invalid JSON response") from None
        except (TimeoutError, aiohttp.ClientError, OSError):
            raise CommunicationError("Cannot communicate with SEMA") from None
