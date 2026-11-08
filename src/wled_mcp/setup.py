"""``wled-mcp config`` commands: init, add-device and validate (issue #16).

Contract: docs/contract/cli.md. The commands write only the selected configuration
file (atomically: temporary file in the same directory, fsync, ``os.replace``), never
create the data directory, generate or store a credential, or contact a device or the
network. Results go to stdout (a separate process from stdio serving); messages never
contain a URL, credential or path.
"""

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from wled_mcp.config import (
    MAX_CONFIG_BYTES,
    ConfigurationError,
    InventoryConfig,
    access_facts,
    access_line,
    validate_document,
)

CONFIG_ENV = "WLED_MCP_CONFIG"
DATA_ENV = "WLED_MCP_DATA_DIR"
JSON_SCHEMA_VERSION = 1

EXIT_OK, EXIT_PROBLEM, EXIT_USAGE, EXIT_INTERNAL = 0, 1, 2, 3

Format = Literal["text", "json"]

# A root-level empty inline array, the form `config init` writes for zero devices.
_EMPTY_DEVICES = re.compile(r"[ \t]*devices[ \t]*=[ \t]*\[[ \t]*\][ \t]*(#[^\n]*)?\r?\n?")
_TABLE_HEADER = re.compile(r"[ \t]*\[")
_DEVICES_ASSIGNMENT = re.compile(r"[ \t]*devices[ \t]*=")

_TEMPLATE_HEADER = (
    "# WLED MCP inventory configuration (schema 1), written by `wled-mcp config init`.\n"
    "# Check every edit with `wled-mcp config validate`, then restart the server\n"
    "# (docs/DEPLOYMENT.md). Never put credentials in this file.\n"
    "schema_version = 1\n"
)


class UsageError(Exception):
    """A missing or contradictory command-line value (exit 2)."""


@dataclass
class CommandResult:
    """One subcommand result; ``data`` is printed as JSON, ``lines`` as text."""

    command: str
    exit_code: int
    lines: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def render(self, output: Format) -> str:
        if output == "json":
            document = {
                "schema_version": JSON_SCHEMA_VERSION,
                "command": self.command,
                "ok": self.exit_code == EXIT_OK,
                **self.data,
            }
            return json.dumps(document, ensure_ascii=False, sort_keys=True)
        return "\n".join(self.lines)


def emit(result: CommandResult, output: Format) -> int:
    sys.stdout.write(result.render(output) + "\n")
    sys.stdout.flush()
    return result.exit_code


# -- paths ---------------------------------------------------------------------


def option_path(value: str | None, env_name: str, environ: Mapping[str, str]) -> str | None:
    """Flag first, then the same environment variable the server reads (TD-16-2)."""
    if value is not None:
        return value
    return environ.get(env_name) or None


def backups_writable(data_dir: Path, access: Callable[[Path, int], bool] | None = None) -> bool:
    """Advisory: can the server create ``<data-dir>/backups`` snapshots?

    Mirrors ``SnapshotStore.plan_backup``: the nearest existing path is checked with
    ``os.access``; nothing is created. A non-directory ``backups`` entry is unusable,
    and so is a location that cannot even be inspected (for example a data directory
    the user cannot search): any ``OSError`` counts as "not writable".
    """
    check = access if access is not None else os.access
    probe = data_dir / "backups"
    try:
        if probe.exists() and not probe.is_dir():
            return False
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        return bool(check(probe, os.W_OK | os.X_OK))
    except OSError:
        return False


def data_dir_usable(data_dir: Path) -> bool:
    """The directory exists and is a directory; an inaccessible one counts as unusable."""
    try:
        return data_dir.is_dir()
    except OSError:
        return False


# -- TOML rendering --------------------------------------------------------------

_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f"}
_ESCAPES["\r"] = "\\r"


