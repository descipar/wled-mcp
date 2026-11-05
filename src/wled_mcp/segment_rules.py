"""Segment input rules shared by ``wled_patch_segments`` (#6) and ``wled_replace_layout`` (#7).

Issue #48, ``ISSUE-48-DEC-001`` (docs/decisions/issue-48.md): both tools apply the same
rules before any write, identically in a dry run, so that inputs the pinned firmware
(profile 0, v0.15.1 source) cannot represent are refused instead of surfacing after
writes as ``VERIFICATION_MISMATCH``:

* a segment name is at most 32 UTF-8 bytes (the build-independent firmware minimum;
  the firmware truncates by bytes) and must not contain U+0000 (C-string end);
* ``grouping`` is 1-255 and ``spacing`` 0-255 (firmware ``uint8_t`` arguments);
* ``on=true`` with ``brightness=0`` is rejected (the firmware ends ON);
* ``brightness=0`` with omitted ``on`` is accepted only on a segment that is off;
* a positive ``brightness`` with omitted ``on`` on an off segment is sent together with
  the resolved ``on=false`` (the firmware would otherwise switch the segment on).

Module-private to this package; the planners import it, nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

from wled_mcp.client import ClientFailure

SEGMENT_NAME_MAX_BYTES = 32
GROUPING_MAX = 255
SPACING_MAX = 255


def check_segment_name(seg_id: int, name: str | None) -> None:
    """Reject a supplied name the firmware would truncate (bytes) or cut at U+0000."""
    if name is None:
        return
    if "\x00" in name:
        raise ClientFailure("VALIDATION_ERROR", f"Segment {seg_id}: name must not contain U+0000.")
    try:
        size = len(name.encode("utf-8"))
    except UnicodeEncodeError:
        raise ClientFailure(
            "VALIDATION_ERROR", f"Segment {seg_id}: name is not valid UTF-8 text."
        ) from None
    if size > SEGMENT_NAME_MAX_BYTES:
        raise ClientFailure(
            "VALIDATION_ERROR",
            f"Segment {seg_id}: name is {size} UTF-8 bytes; the limit is "
            f"{SEGMENT_NAME_MAX_BYTES} bytes (the firmware would truncate it).",
        )


@dataclass(frozen=True)
class SegmentPower:
    """Resolved power for one segment request.

    ``resolved_on`` is the power after the write (``None`` only when the device did not
    report the current power and the request touches neither power nor brightness).
    ``compensate_off`` is true when a positive brightness is requested with omitted
    ``on`` on a segment that is off: the planner must also send ``on=false`` with the
    ``bri`` (targeted compensation shown in the plan).
    """

    resolved_on: bool | None
    compensate_off: bool


def resolve_segment_power(
    seg_id: int, requested_on: bool | None, brightness: int | None, current_on: bool | None
) -> SegmentPower:
    """Apply the shared power/brightness rules before any write.

    ``current_on`` is the fresh readback (``None`` when the device did not report a
    usable value). A new segment of ``wled_replace_layout`` passes its default ``True``.
    """
    ctx = f"Segment {seg_id}: "
    if requested_on is True and brightness == 0:
        raise ClientFailure(
            "VALIDATION_ERROR",
            f"{ctx}on=true with brightness=0 is rejected; pass on=false for off, "
            "or a positive brightness.",
        )
    if requested_on is not None:
        return SegmentPower(resolved_on=requested_on, compensate_off=False)
    if brightness == 0:
        if current_on is not False:
            raise ClientFailure(
                "VALIDATION_ERROR",
                f"{ctx}brightness=0 on a segment that is not off requires an explicit on=false.",
            )
        return SegmentPower(resolved_on=False, compensate_off=False)
    if current_on is None:
        if brightness is not None:
            raise ClientFailure(
                "UNSUPPORTED_CAPABILITY",
                f"{ctx}current segment power is unknown, so a brightness change could "
                "switch it on; pass on explicitly.",
            )
        return SegmentPower(resolved_on=None, compensate_off=False)
    return SegmentPower(
        resolved_on=current_on,
        compensate_off=brightness is not None and current_on is False,
    )
