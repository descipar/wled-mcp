"""Bounded fixed-endpoint WLED plumbing; no public arbitrary URL forwarding."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import cast

import anyio
import httpx2 as httpx
from pydantic import JsonValue

from wled_mcp.config import Device, HTTPSettings
from wled_mcp.models import DomainError, ErrorCode


class Endpoint(Enum):
    INFO = "/json/info"
    STATE = "/json/state"
    EFFECTS = "/json/eff"
    PALETTES = "/json/pal"
    FXDATA = "/json/fxdata"
    PRESETS = "/presets.json"

    @property
    def label(self) -> str:
        """Fixed, safe resource label for diagnostics (never a URL)."""
        return self.name.lower()


class ClientFailure(Exception):
    """Transport-independent failure with no original body, URL or exception text."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool = False,
        reconciliation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = DomainError(
            code=code,
            message=message,
            read_retryable=retryable,
            reconciliation=reconciliation
            or "Read the configured device explicitly; never replay the write.",
        )


@dataclass(frozen=True)
class Deadline:
    expires: float

    @classmethod
    def after(cls, seconds: float) -> "Deadline":
        return cls(anyio.current_time() + seconds)

    def remaining(self) -> float:
        remaining = self.expires - anyio.current_time()
        if remaining <= 0:
            raise ClientFailure("TIMEOUT", "Operation deadline expired.", retryable=True)
        return remaining


def validate_json(value: object) -> None:
    """Finite, bounded JSON nesting/shape, before dispatch and after bounded parsing."""
    stack: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 32 or nodes > 100000:
            raise ValueError("JSON shape exceeds supported limits")
        if item is None or type(item) in {str, bool, int}:
            continue
        if type(item) is float and math.isfinite(item):
            continue
        if isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, dict) and all(type(key) is str for key in item):
            stack.extend((child, depth + 1) for child in item.values())
        else:
            raise ValueError("Invalid JSON value")


class WLEDClient:
    def __init__(
        self,
        settings: HTTPSettings,
        transport: httpx.AsyncBaseTransport | None = None,
        observer: Callable[[str, ErrorCode | None], None] | None = None,
    ) -> None:
        self.settings = settings
        # Called with the device ID and None (success) or the failure code of every request
        # that reached the transport; it must not do I/O (issue #20, TD-20-11).
        self.observer = observer
        self.http = httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            verify=True,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    def encode_payload(self, payload: object) -> bytes:
        try:
            if not isinstance(payload, dict):
                raise ValueError("Expected state object")
            validate_json(payload)
            body = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")
            if len(body) > self.settings.max_request_bytes:
                raise ValueError("Request exceeds size limit")
            return body
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise ClientFailure("VALIDATION_ERROR", "Invalid or oversized state request.") from None

    async def read(self, device: Device, endpoint: Endpoint, deadline: Deadline) -> JsonValue:
        if not isinstance(endpoint, Endpoint):
            raise ClientFailure("VALIDATION_ERROR", "Unsupported internal endpoint.")
        for attempt in range(self.settings.read_retries + 1):
            try:
                return await self._request(device, endpoint, deadline, None)
            except ClientFailure as failure:
                if not failure.error.read_retryable or attempt == self.settings.read_retries:
                    raise
                deadline.remaining()
        raise AssertionError("Unreachable retry state")

    async def post_state(self, device: Device, body: bytes, deadline: Deadline) -> JsonValue:
        """Already-validated bytes, exactly one transport attempt; internal use only."""
        try:
            if len(body) > self.settings.max_request_bytes:
                raise ValueError("Oversized request")
            parsed: object = json.loads(body.decode("utf-8"))
            self.encode_payload(parsed)
        except (ValueError, UnicodeError, RecursionError):
            raise ClientFailure("VALIDATION_ERROR", "Invalid or oversized state request.") from None
        return await self._request(device, Endpoint.STATE, deadline, body)

    @staticmethod
    def _request_headers(endpoint: Endpoint, body: bytes | None) -> dict[str, str] | None:
        if body is not None:
            return {"Content-Type": "application/json"}
        if endpoint is Endpoint.PRESETS:
            # Persistent-file readbacks must never be answered from an intermediary cache.
            return {"Cache-Control": "no-cache", "Pragma": "no-cache"}
        return None

    async def _request(
        self, device: Device, endpoint: Endpoint, deadline: Deadline, body: bytes | None
    ) -> JsonValue:
        remaining = deadline.remaining()  # an expired deadline sent nothing: not an observation
        try:
            value = await self._exchange(device, endpoint, remaining, body)
        except ClientFailure as failure:
            # A rejected address (CONFIG_ERROR) never reached the device either.
            if failure.error.code != "CONFIG_ERROR":
                self._observe(device, failure.error.code)
            raise
        self._observe(device, None)
        return value

    def _observe(self, device: Device, code: ErrorCode | None) -> None:
        if self.observer is not None:
            self.observer(device.id, code)

    async def _exchange(
        self, device: Device, endpoint: Endpoint, remaining: float, body: bytes | None
    ) -> JsonValue:
        label = endpoint.label
        timeout = httpx.Timeout(
            remaining, connect=min(remaining, self.settings.connect_timeout_seconds)
        )
        try:
            with anyio.fail_after(remaining):
                async with self.http.stream(
                    "GET" if body is None else "POST",
                    device.base_url + endpoint.value,
                    content=body,
                    headers=self._request_headers(endpoint, body),
                    timeout=timeout,
                ) as response:
                    if response.status_code != 200:
                        raise ClientFailure(
                            "INVALID_RESPONSE",
                            f"Device returned unexpected HTTP status {response.status_code} "
                            f"for {label}.",
                        )
                    media = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    encoding = response.headers.get("content-encoding", "identity").lower()
                    if media != "application/json" or encoding not in {"", "identity"}:
                        raise ClientFailure(
                            "INVALID_RESPONSE", f"Expected uncompressed JSON response for {label}."
                        )
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > self.settings.max_response_bytes:
                            raise ClientFailure(
                                "INVALID_RESPONSE",
                                f"Device response for {label} exceeds size limit.",
                            )
                        content.extend(chunk)
                    value: object = json.loads(content.decode("utf-8"))
                    validate_json(value)
                    if endpoint in {Endpoint.INFO, Endpoint.STATE, Endpoint.PRESETS}:
                        if not isinstance(value, dict):
                            raise ValueError("Expected object")
                    elif not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        raise ValueError("Expected catalog")
                    return cast(JsonValue, value)
        except ClientFailure:
            raise
        except httpx.InvalidURL:
            # Raised while building the request, before any send; its text echoes the host.
            raise ClientFailure(
                "CONFIG_ERROR",
                f"Configured device address cannot be used for {label}; no request was sent.",
                reconciliation=(
                    "Correct the device's base_url in the inventory and restart; "
                    "nothing was sent to the device."
                ),
            ) from None
        except (TimeoutError, httpx.TimeoutException):
            raise ClientFailure(
                "TIMEOUT", f"Device request for {label} timed out.", retryable=True
            ) from None
        except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
            raise ClientFailure(
                "UNREACHABLE", f"Device connection for {label} failed.", retryable=True
            ) from None
        except httpx.HTTPError:
            raise ClientFailure("UNREACHABLE", f"Device request for {label} failed.") from None
        except (ValueError, UnicodeError, RecursionError):
            raise ClientFailure(
                "INVALID_RESPONSE", f"Device returned invalid JSON data for {label}."
            ) from None
