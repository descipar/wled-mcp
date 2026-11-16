"""#235: the schema slimming removes only generated titles and ``default: null``."""

from __future__ import annotations

import copy
from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wled_mcp.models import Outcome
from wled_mcp.schema_slim import slim_schema


class Inner(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(description="A field that is literally called title.")
    level: Annotated[int, Field(ge=0, le=5)] = 3


class Request(BaseModel):
    """A synthetic request."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str | None = Field(default=None, description="Optional text.")
    count: int | None = None
    flag: bool = False
    inner: Inner | None = None
    kept: str = Field(default="x", examples=[{"title": "example data"}])


def test_generated_titles_and_null_defaults_go_and_everything_else_stays():
    generated = Request.model_json_schema()
    assert "title" in generated and generated["properties"]["name"]["default"] is None
    slimmed = slim_schema(generated)
    assert "title" not in slimmed
    assert set(slimmed["properties"]) == set(generated["properties"])
    assert all("title" not in prop for prop in slimmed["properties"].values())
    for name in ("name", "count", "inner"):
        assert "default" not in slimmed["properties"][name]
        assert slimmed["properties"][name]["anyOf"][-1] == {"type": "null"}
    # Non-null defaults, constraints, descriptions and examples are untouched.
    assert slimmed["properties"]["flag"]["default"] is False
    assert slimmed["properties"]["kept"]["default"] == "x"
    assert slimmed["properties"]["kept"]["examples"] == [{"title": "example data"}]
    assert slimmed["properties"]["name"]["description"] == "Optional text."
    assert slimmed["additionalProperties"] is False
    level = slimmed["$defs"]["Inner"]["properties"]["level"]
    assert (level["minimum"], level["maximum"], level["default"]) == (0, 5, 3)
    assert slimmed["description"] == "A synthetic request."


def test_a_field_named_title_survives_and_the_input_is_not_modified():
    generated = Request.model_json_schema()
    before = copy.deepcopy(generated)
    slimmed = slim_schema(generated)
    assert generated == before
    inner = slimmed["$defs"]["Inner"]
    assert set(inner["properties"]) == {"title", "level"}
    assert inner["required"] == ["title"]
    assert "title" not in inner["properties"]["title"]  # its own generated title is gone
    assert inner["properties"]["title"]["type"] == "string"


def test_validation_is_unchanged_because_it_uses_the_models():
    """Omitted and explicit null stay accepted; the slimmed schema is only an annotation."""
    assert Request.model_validate({}).name is None
    assert Request.model_validate({"name": None, "count": None, "inner": None}).count is None
    with pytest.raises(ValidationError):
        Request.model_validate({"flag": None})
    with pytest.raises(ValidationError):
        Request.model_validate({"inner": {"level": 1}})
    with pytest.raises(ValidationError):
        Request.model_validate({"unknown": 1})


def test_output_envelope_keeps_its_structure():
    generated = Outcome.model_json_schema()
    slimmed = slim_schema(generated)
    assert slimmed["required"] == generated["required"]
    assert set(slimmed["properties"]) == set(generated["properties"])
    assert slimmed["$defs"].keys() == generated["$defs"].keys()