def toml_string(value: str) -> str:
    """A TOML basic string; round-trip-checked so a rendering bug fails closed."""
    parts: list[str] = []
    for char in value:
        if char in _ESCAPES:
            parts.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            parts.append(f"\\u{ord(char):04X}")
        else:
            parts.append(char)
    rendered = '"' + "".join(parts) + '"'
    if tomllib.loads(f"v = {rendered}")["v"] != value:
        raise ValueError("TOML string rendering did not round-trip")
    return rendered


def device_block(device_id: str, name: str, base_url: str) -> str:
    return (
        "\n[[devices]]\n"
        f"id = {toml_string(device_id)}\n"
        f"name = {toml_string(name)}\n"
        f"base_url = {toml_string(base_url)}\n"
    )


def initial_document(device: tuple[str, str, str] | None) -> str:
    if device is None:
        return _TEMPLATE_HEADER + "devices = []\n"
    return _TEMPLATE_HEADER + device_block(*device)


def append_device(original: str, block: str) -> str:
    """Append one ``[[devices]]`` block, preserving every existing byte.

    Exception: a root-level empty ``devices = []`` line (written by ``config init`` for
    zero devices) cannot coexist with ``[[devices]]`` tables and is removed.
    """
    lines = original.splitlines(keepends=True)
    root_end = next(
        (index for index, line in enumerate(lines) if _TABLE_HEADER.match(line)), len(lines)
    )
    empty = [index for index in range(root_end) if _EMPTY_DEVICES.fullmatch(lines[index])]
    if len(empty) == 1:
        del lines[empty[0]]
    text = "".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + block


def url_identity(url: str) -> tuple[str, str, int]:
    """Normalized scheme, host and effective port of an already validated root URL."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    port = parts.port or (443 if scheme == "https" else 80)
    return scheme, (parts.hostname or "").lower(), port


# -- atomic write ----------------------------------------------------------------


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":  # directories cannot be opened for fsync on Windows
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(
    target: Path,
    content: bytes,
    mode: int | None,
    before_replace: Callable[[], None] | None = None,
) -> None:
    """Temporary file in the target directory, fsync, then ``os.replace``.

    ``mode`` is applied to the temporary file (``None``: 0600 for a new file).
    ``before_replace`` may raise to abort; the temporary file is then removed and the
    target stays untouched. Once ``os.replace`` succeeded the new content is in place;
    the directory fsync that follows is best-effort (some filesystems do not support
    it), so its failure is not reported as a failed write.
    """
    fd, temporary = tempfile.mkstemp(prefix=".wled-mcp-config-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(temporary, 0o600 if mode is None else stat.S_IMODE(mode))
        if before_replace is not None:
            before_replace()
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    try:
        _fsync_directory(target.parent)
    except OSError:
        pass


# -- commands --------------------------------------------------------------------


class Refusal(Exception):
    """A refused command (exit 1) with a safe code and message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _require_absolute(raw: str | None, flag: str, env_name: str) -> Path:
    if raw is None:
        raise UsageError(f"{flag} (or {env_name}) is required.")
    path = Path(raw)
    if not path.is_absolute():
        raise Refusal("PATH_NOT_ABSOLUTE", f"The {flag} path must be absolute.")
    return path


def _device_values(args: argparse.Namespace, required: bool) -> tuple[str, str, str] | None:
    values = (args.device_id, args.device_name, args.base_url)
    given = [value is not None for value in values]
    if not any(given) and not required:
        return None
    if not all(given):
        raise UsageError("--device-id, --device-name and --base-url are required together.")
    device_id, name, base_url = values
    assert device_id is not None and name is not None and base_url is not None
    for value in (device_id, name, base_url):
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise Refusal("INVALID_TEXT", "Device values must be valid Unicode text.") from None
    return device_id, name, base_url


def _validated(content: str, what: str) -> InventoryConfig:
    try:
        return validate_document(content.encode("utf-8"))
    except ConfigurationError as exc:
        raise Refusal("CONFIG_INVALID", f"{what}: {exc}") from None


