"""Issue #21 A21-04: WLED firmware support tiers (DEC-020, TD-21-6).

The tier is informational: ``wled_get_state`` reports it additively in
``data.diagnostics.firmware_support`` and adds one warning below the floor or for an
unrecognizable version; nothing is refused and write behavior does not depend on it.
Mock transports and loopback only; no device is contacted.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from tests.envelopes import strip_correlation_id
from tests.http_support import DESK, running_service, sdk_client
from tests.layout_support import FakeWLED
from tests.patch_support import WriteRouter
from tests.state_catalog_support import Router, make_info, make_segment
from tests.test_inventory_client import config
from wled_mcp import compat
from wled_mcp.compat import (
    MINIMUM_SUPPORTED,
    UNRECOGNIZED_WARNING,
    UNSUPPORTED_WARNING,
    classify,
    firmware_support,
    support_warning,
)
from wled_mcp.layouts import ReplaceLayoutRequest
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.patches import PatchSegmentsRequest, SetStateRequest
from wled_mcp.resources import Resources

ROOT = Path(__file__).resolve().parents[1]

# (firmware version, tier, warning) per A21-04, plus boundary cases of the parser.
CASES = [
    ("16.0.1", "tested", None),
    ("16.0.0", "unknown", None),
    ("16.2.3", "unknown", None),
    ("16.0.1-b1", "unknown", None),  # a build of a release above the floor
    ("17.0.0", "unknown", None),
    ("0.15.1", "unsupported", UNSUPPORTED_WARNING),
    ("0.15.5", "unsupported", UNSUPPORTED_WARNING),
    ("0.14.0", "unsupported", UNSUPPORTED_WARNING),
    ("15.99.99", "unsupported", UNSUPPORTED_WARNING),
    ("16.0.0-b1", "unsupported", UNSUPPORTED_WARNING),  # pre-release of the floor
    ("16.0.0+mod", "unsupported", UNSUPPORTED_WARNING),  # any suffix on the floor
    ("16.0.0-custom", "unsupported", UNSUPPORTED_WARNING),
    ("١٦.٠.١", "unrecognized", UNRECOGNIZED_WARNING),  # Arabic-Indic
    ("１６.０.１", "unrecognized", UNRECOGNIZED_WARNING),  # fullwidth
    ("v16.0.1", "unrecognized", UNRECOGNIZED_WARNING),
    ("16.0", "unrecognized", UNRECOGNIZED_WARNING),
    ("custom-build", "unrecognized", UNRECOGNIZED_WARNING),
    (" 16.0.1", "unrecognized", UNRECOGNIZED_WARNING),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ------------------------------------------------------------------- classifier


@pytest.mark.parametrize(("version", "tier", "warning"), CASES)
def test_classify_assigns_the_dec_020_tier(version, tier, warning):
    assert classify(version) == tier
    assert support_warning(classify(version)) == warning
    assert firmware_support(version) == {"tier": tier, "minimum_supported": "16.0.0"}


@pytest.mark.parametrize("value", [None, 16, 16.0, b"16.0.1", ["16.0.1"], ""])
def test_classify_never_raises_on_non_string_or_empty_input(value):
    assert classify(value) == "unrecognized"


def test_policy_data_matches_dec_020():
    # DEC-020: floor 16.0.0, tested currently 16.0.1, expected empty until a review.
    assert MINIMUM_SUPPORTED == "16.0.0"
    assert compat.TESTED == frozenset({"16.0.1"})
    assert compat.EXPECTED == frozenset()
    assert all(classify(version) == "tested" for version in compat.TESTED)


def test_expected_tier_is_data_driven(monkeypatch):
    # Promotion to "expected" is a data edit with evidence, not a code change.
    monkeypatch.setattr(compat, "EXPECTED", frozenset({"16.1.0"}))
    assert classify("16.1.0") == "expected"
    assert classify("16.1.1") == "unknown"
    # A listed version below the floor stays unsupported: the floor is checked first.
    monkeypatch.setattr(compat, "TESTED", frozenset({"16.0.1", "0.15.1"}))
    assert classify("0.15.1") == "unsupported"


# ------------------------------------------------------------- wled_get_state


async def get_state(tmp_path: Path, info: dict[str, Any]) -> Outcome:
    router = Router()
    router.device("desk.invalid", info=info)
    router.device("shelf.invalid")
    async with Resources(config(tmp_path), router.transport()) as resources:
        operation = {op.name: op for op in build_operations(resources)}["wled_get_state"]
        return await operation.execute({"device_id": "desk"})


@pytest.mark.anyio
@pytest.mark.parametrize(("version", "tier", "warning"), CASES)
async def test_get_state_reports_the_tier_and_warns_only_outside_support(
    tmp_path, version, tier, warning
):
    result = await get_state(tmp_path, make_info(ver=version))
    assert result.ok, result.error
    assert result.error is None
    diagnostics = result.data["diagnostics"]
    assert diagnostics["firmware_support"] == {"tier": tier, "minimum_supported": "16.0.0"}
    assert result.data["firmware"]["version"] == version  # reported verbatim
    assert result.warnings == ([warning] if warning else [])
    Outcome.model_validate(result.model_dump())


@pytest.mark.anyio
async def test_tier_warning_comes_first_and_does_not_hide_other_warnings(tmp_path):
    info = make_info(ver="0.15.1", leds={"count": 90, "maxseg": 32, "lc": 1, "seglc": [1]})
    result = await get_state(tmp_path, info)
    assert result.ok
    assert result.warnings[0] == UNSUPPORTED_WARNING
    assert any("capability list" in text for text in result.warnings[1:])
    assert result.warnings.count(UNSUPPORTED_WARNING) == 1


@pytest.mark.anyio
async def test_tier_warning_never_echoes_the_device_supplied_version(tmp_path):
    marker = "synthetic-marker-<script>"
    result = await get_state(tmp_path, make_info(ver=marker))
    assert result.data["diagnostics"]["firmware_support"]["tier"] == "unrecognized"
    assert result.warnings == [UNRECOGNIZED_WARNING]
    assert all(marker not in text for text in result.warnings)


@pytest.mark.anyio
async def test_other_read_tools_are_unchanged_by_the_tier(tmp_path):
    # Informational only: catalogs and the device list carry no tier and no tier warning.
    router = Router()
    router.device("desk.invalid", info=make_info(ver="0.15.1"))
    router.device("shelf.invalid")
    async with Resources(config(tmp_path), router.transport()) as resources:
        ops = {op.name: op for op in build_operations(resources)}
        effects = await ops["wled_get_effects"].execute({"device_id": "desk", "refresh": False})
        devices = await ops["wled_list_devices"].execute({"probe": True})
    for outcome in (effects, devices):
        assert outcome.ok
        assert UNSUPPORTED_WARNING not in outcome.warnings
        assert "firmware_support" not in outcome.model_dump_json()


# ------------------------------------------------------------------- both transports

STDIO_SERVER = """
import sys
from pathlib import Path

