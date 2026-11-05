"""Validated Streamable HTTP service settings.

Imports no HTTP stack, so the default stdio path never loads it. Messages are fixed
classes: they never echo the credential, its file path or any supplied header value.
"""

import hashlib
import ipaddress
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from wled_mcp.config import ConfigurationError

TOKEN_ENV = "WLED_MCP_HTTP_TOKEN"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
ENDPOINT_PATH = "/mcp"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MAX_ALLOWLIST_ENTRIES = 16
MAX_ENTRY_LENGTH = 255
TOKEN_MIN, TOKEN_MAX = 32, 512
TOKEN_FILE_MAX_BYTES = 1024

_HOSTNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")


@dataclass(frozen=True)
class HTTPServiceSettings:
    host: str
    port: int
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]
    token_digest: bytes
    graceful_shutdown_seconds: int

    def __repr__(self) -> str:  # never render the credential digest
        return f"HTTPServiceSettings(host={self.host!r}, port={self.port})"


def token_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    if not _HOSTNAME.fullmatch(host):
        return False
    return all(
        label and len(label) <= 63 and not label.startswith("-") and not label.endswith("-")
        for label in host.split(".")
    )


def _valid_port(text: str) -> bool:
    return text.isascii() and text.isdigit() and str(int(text)) == text and 1 <= int(text) <= 65535


def _valid_authority(value: str) -> bool:
    """Exact `host[:port]`; IPv6 only in brackets; no userinfo, wildcard or whitespace."""
    if not value or len(value) > MAX_ENTRY_LENGTH or not value.isascii():
        return False
    if value.startswith("["):
        inner, bracket, rest = value[1:].partition("]")
        if not bracket or ":" not in inner:
            return False
        try:
            ipaddress.IPv6Address(inner)
        except ValueError:
            return False
        return rest == "" or (rest.startswith(":") and _valid_port(rest[1:]))
    host, colon, port = value.partition(":")
    if colon and not _valid_port(port):
        return False
    return ":" not in host and _valid_host(host)


def _normalize_hosts(values: Sequence[str]) -> frozenset[str]:
    if len(values) > MAX_ALLOWLIST_ENTRIES:
        raise ConfigurationError("Too many --allowed-host entries.")
    for value in values:
        if not _valid_authority(value):
            raise ConfigurationError("Invalid --allowed-host entry: expected exact host[:port].")
    return frozenset(value.lower() for value in values)


def _normalize_origins(values: Sequence[str]) -> frozenset[str]:
    if len(values) > MAX_ALLOWLIST_ENTRIES:
        raise ConfigurationError("Too many --allowed-origin entries.")
    for value in values:
        scheme, separator, authority = value.partition("://")
        if (
            not separator
            or scheme.lower() not in {"http", "https"}
            or not _valid_authority(authority)
        ):
            raise ConfigurationError(
                "Invalid --allowed-origin entry: expected exact scheme://host[:port]."
            )
    return frozenset(value.lower() for value in values)


def _read_token_file(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_absolute():
        raise ConfigurationError("The HTTP token file path must be absolute.")
    try:
        if not path.is_file():
            raise ConfigurationError("The HTTP token file must be an existing regular file.")
        with path.open("rb") as stream:
            raw = stream.read(TOKEN_FILE_MAX_BYTES + 1)
    except OSError:
        raise ConfigurationError("The HTTP token file could not be read.") from None
    if len(raw) > TOKEN_FILE_MAX_BYTES:
        raise ConfigurationError("The HTTP token file exceeds the 1 KiB limit.")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise ConfigurationError("The HTTP credential is invalid.") from None
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    return text


def _resolve_token(token_file: str | None, environ: Mapping[str, str]) -> str:
    from_env = environ.get(TOKEN_ENV)
    if from_env is not None and token_file is not None:
        raise ConfigurationError(
            "Configure exactly one HTTP credential source: environment or --http-token-file."
        )
    if from_env is None and token_file is None:
        raise ConfigurationError(
            f"An HTTP credential is required: set {TOKEN_ENV} or --http-token-file."
        )
    token = from_env if from_env is not None else _read_token_file(token_file or "")
    if (
        not TOKEN_MIN <= len(token) <= TOKEN_MAX
        or not token.isascii()
        or not all(0x21 <= ord(char) <= 0x7E for char in token)
    ):
        raise ConfigurationError(
            f"The HTTP credential is invalid: {TOKEN_MIN} to {TOKEN_MAX} printable "
            "ASCII characters without whitespace are required."
        )
    return token


def load_http_settings(
    *,
    host: str | None,
    port: int | None,
    allowed_hosts: Sequence[str],
    allowed_origins: Sequence[str],
    token_file: str | None,
    operation_timeout_seconds: float,
    environ: Mapping[str, str] | None = None,
) -> HTTPServiceSettings:
    """Validate everything before any listener is opened or device contacted."""
    env = os.environ if environ is None else environ
    bind_host = DEFAULT_HOST if host is None else host
    bind_port = DEFAULT_PORT if port is None else port
    if not _valid_host(bind_host):
        raise ConfigurationError("Invalid --host value.")
    if not 1 <= bind_port <= 65535:
        raise ConfigurationError("Invalid --port value.")
    explicit_hosts = _normalize_hosts(allowed_hosts)
    origins = _normalize_origins(allowed_origins)
    if explicit_hosts:
        hosts = explicit_hosts
    elif bind_host in LOOPBACK_HOSTS and bind_port == DEFAULT_PORT:
        hosts = frozenset({f"127.0.0.1:{DEFAULT_PORT}", f"localhost:{DEFAULT_PORT}"})
    else:
        raise ConfigurationError(
            "A changed bind address or port requires an explicit --allowed-host entry."
        )
    token = _resolve_token(token_file, env)
    return HTTPServiceSettings(
        host=bind_host,
        port=bind_port,
        allowed_hosts=hosts,
        allowed_origins=origins,
        token_digest=token_digest(token),
        graceful_shutdown_seconds=math.ceil(operation_timeout_seconds) + 2,
    )