def _read_regular(path: Path) -> tuple[bytes, os.stat_result]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise Refusal("CONFIG_NOT_FOUND", "The configuration file does not exist.") from None
    except OSError:
        raise Refusal("CONFIG_UNREADABLE", "The configuration file could not be read.") from None
    if stat.S_ISLNK(info.st_mode):
        raise Refusal("SYMLINK_REFUSED", "The configuration path is a symbolic link.")
    if not stat.S_ISREG(info.st_mode):
        raise Refusal("NOT_A_FILE", "The configuration path is not a regular file.")
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_CONFIG_BYTES + 1)
    except OSError:
        raise Refusal("CONFIG_UNREADABLE", "The configuration file could not be read.") from None
    return content, info


def _check_parent(parent: Path, access: Callable[[Path, int], bool] | None = None) -> None:
    """The target's directory must exist and be writable; say which one failed."""
    try:
        info = parent.stat()
    except (FileNotFoundError, NotADirectoryError):
        raise Refusal(
            "PARENT_MISSING", "The directory of the configuration path does not exist."
        ) from None
    except OSError:
        raise Refusal(
            "PARENT_INACCESSIBLE",
            "The directory of the configuration path exists but could not be accessed.",
        ) from None
    if not stat.S_ISDIR(info.st_mode):
        raise Refusal(
            "PARENT_MISSING", "The directory of the configuration path is not a directory."
        )
    check = access if access is not None else os.access
    if not check(parent, os.W_OK | os.X_OK):
        raise Refusal(
            "PARENT_INACCESSIBLE",
            "The directory of the configuration path is not writable for this user.",
        )


def _inline_devices(text: str) -> bool:
    """A root-level ``devices = ...`` assignment (an inline array, not tables)."""
    for line in text.splitlines():
        if _TABLE_HEADER.match(line):
            return False
        if _DEVICES_ASSIGNMENT.match(line):
            return True
    return False


def config_init(args: argparse.Namespace, environ: Mapping[str, str]) -> CommandResult:
    command = "config init"
    target = _require_absolute(
        option_path(args.config, CONFIG_ENV, environ), "--config", CONFIG_ENV
    )
    device = _device_values(args, required=False)
    document = initial_document(device)
    validated = _validated(document, "The new configuration would be invalid")
    _check_parent(target.parent)
    mode: int | None = None
    try:
        existing = target.lstat()
    except FileNotFoundError:
        existing = None
    if existing is not None:
        if stat.S_ISLNK(existing.st_mode):
            raise Refusal("SYMLINK_REFUSED", "The configuration path is a symbolic link.")
        if not stat.S_ISREG(existing.st_mode):
            raise Refusal("NOT_A_FILE", "The configuration path is not a regular file.")
        if not args.force:
            raise Refusal(
                "TARGET_EXISTS",
                "The configuration file already exists; it was left unchanged. "
                "Use --force to replace it.",
            )
        mode = existing.st_mode
    atomic_write(target, document.encode("utf-8"), mode)
    count = len(validated.devices)
    return CommandResult(
        command,
        EXIT_OK,
        [
            f"Wrote a schema 1 inventory configuration with {count} device(s).",
            "Next: `wled-mcp config validate` with the same --config, then start the server.",
        ],
        {"written": True, "replaced": existing is not None, "device_count": count},
    )


