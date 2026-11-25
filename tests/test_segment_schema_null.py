"""#246: the served segment schema omits the null branch; validation still accepts it.

Every optional nullable field is derived from the pydantic models (no hand list), so a field
added later is covered. Mocks only; no device is contacted.
"""

from __future__ import annotations

import types
import typing
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

from wled_mcp.layouts import LayoutSegment, ReplaceLayoutRequest
from wled_mcp.patches import PatchSegmentsRequest, SegmentPatch
from wled_mcp.preview_tools import PreviewLayoutRequest
from wled_mcp.schema_slim import SEGMENT_MODEL_NAMES

SEGMENT_MODELS = (SegmentPatch, LayoutSegment)
# Segment tool request model, a function building its request around one segment.
REQUESTS: dict[str, tuple[type[BaseModel], Any]] = {
    "wled_patch_segments": (
        PatchSegmentsRequest,
        lambda seg: {"device_id": "d", "segments": [seg]},
    ),
    "wled_replace_layout": (
        ReplaceLayoutRequest,
        lambda seg: {"device_id": "d", "segments": [seg]},
    ),
    "wled_preview_layout": (
        PreviewLayoutRequest,
        lambda seg: {"device_id": "d", "segments": [seg]},
    ),
}


def is_nullable(info: FieldInfo) -> bool:
    annotation = info.annotation
    return typing.get_origin(annotation) in (typing.Union, types.UnionType) and type(
        None
    ) in typing.get_args(annotation)


def optional_nullable(model: type[BaseModel]) -> list[str]:
    return [n for n, f in model.model_fields.items() if not f.is_required() and is_nullable(f)]


def required_fields(model: type[BaseModel]) -> list[str]:
    return [n for n, f in model.model_fields.items() if f.is_required()]


def non_null_branch(model: type[BaseModel], field: str) -> dict[str, Any]:
    schema = model.model_json_schema()["properties"][field]
    return next(b for b in schema["anyOf"] if b != {"type": "null"})


def valid_value(model: type[BaseModel], field: str) -> Any:
    branch = non_null_branch(model, field)
    kind = branch["type"]
    if kind == "integer":
        return branch.get("minimum", 0)
    if kind == "boolean":
        return True
    if kind == "string":
        return "x"
    assert kind == "array", (field, branch)
    return [[1, 2, 3]]


def invalid_values(model: type[BaseModel], field: str) -> list[Any]:
    branch = non_null_branch(model, field)
    kind = branch["type"]
    wrong: list[Any] = [{"unexpected": 1}]  # no segment field accepts an object
    wrong.append(True if kind == "integer" else 5 if kind in ("string", "boolean") else "x")
    if "maximum" in branch:
        wrong.append(branch["maximum"] + 1)
    if "minimum" in branch and branch["minimum"] > 0:
        wrong.append(branch["minimum"] - 1)
    if "maxLength" in branch:
        wrong.append("x" * (branch["maxLength"] + 1))
    if "minLength" in branch:
        wrong.append("")
    return wrong


def base(model: type[BaseModel]) -> dict[str, Any]:
    required = {"id": 0, "start": 0, "stop": 1}
    return {name: required[name] for name in required if name in model.model_fields}


CASES = [(m, f) for m in SEGMENT_MODELS for f in optional_nullable(m)]


def case_id(case: tuple[type[BaseModel], str]) -> str:
    return f"{case[0].__name__}.{case[1]}"


def test_the_derived_field_lists_are_not_empty_and_required_fields_are_excluded():
    assert len(optional_nullable(SegmentPatch)) >= 30
    assert {"id"} == set(required_fields(SegmentPatch))
    assert {"id", "start", "stop"} == set(required_fields(LayoutSegment))
    assert SEGMENT_MODEL_NAMES == tuple(m.__name__ for m in SEGMENT_MODELS)


@pytest.mark.parametrize(("model", "field"), CASES, ids=[case_id(c) for c in CASES])
def test_explicit_null_and_omission_are_accepted_but_wrong_values_are_rejected(model, field):
    start = base(model)
    # Explicit null is a no-op request for this field, exactly as before the schema change.
    assert getattr(model.model_validate({**start, field: None}), field) is None
    # Omitted is accepted; a valid value is accepted (paired fields supplied together).
    model.model_validate({**start, "on": True} if field != "on" else {**start, "reverse": True})
    pair = {"start": "stop", "stop": "start", "start_y": "stop_y", "stop_y": "start_y"}
    values = {field: valid_value(model, field)}
    if field in pair and pair[field] in model.model_fields and pair[field] not in start:
        values[pair[field]] = valid_value(model, pair[field])
    assert getattr(model.model_validate({**start, **values}), field) == values[field]
    for wrong in invalid_values(model, field):
        with pytest.raises(ValidationError):
            model.model_validate({**start, field: wrong})


@pytest.mark.parametrize("model", SEGMENT_MODELS, ids=lambda m: m.__name__)
def test_required_fields_still_reject_null_and_unknown_keys_are_rejected(model):
    for field in required_fields(model):
        with pytest.raises(ValidationError):
            model.model_validate({**base(model), field: None})
        missing = {k: v for k, v in base(model).items() if k != field}
        with pytest.raises(ValidationError):
            model.model_validate(missing)
    with pytest.raises(ValidationError):
        model.model_validate({**base(model), "unknown_field": 1})


@pytest.mark.parametrize("tool", sorted(REQUESTS))
def test_segment_tool_requests_accept_null_fields_in_each_segment(tool):
    request, build = REQUESTS[tool]
    segment = {"id": 0, "start": 0, "stop": 1, "on": True}
    nulls = dict.fromkeys(optional_nullable(SegmentPatch), None)
    assert set(nulls) >= set(optional_nullable(LayoutSegment))
    model = LayoutSegment if tool != "wled_patch_segments" else SegmentPatch
    segment.update({k: None for k in nulls if k in model.model_fields and k not in segment})
    assert request.model_validate(build(segment)) is not None
    with pytest.raises(ValidationError):
        request.model_validate(build({**segment, "unknown_field": 1}))
    with pytest.raises(ValidationError):
        request.model_validate(build({**segment, "id": None}))
