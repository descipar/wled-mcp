"""Installed console entry point. stdout is reserved for the SDK."""

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Never

import anyio

from wled_mcp import __version__
from wled_mcp.config import ConfigurationError, StartupConfig, load_config
from wled_mcp.http_config import TOKEN_ENV, HTTPServiceSettings, load_http_settings
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server, serve_stdio


async def serve(config: StartupConfig) -> None:
    async with Resources(config) as resources:
        await serve_stdio(create_server(build_operations(resources)))


async def serve_http(config: StartupConfig, settings: HTTPServiceSettings) -> None:
    # Imported lazily: the default stdio path never loads the HTTP stack.
    from wled_mcp.http_service import HTTPService, announce, build_http_app

    async with Resources(config) as resources:
        app = build_http_app(create_server(build_operations(resources)), settings)
        await HTTPService(app, settings, on_started=announce(settings)).serve()


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        self.exit(2, "Invalid command-line arguments. Use --help for supported options.\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = SafeParser(description="WLED MCP inventory service.", allow_abbrev=False)
    parser.add_argument("--version", action="version", version=f"wled-mcp {__version__}")
    parser.add_argument("--config", help="Absolute TOML configuration path (WLED_MCP_CONFIG).")
    parser.add_argument("--data-dir", help="Absolute existing data directory (WLED_MCP_DATA_DIR).")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    http = parser.add_argument_group("streamable-http options")
    http.add_argument("--host", help="Bind address (default 127.0.0.1).")
    http.add_argument("--port", type=int, help="Bind port (default 8000).")
    http.add_argument(
        "--allowed-host",
        action="append",
        help="Exact Host authority host[:port]; repeatable. Required when bind changes.",
    )
    http.add_argument(
        "--allowed-origin",
        action="append",
        help="Exact browser Origin scheme://host[:port]; repeatable. Default: none.",
    )
    http.add_argument(
        "--http-token-file",
        help=f"Absolute path of the bearer credential file (or environment {TOKEN_ENV}).",
    )
    args = parser.parse_args(argv)
    http_given = any(
        value is not None
        for value in (
            args.host,
            args.port,
            args.allowed_host,
            args.allowed_origin,
            args.http_token_file,
        )
    )
    settings: HTTPServiceSettings | None = None
    try:
        config = load_config(args.config, args.data_dir)
        if args.transport == "streamable-http":
            settings = load_http_settings(
                host=args.host,
                port=args.port,
                allowed_hosts=args.allowed_host or [],
                allowed_origins=args.allowed_origin or [],
                token_file=args.http_token_file,
                operation_timeout_seconds=config.http.operation_timeout_seconds,
            )
        elif http_given:
            raise ConfigurationError("HTTP options require --transport streamable-http.")
    except ConfigurationError as exc:
        print(f"Startup configuration error: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        if settings is None:
            anyio.run(serve, config)
        else:
            anyio.run(serve_http, config, settings)
    except KeyboardInterrupt:
        return 0
    except SystemExit:
        # uvicorn exits this way when it cannot bind or its lifespan fails to start.
        print("HTTP service failed to start.", file=sys.stderr)
        return 1
    except Exception:
        print("MCP server stopped after an internal failure.", file=sys.stderr)
        return 1
    return 0