def config_add_device(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    before_replace: Callable[[], None] | None = None,
) -> CommandResult:
    command = "config add-device"
    target = _require_absolute(
        option_path(args.config, CONFIG_ENV, environ), "--config", CONFIG_ENV
    )
    device = _device_values(args, required=True)
    assert device is not None
    original, info = _read_regular(target)
    try:
        current = validate_document(original)
    except ConfigurationError as exc:
        raise Refusal("CONFIG_INVALID", f"The existing configuration is invalid: {exc}") from None
    device_id, name, base_url = device
    if any(existing.id == device_id for existing in current.devices):
        raise Refusal("DUPLICATE_ID", "A device with this ID is already configured.")
    text = original.decode("utf-8")
    candidate = append_device(text, device_block(device_id, name, base_url))
    try:
        validated = _validated(candidate, "The configuration with the new device would be invalid")
    except Refusal:
        if _inline_devices(append_device(text, "")):
            raise Refusal(
                "INLINE_DEVICES_ARRAY",
                "The configuration lists its devices as an inline array "
                "(devices = [...]); config add-device can only append [[devices]] "
                "tables. Rewrite the existing entries as [[devices]] tables first.",
            ) from None
        raise
    added = validated.devices[-1]
    if any(url_identity(d.base_url) == url_identity(added.base_url) for d in current.devices):
        raise Refusal("DUPLICATE_URL", "A device with an equal base URL is already configured.")

    def unchanged() -> None:
        latest, latest_info = _read_regular(target)
        if latest != original or latest_info.st_ino != info.st_ino:
            raise Refusal(
                "CONFIG_CHANGED",
                "The configuration file changed while the device was being added; "
                "nothing was written. Run the command again.",
            )
        if before_replace is not None:
            before_replace()

    atomic_write(target, candidate.encode("utf-8"), info.st_mode, unchanged)
    count = len(validated.devices)
    return CommandResult(
        command,
        EXIT_OK,
        [
            f"Added devices[{count - 1}]; the configuration now lists {count} device(s).",
            "Next: `wled-mcp config validate`, then restart the server to load the change.",
        ],
        {"written": True, "device_index": count - 1, "device_count": count},
    )


def config_validate(args: argparse.Namespace, environ: Mapping[str, str]) -> CommandResult:
    command = "config validate"
    target = _require_absolute(
        option_path(args.config, CONFIG_ENV, environ), "--config", CONFIG_ENV
    )
    raw_data = option_path(args.data_dir, DATA_ENV, environ)
    if args.check_backups and raw_data is None:
        raise UsageError("--check-backups requires --data-dir (or WLED_MCP_DATA_DIR).")
    problems: list[dict[str, str]] = []
    count: int | None = None
    access: dict[str, str | int] | None = None
    try:
        content, _ = _read_regular(target)
        validated = validate_document(content)
        count = len(validated.devices)
        access = access_facts(validated)
    except Refusal as refusal:
        problems.append({"code": refusal.code, "message": refusal.message})
    except ConfigurationError as exc:
        problems.append({"code": "CONFIG_INVALID", "message": str(exc)})
    backups: bool | None = None
    if raw_data is not None:
        data = Path(raw_data)
        if not data.is_absolute():
            problems.append(
                {
                    "code": "DATA_DIR_NOT_ABSOLUTE",
                    "message": "The --data-dir path must be absolute.",
                }
            )
        elif not data_dir_usable(data):
            problems.append(
                {
                    "code": "DATA_DIR_NOT_FOUND",
                    "message": "The data directory must already exist, be a directory and "
                    "be accessible.",
                }
            )
        elif args.check_backups:
            backups = backups_writable(data)
            if not backups:
                problems.append(
                    {
                        "code": "BACKUPS_NOT_WRITABLE",
                        "message": "The backups location in the data directory is not "
                        "writable; snapshot-taking writes would fail with BACKUP_FAILED.",
                    }
                )
    if problems:
        lines = ["Configuration check failed:"] + [f"- {p['message']}" for p in problems]
        exit_code = EXIT_PROBLEM
    else:
        lines = [f"Configuration valid: schema 1, {count} device(s)."]
        if access is not None:
            lines.append(access_line(access))
        if raw_data is not None:
            lines.append("Data directory exists.")
        if backups:
            lines.append("Backups location is writable (advisory check, nothing created).")
        lines.append("Restart a running server to load a changed configuration.")
        exit_code = EXIT_OK
    data_out: dict[str, Any] = {"device_count": count, "problems": problems}
    if access is not None and not problems:
        data_out["access"] = access
    if backups is not None:
        data_out["backups_writable"] = backups
    return CommandResult(command, exit_code, lines, data_out)


