"""Validated, immutable inventory; startup never probes configured controllers."""

import ipaddress
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# ASCII DNS names; labels may contain interior "_" (DHCP-derived names) or "-", but each
# label is 1-63 characters and starts and ends with a letter or digit (ISSUE-61-DEC-002).
_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?")
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?")
# WHATWG "ends in a number": such a host is read as an IPv4 address, so it must be a
# canonical dotted quad; resolvers would otherwise map 1.2.3, 0x7f.1 or 2130706433 to a
# different address (ISSUE-74-DEC-002).
_NUMERIC_LABEL = re.compile(r"[0-9]+|0[xX][0-9a-fA-F]*")
_DEVICE_FIELDS = ("id", "name", "base_url")
_MAX_LOCATORS = 5
SCHEMA_VERSION = 1


class ConfigurationError(ValueError):
    """A safe message suitable for startup diagnostics."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Device(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=128)
    base_url: str

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Invalid device name")
        return value

    @field_validator("base_url")
    @classmethod
    def valid_root(cls, value: str) -> str:
        if len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError("Invalid device URL")
        if any(c in value for c in ("?", "#", "\\", "%")):
            raise ValueError("Invalid device URL")
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.username is not None
            or parts.password is not None
            or parts.path not in {"", "/"}
            or not parts.hostname
            or parts.netloc.endswith(":")
        ):
            raise ValueError("Expected a credential-free HTTP(S) root URL")
        host = parts.hostname
        if ":" in host:
            ipaddress.IPv6Address(host)
        elif _NUMERIC_LABEL.fullmatch(host.rsplit(".", 1)[-1]):
            try:
                ipaddress.IPv4Address(host)
            except ValueError:
                raise ValueError("Invalid host") from None
        elif not _HOST.fullmatch(host) or not all(
            _HOST_LABEL.fullmatch(label) for label in host.split(".")
        ):
            raise ValueError("Invalid host")
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError("Invalid port")
        return value.rstrip("/")


class HTTPSettings(StrictModel):
    connect_timeout_seconds: float = Field(default=3, ge=0.05, le=30, allow_inf_nan=False)
    operation_timeout_seconds: float = Field(default=10, ge=0.05, le=120, allow_inf_nan=False)
    read_retries: int = Field(default=1, ge=0, le=1)
    max_request_bytes: int = Field(default=65536, ge=128, le=1048576)
    max_response_bytes: int = Field(default=2097152, ge=128, le=8388608)
    catalog_cache_seconds: int = Field(default=300, ge=0, le=86400)


class BackupSettings(StrictModel):
    retain_per_device: int = Field(default=20, ge=1, le=1000)


class FeatureSettings(StrictModel):
    raw_state_patch: bool = False

    @field_validator("raw_state_patch")
    @classmethod
    def disabled(cls, value: bool) -> bool:
        if value:
            raise ValueError("Raw state patch is not supported")
        return value


class InventoryConfig(StrictModel):
    schema_version: int
    devices: list[Device] = Field(max_length=256)
    http: HTTPSettings = HTTPSettings()
    backups: BackupSettings = BackupSettings()
    features: FeatureSettings = FeatureSettings()

    @field_validator("schema_version")
    @classmethod
    def version_one(cls, value: int) -> int:
        if value != SCHEMA_VERSION:
            raise ValueError("Unsupported schema version")
        return value

    @field_validator("devices")
    @classmethod
    def unique_ids(cls, devices: list[Device]) -> list[Device]:
        if len({device.id for device in devices}) != len(devices):
            raise ValueError("Duplicate device IDs")
        return devices


@dataclass(frozen=True)
class StartupConfig:
    config_path: Path
    data_dir: Path
    devices: tuple[Device, ...] = ()
    http: HTTPSettings = HTTPSettings()
    backups: BackupSettings = BackupSettings()


MAX_CONFIG_BYTES = 65536
_GENERIC_INVALID = (
    "Invalid inventory configuration{located}: check schema version, unique device "
    "IDs, credential-free HTTP(S) root URLs and supported settings."
)


def validate_document(content: bytes) -> InventoryConfig:
    """Validate complete configuration bytes exactly as startup does (issue #16, TD-16-4).

    Shared by ``load_config``, ``wled-mcp config validate``/``add-device`` and
    ``doctor``: the same 64 KiB bound, schema-version naming and positional, value-free
    messages. Never reads or writes a file.
    """
    if len(content) > MAX_CONFIG_BYTES:
        raise ConfigurationError("Configuration exceeds the 64 KiB limit.")
    try:
        parsed = tomllib.loads(content.decode("utf-8"))
        _check_schema_version(parsed.get("schema_version"))
        return InventoryConfig.model_validate(parsed)
    except (ValueError, UnicodeError, ValidationError, RecursionError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        located = _device_locators(exc) if isinstance(exc, ValidationError) else ""
        raise ConfigurationError(_GENERIC_INVALID.format(located=located)) from None


def load_config(
    config_path: str | None,
    data_dir: str | None,
    environ: Mapping[str, str] | None = None,
) -> StartupConfig:
    """Validate the entire configuration before creating any device request."""
    env = os.environ if environ is None else environ
    raw_config = config_path if config_path is not None else env.get("WLED_MCP_CONFIG")
    raw_data = data_dir if data_dir is not None else env.get("WLED_MCP_DATA_DIR")
    if not raw_config or not raw_data:
        raise ConfigurationError(
            "Both --config and --data-dir paths are required "
            "(or their WLED_MCP environment variables)."
        )
    try:
        config, data = Path(raw_config), Path(raw_data)
        if not config.is_absolute() or not data.is_absolute():
            raise ConfigurationError("Configuration and data directory paths must be absolute.")
        if not data.is_dir():
            raise ConfigurationError("The data directory must already exist and be a directory.")
        with config.open("rb") as stream:
            content = stream.read(MAX_CONFIG_BYTES + 1)
    except (OSError, ValueError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(_GENERIC_INVALID.format(located="")) from None
    validated = validate_document(content)
    return StartupConfig(
        config.resolve(),
        data.resolve(),
        tuple(validated.devices),
        validated.http,
        validated.backups,
    )


def _check_schema_version(version: object) -> None:
    """Name an unsupported integer ``schema_version`` (issue #21, TD-21-5).

    Only an integer from 0 to 9999 is echoed (as for snapshots); any other value keeps
    the generic message, which never quotes file content. The file is only read, never
    rewritten.
    """
    if type(version) is not int or version == SCHEMA_VERSION or not 0 <= version <= 9999:
        return
    message = (
        f"Unsupported inventory configuration schema_version {version}; this server reads "
        f"schema_version {SCHEMA_VERSION}."
    )
    if version > SCHEMA_VERSION:
        message += (
            " The file was written for a newer server version; after a downgrade, use the "
            "configuration kept for this version (docs/contract/versioning.md)."
        )
    raise ConfigurationError(message)


def _device_locators(exc: ValidationError) -> str:
    """Name offending device entries from error locations only, never from values or text.

    The zero-based index follows the ``[[devices]]`` order. Unknown keys are reported
    without their name because keys are file content.
    """
    found: set[tuple[int, int, str]] = set()
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        loc = error["loc"]
        if len(loc) < 2 or loc[0] != "devices" or type(loc[1]) is not int:
            continue
        index = loc[1]
        field = loc[2] if len(loc) > 2 else None
        if field is None:
            order, text = -1, f"devices[{index}]: invalid"
        elif field in _DEVICE_FIELDS:
            category = "missing" if error["type"] == "missing" else "invalid"
            order, text = _DEVICE_FIELDS.index(field), f"devices[{index}].{field}: {category}"
        else:
            order, text = len(_DEVICE_FIELDS), f"devices[{index}]: unsupported field"
        found.add((index, order, text))
    if not found:
        return ""
    texts = [text for _, _, text in sorted(found)]
    shown = ", ".join(texts[:_MAX_LOCATORS])
    if len(texts) > _MAX_LOCATORS:
        shown += f" and {len(texts) - _MAX_LOCATORS} more"
    return f" ({shown})"
