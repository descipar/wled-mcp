"""WLED firmware support tiers (DEC-020, ISSUE-21-DEC-002 TD-21-6).

The classifier is informational: it never refuses a request and never changes how a
read or write is performed. ``wled_get_state`` reports the tier in
``data.diagnostics.firmware_support``; later diagnostics (``doctor``, #16) reuse
``classify`` instead of defining a second firmware policy.

Tiers, in the vocabulary of docs/contract/compatibility.md:

- ``tested``: a release recorded with hardware evidence (``TESTED``).
- ``expected``: a release expected to work from a recorded source review (``EXPECTED``,
  empty until such a review exists).
- ``unknown``: any other release at or above the floor; no claim either way.
- ``unsupported``: below the floor, including every 0.x release and any suffixed
  version of the floor itself (pre-release ``16.0.0-b1`` or build ``16.0.0+mod``,
  ``16.0.0-custom``); served with a warning.
- ``unrecognized``: no leading ASCII-numeric ``MAJOR.MINOR.PATCH``; served with a
  warning.

Promotion to ``tested`` or ``expected`` edits only the data below, together with the
evidence link in docs/contract/compatibility.md.
"""

import re
from typing import Final, Literal

from pydantic import JsonValue

Tier = Literal["tested", "expected", "unknown", "unsupported", "unrecognized"]

_FLOOR: Final = (16, 0, 0)
MINIMUM_SUPPORTED: Final = ".".join(map(str, _FLOOR))
TESTED: Final[frozenset[str]] = frozenset({"16.0.1"})
EXPECTED: Final[frozenset[str]] = frozenset()

# Leading ASCII-numeric core (re.ASCII: no other Unicode digits); anything after it
# (``-b1``, ``-mod``, ``+custom``) is a suffix.
_VERSION = re.compile(r"(\d{1,9})\.(\d{1,9})\.(\d{1,9})(.*)", re.S | re.ASCII)

UNSUPPORTED_WARNING: Final = (
    f"The firmware version is below the minimum supported WLED version {MINIMUM_SUPPORTED}; "
    "the request was served, but behavior on this firmware is unsupported."
)
UNRECOGNIZED_WARNING: Final = (
    "The firmware version is not a recognizable WLED release number; the request was "
    f"served, but support cannot be determined (minimum supported {MINIMUM_SUPPORTED})."
)


def _core(version: str) -> tuple[tuple[int, int, int], str] | None:
    match = _VERSION.fullmatch(version)
    if match is None:
        return None
    major, minor, patch, suffix = match.groups()
    return (int(major), int(minor), int(patch)), suffix


def classify(version: object) -> Tier:
    """Support tier of a firmware version string as reported in ``info.ver``."""
    if not isinstance(version, str):
        return "unrecognized"
    parsed = _core(version)
    if parsed is None:
        return "unrecognized"
    core, suffix = parsed
    # Any suffix on the floor itself (a pre-release such as ``-b1`` or a build such as
    # ``+mod`` or ``-custom``) counts as below the floor: DEC-020 names the plain 16.0.0
    # release as the first supported one, and a suffix cannot be ordered against it.
    if core < _FLOOR or (core == _FLOOR and suffix):
        return "unsupported"
    if version in TESTED:
        return "tested"
    if version in EXPECTED:
        return "expected"
    return "unknown"


def firmware_support(version: object) -> dict[str, JsonValue]:
    """The additive ``diagnostics.firmware_support`` object of ``wled_get_state``."""
    return {"tier": classify(version), "minimum_supported": MINIMUM_SUPPORTED}


def support_warning(tier: Tier) -> str | None:
    """One warning for a tier outside the supported range; ``None`` otherwise."""
    if tier == "unsupported":
        return UNSUPPORTED_WARNING
    if tier == "unrecognized":
        return UNRECOGNIZED_WARNING
    return None
