"""Issue #31: device-aware effect search over the curated property catalog.

Matching tests inject small synthetic catalogs into the pure matcher; one block checks the
shipped file against an independent transcription of the WLED 16.0.1 names and IDs. Mock
transports and loopback only; no device is contacted.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import ValidationError

from tests.envelopes import strip_correlation_id
from tests.http_support import DESK, running_service, sdk_client
from tests.patch_support import WriteRouter
from tests.state_catalog_support import Router, make_info
from tests.test_inventory_client import config
from tests.tool_contract import ToolClass, names_of
from wled_mcp.compat import UNSUPPORTED_WARNING
from wled_mcp.effect_search import (
    CatalogFileError,
    SearchEffectsRequest,
    parse_catalog,
    search,
    shipped_catalog,
)
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

ROOT = Path(__file__).resolve().parents[1]

# Independent transcription of (ID, name) from WLED v16.0.1 FX.h `FX_MODE_*` and the
# `_data_FX_MODE_*` strings of FX.cpp (commit 29b389d). A wrong ID in the shipped data
# fails against this record, not against itself.
WLED_16_0_1_EFFECTS = {
    0: "Solid",
    1: "Blink",
    2: "Breathe",
    8: "Colorloop",
    9: "Rainbow",
    12: "Fade",
    17: "Twinkle",
    23: "Strobe",
    67: "Colorwaves",
    72: "Noise 3",
    108: "Sine",
    115: "Blends",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def prop(value, confidence="recommended", basis="author_judgement", evidence="synthetic"):
    return {"value": value, "confidence": confidence, "basis": basis, "evidence": evidence}


def catalog(*effects: tuple[int, str, dict[str, Any]], **overrides: Any):
    document: dict[str, Any] = {
        "schema_version": 1,
        "data_version": "synthetic",
        "property_notes": "synthetic",
        "firmware": {"reviewed": ["16.0.1"], "source": "synthetic"},
        "effects": [{"id": i, "name": n, "properties": p} for i, n, p in effects],
    }
    document.update(overrides)
    return parse_catalog(json.dumps(document))


def request(**filters: Any) -> SearchEffectsRequest:
    return SearchEffectsRequest.model_validate({"device_id": "desk", **filters})


def run(cat, names, version="16.0.1", **filters):
    data, warnings = search(cat, tuple(names), version, request(**filters))
    return data, warnings


def ids(data):
    return [r["id"] for r in data["results"]]


# A small synthetic catalog: A has everything known, B has an unknown flashing, C is a
# known frequent flasher, D a subjective-only entry.
BASE = catalog(
    (0, "Alpha", {"flashing": prop("none", "verified", "source_review"), "motion": prop("calm")}),
    (1, "Bravo", {"motion": prop("calm")}),
    (2, "Charlie", {"flashing": prop("frequent", "verified", "source_review")}),
    (3, "Delta", {"visibility": prop("low"), "palette_saturation_need": prop("high")}),
)
NAMES = ["Alpha", "Bravo", "Charlie", "Delta"]


# ---------------------------------------------------------------- AC-31-03/04 semantics


def test_strict_excludes_unknown_and_non_strict_returns_it_as_partial():
    strict, _ = run(BASE, NAMES, flashing=["none"])
    assert ids(strict) == [0]
    loose, _ = run(BASE, NAMES, flashing=["none"], strict=False)
    assert ids(loose) == [0, 1, 3]
    by_id = {r["id"]: r for r in loose["results"]}
    assert by_id[0]["match"] == "full" and by_id[0]["unverified"] == []
    assert by_id[1]["match"] == "partial" and by_id[1]["unverified"] == ["flashing"]
    assert by_id[0]["matched"][0]["property"] == "flashing"
    assert by_id[0]["matched"][0]["confidence"] == "verified"


def test_known_mismatch_is_excluded_in_both_modes():
    for strict in (True, False):
        data, _ = run(BASE, NAMES, flashing=["none"], strict=strict)
        assert 2 not in ids(data)  # Charlie is known to flash frequently
    only, _ = run(BASE, ["Charlie"], flashing=["none"], strict=False)
    assert only["results"] == []
    assert only["no_match"]["reason"] == "excluded_by_known_properties"


def test_verified_floor_never_satisfied_by_subjective_properties():
    data, _ = run(BASE, NAMES, min_confidence="verified", min_visibility="low")
    assert data["results"] == []
    assert data["no_match"]["reason"] == "only_unverified_candidates"
    # Non-strict lists them as partial with the property unverified, never as matched.
    loose, _ = run(BASE, NAMES, min_confidence="verified", min_visibility="low", strict=False)
    assert all(
        r["match"] == "partial" and r["unverified"] == ["visibility"] for r in loose["results"]
    )
    assert all(r["matched"] == [] for r in loose["results"])


def test_recommended_property_is_labelled_with_confidence_and_basis():
    data, _ = run(BASE, NAMES, motion=["calm"])
    first = data["results"][0]
    assert first["matched"][0]["confidence"] == "recommended"
    assert first["matched"][0]["basis"] == "author_judgement"
    assert first["properties"]["motion"]["confidence"] == "recommended"
    assert "recommendations, not guarantees" in data["note"]
    assert "not a photosensitivity" in data["note"]


def test_visibility_and_saturation_filters_are_ordinal():
    cat = catalog(
        (0, "Low", {"visibility": prop("low"), "palette_saturation_need": prop("low")}),
        (1, "Mid", {"visibility": prop("medium"), "palette_saturation_need": prop("medium")}),
        (2, "High", {"visibility": prop("high"), "palette_saturation_need": prop("high")}),
    )
    names = ["Low", "Mid", "High"]
    assert ids(run(cat, names, min_visibility="medium")[0]) == [1, 2]
    assert ids(run(cat, names, max_palette_saturation_need="medium")[0]) == [0, 1]
    both, _ = run(cat, names, min_visibility="medium", max_palette_saturation_need="medium")
    assert ids(both) == [1]


def test_shipped_observed_run_entries_filter_for_visibility():
    names = [WLED_16_0_1_EFFECTS.get(i, "RSVD") for i in range(116)]
    # Barely visible with pale palettes: Noise 3, Blends and Sine need a saturated palette.
    pale, _ = run(shipped_catalog(), names, max_palette_saturation_need="medium")
    assert not {72, 108, 115} & set(ids(pale))
    visible, _ = run(shipped_catalog(), names, min_visibility="medium")
    assert ids(visible) == [0]  # only Solid is curated as clearly visible


def test_no_filters_lists_covered_effects_with_explanations():
    data, _ = run(BASE, NAMES)
    assert ids(data) == [0, 1, 2, 3]
    assert all(r["matched"] == [] and r["unverified"] == [] for r in data["results"])
    assert all(r["mapping"] == "exact" and r["properties"] for r in data["results"])


def test_colors_and_palette_and_strip_length_filters():
    cat = catalog(
        (
            0,
            "One",
            {
                "colors": prop(1, "verified", "source_review"),
                "uses_palette": prop(False, "verified", "source_review"),
                "strip_length": prop(["long"]),
            },
        ),
        (
            1,
            "Three",
            {
                "colors": prop(3, "verified", "source_review"),
                "uses_palette": prop(True, "verified", "source_review"),
                "strip_length": prop(["short", "long"]),
            },
        ),
    )
    names = ["One", "Three"]
    assert ids(run(cat, names, colors_min=2)[0]) == [1]
    assert ids(run(cat, names, colors_max=1)[0]) == [0]
    assert ids(run(cat, names, uses_palette=True)[0]) == [1]
    assert ids(run(cat, names, strip_length="short")[0]) == [1]
    assert ids(run(cat, names, strip_length="long")[0]) == [0, 1]


# ---------------------------------------------------------------- AC-31-02 intersection


def test_changed_id_is_flagged_and_only_returned_non_strict():
    cat = catalog((0, "Alpha", {"flashing": prop("none", "verified", "source_review")}))
    names = ["RSVD", "Other", "Alpha"]  # catalog ID 0 holds a placeholder, name is at 2
    strict, _ = run(cat, names, flashing=["none"])
    assert strict["results"] == []
    assert strict["no_match"]["reason"] == "only_stale_candidates"
    loose, _ = run(cat, names, flashing=["none"], strict=False)
    [result] = loose["results"]
    assert result["id"] == 2 and result["name"] == "Alpha"
    assert result["mapping"] == "id_changed" and result["match"] == "partial"
    assert "ID 0" in result["stale_reason"] and "ID 2" in result["stale_reason"]


def test_name_conflict_is_not_returned_and_is_listed():
    cat = catalog((1, "Alpha", {}))
    data, _ = run(cat, ["Zero", "Different"], strict=False)
    assert data["results"] == []
    assert data["diagnostics"]["stale_mappings"] == [
        {"catalog_id": 1, "catalog_name": "Alpha", "device_name": "Different"}
    ]
    assert data["no_match"]["reason"] == "no_curated_overlap"


def test_ambiguous_names_are_not_returned_and_candidates_are_bounded():
    cat = catalog((0, "Alpha", {}), (1, "Bravo", {}))
    names = ["Alpha"] * 12 + ["Bravo"]
    data, _ = run(cat, names, strict=False)
    assert ids(data) == [12]  # Bravo is unique at a changed ID; Alpha is ambiguous
    [ambiguous] = data["diagnostics"]["ambiguous"]
    assert ambiguous["total"] == 12 and len(ambiguous["candidates"]) == 10


def test_placeholders_never_match_and_noncontiguous_ids_are_kept():
    cat = catalog((0, "Alpha", {}), (5, "Bravo", {}), (9, "Charlie", {}))
    names = ["Alpha", "RSVD", "RSVD", "RSVD", "RSVD", "Bravo", "RSVD", "RSVD", "RSVD", "RSVD"]
    data, _ = run(cat, names)
    assert [(r["id"], r["name"]) for r in data["results"]] == [(0, "Alpha"), (5, "Bravo")]
    assert data["diagnostics"]["not_on_device_count"] == 1  # Charlie: RSVD slot, no name
    assert data["diagnostics"]["device_effects_without_curation"] == 0


def test_empty_overlap_is_reported():
    data, _ = run(BASE, ["Other", "Another"])
    assert data["results"] == [] and data["no_match"]["reason"] == "no_curated_overlap"
    assert data["diagnostics"]["device_effects_without_curation"] == 2
    assert "no_match" not in run(BASE, NAMES)[0]


def test_ordering_limit_and_truncation():
    cat = catalog(
        (0, "A", {"flashing": prop("none", "verified", "source_review")}),
        (1, "B", {}),
        (2, "C", {"flashing": prop("none", "verified", "source_review")}),
        (3, "D", {}),
    )
    data, _ = run(cat, ["A", "B", "C", "D"], flashing=["none"], strict=False)
    assert ids(data) == [0, 2, 1, 3]  # full first, then partial; ID order inside each
    limited, _ = run(cat, ["A", "B", "C", "D"], flashing=["none"], strict=False, limit=3)
    assert ids(limited) == [0, 2, 1]
    assert limited["total_matches"] == 4 and limited["truncated"] is True
    assert data["truncated"] is False


# ---------------------------------------------------------------------- AC-31-01 firmware


@pytest.mark.parametrize(
    ("version", "match", "warns"),
    [
        ("16.0.1", "reviewed", False),
        ("16.0.1-custom", "unreviewed", True),
        ("16.1.0", "unreviewed", True),
    ],
)
def test_firmware_review_state_warns_but_still_returns_exact_matches(version, match, warns):
    data, warnings = run(BASE, NAMES, version=version)
    assert data["catalog"]["firmware_match"] == match
    assert bool(warnings) is warns
    assert ids(data) == [0, 1, 2, 3]


@pytest.mark.parametrize("version", ["0.15.1", "15.9.9", "16.0.0-b1", "not-a-version"])
def test_unsupported_or_unrecognizable_firmware_does_not_apply_the_catalog(version):
    data, warnings = run(BASE, NAMES, version=version)
    assert data["results"] == []
    assert data["no_match"]["reason"] == "catalog_not_applicable"
    assert data["catalog"]["firmware_match"] == "not_applicable"
    assert warnings


# ------------------------------------------------------------------- AC-31-01 loader


def test_shipped_catalog_validates_and_matches_the_16_0_1_names_and_ids():
    shipped = shipped_catalog()
    assert {e.id: e.name for e in shipped.effects} == WLED_16_0_1_EFFECTS
    assert shipped.firmware.reviewed == ["16.0.1"]
    for entry in shipped.effects:
        for name, value in entry.properties.items():
            if name in ("motion", "strip_length", "visibility", "palette_saturation_need"):
                assert value.confidence == "recommended", (entry.name, name)


def raw_catalog() -> dict[str, Any]:
    return json.loads(
        (ROOT / "src" / "wled_mcp" / "catalog_data" / "effect_properties.json").read_text("utf-8")
    )


def mutated(mutate) -> str:
    document = copy.deepcopy(raw_catalog())
    mutate(document)
    return json.dumps(document)


@pytest.mark.parametrize("version", [2, 0, "1", None, 1.5])
def test_loader_rejects_unknown_schema_versions_naming_both(version):
    text = mutated(lambda d: d.__setitem__("schema_version", version))
    with pytest.raises(
        CatalogFileError, match=r"schema_version .* not supported.*reads schema_version 1"
    ):
        parse_catalog(text)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["effects"][0]["properties"].__setitem__("sparkliness", prop("high")),
        lambda d: d["effects"][0]["properties"].__setitem__("motion", prop("frantic")),
        lambda d: d["effects"][0]["properties"].__setitem__(
            "motion", prop("calm", "verified", "source_review")
        ),
        lambda d: d["effects"][0]["properties"].__setitem__(
            "flashing", prop("none", "verified", "author_judgement")
        ),
        lambda d: d["effects"][0]["properties"].__setitem__("flashing", prop("none", evidence="")),
        lambda d: d["effects"][0]["properties"].__setitem__("colors", prop(4)),
        lambda d: d["effects"][0]["properties"].__setitem__(
            "strip_length", prop(["short", "short"])
        ),
        lambda d: d["effects"][0].__setitem__("name", "RSVD"),
        lambda d: d["effects"][1].__setitem__("id", d["effects"][0]["id"]),
        lambda d: d["effects"][0].__setitem__("extra", 1),
    ],
)
def test_loader_rejects_invalid_entries(mutate):
    with pytest.raises(CatalogFileError):
        parse_catalog(mutated(mutate))


def test_package_data_is_inside_the_package_tree():
    # check_distribution.py inspects the wheel and sdist; here the file must sit in the package.
    assert (ROOT / "src" / "wled_mcp" / "catalog_data" / "effect_properties.json").is_file()
    distribution = (ROOT / "scripts" / "check_distribution.py").read_text("utf-8")
    assert "wled_mcp/catalog_data/effect_properties.json" in distribution


# -------------------------------------------------------------------- request validation


@pytest.mark.parametrize(
    "bad",
    [
        {"motion": ["frantic"]},
        {"motion": []},
        {"flashing": "none"},
        {"colors_min": 4},
        {"colors_min": 3, "colors_max": 1},
        {"strip_length": "huge"},
        {"min_visibility": "max"},
        {"min_confidence": "guess"},
        {"limit": 0},
        {"limit": 51},
        {"name": "Solid"},  # no free-text query in v1
    ],
)
def test_invalid_requests_are_rejected(bad):
    with pytest.raises(ValidationError):
        request(**bad)


# ----------------------------------------------------------------- tool, read-only, parity


def device_effects(**extra: str) -> list[str]:
    names = ["RSVD"] * 116
    for effect_id, name in WLED_16_0_1_EFFECTS.items():
        names[effect_id] = name
    names.extend(extra.values())
    return names


async def call(tmp_path, router, **arguments):
    async with Resources(config(tmp_path), router.transport()) as resources:
        operation = {op.name: op for op in build_operations(resources)}["wled_search_effects"]
        validated = SearchEffectsRequest.model_validate({"device_id": "desk", **arguments})
        return await operation.execute(validated.model_dump())


def fleet(**kwargs) -> Router:
    router = Router()
    router.device("desk.invalid", **kwargs)
    router.device("shelf.invalid")
    return router


@pytest.mark.anyio
async def test_tool_returns_exact_device_ids_and_only_reads(tmp_path):
    router = fleet(eff=device_effects(), info=make_info(fxcount=116))
    result = await call(tmp_path, router, flashing=["none"], strip_length="short")
    assert result.ok, result.error
    assert result.application == "not_attempted" and result.verification == "not_requested"
    assert result.operation == "wled_search_effects" and result.device_id == "desk"
    assert [r["name"] for r in result.data["results"]] == ["Solid", "Breathe", "Colorloop", "Fade"]
    assert [r["id"] for r in result.data["results"]] == [0, 2, 8, 12]
    assert result.data["device"]["id"] == "desk"
    assert result.data["freshness"]["source"] == "device"
    assert result.data["catalog"]["firmware_match"] == "reviewed"
    assert {path for _, path in router.calls} <= {"/json/info", "/json/eff", "/json/fxdata"}
    Outcome.model_validate(result.model_dump())  # Router asserts every request is a GET


@pytest.mark.anyio
async def test_missing_fxdata_does_not_affect_results(tmp_path):
    router = fleet(eff=device_effects(), fxdata=httpx.ConnectError("synthetic"))
    result = await call(tmp_path, router, flashing=["none"])
    assert result.ok and {r["id"] for r in result.data["results"]} >= {0, 2}
    assert not any("metadata" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_unsupported_firmware_is_a_successful_empty_search(tmp_path):
    router = fleet(eff=device_effects(), info=make_info(ver="0.15.1"))
    result = await call(tmp_path, router)
    assert result.ok and result.data["results"] == []
    assert result.data["no_match"]["reason"] == "catalog_not_applicable"
    assert UNSUPPORTED_WARNING in result.warnings


@pytest.mark.anyio
async def test_transport_failure_is_a_read_error(tmp_path):
    router = fleet(info=httpx.ConnectError("synthetic"))
    result = await call(tmp_path, router)
    assert not result.ok and result.application == "not_attempted"
    assert result.error is not None


def test_tool_is_registered_as_read_class_and_read_only():
    from tests.tool_contract import READ

    assert "wled_search_effects" in names_of(READ)
    assert ToolClass.READ == READ


STDIO_SERVER = """
import anyio
from pathlib import Path

