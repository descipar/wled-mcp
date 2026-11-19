"""Fakes for the ``wled_discover_devices`` tests (issue #200): no real socket, ever.

``FakeEngine`` replaces ``discovery_tools.run_engine``. By default it runs the real
engine against the simulated multicast network and scripted ``GET /json/info`` of the
engine tests, so the coverage report is the engine's own; a test can also gate it with
events to test single flight and cancellation.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.patch_support import WriteRouter
from tests.state_catalog_support import FakeClock
from tests.test_discovery import FakeNetwork
from tests.test_discovery_engine import FakeTransport
from wled_mcp import discovery_engine
from wled_mcp.access import AccessPolicy
from wled_mcp.config import Device, HTTPSettings, StartupConfig
from wled_mcp.discovery_engine import DiscoveryResult
from wled_mcp.resources import Resources


class FakeEngine:
    def __init__(
        self,
        network: FakeNetwork | None = None,
        transport: FakeTransport | None = None,
        raises: BaseException | None = None,
    ) -> None:
        self.network = network or FakeNetwork()
        self.transport = transport or FakeTransport()
        self.raises = raises
        self.calls: list[dict[str, Any]] = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()  # a test clears it to hold the worker thread

    def __call__(self, **kwargs: Any) -> DiscoveryResult:
        self.calls.append(kwargs)
        self.started.set()
        assert self.release.wait(10), "the test never released the worker"
        if self.raises is not None:
            raise self.raises
        return discovery_engine.run_discovery(
            **kwargs,
            transport=self.transport,
            opener=self.network.opener,
            clock=self.network.clock,
        )


def refusing_engine(**kwargs: Any) -> DiscoveryResult:
    raise AssertionError("a test reached the real discovery engine (a real multicast socket)")


def make_resources(
    tmp_path: Path,
    devices: tuple[tuple[str, str], ...] = (("desk", "http://desk.invalid"),),
    profile: str = "full",
) -> Resources:
    config = StartupConfig(
        tmp_path / "config.toml",
        tmp_path,
        tuple(Device(id=name, name=f"Example {name}", base_url=url) for name, url in devices),
        HTTPSettings(operation_timeout_seconds=0.5),
        access=AccessPolicy(profile, {}),  # type: ignore[arg-type]
    )
    return Resources(config, WriteRouter().transport(), FakeClock().clock())


def with_ranges(ranges: tuple[str, ...]) -> Callable[[object], tuple[str, ...]]:
    return lambda config: ranges
