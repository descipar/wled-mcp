"""Shared strict-JSON and ``format_version`` helpers for the group and scene documents.

Schema evolution follows TD-21-5 (ISSUE-21-DEC-002), the same rule as the preset bundle
(``bundles.parse_bundle``) and the snapshot files (``backups.parse_snapshot``): an
integer ``format_version`` 0-9999, a higher or unknown version is rejected with the
version named, and the server never rewrites or migrates a stored file. This module is
the third use of that rule (issue #17) and keeps it in one place for groups and scenes.

No network or filesystem access. Messages never quote document content.
"""

from __future__ import annotations

import json
from collections.abc import Collection

from pydantic import JsonValue

from wled_mcp.client import ClientFailure, validate_json

MAX_FORMAT_VERSION = 9999
KEY_ECHO = 32


def is_int(value: object) -> bool:
    """A real integer; booleans are not accepted."""
    return isinstance(value, int) and not isinstance(value, bool)


def echo(key: object) -> str:
    """A bounded representation of an unknown key name for a message."""
    return repr(str(key)[:KEY_ECHO])


LOCAL_RECONCILE = (
    "Correct the definition or request; no device was contacted and nothing was stored."
)


def invalid(message: str, reconciliation: str = LOCAL_RECONCILE) -> ClientFailure:
    return ClientFailure("VALIDATION_ERROR", message, reconciliation=reconciliation)


def _reject_duplicates(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(_: str) -> JsonValue:
    raise ValueError("non-finite number")


def serialized_size(value: object) -> int:
    """UTF-8 size of the compact JSON serialization."""
    text = json.dumps(value, allow_nan=False, separators=(",", ":"), ensure_ascii=False)
    return len(text.encode("utf-8"))


def decode_document(raw: str | bytes | dict[str, JsonValue], label: str, max_bytes: int) -> object:
    """Strictly decode JSON text or bytes; an object is passed through to validation.

    Size is bounded before parsing; syntax errors, duplicate keys, NaN and Infinity are
    rejected. The result is checked for a plain JSON shape and the serialized size.
    """
    document: object
    if isinstance(raw, (str, bytes)):
        try:
            encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
            text = raw if isinstance(raw, str) else raw.decode("utf-8")
        except UnicodeError:
            raise invalid(f"The {label} text is not valid Unicode.") from None
        if len(encoded) > max_bytes:
            raise invalid(f"The {label} exceeds {max_bytes} bytes.")
        try:
            document = json.loads(
                text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant
            )
        except (ValueError, RecursionError):
            raise invalid(
                f"The {label} is not strict JSON (syntax errors, duplicate keys, NaN and "
                "Infinity are rejected)."
            ) from None
    else:
        document = raw
    try:
        validate_json(document)
        size = serialized_size(document)
    except (ValueError, TypeError, RecursionError):
        raise invalid(
            f"The {label} has an unsupported JSON shape or a non-finite number."
        ) from None
    if size > max_bytes:
        raise invalid(f"The {label} exceeds {max_bytes} bytes.")
    return document


def check_format(
    document: dict[str, JsonValue],
    *,
    format_name: str,
    label: str,
    supported: Collection[int],
    current: int,
) -> int:
    """Check ``format`` and ``format_version`` (TD-21-5); return the version.

    A non-integer or out-of-range version keeps a generic message; an integer 0-9999 that
    this server does not read is named. Nothing of the document is quoted otherwise.
    """
    if document.get("format") != format_name:
        raise invalid(f"Not a {label}: 'format' must be {format_name!r}.")
    version = document.get("format_version")
    if not is_int(version) or not 0 <= version <= MAX_FORMAT_VERSION:  # type: ignore[operator]
        raise invalid(f"'format_version' must be an integer 0-{MAX_FORMAT_VERSION}.")
    assert isinstance(version, int)
    if version not in supported:
        raise invalid(
            f"Unsupported {label} format_version {version}; this server reads "
            f"format_version {current}."
        )
    return version
