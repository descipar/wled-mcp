# Proposed MCP tool contract

This document is a design contract, not an implemented API. Names may change only with updated requirements, examples and issues. Requirement IDs refer to [REQUIREMENTS.md](REQUIREMENTS.md).

## Shared conventions

- The same tools, input/output schemas and domain outcomes are exposed over stdio and Streamable HTTP. Select transport at startup; transport does not change device behavior or overwrite rules. `/mcp` is the independent service endpoint; stdio is client-managed via uvx. Both are required v1 modes.
- HTTP requests/sessions share process-wide device coordination. Transport disconnects do not imply a write was cancelled, and reconnect must not replay mutations. Authentication/Host/Origin rejection occurs before any device action and is distinct from tool-domain errors.

- Device-targeted tools require a configured `device_id`; no caller-supplied host or URL.
- Unknown properties and null for nonnullable fields are rejected. Missing optional fields mean unchanged, never zero or false. No schema-inserted default for a patchable light value.
- Human-facing brightness is 0–255 in v1. Transition input is `transition_ms`; the adapter documents WLED conversion, rounds deterministically to supported units and reports the effective value. If a request cannot be represented meaningfully, reject it rather than silently changing units.
- LED ranges use zero-based `start` and exclusive `stop`. Segment IDs are explicit and stable; array position is not an identifier.
- All write tools support `dry_run=false`; true permits bounded reads only. Dry runs include a plan and target identity, never claim state was applied or slots reserved.
- Default scope is one controller per call. Different-device calls can overlap; a per-device lock covers the entire mutation and verification sequence.
- The server does not add interactive confirmation dialogs. Explicit overwrite flags and precise target parameters express intent; the host applies user authorization.

## Proposed v1 tools

| Tool | Essential inputs | Result / behavior | Priority |
| --- | --- | --- | --- |
| `wled_list_devices` | `probe=false` | Configured IDs/names; optional bounded per-device reachability | Must |
| `wled_get_state` | `device_id` | Current normalized state, raw state, essential info/capabilities | Must |
| `wled_get_effects` | `device_id`, `refresh=false` | Real effect IDs, names, optional metadata, freshness | Must |
| `wled_get_palettes` | `device_id`, `refresh=false` | Real palette IDs/names, freshness | Must |
| `wled_set_state` | `device_id`, optional `on`, `brightness`, `transition_ms`, `dry_run` | Master state patch only; require at least one changed field | Must |
| `wled_patch_segments` | `device_id`, `segments`, `dry_run` | Patch explicit existing segment IDs; no removal | Must |
| `wled_replace_layout` | `device_id`, complete `segments`, `dry_run` | Create requested active layout; explicitly remove other existing IDs | Must |
| `wled_list_presets` | `device_id` | Persistent IDs/names/types, including ordinary vs playlist distinction | Must |
| `wled_get_preset` | `device_id`, `preset_id` | Full saved object with field preservation | Must |
| `wled_activate_preset` | `device_id`, `preset_id`, `dry_run` | Activate existing preset/playlist without modifying storage | Must |
| `wled_save_preset` | `device_id`, `name`, optional `preset_id`, `overwrite=false`, `dry_run` | Save current state; allocate a free ID if omitted; verify persistence | Must |
| `wled_delete_preset` | `device_id`, `preset_id`, `dry_run` | Snapshot first; delete that ID; verify persistent absence | Must |
| `wled_restore_preset` | `device_id`, `backup_id`, `preset_id`, `overwrite=false`, `dry_run` | Restore one validated snapshot; obey destination collision and backup rules | Should |
| `wled_patch_raw_state` | `device_id`, JSON object `patch`, `dry_run` | Optional allowlisted advanced state patch; default disabled | Should |

Saving supplied state is a Should extension to `wled_save_preset`: add a typed `state` only after behavior and live-output side effects are established. Absence means current state; an empty state object must not mean “capture current” accidentally. Proposed preset ID range is 1–250, but the implementing agent must verify firmware behavior and handle reserved entries before claiming compatibility.

## Segment schema

