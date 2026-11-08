"""Test-only fixture wiring; production has no test mode or arbitrary import hook."""

from pathlib import Path

import anyio
import httpx2 as httpx

from wled_mcp.config import Device, StartupConfig
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server, serve_stdio


async def main():
    config = StartupConfig(
        Path.cwd() / "synthetic.toml",
        Path.cwd(),
        (
            Device(id="desk", name="Example desk", base_url="http://desk.invalid"),
            Device(id="shelf", name="Example shelf", base_url="http://shelf.invalid"),
        ),
    )

    def handler(request):
        assert request.method == "GET" and request.url.path == "/json/info"
        if request.url.host == "desk.invalid":
            return httpx.Response(200, json={"ver": "16.0.1"})
        return httpx.Response(200, text="synthetic-secret", headers={"content-type": "text/html"})

    async with Resources(config, httpx.MockTransport(handler)) as resources:
        await serve_stdio(create_server(build_operations(resources)))


if __name__ == "__main__":
    anyio.run(main)