import anyio

from tests.state_catalog_support import Router, make_info
from wled_mcp.config import Device, StartupConfig
from wled_mcp.operations import build_operations
from wled_mcp.patches import PatchSegmentsRequest, SetStateRequest
from wled_mcp.resources import Resources
from wled_mcp.server import create_server, serve_stdio


async def main(version):
    config = StartupConfig(
        Path.cwd() / "synthetic.toml",
        Path.cwd(),
        (
            Device(id="desk", name="Example desk", base_url="http://desk.invalid"),
            Device(id="shelf", name="Example shelf", base_url="http://shelf.invalid"),
        ),
    )
    router = Router()
    router.device("desk.invalid", info=make_info(ver=version))
    router.device("shelf.invalid")
    async with Resources(config, router.transport()) as resources:
        await serve_stdio(create_server(build_operations(resources)))


anyio.run(main, sys.argv[1])
"""


def comparable(envelope: dict[str, Any]) -> dict[str, Any]:
    """The envelope without the read timestamp and the per-call correlation ID."""
    result = strip_correlation_id(envelope)
    result["data"]["freshness"].pop("read_at")
    return result


@pytest.mark.anyio
@pytest.mark.parametrize("version", ["16.0.1", "0.15.1", "custom-build"])
async def test_stdio_and_http_return_the_same_tier_envelope(tmp_path, version):
    router = WriteRouter()
    router.device(DESK, info=make_info(ver=version))
    router.device("shelf.invalid")
    params = StdioServerParameters(
        command=sys.executable, cwd=ROOT, args=["-c", STDIO_SERVER, version]
    )
    with anyio.fail_after(60):
        async with Client(params, mode="legacy", read_timeout_seconds=20) as over_stdio:
            stdio = await over_stdio.call_tool("wled_get_state", {"device_id": "desk"})
        async with running_service(tmp_path, router) as run, sdk_client(run) as over_http:
            http = await over_http.call_tool("wled_get_state", {"device_id": "desk"})
    assert stdio.structured_content is not None and http.structured_content is not None
    assert comparable(stdio.structured_content) == comparable(http.structured_content)
    assert stdio.content[0].text and http.content[0].text
    support = http.structured_content["data"]["diagnostics"]["firmware_support"]
    assert support == firmware_support(version)
    assert stdio.is_error is http.is_error is False


# ---------------------------------------------------------- no refusal on writes


def legacy_fake(version: str) -> FakeWLED:
    fake = FakeWLED([make_segment(0, 0, 10), make_segment(1, 10, 20)])
    base_info = fake.info

    def info() -> dict[str, Any]:
        return {**base_info(), "ver": version}

    fake.info = info  # type: ignore[method-assign]
    return fake


async def write_sequence(tmp_path: Path, version: str) -> tuple[list[Any], list[Any]]:
    fake = legacy_fake(version)
    async with Resources(config(tmp_path / version), fake.transport()) as resources:
        ops = {op.name: op for op in build_operations(resources)}
        requests = [
            ("wled_set_state", SetStateRequest, {"brightness": 40}),
            (
                "wled_patch_segments",
                PatchSegmentsRequest,
                {"segments": [{"id": 1, "brightness": 90}]},
            ),
            (
                "wled_replace_layout",
                ReplaceLayoutRequest,
                {"segments": [{"id": 0, "start": 0, "stop": 20}]},
            ),
        ]
        outcomes = []
        for name, model, arguments in requests:
            for dry_run in (True, False):
                request = model.model_validate(
                    {"device_id": "desk", "dry_run": dry_run, **arguments}
                )
                outcome = await ops[name].execute(request.model_dump())
                outcomes.append(outcome.model_dump())
    return outcomes, list(fake.posts)


@pytest.mark.anyio
@pytest.mark.parametrize("version", ["0.15.1", "custom-build"])
async def test_writes_on_unsupported_firmware_are_identical_and_not_refused(tmp_path, version):
    (tmp_path / version).mkdir()
    (tmp_path / "16.0.1").mkdir()
    legacy, legacy_posts = await write_sequence(tmp_path, version)
    current, current_posts = await write_sequence(tmp_path, "16.0.1")
    assert [outcome["ok"] for outcome in legacy] == [True] * len(legacy)
    assert legacy == current
    assert legacy_posts == current_posts and legacy_posts
    assert all(UNSUPPORTED_WARNING not in outcome["warnings"] for outcome in legacy)