Core fields: `id`, `start`, `stop`, `on`, `brightness`, `colors`, `effect_id` or `effect_name`, `palette_id` or `palette_name`, `speed`, `intensity`. `colors` is a list of up to three channel arrays, each RGB or supported RGBW. Effect and palette ID/name forms are mutually exclusive. Do not pad a missing white channel or change white/CCT interpretation silently.

Additional Should fields: `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected`, `name`; CCT/2D fields require an explicitly documented extension and fixture/hardware coverage. Reject unsupported field requests with a useful capability error rather than ignoring them.

Patch mode requires an existing `id` plus at least one mutable field; ranges may be changed if the resulting range is valid. Replace mode requires each active segment's `id`, `start`, `stop` and colors or a documented explicit color-preservation choice. Construct removal commands from observed old IDs minus desired IDs, using WLED's documented removal semantics. Never assume ten trailing deletion entries are sufficient. Validate the resulting layout, including unchanged segments when range changes can conflict.

Example patch (synthetic device):

```json
{
  "device_id": "desk",
  "segments": [{"id": 2, "speed": 80}],
  "dry_run": true
}
```

Example replacement:

```json
{
  "device_id": "desk",
  "segments": [
    {"id": 0, "start": 0, "stop": 30, "colors": [[255, 140, 40]], "effect_id": 0},
    {"id": 1, "start": 30, "stop": 60, "colors": [[0, 0, 255]], "effect_id": 0}
  ],
  "dry_run": true
}
```

The exact missing-field behavior of replacement must be finalized in [issue #2](https://github.com/descipar/wled-mcp/issues/2): preferred default is to preserve unspecified state on an existing desired ID and apply documented server defaults to newly created IDs. The plan must show both; replacement guarantees the set/ranges of active segments, not an undocumented reset of every WLED parameter.

## Result envelope

Proposed structured content:

```json
{
  "schema_version": 1,
  "ok": true,
  "operation": "patch_segments",
  "device_id": "desk",
  "dry_run": true,
  "application": "not_attempted",
  "verification": "not_requested",
  "data": {"plan": {"update_segment_ids": [2]}},
  "warnings": [],
  "error": null
}
```

`application`: `not_attempted`, `applied`, `not_applied`, `unknown`. `verification`: `not_requested`, `verified`, `mismatch`, `unknown`. Expected offline/validation/capability failures have `ok=false`, a stable error code and compact message. A mutation only has `ok=true` once required verification succeeds. A dry run has `ok=true` if its plan is valid, while application remains `not_attempted`.

Proposed errors: `CONFIG_ERROR`, `UNKNOWN_DEVICE`, `UNREACHABLE`, `TIMEOUT`, `INVALID_RESPONSE`, `VALIDATION_ERROR`, `UNSUPPORTED_CAPABILITY`, `AMBIGUOUS_NAME`, `PRESET_NOT_FOUND`, `PRESET_CONFLICT`, `BACKUP_FAILED`, `WRITE_OUTCOME_UNKNOWN`, `VERIFICATION_MISMATCH`. Include retryability for reads and a clear reconciliation suggestion for uncertain writes. Never recommend blind replay of an indeterminate write.

When supported by the selected SDK, return this envelope through `structuredContent`, enforce an output schema, and provide a text rendering of the same outcome for older clients. Use `isError=true` for unsuccessful tool execution, including uncertain writes; do not turn device failures into JSON-RPC transport errors. An offline entry in a successful multi-device inventory probe is data, not failure of the whole inventory request.

## Idempotency and side effects

Reads are read-only. Absolute state setters can be semantically idempotent, but animations, transitions and external controllers limit assumptions; choose annotations based on actual behavior. Preset allocation is not idempotent. Overwrite/delete/restore are destructive storage operations with explicit intent and backups. Tool descriptions must state physical output changes, persistence changes, and whether playback/active presets can interfere.

## Contract evolution

Add representative input/output examples and schema snapshots when implementing. Keep request validation and normalized domain behavior independent from MCP decoration. Any change to patch/replace or overwrite semantics needs an updated decision record and corresponding tests.
