"""NAME-01: names resolve before writes, and numeric plans/readbacks stay authoritative."""

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from tests.layout_support import FakeWLED
from tests.test_inventory_client import config
from wled_mcp.layouts import LayoutSegment
from wled_mcp.operations import build_operations
from wled_mcp.patches import SegmentPatch
from wled_mcp.resources import Resources


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def call(resources, tool, segments, *, dry_run=False):
    op = {o.name: o for o in build_operations(resources)}[tool]
    args = {"device_id": "desk", "segments": segments, "dry_run": dry_run}
    return await op.execute(op.request_model.model_validate(args).model_dump())


def segment(tool, **fields):
    geometry = {"start": 0, "stop": 10} if tool == "wled_replace_layout" else {}
    return {"id": 0, **geometry, **fields}


TOOLS = ["wled_patch_segments", "wled_replace_layout"]


@pytest.mark.anyio
@pytest.mark.parametrize("tool", TOOLS)
async def test_names_plan_and_write_same_ids_under_lock(tmp_path, tool):
    fake = FakeWLED()
    async with Resources(config(tmp_path), fake.transport()) as resources:
        fake.read_hook = lambda: resources.locks["desk"].locked() or pytest.fail("lock absent")
        fields = [segment(tool, effect_name="  wIpE ", palette_name="Party")]
        preview = await call(resources, tool, fields, dry_run=True)
        assert preview.ok, preview
        assert fake.posts == []
        actual = await call(resources, tool, fields)
    assert actual.ok and actual.verification == "verified", actual
    assert actual.data["plan"] == preview.data["plan"]
    planned = preview.data["plan"]["resolved_segments"][0]
    assert planned["effect_id"] == 3 and planned["palette_id"] == 2
    written = []
    for post in fake.posts:
        value = post.get("seg", [])
        written.extend(value if isinstance(value, list) else [value])
    assert any(p.get("fx") == 3 and p.get("pal") == 2 for p in written)
    # Each catalog kind is fetched only once per call (second invocation uses the cache).
    assert fake.calls.count(("GET", "/json/eff")) == 1
    assert fake.calls.count(("GET", "/json/pal")) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("dry_run", [True, False])
async def test_later_unknown_name_prevents_every_write_and_returns_suggestions(
    tmp_path, tool, dry_run
):
    fake = FakeWLED()
    entries = [segment(tool, effect_name="Solid")]
    entries.append({"id": 2, "start": 10, "stop": 20, "effect_name": "wi"})
    async with Resources(config(tmp_path), fake.transport()) as resources:
        result = await call(resources, tool, entries, dry_run=dry_run)
    assert not result.ok and result.error.code == "VALIDATION_ERROR"
    assert result.application == "not_attempted"
    assert result.data["candidates"] == [{"id": 3, "name": "Wipe"}]
    assert fake.posts == []
    assert 5 in fake.layout()  # Even layout replacement has not started stale removal.


@pytest.mark.anyio
@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("dry_run", [True, False])
async def test_ambiguous_names_keep_bounded_candidates_and_do_not_write(tmp_path, tool, dry_run):
    fake = FakeWLED()

    async def transport(request):
        if request.url.path == "/json/pal":
            return httpx.Response(200, json=["Party"] * 12)
        return await fake(request)

    async with Resources(config(tmp_path), httpx.MockTransport(transport)) as resources:
        result = await call(resources, tool, [segment(tool, palette_name="Party")], dry_run=dry_run)
    assert not result.ok and result.error.code == "AMBIGUOUS_NAME"
    assert result.data["candidates"] == [{"id": i, "name": "Party"} for i in range(10)]
    assert result.data["candidate_total"] == 12
    assert fake.posts == []


@pytest.mark.anyio
@pytest.mark.parametrize("tool", TOOLS)
async def test_resolved_ids_drive_readback_not_acknowledgement(tmp_path, tool):
    fake = FakeWLED()
    fake.ignore_keys.update({"fx", "pal"})
    async with Resources(config(tmp_path), fake.transport()) as resources:
        result = await call(
            resources, tool, [segment(tool, effect_name="Blink", palette_name="Party")]
        )
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert fake.posts


@pytest.mark.anyio
async def test_placeholder_never_resolves_and_unknown_suggestions_are_bounded(tmp_path):
    fake = FakeWLED()
    async with Resources(config(tmp_path), fake.transport()) as resources:
        result = await call(resources, TOOLS[0], [{"id": 0, "effect_name": "RSVD"}])
    assert result.error.code == "VALIDATION_ERROR" and result.data["candidates"] == []
    assert fake.posts == []

    async def transport(request):
        if request.url.path == "/json/pal":
            return httpx.Response(200, json=[f"Party {i}" for i in range(12)])
        return await fake(request)

    async with Resources(config(tmp_path), httpx.MockTransport(transport)) as resources:
        result = await call(resources, TOOLS[0], [{"id": 0, "palette_name": "PARTY"}])
    assert result.error.code == "VALIDATION_ERROR"
    assert len(result.data["candidates"]) == 10 and result.data["candidate_total"] == 12
    assert fake.posts == []


@pytest.mark.parametrize("model", [SegmentPatch, LayoutSegment])
@pytest.mark.parametrize(
    "fields",
    [
        {"effect_name": " "},
        {"palette_name": ""},
        {"effect_name": "Solid", "effect_id": 0},
        {"palette_name": "Default", "palette_id": 0},
    ],
)
def test_invalid_name_inputs_are_rejected_before_io(model, fields):
    with pytest.raises(ValidationError):
        model.model_validate({"id": 0, "start": 0, "stop": 10, **fields})
