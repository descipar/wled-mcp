"""Strict, read-only startup configuration for the bootstrap profile."""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """A safe message suitable for startup diagnostics."""


@dataclass(frozen=True)
class StartupConfig:
    config_path: Path
    data_dir: Path


def load_config(
    config_path: str | None,
    data_dir: str | None,
    environ: Mapping[str, str] | None = None,
) -> StartupConfig:
    """Validate supported settings without creating files or contacting devices."""
    env = os.environ if environ is None else environ
    raw_config = config_path if config_path is not None else env.get("WLED_MCP_CONFIG")
    raw_data = data_dir if data_dir is not None else env.get("WLED_MCP_DATA_DIR")
    if not raw_config or not raw_data:
        raise ConfigurationError(
            "Both --config and --data-dir paths are required "
            "(or their WLED_MCP environment variables)."
        )
    try:
        config = Path(raw_config)
        data = Path(raw_data)
        if not config.is_absolute() or not data.is_absolute():
            raise ConfigurationError("Configuration and data directory paths must be absolute.")
        if not data.is_dir():
            raise ConfigurationError("The data directory must already exist and be a directory.")
        with config.open("rb") as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            raise ConfigurationError("Configuration exceeds the 64 KiB bootstrap limit.")
        parsed = tomllib.loads(content.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError("Cannot read a valid UTF-8 TOML configuration.") from None
    if set(parsed) != {"schema_version", "devices"}:
        raise ConfigurationError(
            "Bootstrap supports only schema_version and an empty devices array; "
            "inventory settings require issue #4."
        )
    if type(parsed["schema_version"]) is not int or parsed["schema_version"] != 1:
        raise ConfigurationError("Unsupported configuration schema_version; expected integer 1.")
    if not isinstance(parsed["devices"], list) or parsed["devices"]:
        raise ConfigurationError(
            "Bootstrap requires devices = []; device inventory support belongs to issue #4."
        )
    return StartupConfig(config.resolve(), data.resolve())