from tests.state_catalog_support import Router
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
    router = Router()
    router.device("desk.invalid")
    router.device("shelf.invalid")
    async with Resources(config, router.transport()) as resources:
        await serve_stdio(create_server(build_operations(resources)))


anyio.run(main)
"""


def comparable(envelope: dict[str, Any]) -> dict[str, Any]:
    result = strip_correlation_id(envelope)
    result["data"]["freshness"].pop("fetched_at")
    return result


@pytest.mark.anyio
async def test_stdio_and_http_return_the_same_envelope(tmp_path):
    router = WriteRouter()
    router.device(DESK)
    router.device("shelf.invalid")
    params = StdioServerParameters(command=sys.executable, cwd=ROOT, args=["-c", STDIO_SERVER])
    arguments = {"device_id": "desk", "flashing": ["none"]}
    with anyio.fail_after(60):
        async with Client(params, mode="legacy", read_timeout_seconds=20) as over_stdio:
            stdio = await over_stdio.call_tool("wled_search_effects", arguments)
            listed = {tool.name for tool in (await over_stdio.list_tools()).tools}
        async with running_service(tmp_path, router) as run, sdk_client(run) as over_http:
            http = await over_http.call_tool("wled_search_effects", arguments)
    assert "wled_search_effects" in listed
    assert stdio.structured_content is not None and http.structured_content is not None
    assert stdio.is_error is http.is_error is False
    assert [r["id"] for r in http.structured_content["data"]["results"]] == [0]  # Solid only
    assert comparable(stdio.structured_content) == comparable(http.structured_content)
