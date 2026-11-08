"""Installed console entry point. stdout is reserved for the SDK while serving.

Without a subcommand the console serves MCP exactly as before. The subcommands of
issue #16 (``config init|add-device|validate``, ``doctor`` and ``discover``,
docs/contract/cli.md) run as separate processes, never serve and write their result
to stdout.
"""

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import Never

import anyio

from wled_mcp import __version__, discovery, doctor, setup
from wled_mcp.access import PROFILE_NAMES
from wled_mcp.config import ConfigurationError, StartupConfig, load_config
from wled_mcp.diagnostics import LogSettings, configure_logging, load_log_settings
from wled_mcp.http_config import TOKEN_ENV, HTTPServiceSettings, load_http_settings
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server, serve_stdio

log = logging.getLogger("wled_mcp")


def announce_profile(config: StartupConfig, transport: str) -> None:
    """One startup event with the effective profile and the number of capped devices."""
    log.info(
        "service starting: transport=%s profile=%s capped_devices=%d",
        transport,
        config.access.profile,
        len(config.access.caps),
    )


def attach_monitor(
    resources: Resources, transport: str, backups_writable: bool | None = None
) -> None:
    """Tell the status tool which transport serves and what the startup check found.

    ``backups_writable`` is the result of the one startup check made by ``main``; without
    it (a caller that did not check) the check runs here once.
    """
    resources.monitor.transport = transport
    resources.monitor.backups_writable = (
        setup.backups_writable(resources.config.data_dir)
        if backups_writable is None
        else backups_writable
    )


async def serve(config: StartupConfig, backups_writable: bool | None = None) -> None:
    announce_profile(config, "stdio")
    async with Resources(config) as resources:
        attach_monitor(resources, "stdio", backups_writable)
        server = create_server(build_operations(resources), config.access, resources.monitor)
        await serve_stdio(server)


async def serve_http(
    config: StartupConfig, settings: HTTPServiceSettings, backups_writable: bool | None = None
) -> None:
    # Imported lazily: the default stdio path never loads the HTTP stack.
    from wled_mcp.http_service import HTTPService, announce, build_http_app

    announce_profile(config, "streamable-http")
    async with Resources(config) as resources:
        attach_monitor(resources, "streamable-http", backups_writable)
        server = create_server(build_operations(resources), config.access, resources.monitor)
        app = build_http_app(server, settings)
        await HTTPService(app, settings, on_started=announce(settings)).serve()


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        self.exit(2, "Invalid command-line arguments. Use --help for supported options.\n")


BACKUPS_ADVISORY = (
    "Warning: the backups location in the data directory is not writable; the server "
    "starts, but writes that take a snapshot fail with BACKUP_FAILED. "
    "Run `wled-mcp doctor` for details."
)
SUBCOMMANDS = ("config", "doctor", "discover")


def build_parser() -> SafeParser:
    """The complete ``wled-mcp`` parser: serve options plus the #16 subcommands."""
    parser = SafeParser(description="WLED MCP inventory service.", allow_abbrev=False)
    parser.add_argument("--version", action="version", version=f"wled-mcp {__version__}")
    parser.add_argument("--config", help="Absolute TOML configuration path (WLED_MCP_CONFIG).")
    parser.add_argument("--data-dir", help="Absolute existing data directory (WLED_MCP_DATA_DIR).")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument(
        "--profile",
        choices=PROFILE_NAMES,
        help="Access profile: read-only, control or full (default: [access] profile, else full).",
    )
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
    commands = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
        title="setup and diagnostics (without a command: serve MCP)",
    )
    setup.register(commands)
    doctor.register(commands)
    discovery.register(commands)
    return parser


def run_subcommand(args: argparse.Namespace) -> int:
    """Dispatch one subcommand; unexpected failures exit 3 without a traceback."""
    try:
        if args.command == "doctor":
            return doctor.run(args, os.environ)
        if args.command == "discover":
            return setup.run(discovery.handler, "discover", args, os.environ)
        handler = setup.HANDLERS[args.config_command]
        return setup.run(handler, f"config {args.config_command}", args, os.environ)
    except Exception:
        print(f"wled-mcp {args.command}: internal failure.", file=sys.stderr)
        return setup.EXIT_INTERNAL


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(arguments)
    if args.command is not None:
        # Serve options before a subcommand are a usage error (TD-16-1).
        if arguments[0] != args.command:
            parser.error("serve options combined with a subcommand")
        return run_subcommand(args)
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
    log_settings = LogSettings()
    try:
        log_settings = load_log_settings(os.environ)
        config = load_config(args.config, args.data_dir, profile=args.profile)
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
    configure_logging(log_settings)
    writable = setup.backups_writable(config.data_dir)
    if not writable:
        # OPS-04 (TD-16-7): advisory only; tool-level BACKUP_FAILED stays fail-closed.
        print(BACKUPS_ADVISORY, file=sys.stderr)
    try:
        if settings is None:
            anyio.run(serve, config, writable)
        else:
            anyio.run(serve_http, config, settings, writable)
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
