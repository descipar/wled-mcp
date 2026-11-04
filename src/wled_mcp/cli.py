"""Installed console entry point. stdout is reserved for the SDK."""

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Never

import anyio

from wled_mcp import __version__
from wled_mcp.config import ConfigurationError, StartupConfig, load_config
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server, serve_stdio


async def serve(config: StartupConfig) -> None:
    async with Resources(config) as resources:
        await serve_stdio(create_server(build_operations(resources)))


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        self.exit(2, "Invalid command-line arguments. Use --help for supported options.\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = SafeParser(description="WLED MCP inventory service.")
    parser.add_argument("--version", action="version", version=f"wled-mcp {__version__}")
    parser.add_argument("--config", help="Absolute TOML configuration path (WLED_MCP_CONFIG).")
    parser.add_argument("--data-dir", help="Absolute existing data directory (WLED_MCP_DATA_DIR).")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, args.data_dir)
        if args.transport == "streamable-http":
            raise ConfigurationError(
                "Streamable HTTP is not implemented yet; authenticated service support "
                "is tracked by issue #14. Use --transport stdio."
            )
    except ConfigurationError as exc:
        print(f"Startup configuration error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        anyio.run(serve, config)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("MCP server stopped after an internal failure.", file=sys.stderr)
        return 1
    return 0
