"""Scene format 1 of issue #17: AC-17-02, -05 and -10 (document, expansion and sharing).

Pure model tests; no filesystem, no device.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tests.scene_support import canonical_scene, device_target, group_target, scene_document
from tests.test_inventory_client import device
from wled_mcp.client import ClientFailure
from wled_mcp.groups import Group, Member
from wled_mcp.scenes import (
    MAX_EXPANDED_DEVICES,
    MAX_SEGMENT_PATCHES,
    TargetMapping,
    apply_target_map,
    expand_scene,
    export_scene,
    group_references,
    inventory_tokens,
    parse_scene,
)
from wled_mcp.scenes import scene_document as to_document

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "contracts" / "scene.json"


def parsed(document: dict[str, Any], *, placeholders: bool = False):
    return parse_scene(document, allow_placeholders=placeholders)


def rejected(raw: Any, *, placeholders: bool = False) -> str:
    with pytest.raises(ClientFailure) as caught:
        parse_scene(raw, allow_placeholders=placeholders)
    assert caught.value.error.code == "VALIDATION_ERROR"
    return caught.value.error.message


def entry(**fields: Any) -> dict[str, Any]:
    return {"ids": [0], **fields}


def with_entry(**fields: Any) -> dict[str, Any]:
    return scene_document({"device": "desk", "segments": [entry(**fields)]})


def group(group_id: str, *members: Member) -> Group:
    return Group(group_id, f"Group {group_id}", tuple(members))


# ------------------------------------------------------------------------ parsing


def test_canonical_scene_round_trips_through_the_parser_and_document_builder():
    scene = parsed(canonical_scene())
    assert to_document(scene) == canonical_scene()
    assert parsed(json.loads(json.dumps(to_document(scene)))) == scene
    assert parse_scene(json.dumps(canonical_scene()), allow_placeholders=False) == scene


@pytest.mark.parametrize("value", [0, 2, 9999, 10000, -1, 1.0, True, "1", None])
def test_version_other_than_one_is_rejected_and_an_integer_is_named(value):
    message = rejected(scene_document(format_version=value))
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9999:
        assert f"scene format_version {value}" in message
        assert "reads format_version 1" in message
    else:
        assert "integer 0-9999" in message


def test_wrong_format_unknown_missing_keys_and_descriptions_are_rejected():
    assert "Not a scene" in rejected(scene_document(format="wled-mcp.group"))
    assert "Unknown scene key" in rejected(scene_document(created_at="x"))
    doc = scene_document()
    del doc["targets"]
    assert "Missing scene key 'targets'" in rejected(doc)
    assert "description" in rejected(scene_document(description=""))
    assert "description" in rejected(scene_document(description="x" * 257))
    assert "description" in rejected(scene_document(description="a\nb"))
    assert parsed(scene_document(description="x" * 256)).description == "x" * 256


@pytest.mark.parametrize("identifier", ["", "Upper", "../x", "a b", "x" * 65, None])
def test_scene_id_rules(identifier):
    assert "scene ID" in rejected(scene_document(id=identifier))


@pytest.mark.parametrize("name", ["", "  ", "x" * 129, "a\x00b", 5])
def test_scene_name_rules(name):
    assert "scene name" in rejected(scene_document(name=name))


def test_target_count_and_shape_rules():
    doc = scene_document()
    doc["targets"] = []
    assert "1-16" in rejected(doc)
    doc["targets"] = [device_target(f"d{i}") for i in range(17)]
    assert "1-16" in rejected(doc)
    doc["targets"] = [device_target(f"d{i}") for i in range(16)]
    assert len(parsed(doc).targets) == 16
    assert "exactly one" in rejected(scene_document({"master": {"on": True}}))
    assert "exactly one" in rejected(
        scene_document({"device": "a", "group": "b", "master": {"on": True}})
    )
    assert "'master' and/or 'segments'" in rejected(scene_document({"device": "a"}))
    assert "unknown key" in rejected(
        scene_document({"device": "a", "master": {"on": True}, "url": "x"})
    )
    assert "must be an object" in rejected(scene_document("a"))


@pytest.mark.parametrize("reference", ["http://example.invalid", "192.0.2.5", "Desk", "a/b", ""])
def test_a_reference_cannot_carry_an_address_or_url(reference):
    assert "reference" in rejected(scene_document({"device": reference, "master": {"on": True}}))


@pytest.mark.parametrize(
    "master, fragment",
    [
        ({}, "nonempty"),
        ({"transition_ms": 500}, "at least one of 'on' or 'brightness'"),
        ({"on": True, "nope": 1}, "unknown master field"),
        ({"on": 1}, "master"),
        ({"brightness": 256}, "brightness"),
        ({"brightness": -1}, "brightness"),
        ({"brightness": True}, "brightness"),
        ({"on": True, "transition_ms": 65501}, "transition_ms"),
        ({"brightness": 1.5}, "brightness"),
    ],
)
def test_master_fields_follow_the_set_state_rules(master, fragment):
    assert fragment in rejected(scene_document({"device": "a", "master": master}))


def test_valid_master_is_kept_in_canonical_order():
    scene = parsed(scene_document({"device": "a", "master": {"transition_ms": 0, "on": False}}))
    assert list(scene.targets[0].master) == ["on", "transition_ms"]


@pytest.mark.parametrize(
    "field",
    [
        "start",
        "stop",
        "start_y",
        "grouping",
        "spacing",
        "offset",
        "reverse",
        "mirror",
        "selected",
        "name",
        "freeze",
        "blend_mode",
        "transpose",
        "map_1d_2d",
        "segment_set",
        "sound_simulation",
        "seg",
        "i",
        "timers",
        "nl",
        "udpn",
        "allow_overlap",
    ],
)
def test_geometry_and_other_non_scene_fields_are_rejected_by_name(field):
    message = rejected(with_entry(on=True, **{field: 1}))
    assert "unknown or unsupported segment field" in message and field in message


@pytest.mark.parametrize(
    "fields",
    [
        {"effect_id": 1, "effect_name": "Solid"},
        {"palette_id": 1, "palette_name": "Default"},
    ],
)
def test_ids_and_names_of_one_kind_are_mutually_exclusive(fields):
    assert "mutually exclusive" in rejected(with_entry(**fields))
    # Different kinds may mix.
    assert parsed(with_entry(effect_id=1, palette_name="Default"))


@pytest.mark.parametrize(
    "fields",
    [
        {"speed": 256},
        {"speed": -1},
        {"intensity": 1.5},
        {"cct": 256},
        {"custom3": 32},
        {"custom1": 256},
        {"check1": 1},
        {"on": "yes"},
        {"brightness": 256},
        {"effect_id": -1},
        {"palette_id": True},
    ],
)
def test_segment_field_bounds_come_from_the_patch_model(fields):
    assert "field" in rejected(with_entry(**fields))


def test_a_field_error_names_the_field_and_never_quotes_the_value():
    message = rejected(with_entry(speed="synthetic-secret-value"))
    assert "speed" in message and "synthetic-secret-value" not in message


@pytest.mark.parametrize(
    "fields",
    [
        {"effect_name": ""},
        {"effect_name": "   "},
        {"effect_name": "x" * 129},
        {"effect_name": "a\x00b"},
        {"effect_name": 3},
        {"palette_name": ["a"]},
    ],
)
def test_catalog_names_must_be_nonblank_bounded_text(fields):
    assert "catalog name" in rejected(with_entry(**fields))


@pytest.mark.parametrize(
    "colors",
    [
        [],
        [[1, 2]],
        [[1, 2, 3, 4, 5]],
        [[1, 2, 256]],
        [[1, 2, -1]],
        [[1, 2, True]],
        "red",
        [[1, 2, 3]] * 4,
        [1],
    ],
)
def test_colors_are_one_to_three_slots_of_three_or_four_integers(colors):
    assert "colors" in rejected(with_entry(colors=colors))


def test_colors_of_both_widths_parse_because_the_width_is_a_per_device_fact():
    assert parsed(with_entry(colors=[[1, 2, 3]]))
    assert parsed(with_entry(colors=[[1, 2, 3, 4], [0, 0, 0, 0]]))


def test_segment_entry_rules():
    assert "needs explicit 'ids'" in rejected(
        scene_document({"device": "a", "segments": [{"on": True}]})
    )
    assert "at least one field" in rejected(
        scene_document({"device": "a", "segments": [{"ids": [0]}]})
    )
    assert "1-16" in rejected(scene_document({"device": "a", "segments": []}))
    assert "1-16" in rejected(
        scene_document({"device": "a", "segments": [{"ids": [i], "on": True} for i in range(17)]})
    )
    assert "more than one entry" in rejected(
        scene_document(
            {"device": "a", "segments": [{"ids": [0, 1], "on": True}, {"ids": [1], "speed": 1}]}
        )
    )
    assert "must be an object" in rejected(scene_document({"device": "a", "segments": [3]}))


def test_group_target_entry_may_omit_ids():
    scene = parsed(scene_document({"group": "g", "segments": [{"on": True}]}))
    assert scene.targets[0].segments[0].ids is None


def test_strict_json_text_rejects_duplicate_keys_nan_and_oversize():
    text = json.dumps(scene_document())
    assert "strict JSON" in rejected(text.replace('"id": "evening"', '"id": "x", "id": "evening"'))
    assert "strict JSON" in rejected(text.replace('"on": true', '"on": NaN'))
    assert "strict JSON" in rejected("{")
    assert "exceeds" in rejected(" " * (64 * 1024 + 1))
    assert "JSON object" in rejected("[]")


def test_an_oversized_object_is_rejected_by_serialized_size():
    doc = scene_document(description="x" * 256)
    doc["targets"] = [
        {
            "device": f"d{i}",
            "segments": [
                {"ids": [n], "effect_name": "x" * 128, "palette_name": "y" * 128} for n in range(16)
            ],
        }
        for i in range(16)
    ]
    # 16 targets x 16 entries x 256 characters is above the 64 KiB bound.
    assert "exceeds" in rejected(doc)


def test_parsing_does_not_mutate_its_input():
    doc = canonical_scene()
    snapshot = copy.deepcopy(doc)
    parsed(doc)
    assert doc == snapshot


def test_stored_form_refuses_placeholders_but_the_shared_form_accepts_them():
    shared_doc = to_document(
        export_scene(parsed(canonical_scene()), include_targets=False, tokens=[])
    )
    assert "placeholders" in shared_doc
    assert "stored scene cannot carry" in rejected(shared_doc)
    assert parsed(shared_doc, placeholders=True).placeholders == ("t1", "t2")


def test_placeholders_must_match_the_references_exactly():
    shared_doc = to_document(
        export_scene(parsed(canonical_scene()), include_targets=False, tokens=[])
    )
    for bad in (["t1"], ["t1", "t2", "t3"], ["t1", "t1"], ["t1", "T2"], [], "t1"):
        doc = copy.deepcopy(shared_doc)
        doc["placeholders"] = bad
        rejected(doc, placeholders=True)


# --------------------------------------------------------------------- expansion


def test_expansion_is_in_document_order_and_groups_expand_in_member_order():
    scene = parsed(
        scene_document(
            device_target("desk"),
            group_target("shelf", master={"brightness": 10}),
            device_target("lamp"),
        )
    )
    groups = {"shelf": group("shelf", Member("right"), Member("left"))}
    expanded = expand_scene(scene, groups)
    assert [(e.device_id, e.origin, e.target_index) for e in expanded] == [
        ("desk", "device", 1),
        ("right", "group:shelf/member:1", 2),
        ("left", "group:shelf/member:2", 2),
        ("lamp", "device", 3),
    ]
    assert expanded[1].master == {"brightness": 10}
    assert group_references(scene) == ["shelf"]


def test_group_segment_entries_use_designated_ids_unless_the_scene_names_ids():
    scene = parsed(
        scene_document(
            {"group": "g", "segments": [{"on": True}]},
            {"group": "h", "segments": [{"ids": [4], "on": False}]},
        )
    )
    groups = {
        "g": group("g", Member("a", (1, 3)), Member("b", (2,))),
        "h": group("h", Member("c", (9,)), Member("d")),
    }
    expanded = expand_scene(scene, groups)
    ids = {e.device_id: [s.ids for s in e.segments] for e in expanded}
    assert ids == {"a": [(1, 3)], "b": [(2,)], "c": [(4,)], "d": [(4,)]}


def test_an_entry_without_ids_needs_every_member_to_designate_segments():
    scene = parsed(scene_document({"group": "g", "segments": [{"on": True}]}))
    with pytest.raises(ClientFailure) as caught:
        expand_scene(scene, {"g": group("g", Member("a", (0,)), Member("b"))})
    assert caught.value.error.code == "VALIDATION_ERROR"
    message = caught.value.error.message
    assert "'b'" in message and "designates no segments" in message


def test_unknown_group_is_refused_before_any_device_is_considered():
    scene = parsed(scene_document(device_target("desk"), group_target("missing")))
    with pytest.raises(ClientFailure) as caught:
        expand_scene(scene, {})
    assert "'missing'" in caught.value.error.message
    assert "not stored" in caught.value.error.message


def test_expansion_does_not_decide_whether_a_device_is_configured():
    scene = parsed(scene_document(device_target("not_in_any_inventory")))
    assert expand_scene(scene, {})[0].device_id == "not_in_any_inventory"


@pytest.mark.parametrize(
    "targets, groups, origins",
    [
        # direct plus group
        (
            [device_target("a"), group_target("g")],
            {"g": group("g", Member("b"), Member("a"))},
            ("target 1 (device)", "target 2 (group:g/member:2)"),
        ),
        # group plus direct
        (
            [group_target("g"), device_target("a")],
            {"g": group("g", Member("a"))},
            ("target 1 (group:g/member:1)", "target 2 (device)"),
        ),
        # two groups sharing a device
        (
            [group_target("g"), group_target("h")],
            {"g": group("g", Member("x")), "h": group("h", Member("y"), Member("x"))},
            ("target 1 (group:g/member:1)", "target 2 (group:h/member:2)"),
        ),
        # the same device twice directly
        (
            [device_target("a"), device_target("a")],
            {},
            ("target 1 (device)", "target 2 (device)"),
        ),
    ],
)
def test_a_device_may_occur_once_after_expansion_naming_device_and_both_origins(
    targets, groups, origins
):
    scene = parsed(scene_document(*targets))
    with pytest.raises(ClientFailure) as caught:
        expand_scene(scene, groups)
    message = caught.value.error.message
    assert caught.value.error.code == "VALIDATION_ERROR"
    assert "targeted twice" in message and all(origin in message for origin in origins)


def test_the_same_group_twice_is_a_duplicate_and_nothing_is_merged():
    scene = parsed(scene_document(group_target("g"), group_target("g")))
    with pytest.raises(ClientFailure):
        expand_scene(scene, {"g": group("g", Member("a"))})
    # A device and a group that happen to share an ID are different references.
    other = parsed(scene_document(device_target("a"), group_target("a")))
    assert len(expand_scene(other, {"a": group("a", Member("b"))})) == 2


def test_expansion_limits_devices_and_segment_patches():
    members = tuple(Member(f"d{i}") for i in range(MAX_EXPANDED_DEVICES))
    ok = parsed(scene_document(group_target("g")))
    assert len(expand_scene(ok, {"g": group("g", *members)})) == MAX_EXPANDED_DEVICES
    over = parsed(scene_document(group_target("g"), device_target("one_more")))
    with pytest.raises(ClientFailure) as caught:
        expand_scene(over, {"g": group("g", *members)})
    assert "more than 16 devices" in caught.value.error.message
    half = MAX_SEGMENT_PATCHES // 2
    entries = [
        {"ids": list(range(half + 1)), "on": True},
        {"ids": list(range(100, 100 + half)), "on": False},
    ]
    many = parsed(scene_document({"device": "a", "segments": entries}))
    with pytest.raises(ClientFailure) as caught:
        expand_scene(many, {})
    assert "65 segment patches" in caught.value.error.message


def test_group_designated_segments_repeated_by_two_entries_are_refused():
    scene = parsed(
        scene_document({"group": "g", "segments": [{"on": True}, {"ids": [1], "speed": 5}]})
    )
    with pytest.raises(ClientFailure) as caught:
        expand_scene(scene, {"g": group("g", Member("a", (1,)))})
    assert "segment ID 1" in caught.value.error.message


# ----------------------------------------------------------------------- sharing


def shared(include_targets: bool = False, tokens: list[str] | None = None):
    return export_scene(
        parsed(canonical_scene()), include_targets=include_targets, tokens=tokens or []
    )


def test_export_replaces_references_by_positional_placeholders():
    document = to_document(shared())
    assert document["placeholders"] == ["t1", "t2"]
    assert [next(iter(t)) for t in document["targets"]] == ["device", "group"]
    assert document["targets"][0]["device"] == "t1" and document["targets"][1]["group"] == "t2"
    text = json.dumps(document)
    assert "desk" not in text and "shelf" not in text


def test_export_with_include_targets_keeps_references_and_has_no_placeholders():
    document = to_document(shared(include_targets=True))
    assert "placeholders" not in document and document == canonical_scene()


def test_export_refuses_free_text_with_an_inventory_host_naming_field_not_text():
    tokens = inventory_tokens([device("desk")])
    assert "desk.invalid" in tokens and "http://desk.invalid" in tokens
    for field in ("name", "description"):
        doc = canonical_scene()
        doc[field] = "Kitchen strip at DESK.invalid"
        with pytest.raises(ClientFailure) as caught:
            export_scene(parsed(doc), include_targets=False, tokens=tokens)
        message = caught.value.error.message
        assert field in message
        assert "desk.invalid" not in message.casefold() and "Kitchen" not in message
    # include_targets does not disable the leak check.
    doc = canonical_scene()
    doc["name"] = "http://desk.invalid/"
    with pytest.raises(ClientFailure):
        export_scene(parsed(doc), include_targets=True, tokens=tokens)


def hosted_scene(**changes: Any) -> dict[str, Any]:
    """The canonical scene with one catalog name or ID changed."""
    document = canonical_scene()
    segment = document["targets"][0]["segments"][0]
    for key, value in changes.items():
        if key in ("effect_name", "palette_name"):
            segment[key] = value
        else:
            document[key] = value
    return document


@pytest.mark.parametrize(
    ("changes", "path"),
    [
        ({"effect_name": "Fire at DESK.invalid"}, "targets.1.segments.1.effect_name"),
        ({"palette_name": "http://desk.invalid/ocean"}, "targets.1.segments.1.palette_name"),
        ({"id": "x-desk-invalid"}, "id"),
    ],
)
@pytest.mark.parametrize("include_targets", [False, True])
def test_export_scans_every_exported_string_not_only_name_and_description(
    changes, path, include_targets
):
    # The scan covers the catalog names and the scene ID too, with or without the targets.
    tokens = inventory_tokens([device("desk")]) + ["x-desk-invalid"]
    with pytest.raises(ClientFailure) as caught:
        export_scene(
            parsed(hosted_scene(**changes)), include_targets=include_targets, tokens=tokens
        )
    message = caught.value.error.message
    assert f"'{path}'" in message
    assert "desk.invalid" not in message.casefold() and "Fire" not in message
    assert "ocean" not in message


def test_export_scans_the_kept_target_references_only_when_they_are_kept():
    scene = parsed(canonical_scene())  # device "desk" and group "shelf"
    # A host that equals a device ID: kept references leak it, placeholders do not.
    with pytest.raises(ClientFailure) as caught:
        export_scene(scene, include_targets=True, tokens=["desk"])
    assert "'targets.1.device'" in caught.value.error.message
    assert export_scene(scene, include_targets=False, tokens=["desk"])
    # A reference that merely resembles a token is no leak.
    assert export_scene(scene, include_targets=True, tokens=["shelf-strip.invalid"])


def test_a_catalog_name_without_a_host_exports_unchanged():
    tokens = inventory_tokens([device("desk")])
    shared_scene = export_scene(
        parsed(hosted_scene(effect_name="Fire 2012")), include_targets=False, tokens=tokens
    )
    assert to_document(shared_scene)["targets"][0]["segments"][0]["effect_name"] == "Fire 2012"


def test_a_device_id_inside_free_text_is_not_an_inventory_host():
    # Only addresses are scanned; the placeholder form is what hides device IDs.
    doc = canonical_scene()
    doc["name"] = "desk evening"
    tokens = inventory_tokens([device("desk")])
    assert export_scene(parsed(doc), include_targets=False, tokens=tokens)


MAPPING = {"t1": TargetMapping("device", "lamp"), "t2": TargetMapping("group", "shelf")}


def test_target_map_round_trip_restores_the_original_scene():
    scene = parsed(to_document(shared()), placeholders=True)
    mapped = apply_target_map(
        scene,
        {"t1": TargetMapping("device", "desk"), "t2": TargetMapping("group", "shelf")},
        devices={"desk"},
        groups={"shelf"},
    )
    assert to_document(mapped) == canonical_scene()
    assert mapped == parsed(canonical_scene())


def test_target_map_is_all_or_nothing_and_validated():
    scene = parsed(to_document(shared()), placeholders=True)

    def attempt(mapping, devices=("lamp",), groups=("shelf",)):
        with pytest.raises(ClientFailure) as caught:
            apply_target_map(scene, mapping, devices=set(devices), groups=set(groups))
        assert caught.value.error.code == "VALIDATION_ERROR"
        return caught.value.error.message

    assert "'t2' has no entry" in attempt({"t1": MAPPING["t1"]})
    assert "not a placeholder" in attempt({**MAPPING, "t3": MAPPING["t1"]})
    assert "stands for a device" in attempt({**MAPPING, "t1": TargetMapping("group", "shelf")})
    assert "which is not configured" in attempt(MAPPING, devices=())
    assert "not a stored group" in attempt(MAPPING, groups=())
    assert apply_target_map(scene, MAPPING, devices={"lamp"}, groups={"shelf"}).placeholders is None


def test_retained_example_parses_with_the_real_parser_and_is_the_canonical_export():
    document = json.loads(EXAMPLE.read_text("utf-8"))
    scene = parsed(document, placeholders=True)
    assert scene.placeholders == ("t1", "t2")
    assert to_document(scene) == document == to_document(shared())
    text = EXAMPLE.read_text("utf-8").casefold()
    assert "desk" not in text and ".invalid" not in text and "http" not in text