Handler = Callable[[argparse.Namespace, Mapping[str, str]], CommandResult]


def run(
    handler: Handler, command: str, args: argparse.Namespace, environ: Mapping[str, str]
) -> int:
    """Map refusals and usage problems to the documented exit codes (TD-16-1)."""
    output: Format = args.format
    try:
        result = handler(args, environ)
    except UsageError as exc:
        print(f"Invalid command-line arguments: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Refusal as refusal:
        result = CommandResult(
            command,
            EXIT_PROBLEM,
            [f"{command}: {refusal.message}"],
            {"written": False, "problems": [{"code": refusal.code, "message": refusal.message}]}
            if command != "config validate"
            else {"problems": [{"code": refusal.code, "message": refusal.message}]},
        )
    except (OSError, UnicodeError) as exc:
        code, message = _unexpected_failure(command, exc)
        data: dict[str, Any] = {"problems": [{"code": code, "message": message}]}
        if command != "config validate":
            data["written"] = False
        result = CommandResult(command, EXIT_PROBLEM, [f"{command}: {message}"], data)
    return emit(result, output)


def _unexpected_failure(command: str, exc: BaseException) -> tuple[str, str]:
    """A per-command code for an unexpected I/O or text error (never its text)."""
    if isinstance(exc, UnicodeError):
        return "INVALID_TEXT", "The input is not valid Unicode text; nothing was written."
    if command == "config validate":
        return "CHECK_FAILED", "The configuration could not be checked (file system error)."
    if command == "discover":
        return "DISCOVERY_FAILED", "Discovery failed with a system error; nothing was written."
    return "WRITE_FAILED", "The configuration file could not be written; it was left unchanged."


def add_format_option(parser: Any) -> None:
    """``--format``; ``parser`` may also be a mutually exclusive group."""
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format (text)."
    )


def register(commands: Any) -> None:
    """Add ``config init|add-device|validate`` to the ``wled-mcp`` subcommands."""
    config = commands.add_parser(
        "config", help="Write or check the inventory configuration.", allow_abbrev=False
    )
    actions = config.add_subparsers(dest="config_command", metavar="ACTION", required=True)

    init = actions.add_parser(
        "init", help="Write a new schema 1 configuration file.", allow_abbrev=False
    )
    init.add_argument("--config", help="Absolute path of the file to write (WLED_MCP_CONFIG).")
    init.add_argument("--force", action="store_true", help="Replace an existing file.")

    add = actions.add_parser(
        "add-device", help="Append one device to a configuration.", allow_abbrev=False
    )
    add.add_argument("--config", help="Absolute configuration path (WLED_MCP_CONFIG).")

    for parser, optional in ((init, True), (add, False)):
        suffix = " (optional; all three together)" if optional else ""
        parser.add_argument("--device-id", help=f"Device ID, e.g. desk{suffix}.")
        parser.add_argument("--device-name", help=f"Display name{suffix}.")
        parser.add_argument("--base-url", help=f"Root URL, e.g. http://192.0.2.10{suffix}.")
        add_format_option(parser)

    validate = actions.add_parser(
        "validate", help="Check a configuration without network.", allow_abbrev=False
    )
    validate.add_argument("--config", help="Absolute configuration path (WLED_MCP_CONFIG).")
    validate.add_argument("--data-dir", help="Absolute data directory (WLED_MCP_DATA_DIR).")
    validate.add_argument(
        "--check-backups",
        action="store_true",
        help="Also check that the backups location is writable (advisory, creates nothing).",
    )
    add_format_option(validate)


HANDLERS: dict[str, Handler] = {
    "init": config_init,
    "add-device": config_add_device,
    "validate": config_validate,
}
