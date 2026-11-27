# V1 MCP tool contract

Design baseline for [issue #2](https://github.com/descipar/wled-mcp/issues/2) plus the tools added since. Technical
choices and their authority are in [the issue decisions](decisions/stage-1.md); requirement IDs refer to
[REQUIREMENTS.md](REQUIREMENTS.md); synthetic cases are in [examples/contracts](../examples/contracts/README.md).
Contract text added from stage 2 on lives in per-area files under `docs/contract/`, linked from the [list at the
end](#stage-2-and-later-files); see [where new documentation goes](AGENT-WORKFLOW.md#where-new-documentation-goes).
Inventory and client foundations: [INVENTORY-CLIENT.md](INVENTORY-CLIENT.md).

Status: every tool in the tables below is implemented; the "V1 tools" table names the owning issue and file. The
discovery tools of M8 are released; live evidence (the #203 enrollment ran twice on 2026-11-19, the #204
discovery runs passed on 2026-11-20) is in [validation/m7-m8.md](validation/m7-m8.md). `wled_patch_raw_state` remains a design
requirement, not executable behavior (ISSUE-13-DEC-001). Hardware acceptance of the preset tools (H06): [VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).

## Shared conventions

- stdio and Streamable HTTP expose identical tools, schemas and domain outcomes.
- Device tools require a configured `device_id`; no caller-supplied host/URL. The one bounded exception is
  `wled_add_device` (an RFC 1918 IPv4 literal, one `GET /json/info`, class `manage`;
  [contract/discovery.md](contract/discovery.md)); discovery probes only configured ranges.
- Reject unknown fields, null nonnullable values, booleans as integers and values outside limits. Omitted fields mean
  unchanged, never zero/false/reset. No light-value defaults in patch schemas. Empty patch objects/lists fail.
- Ranges are zero-based with exclusive `stop`; explicit segment IDs are stable identifiers, not request-array positions.
- All mutations accept `dry_run=false`. True permits bounded reads only: no device POST, snapshot/temp-file/retention
  write or slot reservation. A valid plan is not a transaction or reservation; actual writes replan under the same
  device lock.
- One process-wide per-device lock covers fresh reads, complete validation, collision recheck, backup, all writes and
  verification. Different devices progress concurrently; external clients stay outside this lock.
- The served schemas are slimmed (#235): generated `title` keys and `default: null` on nullable optional fields are not
  served; validation, field names, bounds and non-null defaults are unchanged. `tests/test_tool_budget.py` enforces a
  size budget per tool and per profile ([measurements](validation/m7-m8.md)); growth is a deliberate decision.
  Since #246 the segment definitions (`SegmentPatch`, `LayoutSegment`) of `wled_patch_segments`, `wled_replace_layout`
  and `wled_preview_layout` are served without the `null` branch of optional fields; other tools keep `anyOf [T, null]`
  for nullable optional fields (#290 measured, not implemented). Explicit `null` is accepted everywhere as before.
  See [validation notes](validation/m7-m8.md).
- Validate the entire request and planned sequence before the first write. Report interference; never repeatedly
  overwrite to make verification pass.
- User authorization belongs to the MCP host; no interactive approval mechanism is added inside the server. Precise
  targets/overwrite flags express intent.

## Tools at a glance

Hints are MCP tool annotations for the host; they are advisory, not an authorization barrier. A deployment can
register only some tools by group ([tool groups](contract/profiles.md#tool-groups)); each tool belongs to one group,
listed there. The next section lists the
essential inputs of each tool.

| Tool | Hint | Purpose |
| --- | --- | --- |
| `wled_list_devices` | read-only | Configured device IDs, names and rooms; optional reachability probe |
| `wled_get_service_status` | read-only | Local service facts; contacts no device |
| `wled_get_state` | read-only | Normalized state, segments and capabilities |
| `wled_get_live_snapshot` | read-only | Sampled LED colors per segment |
| `wled_explain_lighting` | read-only | Observed facts, candidate causes and next checks; two GETs, never a write |
| `wled_get_effects` | read-only | Effect IDs and names, with cache freshness |
| `wled_get_palettes` | read-only | Palette IDs and names, with cache freshness |
| `wled_search_effects` | read-only | Effects matching curated properties, with an explanation per result |
| `wled_list_zones` | read-only | Stored named zones, or one zone's document |
| `wled_plan_zone` | read-only | Preview of a zone's exact segments and LED ranges, or the refusal |
| `wled_apply_zone` | write | Segment fields on exactly the segments inside one zone |
| `wled_apply_room` | write | A master state or stored scene to one room; strict preflight, not atomic |
| `wled_preview_layout` | read-only | Static SVG of the observed or a proposed 1D layout; no write |
| `wled_start_signal` | write | Temporary colour on chosen segments for 1 to 300 seconds, then conditional restore |
| `wled_get_signal_status` | read-only | Temporary signals from process memory; contacts no device |
| `wled_cancel_signal` | write | End a signal now with the same conditional restore |
| `wled_discover_devices` | read-only | Candidate controllers from mDNS and stored ranges; writes nothing ([contract/discovery.md](contract/discovery.md)) |
| `wled_set_discovery_ranges` | destructive | Replace the stored discovery ranges; local inventory file only |
| `wled_add_device` | write | Add one controller after one read-only `GET /json/info`; no device write |
| `wled_set_state` | write | Master power, brightness and transition |
| `wled_patch_segments` | write | Change selected existing segments by ID |
| `wled_replace_layout` | destructive | Set the complete segment layout; unlisted segments are removed |
| `wled_list_presets` | read-only | Persistent preset IDs, names and types |
| `wled_get_preset` | read-only | One stored preset as the device keeps it |
| `wled_activate_preset` | write | Activate an existing state preset or playlist |
| `wled_save_preset` | destructive | Save the current live state as a preset; overwriting needs `overwrite=true` |
| `wled_delete_preset` | destructive | Delete one preset after a durable snapshot |
| `wled_list_snapshots` | read-only | Stored preset snapshots, newest first; no device read |
| `wled_restore_preset` | destructive | Restore one snapshot entry live, then store it |
| `wled_store_preset` | destructive | Store a supplied, validated state as a preset |
| `wled_save_playlist` | destructive | Create or replace a playlist of existing state presets |
| `wled_export_presets` | read-only | Portable preset bundle without addresses or credentials |
| `wled_import_presets` | destructive | Import a bundle with dry-run preview, explicit mapping and per-entry verification |
| `wled_list_groups` | read-only | Stored groups with their member expansion; local files only |
| `wled_save_group` | destructive | Create or replace a named group (local file) |
| `wled_delete_group` | destructive | Delete one stored group file |
| `wled_list_scenes` | read-only | Stored scenes, one scene, or a shareable export |
| `wled_save_scene` | destructive | Validate and store a versioned scene; replacing needs `overwrite=true` |
| `wled_delete_scene` | destructive | Delete one stored scene file |
| `wled_plan_scene` | read-only | Dry-run plan of a scene; no write |
| `wled_apply_scene` | write | Apply a stored scene: strict preflight, one verified outcome per device, not atomic |

## V1 tools

| Tool | Essential inputs | Behavior | Priority / owner |
| --- | --- | --- | --- |
| `wled_list_devices` | `probe=false` | Configured IDs/names, each with its `room` (local groups; never fails the list); optional independent bounded reachability | Must; room fields #183 ([rooms](contract/rooms.md)) |
| `wled_get_service_status` | none | Local service facts: version, transport, uptime, profile, tool groups and per-device ceilings, last observed outcome per device, call counters; never contacts a device | S2-ACCESS-03; #20 ([diagnostics](contract/diagnostics.md)) |
| `wled_get_state` | `device_id` | Normalized current state, raw state, essential info/capabilities | Must |
| `wled_get_live_snapshot` | `device_id`, optional `max_runs=512` | Sample-only per-segment RGB runs with global bounds, unavailable endpoints and unmapped matrix geometry | LIVE-01; #150 ([live-snapshot](contract/live-snapshot.md)) |
| `wled_explain_lighting` | `device_id`, optional `segment_id`, optional `requested` (`white_channel`, `effect_id`, `palette_id`) | Fresh state and info read once each, combined with process-local last-control evidence; observations, inferred causes (capped at medium; a directly observed blocker may be high), conclusion, limits | S3-EXPLAIN-01/-02; #30 ([explain](contract/explain.md)) |
| `wled_get_effects` | `device_id`, `refresh=false`, optional `query`, `two_d`, `audio_reactive` | Original IDs/names, optional metadata, freshness | Must |
| `wled_get_palettes` | `device_id`, `refresh=false` | Original IDs/names, freshness | Must |
| `wled_search_effects` | `device_id`, optional `motion`, `flashing`, `colors_min`, `colors_max`, `uses_palette`, `strip_length`, `min_visibility`, `max_palette_saturation_need`, `strict=true`, `min_confidence`, `limit` | Curated property search intersected with the device's effect list; read-only | S3-EFFECT-01, S3-EFFECT-02; #31 ([effect-search](contract/effect-search.md)) |
| `wled_list_zones` | optional `zone` (ID or name) | Zone summaries and cross-zone warnings, or one zone's stored document; local files only | S3-ZONE-01; #27 ([zones](contract/zones.md)) |
| `wled_plan_zone` | `zone`, optional `segments` (one object of segment fields), optional `room`, `mode=strict` | Read-only resolution onto existing segments, per-device refusals, optional real segment plan | S3-ZONE-01, S3-ZONE-02; #27 |
| `wled_apply_zone` | `zone`, `segments` (one object of segment fields), optional `room`, `mode=strict`, `dry_run` | Verified write of those fields to the zone's segments only; `dry_run` equals the plan | S3-ZONE-02; #27 |
| `wled_apply_room` | `room`, exactly one of `state` (`on`, `brightness`, `transition_ms`) and `scene_id`, `mode=strict`, `dry_run` | Verified master state or stored scene on the members of a room; refused as a whole before any write for a conflict, a partly assigned member with `state`, or a scene outside the room; `dry_run` returns the plan | ROOM-03; #183 ([rooms](contract/rooms.md)) |
| `wled_preview_layout` | `device_id`, optional `segments` (a proposed complete layout), `allow_overlap=false`, `zone`, `live_samples=false` | Read-only SVG string `data.svg` plus a summary; observed without `segments`, proposed and planner-validated with them; 1D only, matrix refused | S3-PREVIEW-01, S3-PREVIEW-02; #29 ([layout-preview](contract/layout-preview.md)) |
| `wled_start_signal` | `device_id`, `segment_ids`, `color` (RGB), `duration_seconds` (1-300), `dry_run` | Verified apply of slot-0 colour and the Solid effect on existing segments, operation ID and captured prior values; restore at expiry only if the owned fields are unchanged, else `skipped_conflict` | S3-SIGNAL-01, S3-SIGNAL-02; #28 ([signals](contract/signals.md)) |
| `wled_get_signal_status` | optional `operation_id` | Active and recently ended signals with owned fields and restoration result; process memory only | S3-SIGNAL-01; #28 |
| `wled_cancel_signal` | `operation_id` | The same conditional restore now; result `restored`, `skipped_conflict` or `uncertain` | S3-SIGNAL-02; #28 |
| `wled_discover_devices` | optional `methods` (`mdns`, `unicast`), `timeout_seconds` (1-30), `max_candidates` (1-64); no range, host or cap field | `candidates`, `coverage`, `proposed_ranges`; one run at a time (`DISCOVERY_BUSY`) | DISC-01 to DISC-06; #200 |
| `wled_set_discovery_ranges` | `ranges` (the complete new list, `[]` clears), `dry_run` | Validated against the hard caps (all rejections in `data.rejected[]` with `index` and `reason`), written to `[discovery].ranges` of the inventory file through the shared writer and applied without restart; result `ranges_before`, `ranges_after`, `changed`, `written`, `reloaded`, `backup`, `caps`; writes no device | DISC-07; #202 ([discovery](contract/discovery.md)) |
| `wled_add_device` | `base_url` (`http://<RFC 1918 IPv4>[:port]`), optional `device_id`, `name`, `expected_mac`, `dry_run`; no candidate, range, host or timeout field | One read-only `GET /json/info`, then one `[[devices]]` entry (with `mac`) written through the shared writer and applied without restart; result `entry`, `verified`, `inventory_size`, `reloaded`, `written`; refuses duplicate ID, address or MAC (`INVENTORY_CONFLICT`), a non-WLED answer is `NOT_WLED`; writes no device | DISC-08; #203 ([discovery](contract/discovery.md)) |
| `wled_set_state` | `device_id`, optional `on`, `brightness`, `transition_ms`, `dry_run` | Master patch, at least on or brightness | Must |
| `wled_patch_segments` | `device_id`, nonempty `segments`, `dry_run` | Patch explicit existing active IDs, no removal | Must |
| `wled_replace_layout` | `device_id`, nonempty complete `segments`, `dry_run` | Exactly desired active IDs/ranges; remove stale IDs | Must |
| `wled_list_presets` | `device_id` | Persistent IDs/names/types, excluding reserved/empty entries | Must |
| `wled_get_preset` | `device_id`, `preset_id` | Exact persistent object, unknown fields preserved | Must |
| `wled_activate_preset` | `device_id`, `preset_id`, `dry_run` | Activate supported existing state/playlist entry, no storage edit | Must |
| `wled_save_preset` | `device_id`, `name`, optional `preset_id`, `overwrite=false`, `dry_run` | Save current state; lowest free ID if omitted; persistent verification | Must |
| `wled_delete_preset` | `device_id`, `preset_id`, `dry_run` | Snapshot first; delete exactly that ID; verify absence | Must |
| `wled_list_snapshots` | `device_id`, optional `preset_id` | Server snapshot metadata, newest first; no device I/O | Should; #18 ([presets](contract/presets.md)) |
| `wled_restore_preset` | `device_id`, `backup_id`, optional `preset_id`, `overwrite=false`, `dry_run` | Explicit single-entry storage restoration; applies the entry live (or starts the playlist), then stores it | Should; #18 |
| `wled_store_preset` | `device_id`, `name`, `state`, optional `preset_id`, `overwrite=false`, `dry_run` | Supplied, validated light state; applied live, then stored | Should; #18 |
| `wled_save_playlist` | `device_id`, `name`, `entries`, `repeat`, `shuffle`, optional `end_preset_id`, `preset_id`, `overwrite=false`, `dry_run` | Native playlist of existing state presets; saving starts it, then it is stored | Should; #18 |
| `wled_export_presets` | `device_id`, optional `preset_ids`, `include_unwritable=false` | Versioned preset bundle without device data, returned inline | Should; #18 |
| `wled_import_presets` | `device_id`, `bundle`, optional `id_map`, `effect_map`, `palette_map`, `overwrite_ids`, `dry_run` | Dry-run preview, explicit mappings, snapshots first, per-entry single writes, stop at the first unverified entry | Should; #18 |
| `wled_list_groups` | optional `group_id` | Stored groups with the exact member expansion; one group with its document; local files only | Should; #17 ([groups-scenes](contract/groups-scenes.md)) |
| `wled_save_group` | `group_id`, `name`, `members` (`device`, optional `segments`), `kind="group"` (or `room`), `overwrite=false`, `dry_run` | Create or replace a group of configured devices as a local file; no device I/O | Should; #17 |
| `wled_delete_group` | `group_id`, `dry_run` | Delete one stored group file | Should; #17 |
| `wled_list_scenes` | optional `scene_id`, `shareable=false`, `include_targets=false` | Stored scenes; one scene document; shareable export with placeholders; local files only | Should; #17 |
| `wled_save_scene` | `scene` (JSON text or object), optional `target_map`, `overwrite=false`, `dry_run` | Validate and store a versioned scene as a local file; placeholders need `target_map`; no device I/O | Should; #17 |
| `wled_delete_scene` | `scene_id`, `dry_run` | Delete one stored scene file | Should; #17 |
| `wled_plan_scene` | `scene_id`, `mode=strict` | Read-only plan: exact targets, per-device preflight with the real planners, names resolved per device, no write | Should; #17 |
| `wled_apply_scene` | `scene_id`, `mode=strict`, `dry_run` | Preflight of every device, then per device master state first and segments second through the verified write path; one independent outcome per device, no cross-device atomicity, rollback or replay; `dry_run` returns exactly the plan | Should; #17 |
| `wled_patch_raw_state` | `device_id`, JSON object `patch`, `dry_run` | Restricted advanced state patch | Should; excluded from stage 1, `raw_state_patch = true` rejected at startup, no owning issue (ISSUE-13-DEC-001) |

Tool descriptions state physical output, playback and storage effects. State/layout changes may clear the active-preset
marker or interrupt playback without editing saved objects. Never silently disable timers, realtime inputs or another
client. Activation is restricted to verified state/playlist shapes and safe referenced entries; API-command/unknown
presets remain readable and backupable, but activation returns `UNSUPPORTED_CAPABILITY`. No arbitrary command forwarding
or implicit playlist editing.

## Read tools: state and catalogs (implemented in #5)

Requirements READ-01/02/03, DEV-02, MCP-02 and partial OPS-04; decisions [ISSUE-5-DEC-001–008](decisions/stage-1.md).
Inputs are strict (unknown fields and non-boolean `refresh` rejected). All three are read-only, idempotent, closed-world
and return `application=not_attempted`, `verification=not_requested`, `dry_run=false`. Failures use existing error codes
only, with `ok=false` and empty `data`; messages name the fixed resource label and numeric HTTP status, never a body,
URL or exception text. An unknown `device_id` gives `UNKNOWN_DEVICE` (envelope `device_id` null) and no HTTP.

**`wled_get_state(device_id)`** reads `/json/state` then `/json/info` sequentially under one deadline and the per-device
lock. It is never cached and not an atomic snapshot. `data`: `device{id,name}`, `freshness{source="device",read_at}`,
`firmware{version,build_id,product,brand, arch}` (null if absent; only `ver` is required), `capabilities` (`led_count`,
`max_segments`, `effect_count`, `palette_count`, `device_wide_color`, `segment_color_capability_reported`, `matrix`),
`state`, `raw{state,info,redacted_info_keys}` and
`diagnostics{server_version,unknown_capabilities,firmware_support{tier,minimum_supported}}`; `warnings` lists tolerated
anomalies. `firmware_support` is the informational DEC-020 firmware tier with one warning below 16.0.0 or for an
unrecognizable version, never a refusal ([compatibility](contract/compatibility.md#wled-firmware-tiers), #21).

- Required: info object with string `ver`; state boolean `on`, integer `bri` 0–255 (booleans rejected), `seg` list of
  objects with unique non-negative integer `id` and integer `start`/`stop`. Violations give `INVALID_RESPONSE`. Optional
  fields of the wrong type become `null` plus a warning; unreported capabilities are `null`, never `false`, and the
  unknown names are listed in `diagnostics.unknown_capabilities`.
- `state`: `on`, `brightness` (remembered), `effective_brightness` (`on ? bri : 0`), `default_transition_ms`
  (`transition * 100`), `active_preset_id` and `active_playlist_id` (`-1` becomes `null`), `main_segment` and
  `segments`. Segments are identified by their explicit `id`, never by array position, and carry `start`, `stop`, `on`,
  `brightness`, `effective_brightness` (`brightness` if the segment is on, else 0; the pinned firmware reports segment
  `bri` as 255 when its opacity is 0, so such a segment shows 255 even while on), `colors`, `color_channels`,
  `reported_color_capability`, `effect_id`, `palette_id`, `speed`, `intensity` and, when present, `grouping`, `spacing`,
  `offset`, `reverse`, `mirror`, `selected`, `name`; missing values are null. Issue #19 adds further fields
  ([contract/segments.md](contract/segments.md)).
- `device_wide_color{scope,rgb,white,cct}` is the firmware aggregate (`info.leds.lc`), reported only when that value is
  an integer, and is not proof for any range. `reported_color_capability` comes from `state.seg[].lc` or else from
  `info.leds.seglc` (#19, [contract/segments.md](contract/segments.md)), the latter used only when its length equals the
  segment list. A fourth color channel is trimmed only when `info.leds.seglc` proves the segment RGB-only (RGB bit
  without white/CCT) and every slot's fourth channel is 0; `raw.state` always keeps the original arrays.
- Redaction (DEC-006): `mac`, `ip` and `wifi.bssid` are removed from `raw.info` and listed in `raw.redacted_info_keys`.
  Raw state is unchanged.

**`wled_get_effects` / `wled_get_palettes(device_id, refresh=false)`** return `effects` or `palettes` as
`[{id,name,[metadata:{fxdata,parsed,warnings}]}]` ordered by ID, `count`, (effects only) `metadata{status:
available|unavailable, reason}` and `freshness{source: device|cache, fetched_at, age_seconds, cache_ttl_seconds,
firmware{version,build_id}, refreshed}`. `refreshed` echoes that the call bypassed the cache by request.

- ID is the original array index of the device list; IDs are never renumbered and no count is hardcoded. A difference
  from `fxcount`/`palcount` is a warning only. Effect slots serialized as `"RSVD"` are excluded from listing and name
  resolution (#148). `/json/pal` lists built-in/gradient names, not custom palettes, so `palcount` may exceed the list.
- Effect metadata is the raw `/json/fxdata` string per effect, attached by index only when the list length equals the
  effect list; it is never a name source. Lenient parsed labels, palette selector, flags and defaults are additive
  (#148); unknown/malformed properties remain unknown with warnings. Any fxdata failure or length mismatch gives
  `ok=true`, intact names, `metadata.status=unavailable`, a reason (error code or `length_mismatch`) and one warning.
  The optional read gets at most half of the remaining deadline.
- `wled_get_effects` also accepts optional `query`, `two_d` and `audio_reactive` filters; unknown metadata matches
  neither boolean. `count` is the number returned ([effect metadata](contract/effect-metadata.md)).
- Cache: key `(device_id, kind)`, effects plus fxdata one unit, TTL `http.catalog_cache_seconds` (0 disables storage).
  Every call performs one fresh `/json/info` read. A live entry with identical `(ver, vid)` is served as `source=cache`
  with its age and no catalog/fxdata request; a changed identity drops it and refetches. `refresh=true` always reads the
  device and replaces the entry only on success; a failed refresh or info failure returns that error (no stale fallback,
  an expired entry is never served) and leaves the previous entry in place. Cached warnings repeat for the entry's
  lifetime.
- Shared name resolution: a unique exact case-sensitive match, else a unique case-folded trimmed match. Segment tools
  expose names (#149): several matches give `AMBIGUOUS_NAME` with at most ten `{id,name}` entries in `data.candidates`;
  no match gives `VALIDATION_ERROR` with up to ten substring suggestions, never applied automatically
  ([contract/segment-names.md](contract/segment-names.md)).

## Power, brightness and transition

`brightness` accepts integers 0–255. Reads distinguish remembered brightness from `effective_brightness` (zero while
off). Positive brightness sets the remembered level and preserves omitted `on`; the adapter compensates coupled firmware
power behavior. `on=false` alone preserves remembered brightness. A zero request targets off/effective zero. To preserve
omitted power, accept zero only when resolved `on` is false; otherwise reject before POST and suggest explicit
`on=false`. Reject explicit `on=true, brightness=0`. Turning on requires a known positive remembered value or an
explicit positive brightness. An omitted field never silently turns the light off/on.

The reviewed firmware handles master and segment state differently: master `bri` readback is remembered brightness while
`on` reflects actual power; segment zero brightness switches its on flag off while retaining opacity. Verify normalized
power/effective zero and retained remembered level separately; do not demand raw `bri=0` or treat remembered nonzero
readback as failed off. Effects and unrelated transient frames are not equality targets.

### Master power rules (`wled_set_state`)

Issue #52, [ISSUE-52-DEC-001](decisions/hardening.md). The pinned v0.15.1 firmware couples master power to brightness
(`on = root["on"] | (bri > 0)`), so a positive `bri` alone turns an off master on. The planner applies these rules
before any write and identically in a dry run (evidence: [SOURCES.md](SOURCES.md); hardware confirmation stays with
#12).

| Input | Rule | Outcome |
| --- | --- | --- |
| `on=true` with `brightness=0` | Rejected | `VALIDATION_ERROR`, zero POSTs |
| `brightness=0`, `on` omitted | Accepted only when the master is off; otherwise pass `on=false` explicitly | Off master: `{"bri": 0}`, verified off; on master: `VALIDATION_ERROR`, zero POSTs |
| `on=true` without `brightness` | Requires a positive remembered brightness | Remembered zero: `VALIDATION_ERROR`, zero POSTs |
| `brightness > 0`, `on` omitted, master off | Targeted compensation: the resolved `on=false` is sent with `bri` and listed in `plan.targeted_compensation` as `{"on": false}`; the master stays off and remembers the new brightness | Payload `{"on": false, "bri": X}`, `applied/verified` |
| `brightness > 0`, `on` omitted, master on | `bri` is sent alone; the master stays on | `applied/verified` |
| Explicit `on` with `brightness` | Sent as requested; not a compensation (`targeted_compensation` is `[]`) | `applied/verified` |
| Current master `on` not a boolean | Power is unknown; the state read already fails before planning | `INVALID_RESPONSE`, zero POSTs |

`plan.targeted_compensation` is always present for `wled_set_state` (`[]` or `[{"on": false}]`). `plan.on` keeps the
requested value (`null` when omitted) and `plan.resolved` shows the resolved `on` and `brightness`. Every master write
verifies the resolved `on` in the readback; a power flip is a `VERIFICATION_MISMATCH` (`application=unknown`), never a
silent success, and is not replayed. One-call `tt` is unchanged by compensation; whether the off master shows any
visible transition is unverified on hardware (#12). The plan is rebuilt from a fresh read under the per-device lock; an
external power change between that read and the POST remains a residual risk, and verification compares the readback
with the resolved target of that read, so such a reversal is not detected. `wled_set_state` has no segment fields, and
master `on=false` does not change segment power.

Master `transition_ms` affects this change only via WLED `tt`, leaving persistent `transition` untouched. Accept integer
0–65500 ms; wire units are `floor((transition_ms + 50) / 100)` (nearest 100 ms, half upward: 149 -> 100 ms, 150 -> 200
ms). Zero is immediate; reject 1–49 ms (they round to zero), overflow/negative/fractional values and transition-only
requests. Report requested/effective milliseconds and units. Readback verifies target state after the effective
transition. Reject before write when the overall deadline cannot accommodate the transition and verification; an ACK
that starts a long transition is not success. No physical timing precision is promised.

## Segments: schema and omissions

Core fields: `id`, `start`, `stop`, `on`, `brightness`, `colors`, `effect_id`, `palette_id`, `effect_name`,
`palette_name`, `speed`, `intensity`. Segment tools accept an effect or palette name instead of its ID, resolving per
device before planning or writing ([segment-names](contract/segment-names.md),
[groups-scenes](contract/groups-scenes.md)). Brightness/speed/intensity are integers 0–255; effects/palettes must exist
in target catalogs. Should fields: `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected`, `name`. Offset is 0
<= offset < resulting physical range length (no implicit wrap).

### Shared segment limits (`wled_patch_segments` and `wled_replace_layout`)

Issue #48, [ISSUE-48-DEC-001](decisions/hardening.md) (human decision; supersedes the #7-only name, 255-bound and `bri`
sending points of ISSUE-7-DEC-006). Both tools apply one rule set, implemented once (`src/wled_mcp/segment_rules.py`),
before any write and identically in a dry run. Evidence is the pinned v0.15.1 source
([SOURCES.md](SOURCES.md#issue-7-layout-evidence)); hardware confirmation stays with #12.

| Input | Rule | Outcome |
| --- | --- | --- |
| `name` | At most 32 UTF-8 bytes on every device (the firmware truncates by bytes; 32 is the build-independent minimum), no U+0000. The input schema keeps `maxLength: 32` (characters) as a coarse bound. | Otherwise `VALIDATION_ERROR` naming the segment and the byte limit, zero POSTs |
| `grouping` / `spacing` | 1-255 / 0-255 (firmware `uint8_t`); both input schemas advertise `maximum: 255` | 256 or more fails schema validation (`VALIDATION_ERROR`), zero HTTP |
| `on=true` with `brightness=0` | Rejected (the firmware would end on) | `VALIDATION_ERROR`, zero POSTs |
| `brightness=0`, `on` omitted | Accepted only when the segment is reported off (a new #7 ID counts as on; an unreported current power also counts as not off); otherwise pass `on=false` explicitly | `VALIDATION_ERROR`, zero POSTs |
| `brightness > 0`, `on` omitted, segment off | Targeted compensation: the resolved `on=false` is sent with `bri` and listed in `plan.targeted_compensation` as `{"id": N, "on": false}`; the segment stays off with the new remembered brightness | `applied/verified` |
| `brightness > 0`, `on` omitted, segment on | `bri` is sent alone; the firmware keeps the segment on | `applied/verified` |
| `brightness > 0`, `on` omitted, current power not reported | The power effect cannot be predicted; pass `on` explicitly | `UNSUPPORTED_CAPABILITY`, zero POSTs (unrelated fields still work) |

Whenever a positive `bri` is sent, the readback also verifies the resolved `on`, so a power flip is a
`VERIFICATION_MISMATCH`. For `wled_replace_layout` all of these causes are rejected or compensated before the first
POST; partial application remains possible only for other causes (external interference or an uncertain step), as
described below. The #19 segment fields (CCT, white-only colors, effect options, 2D bounds and orientation, blend mode)
and the `allow_overlap` opt-in follow the same rules in both tools
([contract/segments.md](contract/segments.md#write-rules-second-pull-request)). Unsupported fields/capabilities fail
explicitly; preservation of an existing unexposed field does not expose its setter.

`colors` is a nonempty list of 1–3 leading slots; channels are integers 0–255. Require exactly three channels for a
proven RGB-only range and four for RGBW; never pad white or drop it silently. Existing IDs retain omitted trailing
slots; new IDs resolve missing slots to black. An existing segment's reported capability supports its unchanged range;
new/moved ranges require a validated topology/range profile. Array width or the device-wide aggregate is not proof of
range capability. Unknown/inconsistent evidence is `UNSUPPORTED_CAPABILITY` before write; unrelated scalar changes can
still proceed.

Patch requires an existing active `id` plus at least one mutable field. All omitted fields and unrelated segments,
including unexposed extension state, are preserved. Firmware side effects (omitted name clearing on geometry changes,
effect parameter resets) require proven targeted compensation shown in `plan.targeted_compensation` with the same entry
shapes as `wled_replace_layout` (`{"id": N, "name": ...}` for a name resent on a geometry change, `{"id": N, "on":
false}` for the power compensation); never round-trip the whole configuration; reject an unrepresentable preservation
plan. Scalar patches may retain preexisting overlaps; a range-changing patch rejects introduced overlaps against the
complete resulting layout, including untouched IDs.

Replace requires every desired `id`, `start`, `stop`. Existing desired active IDs preserve omitted colors and other
state. New/reused inactive IDs require explicit colors and resolve omitted public fields using server defaults:

| Field | New segment default |
| --- | --- |
| on / brightness | true / 255 |
| colors | supplied leading slots, remaining slots black with proven channel width |
| effect_id / palette_id | 0 (Solid) / 0, verified in target catalogs |
| speed / intensity | 128 / 128 |
| grouping / spacing / offset | 1 / 0 / 0 |
| reverse / mirror / selected | false / false / false |
| name | empty string |

Defaults are established explicitly even in reused slots; ancillary inherited state affecting output (for example
freeze) is accounted for or rejected under the selected profile. These are server design choices, not firmware
constructor defaults. Master state is preserved. Derived selection/main-segment effects of removal appear in the plan;
if necessary a proven adapter selects the lowest desired main ID, otherwise reject. Segment IDs are never silently
remapped.

Before any write validate unique nonnegative IDs, known ID/count limits, `0 <= start < stop <= led_count`, all
field/capability constraints and the whole resulting layout. Empty replacement and replacement overlaps fail. Stale IDs
are fresh active old IDs minus desired IDs; deletion uses explicit ID and `stop=0`. Never append a fixed dummy tail.

### Firmware representability and partial writes

The [pinned source](SOURCES.md#issue-2-contract-evidence) shows that raw pass-through cannot guarantee this contract. A
supported profile must know ID allocation: existing IDs can be reused; new IDs are added ascending from the known next
allocatable slot; sparse new IDs that would append elsewhere are rejected (no gap fillers); unknown next-slot information
blocks creation, not valid existing-ID operations. For the reviewed profile, single-object `seg` deletion avoids the array
bulk-purge path, so a bounded plan uses exact-ID updates/creates and separate single-ID removals with interim readback;
intermediate ranges/ordering are validated, the final exact active IDs/ranges and preserved fields are verified, and the
sequence stops on mismatch/uncertainty with no replay, automatic rollback or further destructive steps. Completed steps,
remaining IDs and the last observed state are reported. Verified partial application is `application=applied`,
`verification=mismatch`, `ok=false`; any uncertain step makes application `unknown`. Intermediate light output is visible
and external clients can race. The [replacement fixture](../examples/contracts/replace.json) holds a representable
noncontiguous layout and a rejected sparse-new-ID request (acceptance targets, not firmware evidence).

## Layout replacement (implemented in #7)

Requirements SEG-02, SEG-03, SEG-04, SEG-05, MULTI-01 and REL-03 (plus REL-01/02 and the MCP-02 envelope); decisions
[ISSUE-7-DEC-001–007](decisions/stage-1.md) and [ISSUE-48-DEC-001](decisions/hardening.md). Evidence is mock-only and
source-derived ([SOURCES.md](SOURCES.md#issue-7-layout-evidence)); hardware check H05 is recorded for one controller in
[VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06), without stale-ID removal by this tool on
hardware.

**`wled_replace_layout(device_id, segments, dry_run=false)`**. Strict input (`segments`: 1-64 entries, unknown fields
rejected). Each entry needs `id`, `start`, `stop`; optional: `on`, `brightness`, `colors`, `effect_id`, `palette_id`,
`speed`, `intensity`, `grouping` (1-255), `spacing` (0-255), `offset`, `reverse`, `mirror`, `selected`, `name` (at most
32 UTF-8 bytes, no U+0000). ISSUE-7-DEC-002: #7 follows #6 wherever #6 defines handling. Names, grouping/spacing bounds
and the power/brightness rules (including the `brightness=0` rejections of ISSUE-7-DEC-007 and the `on=false`
compensation) are the [shared segment limits](#shared-segment-limits-wled_patch_segments-and-wled_replace_layout).
Annotations: `destructive_hint=true`, not read-only, not idempotent, closed-world (hints only).

Both segment tools also accept `cct`, `custom1`-`custom3`, `check1`-`check3`, `sound_simulation`, `segment_set`,
`map_1d_2d`, `freeze`, `blend_mode`, `start_y`/`stop_y`, `reverse_y`/`mirror_y`/`transpose` and the request-level
`allow_overlap` (#19), each settable only with fresh evidence ([contract/segments.md](contract/segments.md)). Not
exposed (ISSUE-19-DEC-002, ISSUE-13-DEC-001): pixel streaming (`i`), `rpt`, `fxdef`, matrix/panel configuration,
presets/snapshots and master `on`/`bri`/transition. Effect/palette name forms exist in the segment tools
([segment-names](contract/segment-names.md)).

Planning (one fresh read of state and info under the per-device lock and one deadline; identical for dry run and live
call; an earlier dry run is never a reservation):

1. Classify: `existing` = desired and active, `new` = desired and not active (including reused inactive slots), `stale`
   = active and not desired (exact set difference, any size, any gaps).
2. Validate the whole request before the first POST (unique IDs, `id < maxseg`, `0 <= start < stop <= led_count`, no
   overlap in the desired layout, effect/palette IDs inside the catalogs, offset `0 <= offset < length`, the shared
   segment limits, color widths). New IDs need explicit `colors`. Channel evidence for a new range is the profile-0
   uniform RGB-only rule (`leds.lc` is RGB-only and `leds.seglc` is absent or aligned and RGB-only); otherwise
   `UNSUPPORTED_CAPABILITY`, as for four channels on a new or moved range. Existing unchanged ranges follow
   ISSUE-6-DEC-003. A shrinking move whose preserved offset the firmware would clamp is rejected unless `offset` is
   supplied; an unrepresentable preserved `name`/`offset` is `UNSUPPORTED_CAPABILITY`.
3. Allocation: new ID `n` is accepted if `n <= B`, where `B` starts at `max(active IDs)+1` and becomes `max(B, n+1)`
   after each accepted new ID; IDs below the first bound are reused inactive slots. Otherwise `UNSUPPORTED_CAPABILITY`
   ("New ID 8 cannot be allocated as requested; the known next slot is 6."). `B` is a lower bound of the slot count
   because the single-object path never purges slots.
4. Ordered single-object steps: optional main-ID redirect, exact removals ascending (`{"seg":{"id":X,"stop":0}}`), then
   updates and creates chosen so that no step overlaps a segment still at an old range (creates strictly ascending). A
   range cycle that would need a temporary segment is rejected. When the old main ID is stale the main segment moves to
   the lowest desired ID: before the removals if that ID is active, after its creation otherwise (with a plan warning,
   because the firmware resets main to 0 on that removal).
5. Update steps send only fields that differ from the fresh read, `start`/`stop` only for a geometry change, plus the
   targeted compensation shown in the plan (existing name resent after a geometry change; `on=false` with a positive
   `bri` on an off segment with omitted `on`; `bri` alone on a segment that is on). Existing IDs without any difference
   get no POST (`unchanged_segment_ids`); a request that changes nothing is a no-op: `ok=true`,
   `application=not_attempted`, `verification=not_requested`, one warning, zero POSTs. Create steps send every public
   field (defaults table above) and `frz=false`, plus `cct` and the WLED 16 option defaults where every active segment
   reports the key (TD-19-6). Keys of a reused slot that stay unreset are listed in warning
   `inherited_unexposed_state`.

`data.plan` (dry run and live): `update_segment_ids`, `create_segment_ids`, `remove_segment_ids`,
`unchanged_segment_ids`, `main_segment_id`, `main_segment{current,target,changed,step}`, `resolved_segments` (every
public field plus `color_channels`), `targeted_compensation`, `steps` (text), `step_actions`, `step_payloads` (the exact
bodies), `warnings`, `noop`; plus `data.postconditions`. A dry run performs bounded reads only (`ok=true`,
`application=not_attempted`, no POST, no file write).

Execution: per step exactly one POST attempt and one bounded readback (ACK content is never proof). A step is verified
when the active ID/range set equals the expected intermediate layout and the sent fields match (leading color slots,
missing name equals empty, `bri=0` means segment off). The final check requires exactly the desired IDs and ranges, all
requested and resolved-default fields, preserved fields of existing IDs and the planned main ID. `data.steps_report`
lists `{index, action, id, status}` (`verified|failed|uncertain|not_dispatched`). Success is `applied/verified`. A
possibly dispatched POST that raised stops the sequence (accepted as success only for the last step with a matching
final state); a POST followed by a differing readback is `failed`; unreadable state is `uncertain`; no replay,
rollback, corrective write or further step follows. Mapping: unreadable -> `unknown/unknown` + `WRITE_OUTCOME_UNKNOWN`
(also when the POST raised and the readback matches the pre-write state); readable but differing after an uncertain or
first step -> `unknown/mismatch` + `VERIFICATION_MISMATCH`; later verified steps then a failed step or failed final
check -> `applied/mismatch` + `VERIFICATION_MISMATCH`; budget exhausted before a step -> `TIMEOUT` (`applied/mismatch`
if earlier steps were proven, else `not_attempted`). Failures carry `completed_steps`, `remaining_steps`, `observed`
(active `{id,start,stop}` and `mainseg` of the last read) and `no_replay`; a `failed` step in `remaining_steps` may
still have taken effect, so inspect `observed` before any new call. Failures before the first POST have empty `data`.
The per-device lock is held for the whole sequence. See [errors.json](../examples/contracts/errors.json) and
[replace.json](../examples/contracts/replace.json).

## Persistent presets

The reviewed profile supports integer IDs 1–250 (reserved key 0, temporary 255 and 251–254 excluded). Entries count as
absent only when recognized by the profile; a malformed store is never treated as all slots free. Duplicate names are
labels, not allocation keys; blank names, NUL/control characters and names over 32 UTF-8 bytes are rejected, never
truncated. Save-current has no `state` input; only storage controls are sent (`psave`, `n`, `ib=true`, `sb=true`,
`sc=false`), it does not activate the entry, and capture is asynchronous (not an atomic photograph). The lowest free ID
is rechecked immediately before dispatch; an observed new collision is `PRESET_CONFLICT`, never a silently chosen other
ID. Occupied explicit IDs need `overwrite=true` and a durable snapshot, rechecked before dispatch (an observed change is
a conflict); `overwrite=true` without explicit ID is invalid; exhaustion fails without writing. Delete targets exactly
the one existing ID. Persistent `/presets.json` is polled with cache bypass under one overall deadline: 10 seconds
including reads, backup, dispatch and verification; 3-second connection bound; at most one retry per safe read; initial
100 ms poll interval. Seeing an ID/name or live state alone is never verification; unrelated entry changes are
interference; no repeated write or automatic reversal follows a mismatch. A timed-out write can reconcile to a verified
postcondition with a transport warning; unavailable readback is `WRITE_OUTCOME_UNKNOWN`; a readable differing object at
the deadline is `VERIFICATION_MISMATCH`, not proof the command never applied. Activation verifies supported
state/playlist acceptance through bounded readback (playlist identity/status replaces frame equality).

PRE-03 supplied-state save is not part of #9 (ISSUE-9-DEC-001). #18 implements it as `wled_store_preset` and restore
execution as `wled_restore_preset`, both through one single-entry JSON API write with a documented live effect
(ISSUE-18-DEC-001; [contract/presets.md](contract/presets.md)). The storage-only variant ("without changing live
output") is unsupported on WLED 16; there is no implicit apply/save/restore workaround, no whole-file upload and no
execution of stored commands.

### Persistent presets, implemented in #9

Decisions: [ISSUE-9-DEC-001](decisions/stage-1.md), ISSUE-8-DEC-001 to -003. Evidence: mock-only (T11-T13); firmware
facts are pinned in [SOURCES.md](SOURCES.md#issue-9-preset-evidence) and are not hardware evidence.

Inputs are strict (`extra=forbid`, booleans are not integers). `preset_id` is an integer 1-250. `wled_save_preset(name,
preset_id=None, overwrite=false)`: `overwrite=true` without `preset_id` is rejected before any device access; there is
no `state` input; names are never trimmed or truncated.

Entry types (positive evidence only, `type` in list/get):

| Type | Recognized as | Activation |
| --- | --- | --- |
| `state` | object whose top-level keys are all within the allowlist `on`, `bri`, `transition`, `bs`, `mainseg`, `seg`, `n`, `ql`, `ledmap` (what a firmware save emits; `bs` is the WLED 16 blending style, ISSUE-66-DEC-001) and that has at least one of `on`, `bri`, `seg` | yes |
| `playlist` | object whose `playlist.ps` is a nonempty list of integers 1-250, no other stored control key (`psave`, `pdel`, `ps`, `pd`, `rb`, `win`, `live`, `time`, `bootps`) | yes, if every member (`playlist.ps` and a persistent `playlist.end` of 1-250) exists and is a `state` entry; `end=255` (restore previous preset) and any integer `end` outside 0-255 (the firmware keeps `end` in a byte, so it wraps onto another preset) are refused |
| `api-command` | object with a string-valued `win` key | `UNSUPPORTED_CAPABILITY` |
| `unknown` | any other object, including state-shaped objects with extra keys (`rmcpal`, `wifi`, `np`, `nl`, `lor`, `udpn`, vendor keys, control keys) | `UNSUPPORTED_CAPABILITY` |

A nonempty non-object entry is `unknown` with `malformed=true`: listed and readable, but neither overwritten nor deleted
(it cannot be snapshotted; `VALIDATION_ERROR`). Store keys that are not canonical decimal IDs 0-255 are skipped by
list/get with a count warning; save and delete then fail closed with `INVALID_RESPONSE` and zero POSTs.

- `wled_list_presets`/`wled_get_preset` (read-only): fresh GET of `/presets.json` per call (`Cache-Control: no-cache`),
  under the device lock and one deadline. List data: `device`, `freshness`, `presets` (`id`, `name|null`, `type`,
  optional `malformed`) ascending by ID, `count`. Get data adds the exact `preset` object. An empty slot is
  `PRESET_NOT_FOUND`.
- `wled_activate_preset`: one POST `{"ps": id}`, never any storage control; verified by bounded `/json/state` polling
  (`ps == id`, for a playlist `pl == id`). The firmware ignores re-selecting the already-active preset, so an
  already-active state preset adds a warning (a verified result then cannot prove re-application); an already-running
  playlist is restarted by the firmware but `pl == id` already holds, so only a weaker warning is given. Activation
  changes live output, may interrupt playback and clears/moves the active markers.
- `wled_save_preset`: inside the device lock: read store, choose the lowest free ID (or validate the explicit one), read
  state and info for the capture reference, snapshot if an occupied ID is replaced, recheck the destination, then
  exactly one POST `{"psave": id, "n": name, "ib": true, "sb": true, "sc": false}`. A destination that was free but is
  occupied at the recheck is `PRESET_CONFLICT` (no second allocation); an occupied one that no longer equals the
  snapshotted object is `PRESET_CONFLICT` (the snapshot is kept). Overwrite of an occupied `state`, `api-command` or
  `unknown` object needs `overwrite=true` and warns when the entry type changes; a `playlist` is never replaced
  (`UNSUPPORTED_CAPABILITY`, no snapshot, no POST). A free explicit ID with `overwrite=true` is accepted without
  snapshot (`data.overwrote=false`).
- `wled_delete_preset`: snapshot of any occupied object entry, recheck equality, one POST `{"pdel": id}`, verified by
  absence (key removed, `null` or `{}`). Referencing playlists and the active-preset marker are named in warnings and
  not edited.

Verification polls the persistent file every 100 ms (default) under the one 10 second deadline, reserving at most one
second for readback. The save compares name `n`, master `on`, `bri`, `transition`, `bs`, `mainseg` (each only when
present in the live state, so `bs` is compared on WLED 16 and not on 0.15.x) and, per active live segment, `id`,
`start`, `stop`, `on`, `bri`, `col`, `fx`, `sx`, `ix`, `pal`, `n`, `grp`, `spc`, `of`, `rev`, `mi`, `sel` against the
pre-dispatch state; inactive-slot markers (`{"stop": 0}`) are ignored and the set of stored segment IDs must equal the
live set. Any difference at the deadline is `VERIFICATION_MISMATCH` (`unknown/mismatch`) with `data.observed` and
`data.differences` (field names, bounded). A match is success with the standing warning that capture is asynchronous. A
verified save whose stored entry does not classify as `state` (for example a future firmware key) adds a warning naming
only the unexpected top-level keys that it will not be activated by this server; the outcome is unchanged and nothing is
rewritten. Unrelated entries that differ from the pre-dispatch reading are `data.interference` plus a warning (outcome
stays verified, no corrective write). A failed POST whose target stays unchanged is `WRITE_OUTCOME_UNKNOWN`; unreadable
readback at the deadline is `WRITE_OUTCOME_UNKNOWN`; a verified postcondition after a failed POST succeeds with a
transport warning. The POST is never repeated. Every post-dispatch result carries `data.preset_id`,
`name`/`deleted_type` and, when a snapshot was taken, `data.backup_id` plus prune warnings, so a caller reconciles by
reading before any new attempt (a new call may allocate the same still-unpersisted ID). Pre-dispatch failures (conflict,
unsupported, not found, validation, exhausted ID space `PRESET_CONFLICT`, `BACKUP_FAILED`, read failures) are
`not_attempted` with zero POSTs.

Dry runs perform bounded reads only: zero POSTs, no snapshot, no directory, no prune. Data: `plan`, `payload`,
`postconditions`; a plan is not a reservation. Annotations (hints only): list/get read-only; activate non-destructive
mutation; save and delete `destructive_hint=true`, not idempotent, closed world.

Residual limits: other clients can change the preset file between the final recheck and the firmware's asynchronous
write, and `/presets.json` has no transaction or compare-and-set, so a replaced entry may differ from the snapshotted
one in that window; whether saving moves the active-preset marker or briefly suspends the strip is not verified;
duplicate JSON keys in the store collapse to the last value; a store beyond the 2 MiB response bound fails closed.
`wled_get_preset` returns stored commands to the authorized caller verbatim.

## Snapshot and explicit restoration

A store plus a `Resources` seam (#8). `wled_save_preset` (overwrite), `wled_delete_preset`, `wled_store_preset` and
`wled_restore_preset` (overwrite) call it through `OperationContext.backup_preset` (#9, #18); restoration execution and
listing are in [contract/presets.md](contract/presets.md) (#18).

Format 1 contains exactly `format_version`, opaque server-generated `backup_id`, configured `device_id`, `preset_id`
(1-250), `firmware` identity (`version`, optional `build_id`), UTC `created_at` (`YYYY-MM-DDTHH:MM:SSZ`) and exact
`preset` object ([snapshot.json](../examples/contracts/snapshot.json)). No integrity hash is defined (tampered local
storage is not authenticated); no MAC, URL or credential is stored. Unknown top-level envelope keys are rejected
(additions need a new format version); unknown fields inside `preset` are preserved verbatim and never executed.
Rejected on read: unknown/boolean/string versions, malformed metadata, unsafe IDs, files over 1 MiB, non-UTF-8,
duplicate JSON keys, NaN/Infinity, and empty or non-object `preset`. A snapshot whose envelope device, ID or timestamp
disagrees with its path is invalid.

Layout: `<data_dir>/backups/<device_id>/<backup_id>.json` (directories 0700, files 0600). `backup_id` matches
`b-<YYYYMMDD>T<HHMMSS>Z-<12 hex>` (UTC clock plus 48 random bits, never from preset names or caller text). The file is
created exclusively and never overwrites; a collision regenerates the ID. IDs resolve only inside the data directory: no
caller path, name or glob. Symlinked snapshot files, device directories and the `backups/` root itself are never
followed (#181: an operator who linked the root sees an empty listing with a warning, `PRESET_NOT_FOUND` on load and
`BACKUP_FAILED` on create; `data_dir` must point at the real location). Non-regular files (FIFOs, devices) are rejected
without being opened.

Write sequence (`backup_preset`, blocking I/O shielded from cancellation): same-directory temporary file created
exclusively, write, flush, `fsync`, read back and validate, publish by hard link (never overwrite), directory `fsync`
(best effort; skipped on Windows, so durability there is weaker), re-read and validate the final file. Any failure
removes the temp/final file this call created and raises `BACKUP_FAILED` with a message free of paths and payloads;
earlier snapshots stay intact. Leftover `.tmp` files are ignored.

Ordering for destructive preset operations (`OperationContext.backup_preset`): inside the device lock, read the preset
fresh, validate the whole request, snapshot the exact object, recheck the prior object (changed => `PRESET_CONFLICT`),
then POST. A raised `BACKUP_FAILED` happens in the prepare step (`application=not_attempted`, nothing sent). The store
does no device I/O. The result `data.backup_id` names the newest snapshot of the operation and is kept even when the
write later fails or is uncertain; there is no automatic rollback, restoration or resend (REL-02). Dry-run reports
`backup_required` and an advisory writability flag without creating directories, temp files or pruning.

Retention: default 20 valid snapshots per device (`backups.retain_per_device`, 1-1000). Only after the new snapshot is
durable, the oldest valid recognized snapshots beyond the limit are deleted, ordered by (`created_at`, `backup_id`); the
new snapshot and the source snapshot of a running `wled_restore_preset` are never deleted. Invalid, temporary,
foreign-named, symlink and other devices' files are never deleted nor counted. Prune failure is a warning on the result,
never a failure of the operation. Listing/pruning examines at most 10,000 directory entries.

Errors (no new codes): `BACKUP_FAILED` for storage/durability/read failure, `VALIDATION_ERROR` for malformed or unsafe
IDs, corrupt, unknown-version or mismatched-device snapshots and unrepresentable preset objects, `PRESET_NOT_FOUND` for
a well-formed missing `backup_id`, `UNSUPPORTED_CAPABILITY` when the firmware version differs for restoration planning.
`UNKNOWN_DEVICE` is raised before any filesystem access.

Restoration planning (`SnapshotStore.plan_restore`, read-only, no device I/O): requires the exact `device_id` and
firmware `version`; a target preset ID differing from the snapshot's must be passed explicitly; an occupied destination
requires overwrite intent and a valid prior snapshot of that destination. A plan or export is not restore evidence.
`wled_restore_preset` (#18) uses the helper as its final check after taking the prior snapshot itself, and writes one
`state` or `playlist` entry through a verified single-entry write
([procedure](contract/presets.md#restore-wled_restore_preset)).

Manual procedure, only for what the tool refuses (an `api-command` or `unknown` snapshot, a firmware-version mismatch, a
playlist the firmware would not store reproducibly; untested on hardware): verify the snapshot's `device_id`, firmware
`version` and `preset_id` against the target; copy the destination's current entry from `/presets.json` verbatim into a
file outside Git first (`wled_get_preset` returns the exact object); enter exactly the one `preset` object for the target
ID through the WLED UI or API (never upload or bulk-restore a presets file, never execute stored commands); read
`/presets.json` back and compare with the snapshot, unknown fields included. A difference is a failed or partial
restoration: do not retry blindly, keep the snapshot and the copy, re-read the destination and decide explicitly. After
a timeout, read first.

## Results and errors

Domain envelopes always contain `schema_version=1`, boolean `ok`, stable `operation`, `device_id` (null for inventory),
boolean `dry_run`, `application`, `verification`, object `data`, array `warnings`, and `error` (null on success). Every
served envelope also carries an optional `correlation_id` (16 hex characters, generated per call, the same value as in
the call's log line; [diagnostics](contract/diagnostics.md#correlation-id)); a document that was not served omits it.
Every tool serves the same output schema; it allows additional properties on the envelope and on the error object, so
clients must ignore unknown fields and a later additive field does not invalidate a cached schema
([versioning](contract/versioning.md#contract-evolution), #130). Errors contain `code`, safe `message`,
`read_retryable`, `write_retryable=false`, and `reconciliation`. [Examples](../examples/contracts/README.md) include
valid plans, conflicts and uncertain writes with observable postconditions.

| Observation | application | verification | ok |
| --- | --- | --- | --- |
| Successful read / valid dry-run | not_attempted | not_requested | true |
| Validation/capability/conflict/backup failure before dispatch | not_attempted | not_requested | false |
| Definitive refusal known to have no side effect | not_applied | not_requested | false |
| Required normalized postcondition observed | applied | verified | true |
| ACK only / possible dispatch, readback unavailable | unknown | unknown | false |
| Possible dispatch, differing readable state at deadline | unknown | mismatch | false |
| Proven partial steps, final postcondition not reached | applied | mismatch | false |

A timeout/reset after possible dispatch remains possibly applied; mismatch never proves it was never applied. Readback
proves only the observed postcondition, not causal attribution or immunity from later external change. No automatic
mutation retry (including setters, allocation, activation, delete/restore) or blind replay suggestion. Safe
reconciliation means read/inspect and decide explicitly.

Stable codes: `CONFIG_ERROR`, `UNKNOWN_DEVICE`, `UNREACHABLE`, `TIMEOUT`, `INVALID_RESPONSE`, `VALIDATION_ERROR`,
`UNSUPPORTED_CAPABILITY`, `AMBIGUOUS_NAME`, `PRESET_NOT_FOUND`, `PRESET_CONFLICT`, `BACKUP_FAILED`, `STORAGE_FAILED`,
`WRITE_OUTCOME_UNKNOWN`, `VERIFICATION_MISMATCH`, `INVENTORY_CONFLICT` and `INVENTORY_RELOAD_FAILED` (inventory writes,
[discovery](contract/discovery.md#reload-semantics)), `DISCOVERY_BUSY` (a discovery run is active or the probe gap has
not passed; `not_attempted`, `retry_after_seconds`), `NOT_WLED` (`wled_add_device`: the address answered but not as a
WLED `/json/info`; nothing written), `ACCESS_DENIED` (a tool profile or a device's maximum class does not allow the
call; `not_attempted`, nothing was sent; [profiles](contract/profiles.md#enforcement)). A pre-dispatch timeout is
distinct from possible write application. Offline entries in successful inventory probes are per-device data. For a
device call, `CONFIG_ERROR` means the configured device address cannot be used; no request was sent, it is not retried
and the address is not echoed.

The envelope is returned through MCP `structuredContent` with an output schema and one text content block containing the
same JSON for older clients. `isError = !ok` for tool execution, including uncertain writes. Malformed JSON-RPC, unknown
methods/tools and negotiation errors use SDK protocol errors. Once a known tool's domain validation runs, its errors use
the envelope; SDK argument-shape rejection may precede execution and is tested separately for parity. Device failures
never become HTTP errors or apparently successful prose. Annotations describe read-only/destructive/idempotent behavior
but are not barriers; allocation is not idempotent, and animations/external clients limit setter claims.

## Transport access and lifecycle

Startup selects `--transport stdio|streamable-http`, default stdio, same domain graph. Configuration is validated before
serving without probing/writing controllers. stdio opens no listener, reserves stdout for MCP and uses sanitized stderr
logs; HTTP-only credentials are not required for stdio, and HTTP-only options together with stdio are rejected at
startup (exit 2).

HTTP uses the fixed path `/mcp`, default `--host 127.0.0.1 --port 8000`, one worker and no `--workers` option. A changed
host or port (also a wildcard bind) needs at least one `--allowed-host`, which replaces the defaults. `--allowed-host`
values are exact authorities (host and optional port; defaults `127.0.0.1:8000` and `localhost:8000`);
`--allowed-origin` values are exact absolute origins (scheme/host/port, no path), default empty rejects supplied browser
Origins; authenticated requests without Origin are allowed. Entries accept no wildcard, path or userinfo; at most 16
entries of 255 characters. A malformed/disallowed Host/Origin (including a supplied invalid Origin when credentials are
absent) is rejected as 403 before device actions: the guard answers 403 itself (the SDK's own Host check would answer
421 and runs only after authentication), compares exactly and case-insensitively without implied default-port
equivalence, and never consults `X-Forwarded-*`/`Forwarded`.

Direct auth is mandatory even on loopback and every method. Exactly one nonempty bearer source is configured: runtime
`WLED_MCP_HTTP_TOKEN` or protected file path `--http-token-file`; missing, conflicting or invalid configuration is
rejected before listening. No token CLI value, committed secret or credential logging; secrets are compared in constant
time over digests. After Host/Origin checks, a missing/invalid bearer gives 401 with `WWW-Authenticate: Bearer` and a
fixed body before tool/device execution, then an unknown path gives 404. The credential is 32 to 512 printable ASCII
characters without whitespace; a file is absolute, at most 1 KiB, read once at startup (rotation is a restart). Exactly
one `Authorization` header with the `Bearer` scheme is accepted; there is no attempt rate limiting. An authenticated
proxy requires explicit trust, protected upstream reachability and no unauthenticated bypass. Plain HTTP is for trusted
private networks; HTTPS for untrusted links. Hub auth does not protect direct service access; a shared credential is not
per-user permission. No OAuth server is introduced.

The SDK's stateless Streamable HTTP with JSON responses is used: no session-ID allocation, event replay store,
background jobs or server-initiated streams. Accepted notifications get 202; requests get JSON responses; every non-POST
method (GET, DELETE, PUT, PATCH, OPTIONS, HEAD) returns 405 with `Allow: POST` after the access checks. A stale
`Mcp-Session-Id` is ignored and none is issued. Request bodies are limited to 256 KiB (413, SDK); the unauthenticated
peer's body is never read. Invalid protocol versions, media types/methods use SDK transport/protocol errors rather than
tool envelopes. #3 locks a compatible SDK; #14 proves actual SDK client behavior ([decisions](decisions/stage-1.md)).

All clients share inventory, one async WLED client, caches, snapshot store and per-device locks for process lifetime.
Disconnect is not cancellation: bounded verification continues after dispatch where possible, locks are released
safely, nothing is requeued, and reconnect does not replay mutations. A resubmission is a new invocation; JSON-RPC IDs
are not deduplication tokens and exactly-once execution is not promised. Shutdown (SIGINT/SIGTERM, SIGBREAK on Windows)
stops admission, drains in-flight work within existing operation deadlines (graceful timeout is the configured operation
timeout rounded up plus 2 s), closes shared resources and exits 0; a second SIGINT forces exit. There is no
unauthenticated health route: liveness is a TCP connect or an authenticated `ping` or `tools/list` POST, neither of
which touches a device. Forced interruption leaves possibly applied writes uncertain, never resumed on restart. An
orderly shutdown also gives each active temporary signal one bounded conditional restore attempt
([signals](contract/signals.md#shutdown-and-restart)). Multiple workers require cross-process coordination and are
outside this baseline. Ownership: #14 implements HTTP/access/lifecycle; #10 verifies MCP-03/MCP-04/OPS-05 and T18–T21;
#11 records integration/deployment evidence. Both modes need automated parity coverage.

## Stage 2 and later files

- [agent-guidance](contract/agent-guidance.md): initialization instructions, workflow prompt, field descriptions (#147).
- [cli](contract/cli.md): `config` and `doctor` commands, exit codes, sanitized export (#16).
- [compatibility](contract/compatibility.md): support matrix, WLED firmware tiers (#21).
- [dependencies](contract/dependencies.md): runtime dependency ranges and installation (#22).
- [diagnostics](contract/diagnostics.md): correlation ID, call logs, `wled_get_service_status`, rotation/tenancy (#20).
- [discovery](contract/discovery.md): discovery, enrollment and range tools, hard caps, coverage report (DEC-035, #198-#203).
- [effect-metadata](contract/effect-metadata.md): fxdata parsing and effect catalog filters (#148).
- [effect-search](contract/effect-search.md): `wled_search_effects` and its property catalog (#31).
- [explain](contract/explain.md): `wled_explain_lighting`, evidence allowlist, cause codes (#30).
- [zones](contract/zones.md): named lighting zones and the existing-segments policy (#27).
- [groups-scenes](contract/groups-scenes.md): device groups, scenes, plan, apply and sharing (#17).
- [per-endpoint-tool-sets](contract/per-endpoint-tool-sets.md): proposed design, not implemented (#237).
- [layout-preview](contract/layout-preview.md): `wled_preview_layout`, the static SVG and its security rules (#29).
- [live-snapshot](contract/live-snapshot.md): bounded sampled LED observations (#150).
- [mcpb-bundle](contract/mcpb-bundle.md): the Claude Desktop MCPB bundle, manifest and release flow (DIST-04, #151).
- [presets](contract/presets.md): restore, supplied-state save, snapshot listing, playlists, bundles (#18).
- [profiles](contract/profiles.md): tool classes, access profiles, device ceilings, `ACCESS_DENIED` (#20).
- [resources](contract/resources.md): MCP resources for the device list and the effect and palette catalogs (#258).
- [rooms](contract/rooms.md): rooms (a group with `kind=room`), `wled_apply_room` (#183).
- [segment-names](contract/segment-names.md): catalog names in the segment tools (#149).
- [segments](contract/segments.md): capability model, WLED 16 segment fields, CCT and 2D layouts (#19).
- [signals](contract/signals.md): temporary signals, owned fields, conflict rule, shutdown behavior (#28).
- [versioning](contract/versioning.md): version source, build identity, contract and schema evolution, migration notes (#21, #70).
