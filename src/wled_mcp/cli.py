"""Installed console entry point. stdout is reserved for the SDK."""

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Never

from wled_mcp import __version__
from wled_mcp.config import ConfigurationError, load_config
from wled_mcp.server import create_server, run_stdio


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        self.exit(2, "Invalid command-line arguments. Use --help for supported options.\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = SafeParser(description="WLED MCP bootstrap (device tools follow in later issues).")
    parser.add_argument("--version", action="version", version=f"wled-mcp {__version__}")
    parser.add_argument("--config", help="Absolute TOML configuration path (WLED_MCP_CONFIG).")
    parser.add_argument("--data-dir", help="Absolute existing data directory (WLED_MCP_DATA_DIR).")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    args = parser.parse_args(argv)
    try:
        load_config(args.config, args.data_dir)
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
        run_stdio(create_server())
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("MCP server stopped after an internal failure.", file=sys.stderr)
        return 1
    return 0
