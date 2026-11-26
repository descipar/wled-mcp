"""Agent guidance shared by every MCP transport (AGENT-01)."""

from collections.abc import Collection

_READ_STATE = "Read wled_get_state before changing lighting and choose the smallest change.\n"
_SEGMENTS_BOTH = (
    "Use wled_patch_segments to patch selected existing segments; wled_replace_layout replaces\n"
    "the complete layout and removes active segment IDs omitted from the request. Segment stop\n"
    "(and stop_y) is exclusive. Omitted fields preserve existing values; they are not resets.\n"
)
_SEGMENTS_PATCH_ONLY = (
    "Use wled_patch_segments to patch selected existing segments. Segment stop (and stop_y) is\n"
    "exclusive. Omitted fields preserve existing values; they are not resets.\n"
)
_CATALOGS = (
    "Effect and palette IDs are device-specific: read that device's catalogs rather than guess.\n"
)
_ROOMS = (
    "A room (a group saved with kind=room) is where controllers are, at most one room per\n"
    "controller: use wled_apply_room for a state or scene across a whole room, a plain group for\n"
    "any other set of controllers, a zone for part of a controller and wled_set_state for one\n"
    "controller.\n"
)
_SAFETY = (
    "Use dry_run=true to inspect a proposed write, then inspect the result's application and\n"
    "verification fields and read state when needed. A timed-out or uncertain write may already\n"
    "have applied: never retry it blindly. Overwriting a preset requires overwrite=true and a\n"
    "durable snapshot is taken first. Authorization belongs to the MCP host; these instructions\n"
    "and tool annotations do not add a confirmation mechanism or grant access.\n"
)


def build_instructions(registered: Collection[str]) -> str:
    """Server instructions naming only tools in ``registered`` (issue #236, AGENT-01).

    The full set gives the text of every release before tool groups, byte for byte; a
    profile or group selection drops the sentences about tools it does not serve.
    """
    parts = [_READ_STATE]
    if "wled_patch_segments" in registered:
        both = "wled_replace_layout" in registered
        parts.append(_SEGMENTS_BOTH if both else _SEGMENTS_PATCH_ONLY)
    parts.append(_CATALOGS)
    if "wled_apply_room" in registered and "wled_set_state" in registered:
        parts.append(_ROOMS)
    parts.append(_SAFETY)
    return "".join(parts)


PROMPT_NAME = "change_lighting_safely"
PROMPT_DESCRIPTION = "Plan a small lighting change, preview it, and verify the outcome."
PROMPT_TEXT = """Help make the requested lighting change safely:
1. Identify the configured device or stored room/zone/scene and read its current state.
2. Choose the smallest existing tool. Patch selected segments; replace the complete layout
   only when the request calls for it. stop and stop_y are exclusive; preserve omitted fields.
3. Read the device's effect/palette catalogs when IDs are needed; IDs are device-specific.
4. Preview the change with dry_run=true and check targets, ranges and discarded segments or
   stored entries. Preset overwrite needs overwrite=true and takes a durable snapshot first.
5. Apply the intended change through the available tool, then check application and
   verification. Read state to investigate a mismatch or uncertain result; never blindly retry
   a timed-out write that may already have applied.
This prompt is static guidance and executes no tools. The MCP host controls authorization.
"""
