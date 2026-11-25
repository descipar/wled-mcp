"""Slim served JSON schemas (#235, #246).

Pydantic adds a generated ``title`` to every schema node and a ``"default": null`` to every
optional nullable field. Clients send the served schemas with each model request, and neither
keyword tells a model anything: the title only restates the field name and a nullable
optional field is omitted just as well. This module removes these two annotations from
a generated schema. Everything else stays byte-equal (types, ``anyOf``, bounds, required,
``additionalProperties``, descriptions, examples, non-null defaults).

#246 adds an opt-in third rule for named definitions only (the segment models): an optional
property that is ``anyOf`` of one schema and ``{"type": "null"}`` is advertised as that one
schema, so the served form is "omit the field" and not "send null". Required properties, unions
of other shapes and every other definition stay as generated.

Validation always uses the pydantic models, which are not touched, so omitted and explicit
``null`` are accepted exactly as before.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

# Keywords whose value is a mapping from a *name* (a field or definition name) to a schema.
# A key in such a mapping is data, so a field that is literally called ``title`` survives.
_NAME_MAPPINGS = frozenset({"properties", "$defs", "definitions", "patternProperties"})


# The definitions served without the null branch of optional fields (#246): the segment models
# of wled_patch_segments, wled_replace_layout and wled_preview_layout. A test ties these names
# to the model classes.
SEGMENT_MODEL_NAMES = ("SegmentPatch", "LayoutSegment")

# Keywords whose value is instance data, never a schema; it is copied as is.
_DATA = frozenset({"default", "const", "enum", "examples"})


def _allows_null(node: dict[str, Any]) -> bool:
    options = node.get("anyOf")
    return isinstance(options, list) and any(
        isinstance(option, dict) and option.get("type") == "null" for option in options
    )


def _slim_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_slim_node(item) for item in node]
    if not isinstance(node, dict):
        return node
    result: dict[str, Any] = {}
    for key, value in node.items():
        if key == "title" and isinstance(value, str):
            continue  # generated; a field named "title" lives under a name mapping below
        if key == "default" and value is None and _allows_null(node):
            continue  # an omitted nullable field is already "no value"
        if key in _DATA:
            result[key] = value
        elif key in _NAME_MAPPINGS and isinstance(value, dict):
            result[key] = {name: _slim_node(child) for name, child in value.items()}
        else:
            result[key] = _slim_node(value)
    return result


def _is_null(option: Any) -> bool:
    return isinstance(option, dict) and option == {"type": "null"}


def _collapse_optional_null(definition: dict[str, Any]) -> dict[str, Any]:
    """Advertise the non-null branch of each optional two-branch nullable property."""
    properties = definition.get("properties")
    if not isinstance(properties, dict):
        return definition
    required = set(definition.get("required", ()))
    collapsed: dict[str, Any] = {}
    for name, prop in properties.items():
        options = prop.get("anyOf") if isinstance(prop, dict) else None
        if (
            name not in required
            and isinstance(options, list)
            and len(options) == 2
            and sum(_is_null(option) for option in options) == 1
        ):
            branch = next(option for option in options if not _is_null(option))
            siblings = {key: value for key, value in prop.items() if key != "anyOf"}
            collapsed[name] = {**branch, **siblings}
        else:
            collapsed[name] = prop
    return {**definition, "properties": collapsed}


def slim_schema(
    schema: dict[str, Any], *, collapse_null_in: Collection[str] = ()
) -> dict[str, Any]:
    """Return a copy of a generated JSON schema without titles and ``default: null``.

    ``collapse_null_in`` names ``$defs`` entries whose optional two-branch nullable properties
    are advertised without the null branch (#246); other definitions are not changed.

    ``title`` is dropped from schema nodes only when it is a string (a generated title); a
    property named ``title`` is kept because it is a key of a ``properties`` mapping. The input
    is not modified.
    """
    slimmed = _slim_node(schema)
    assert isinstance(slimmed, dict)
    definitions = slimmed.get("$defs")
    if collapse_null_in and isinstance(definitions, dict):
        for name in collapse_null_in:
            if isinstance(definitions.get(name), dict):
                definitions[name] = _collapse_optional_null(definitions[name])
    return slimmed
