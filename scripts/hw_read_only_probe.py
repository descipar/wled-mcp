"""Read-only H01/H02 probe against a locally launched stdio server.

Calls only wled_list_devices, wled_get_state, wled_get_effects and
wled_get_palettes. No setter, patch or replace tool is ever called. Output goes
to runtime/h01-h02/out/ (git-ignored) and must be sanitized before it is
committed or quoted in documentation.

Usage: python scripts/hw_read_only_probe.py [device_id] [--config PATH]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "runtime" / "h01-h02"
READ_ONLY_TOOLS = frozenset(
    {"wled_list_devices", "wled_get_state", "wled_get_effects", "wled_get_palettes"}
)


def console_command() -> str:
    name = "wled-mcp.exe" if sys.platform == "win32" else "wled-mcp"
    return str(Path(sys.executable).parent / name)


async def run(device_id: str, config: Path) -> None:
    out = WORK / "out"
    out.mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(
        command=console_command(),
        cwd=str(WORK),
        args=["--config", str(config.resolve()), "--data-dir", str((ROOT / "runtime").resolve())],
    )
    calls: list[tuple[str, str, dict[str, Any]]] = [
        ("list_probe", "wled_list_devices", {"probe": True}),
        ("state", "wled_get_state", {"device_id": device_id}),
        ("effects", "wled_get_effects", {"device_id": device_id}),
        ("palettes", "wled_get_palettes", {"device_id": device_id}),
    ]
    async with Client(params, mode="auto", read_timeout_seconds=20) as client:
        listed = sorted(tool.name for tool in (await client.list_tools()).tools)
        print("server tools:", listed)
        for label, tool, arguments in calls:
            if tool not in READ_ONLY_TOOLS:
                raise SystemExit(f"refusing non-read-only tool {tool}")
            result = await client.call_tool(tool, arguments)
            (out / f"{label}.json").write_text(
                json.dumps(result.structured_content, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"{label}: error={result.is_error} -> {out / (label + '.json')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device_id", nargs="?", default="testdev")
    parser.add_argument("--config", type=Path, default=WORK / "devices.toml")
    args = parser.parse_args()
    if not args.config.is_file():
        raise SystemExit(f"config not found: {args.config} (copy the example, see docs)")
    anyio.run(run, args.device_id, args.config)


if __name__ == "__main__":
    main()
