"""Slim served JSON schemas (#235).

Pydantic adds a generated ``title`` to every schema node and a ``"default": null`` to every
optional nullable field. Clients send the served schemas with each model request, and neither
keyword tells a model anything: the title only restates the field name and a nullable
optional field is omitted just as well. This module removes exactly these two annotations from
a generated schema. Everything else stays byte-equal (types, ``anyOf``, bounds, required,
``additionalProperties``, descriptions, examples, non-null defaults). Validation always uses the
pydantic models, which are not touched, so omitted and explicit ``null`` are accepted exactly as
before.
"""

from __future__ import annotations

from typing import Any

# Keywords whose value is a mapping from a *name* (a field or definition name) to a schema.
# A key in such a mapping is data, so a field that is literally called ``title`` survives.
_NAME_MAPPINGS = frozenset({"properties", "$defs", "definitions", "patternProperties"})


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


def slim_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a generated JSON schema without titles and ``default: null``.

    ``title`` is dropped from schema nodes only when it is a string (a generated title); a
    property named ``title`` is kept because it is a key of a ``properties`` mapping. The input
    is not modified.
    """
    slimmed = _slim_node(schema)
    assert isinstance(slimmed, dict)
    return slimmed
