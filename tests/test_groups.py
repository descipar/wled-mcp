"""Group format 1 of issue #17: AC-17-01 (document rules) and AC-17-02 (versioning).

Pure parser tests; no filesystem, no device.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from wled_mcp.client import ClientFailure
from wled_mcp.groups import (
    MAX_MEMBERS,
    Member,
    group_document,
    member_views,
    parse_group,
)


def document(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "format": "wled-mcp.group",
        "format_version": 1,
        "id": "shelf",
        "name": "Shelf strips",
        "members": [{"device": "desk"}, {"device": "left", "segments": [0, 2]}],
    }
    base.update(overrides)
    return base


def rejected(raw: Any) -> str:
    with pytest.raises(ClientFailure) as caught:
        parse_group(raw)
    assert caught.value.error.code == "VALIDATION_ERROR"
    return caught.value.error.message


def test_valid_group_round_trips_through_its_document():
    group = parse_group(document())
    assert group.members == (Member("desk", None), Member("left", (0, 2)))
    assert group_document(group) == document()
    assert parse_group(json.dumps(group_document(group))) == group


@pytest.mark.parametrize("value", [0, 2, 10000, -1, 1.0, True, "1", None])
def test_version_other_than_one_is_rejected_and_integers_are_named(value):
    message = rejected(document(format_version=value))
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9999:
        assert f"format_version {value}" in message and "reads format_version 1" in message
    else:
        assert "integer 0-9999" in message
        assert "None" not in message and "'1'" not in message


def test_a_missing_version_is_rejected_without_quoting_content():
    doc = document()
    del doc["format_version"]
    assert "integer 0-9999" in rejected(doc)


def test_wrong_format_name_unknown_and_missing_keys_are_rejected():
    assert "Not a group" in rejected(document(format="wled-mcp.scene"))
    assert "Unknown group key" in rejected(document(extra=1))
    doc = document()
    del doc["members"]
    assert "Missing group key 'members'" in rejected(doc)


@pytest.mark.parametrize("identifier", ["", "Upper", "../x", "a b", "-lead", "x" * 65, 3, None])
def test_group_id_must_be_a_path_safe_identifier(identifier):
    assert "group ID" in rejected(document(id=identifier))


@pytest.mark.parametrize("name", ["", "   ", "x" * 129, "bad\x00name", "line\nbreak", 3])
def test_group_name_rules_are_the_device_name_rules(name):
    assert "group name" in rejected(document(name=name))


def test_member_count_bounds():
    assert "1-16" in rejected(document(members=[]))
    members = [{"device": f"d{i}"} for i in range(MAX_MEMBERS + 1)]
    assert "1-16" in rejected(document(members=members))
    assert len(parse_group(document(members=members[:MAX_MEMBERS])).members) == MAX_MEMBERS


def test_duplicate_device_is_rejected_and_a_conflicting_segment_list_is_named():
    plain = rejected(document(members=[{"device": "a"}, {"device": "a"}]))
    assert "listed twice" in plain and "conflicting" not in plain
    conflict = rejected(
        document(members=[{"device": "a", "segments": [0]}, {"device": "a", "segments": [1]}])
    )
    assert "conflicting segment lists" in conflict


@pytest.mark.parametrize(
    "segments", [[], [255], [-1], [0, 0], [1.5], ["0"], [True], "0", list(range(65))]
)
def test_member_segments_are_unique_explicit_ids_in_range(segments):
    assert "Member 1" in rejected(document(members=[{"device": "a", "segments": segments}]))


def test_member_segment_designation_is_never_all():
    # An absent list stays absent in the document; it is not expanded to every segment.
    group = parse_group(document(members=[{"device": "a"}]))
    assert group.members[0].segments is None
    assert "segments" not in group_document(group)["members"][0]


def test_unknown_member_key_and_non_object_member_are_rejected():
    assert "unknown key" in rejected(document(members=[{"device": "a", "host": "x.invalid"}]))
    assert "must be an object" in rejected(document(members=["a"]))


def test_strict_json_text_rejects_duplicate_keys_nan_and_trailing_garbage():
    text = json.dumps(document())
    assert "strict JSON" in rejected(text.replace('"id": "shelf"', '"id": "shelf", "id": "x"'))
    assert "strict JSON" in rejected(text.replace('"format_version": 1', '"format_version": NaN'))
    assert "strict JSON" in rejected(text + " x")
    assert "JSON object" in rejected("[]")


def test_document_size_is_bounded_before_parsing():
    assert "exceeds" in rejected("{" + " " * (64 * 1024 + 1) + "}")


def test_member_views_flag_a_device_that_left_the_inventory():
    group = parse_group(document())
    views = member_views(group, {"desk"})
    assert views == [
        {"member": 1, "device_id": "desk", "segments": None, "in_inventory": True},
        {"member": 2, "device_id": "left", "segments": [0, 2], "in_inventory": False},
    ]


def test_parse_does_not_mutate_the_supplied_object():
    original = document()
    snapshot = copy.deepcopy(original)
    parse_group(original)
    assert original == snapshot


def test_unknown_document_keys_are_redacted():
    marker = "synthetic-token@192.0.2.42"
    assert marker not in rejected(document(**{marker: marker}))
    assert marker not in rejected(document(members=[{"device": "desk", marker: marker}]))
