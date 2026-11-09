"""W-CAT-02: compact pinned-source fixtures, conservative unknowns and device filters."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.http_support import running_service, sdk_client
from tests.test_state_catalogs import call, fleet, open_resources
from wled_mcp.effect_metadata import parse_fxdata
from wled_mcp.operations import GetCatalogRequest, GetEffectsRequest

FIXTURE = json.loads((Path(__file__).parent / "fixtures/fxdata/wled-16.0.1.json").read_text())
REAL = {entry["name"]: entry["raw"] for entry in FIXTURE["entries"]}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_pinned_real_metadata_labels_options_colors_flags_and_defaults():
    parsed = {}
    for name, raw in REAL.items():
        parsed[name], warnings = parse_fxdata(raw)
        assert not warnings, name
    assert parsed["Solid"]["flags"]["two_d"] is None
    assert parsed["Solid"]["palette"]["selectable"] is None
    assert parsed["Blink"]["sliders"]["speed"] == "Effect speed"
    assert parsed["Blink"]["sliders"]["intensity"] == "Duty cycle"
    assert parsed["Blink"]["color_slots"] == ["Fx color", "Background color", None]
    assert parsed["Blink"]["flags"]["zero_d"] is True
    assert parsed["Blink"]["flags"]["two_d"] is False
    assert parsed["Wipe"]["flags"]["one_d"] is None  # no UI-inferred fallback
    assert parsed["Palette"]["options"] == {
        "check1": "Animate Shift",
        "check2": "Animate Rotation",
        "check3": "Anamorphic",
    }
    assert parsed["Palette"]["defaults"] == {
        "intensity": 112,
        "custom1": 0,
        "check1": True,
        "check2": False,
        "check3": True,
    }
    assert parsed["Swirl"]["flags"]["volume_reactive"] is True
    assert parsed["GEQ"]["flags"]["frequency_reactive"] is True
    assert parsed["GEQ"]["sliders"]["custom2"] is None
    assert parsed["GEQ"]["defaults"]["palette_id"] == 11
    assert parsed["GEQ"]["defaults"]["custom3"] == 0


def test_partial_unknown_malformed_and_fixed_palette_metadata():
    for raw in ("broken", "name@!;;!", "!;;!;2\n", "!;;!;1;extra=1;trailing"):
        parsed, warnings = parse_fxdata(raw)
        assert warnings and parsed["flags"]["two_d"] is None
    parsed, warnings = parse_fxdata("!,,,,,!,!;!;11;2x;sx=120,unknown=5,c3=255")
    assert len(warnings) == 2
    assert parsed["flags"]["two_d"] is None
    assert parsed["palette"] == {"selectable": False, "label": None, "fixed_palette_id": 11}
    assert parsed["options"]["check1"] == "Check 1"  # generic label, no guessed semantics
    assert parsed["defaults"] == {"speed": 120}
    parsed, _ = parse_fxdata(";;")
    assert parsed["palette"]["selectable"] is False
    assert parsed["flags"]["audio_reactive"] is None


@pytest.mark.anyio
async def test_filter_intersection_preserves_ids_excludes_placeholders_and_unknowns(tmp_path):
    names = ["Solid", "RSVD", "Blink", "Swirl", "Unknown", "GEQ", "Straße"]
    metadata = [
        REAL["Solid"],
        REAL["Swirl"],
        REAL["Blink"],
        REAL["Swirl"],
        "!;;!;future",
        REAL["GEQ"],
        REAL["Blink"],
    ]
    async with open_resources(tmp_path, fleet(eff=names, fxdata=metadata)) as resources:
        all_items = await call(resources, "wled_get_effects")
        assert all_items.ok
        assert [i["id"] for i in all_items.data["effects"]] == [0, 2, 3, 4, 5, 6]
        unknown = next(i for i in all_items.data["effects"] if i["id"] == 4)
        assert unknown["metadata"]["fxdata"] == "!;;!;future"
        assert unknown["metadata"]["warnings"] and all_items.warnings
        for filters, expected in [
            ({"two_d": True, "audio_reactive": True}, [3, 5]),
            ({"two_d": False}, [2, 6]),
            ({"audio_reactive": False}, [2, 6]),
            ({"query": "SWI", "two_d": True}, [3]),
            ({"query": "STRASSE"}, [6]),
            ({"query": "rsvd"}, []),
        ]:
            result = await call(resources, "wled_get_effects", **filters)
            assert [i["id"] for i in result.data["effects"]] == expected
            assert result.data["count"] == len(expected)
    with pytest.raises(ValidationError):
        GetCatalogRequest(device_id="desk", two_d=True)  # palettes stay unchanged
    with pytest.raises(ValidationError):
        GetEffectsRequest(device_id="desk", two_d=1)


@pytest.mark.anyio
async def test_effect_filters_served_and_called_over_http(tmp_path):
    async with running_service(tmp_path) as run, sdk_client(run, "legacy") as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert "two_d" in tools["wled_get_effects"].input_schema["properties"]
        assert "two_d" not in tools["wled_get_palettes"].input_schema["properties"]
        result = await client.call_tool("wled_get_effects", {"device_id": "desk", "query": "bLiNk"})
        assert result.structured_content["ok"]
        assert all(
            "blink" in i["name"].casefold() for i in result.structured_content["data"]["effects"]
        )
        assert run.router.count("POST") == 0
