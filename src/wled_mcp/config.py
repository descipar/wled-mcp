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
        elif not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
            raise ValueError("Invalid host")
        elif any(
            not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
            for label in host.split(".")
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
        if value != 1:
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
            content = stream.read(65537)
        if len(content) > 65536:
            raise ConfigurationError("Configuration exceeds the 64 KiB limit.")
        parsed = tomllib.loads(content.decode("utf-8"))
        validated = InventoryConfig.model_validate(parsed)
    except (OSError, ValueError, UnicodeError, ValidationError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(
            "Invalid inventory configuration: check schema version, unique device IDs, "
            "credential-free HTTP(S) root URLs and supported settings."
        ) from None
    return StartupConfig(
        config.resolve(),
        data.resolve(),
        tuple(validated.devices),
        validated.http,
        validated.backups,
    )
