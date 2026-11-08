"""The one place that prepares served envelopes for stdio/HTTP or in-process comparison.

Every served envelope carries a per-call random ``correlation_id`` (issue #20, TD-20-9), so two
calls of the same tool never serialize identically. A parity test compares envelopes through
these helpers and nowhere else; a field that varies per call is stripped here, after it was
validated, and not in each test.
"""

import copy
import json
import re
from typing import Any

CORRELATION_ID = re.compile(r"^[0-9a-f]{16}$")
INTERNAL_FAILURE_MESSAGE = re.compile(
    r"^Internal operation failure \(correlation_id=([0-9a-f]{16})\)$"
)


def correlation_id_of(envelope: dict[str, Any]) -> str:
    """The envelope's ID, which must be 16 lowercase hex characters."""
    value = envelope["correlation_id"]
    assert isinstance(value, str) and CORRELATION_ID.match(value), value
    return value


def strip_correlation_id(envelope: dict[str, Any], *, served: bool = True) -> dict[str, Any]:
    """A copy of an envelope without its (validated) correlation ID.

    A served envelope must carry a valid ID, so every parity comparison proves that each
    envelope of both transports has one. Pass ``served=False`` only for an envelope that
    legitimately never went through the dispatcher (a direct ``execute`` dump).
    """
    result = copy.deepcopy(envelope)
    if served or "correlation_id" in result:
        correlation_id_of(result)
        del result["correlation_id"]
    return result


def comparable_record(record: dict[str, Any]) -> dict[str, Any]:
    """A ``{"text", "structured", ...}`` record with the ID stripped from both renderings."""
    result = copy.deepcopy(record)
    for key in ("text", "structured"):
        value = result.get(key)
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, dict):
            result[key] = strip_correlation_id(value)
    return result


def without_correlation_id_text(text: str) -> str:
    """Rendered text (JSON or repr) without the random ID, for substring-absence checks.

    A random 16-hex-character ID can contain any short digit sequence by chance, so a test
    that asserts a short fragment is absent from a served result strips the ID first.
    """
    return re.sub(r"correlation_id\W+[0-9a-f]{16}", "correlation_id", text)


def comparable_message(message: str) -> str:
    """The fixed -32603 message with its ID replaced by a placeholder."""
    match = INTERNAL_FAILURE_MESSAGE.match(message)
    return message if match is None else "Internal operation failure (correlation_id=<id>)"
