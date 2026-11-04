"""Test-only stdio subprocess with a synthetic mock fleet; never packaged or selectable."""

import sys
from pathlib import Path

import anyio
import httpx2 as httpx

from tests.state_catalog_support import SECRET, Router
from wled_mcp.config import Device, StartupConfig
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server, serve_stdio


async def main() -> None:
    config = StartupConfig(
        Path.cwd() / "synthetic.toml",
        Path.cwd(),
        (
            Device(id="desk", name="Example desk", base_url="http://desk.invalid"),
            Device(id="shelf", name="Example shelf", base_url="http://shelf.invalid"),
        ),
    )
    router = Router()
    router.device("desk.invalid")
    router.device("shelf.invalid")
    router.set(
        "shelf.invalid",
        "/json/state",
        httpx.Response(200, text=SECRET, headers={"content-type": "text/html"}),
    )
    router.set("shelf.invalid", "/json/info", httpx.Response(302, headers={"location": SECRET}))
    async with Resources(config, router.transport()) as resources:
        await serve_stdio(create_server(build_operations(resources)))


if __name__ == "__main__":
    print("synthetic fixture", file=sys.stderr)
    anyio.run(main)
