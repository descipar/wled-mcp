"""Static agent guidance shared by every MCP transport (AGENT-01)."""

INSTRUCTIONS = """Read wled_get_state before changing lighting and choose the smallest change.
Use wled_patch_segments to patch selected existing segments; wled_replace_layout replaces
the complete layout and removes active segment IDs omitted from the request. Segment stop
(and stop_y) is exclusive. Omitted fields preserve existing values; they are not resets.
Effect and palette IDs are device-specific: read that device's catalogs rather than guess.
Use dry_run=true to inspect a proposed write, then inspect the result's application and
verification fields and read state when needed. A timed-out or uncertain write may already
have applied: never retry it blindly. Overwriting a preset requires overwrite=true and a
durable snapshot is taken first. Authorization belongs to the MCP host; these instructions
and tool annotations do not add a confirmation mechanism or grant access.
"""

PROMPT_NAME = "change_lighting_safely"
PROMPT_DESCRIPTION = "Plan a small lighting change, preview it, and verify the outcome."
PROMPT_TEXT = """Help make the requested lighting change safely:
1. Identify the configured device or stored zone/scene and read its current state.
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
