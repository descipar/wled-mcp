# V1 MCP tool contract

Contract text added from stage 2 on lives in per-area files under
`docs/contract/`, linked from the
[list at the end](#stage-2-and-later-files) of this document; see
[where new documentation goes](AGENT-WORKFLOW.md#where-new-documentation-goes).

Implementation status: #4 exposes `wled_list_devices`; #5 adds the read-only
`wled_get_state`, `wled_get_effects` and `wled_get_palettes` (see
[Read tools](#read-tools-state-and-catalogs-implemented-in-5)). Inventory and client
foundations are in [INVENTORY-CLIENT.md](INVENTORY-CLIENT.md). #6 adds `wled_set_state`
and `wled_patch_segments`; #7 adds `wled_replace_layout` (see
[Layout replacement](#layout-replacement-implemented-in-7)); #14 adds the protected HTTP
service; #9 adds the five persistent-preset tools (see
[Persistent presets, implementation](#persistent-presets-implemented-in-9)).
#18 adds `wled_list_snapshots`, `wled_restore_preset`, `wled_store_preset`,
`wled_save_playlist`, `wled_export_presets` and `wled_import_presets` (see
[contract/presets.md](contract/presets.md)). `wled_patch_raw_state` remains a design
requirement, not executable behavior: the raw state patch is excluded from stage 1
(ISSUE-13-DEC-001). Hardware acceptance of the preset tools (H06) is recorded for one controller on WLED
16.0.1 in [VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06);
activating a preset saved by WLED 16 is refused there
([#66](https://github.com/descipar/wled-mcp/issues/66)). With the #66 fix, saving and
activating such a preset was verified on that controller in
[run 2](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06) (classification
`state`, readback matched).

Design baseline for [issue #2](https://github.com/descipar/wled-mcp/issues/2), not
an implemented API or hardware compatibility claim. Technical choices and their
authority are in [the issue decisions](decisions/issue-2.md). Requirement IDs refer
to [REQUIREMENTS.md](REQUIREMENTS.md); representative synthetic cases are in
[examples/contracts](../examples/contracts/README.md).

## Shared conventions

- stdio and Streamable HTTP expose identical tools, schemas and domain outcomes.
- Device tools require a configured `device_id`; no caller-supplied host/URL.
- Reject unknown fields, null nonnullable values, booleans as integers and values
  outside limits. Omitted fields mean unchanged, never zero/false/reset. Do not
  inject light-value defaults into patch schemas. Empty patch objects/lists fail.
- Ranges are zero-based with exclusive `stop`; explicit segment IDs are stable
  identifiers, not request-array positions.
- All mutations accept `dry_run=false`. True permits bounded reads only: no device
  POST, snapshot/temp-file/retention write or slot reservation. A valid plan is not
  a transaction or reservation; actual writes replan under the same device lock.
- One process-wide per-device lock covers fresh reads, complete validation,
  collision recheck, backup, all writes and verification. Different devices can
  progress concurrently. External clients/processes remain outside this lock.
- Validate the entire request and planned sequence before the first write. Report
  interference; never repeatedly overwrite to make verification pass.
- User authorization belongs to the MCP host; no interactive approval mechanism
  is added inside the server. Precise targets/overwrite flags express intent.

## V1 tools

| Tool | Essential inputs | Behavior | Priority |
| --- | --- | --- | --- |
| `wled_list_devices` | `probe=false` | Configured IDs/names; optional independent bounded reachability | Must |
| `wled_get_state` | `device_id` | Normalized current state, raw state, essential info/capabilities | Must |
| `wled_get_effects` | `device_id`, `refresh=false` | Original IDs/names, optional metadata, freshness | Must |
| `wled_get_palettes` | `device_id`, `refresh=false` | Original IDs/names, freshness | Must |
| `wled_set_state` | `device_id`, optional `on`, `brightness`, `transition_ms`, `dry_run` | Master patch, at least on or brightness | Must |
| `wled_patch_segments` | `device_id`, nonempty `segments`, `dry_run` | Patch explicit existing active IDs, no removal | Must |
| `wled_replace_layout` | `device_id`, nonempty complete `segments`, `dry_run` | Exactly desired active IDs/ranges; remove stale IDs | Must |
| `wled_list_presets` | `device_id` | Persistent IDs/names/types, excluding reserved/empty entries | Must |
| `wled_get_preset` | `device_id`, `preset_id` | Exact persistent object, unknown fields preserved | Must |
| `wled_activate_preset` | `device_id`, `preset_id`, `dry_run` | Activate supported existing state/playlist entry, no storage edit | Must |
| `wled_save_preset` | `device_id`, `name`, optional `preset_id`, `overwrite=false`, `dry_run` | Save current state; lowest free ID if omitted; persistent verification | Must |
| `wled_delete_preset` | `device_id`, `preset_id`, `dry_run` | Snapshot first; delete exactly that ID; verify absence | Must |
| `wled_list_snapshots` | `device_id`, optional `preset_id` | Server snapshot metadata, newest first; no device I/O | Should; implemented in #18 ([contract/presets.md](contract/presets.md)) |
| `wled_restore_preset` | `device_id`, `backup_id`, optional `preset_id`, `overwrite=false`, `dry_run` | Explicit single-entry storage restoration; applies the entry live (or starts the playlist), then stores it | Should; implemented in #18 ([contract/presets.md](contract/presets.md)) |
| `wled_store_preset` | `device_id`, `name`, `state`, optional `preset_id`, `overwrite=false`, `dry_run` | Supplied, validated light state; applied live, then stored | Should; implemented in #18 ([contract/presets.md](contract/presets.md)) |
| `wled_save_playlist` | `device_id`, `name`, `entries`, `repeat`, `shuffle`, optional `end_preset_id`, `preset_id`, `overwrite=false`, `dry_run` | Native playlist of existing state presets; saving starts it, then it is stored | Should; implemented in #18 ([contract/presets.md](contract/presets.md)) |
| `wled_export_presets` | `device_id`, optional `preset_ids`, `include_unwritable=false` | Versioned preset bundle without device data, returned inline | Should; implemented in #18 ([contract/presets.md](contract/presets.md)) |
| `wled_import_presets` | `device_id`, `bundle`, optional `id_map`, `effect_map`, `palette_map`, `overwrite_ids`, `dry_run` | Dry-run preview, explicit mappings, snapshots first, per-entry single writes, stop at the first unverified entry | Should; implemented in #18 ([contract/presets.md](contract/presets.md)) |
| `wled_patch_raw_state` | `device_id`, JSON object `patch`, `dry_run` | Restricted advanced state patch | Should; excluded from stage 1, `raw_state_patch = true` rejected at startup, no owning issue (ISSUE-13-DEC-001) |

Tool descriptions state physical output, playback and storage effects. State/layout
changes may clear the active-preset marker or interrupt playback without editing
saved objects. Never silently disable timers, realtime inputs or another client.
Activation is restricted to verified state/playlist shapes and safe referenced
entries. API-command/unknown presets remain readable and backupable, but activation
returns `UNSUPPORTED_CAPABILITY` until their effects are validated. No arbitrary
command forwarding or implicit playlist editing.

## Read tools: state and catalogs (implemented in #5)

Requirements READ-01/02/03, DEV-02, MCP-02 and partial OPS-04; decisions
[ISSUE-5-DEC-001–008](decisions/issue-5.md). Inputs are strict (unknown fields and
non-boolean `refresh` rejected). All three are read-only, idempotent, closed-world and
return `application=not_attempted`, `verification=not_requested`, `dry_run=false`.
Failures use existing error codes only, with `ok=false` and empty `data`; messages name
the fixed resource label and numeric HTTP status, never a body, URL or exception text.
An unknown `device_id` gives `UNKNOWN_DEVICE` (envelope `device_id` null) and no HTTP.

**`wled_get_state(device_id)`** reads `/json/state` then `/json/info` sequentially under
one deadline and the per-device lock. It is never cached and not an atomic snapshot.
`data`: `device{id,name}`, `freshness{source="device",read_at}`, `firmware{version,
build_id,product,brand,arch}` (null if absent; only `ver` is required), `capabilities`
(`led_count`, `max_segments`, `effect_count`, `palette_count`, `device_wide_color`,
`segment_color_capability_reported`, `matrix`), `state`, `raw{state,info,redacted_info_keys}` and
`diagnostics{server_version,unknown_capabilities,firmware_support{tier,minimum_supported}}`;
`warnings` lists tolerated anomalies. `firmware_support` is the informational DEC-020
firmware tier with one warning below 16.0.0 or for an unrecognizable version, never a
refusal ([compatibility](contract/compatibility.md#wled-firmware-tiers), #21).

- Required: info object with string `ver`; state boolean `on`, integer `bri` 0–255
  (booleans rejected), `seg` list of objects with unique non-negative integer `id` and
  integer `start`/`stop`. Violations give `INVALID_RESPONSE`. Optional fields of the
  wrong type become `null` plus a warning; unreported capabilities are `null`, never
  `false`, and the unknown names are listed in `diagnostics.unknown_capabilities`.
- `state`: `on`, `brightness` (remembered), `effective_brightness` (`on ? bri : 0`),
  `default_transition_ms` (`transition * 100`), `active_preset_id` and
  `active_playlist_id` (`-1` becomes `null`), `main_segment` and `segments`. Segments are
  identified by their explicit `id`, never by array position, and carry `start`, `stop`,
  `on`, `brightness`, `effective_brightness` (`brightness` if the segment is on, else 0;
  master power is separate; the pinned firmware reports segment `bri` as 255 when its
  opacity is 0, so such a segment shows 255 even while on), `colors`, `color_channels`, `reported_color_capability`,
  `effect_id`, `palette_id`, `speed`, `intensity` and, when present, `grouping`,
  `spacing`, `offset`, `reverse`, `mirror`, `selected`, `name`; missing values are null.
  Issue #19 adds the capability source, CCT, effect options, 2D and further segment
  fields after `name` ([contract/segments.md](contract/segments.md)).
- `device_wide_color{scope,rgb,white,cct}` is the firmware aggregate (`info.leds.lc`),
  reported only when that value is an integer, and is not proof for any range.
  `reported_color_capability` comes from `state.seg[].lc` or else from `info.leds.seglc`
  (issue #19, [contract/segments.md](contract/segments.md)); `info.leds.seglc`, which the
  pinned firmware emits per active segment in order, is used only when its length equals
  the segment list. A fourth color channel is trimmed only when `info.leds.seglc` proves the segment
  RGB-only (RGB bit without white/CCT), every slot's fourth channel is 0 and thus
  nothing is lost; `raw.state` always keeps the original arrays.
- Redaction (runtime privacy default, DEC-006): `mac`, `ip` and `wifi.bssid` are removed
  from `raw.info` and listed in `raw.redacted_info_keys`. Raw state is unchanged.

**`wled_get_effects` / `wled_get_palettes(device_id, refresh=false)`** return `effects` or
`palettes` as `[{id,name,[placeholder:true],[metadata:{fxdata}]}]` ordered by ID, `count`,
(effects only) `metadata{status: available|unavailable, reason}` and `freshness{source:
device|cache, fetched_at, age_seconds, cache_ttl_seconds, firmware{version,build_id},
refreshed}`. `refreshed` echoes that the call bypassed the cache by request.

- ID is the array index of the device list; lists are never compacted and no count is
  hardcoded. A difference from `fxcount`/`palcount` is a warning only. Effect slots the
  firmware serializes as `"RSVD"` are returned with `placeholder=true`; they and
  `RSVD` are never matched by the name resolver. `/json/pal` lists built-in/gradient
  names, not custom palettes, so `palcount` may legitimately exceed the list.
- Effect metadata is the raw `/json/fxdata` string per effect, attached by index only
  when the list length equals the effect list; it is never a name source and is not
  parsed. Any fxdata failure or length mismatch gives `ok=true`, intact names,
  `metadata.status=unavailable`, a reason (error code or `length_mismatch`) and one
  warning. The optional read gets at most half of the remaining deadline.
- Cache: key `(device_id, kind)`, effects plus fxdata one unit, TTL
  `http.catalog_cache_seconds` (0 disables storage). Every call performs one fresh
  `/json/info` read. A live entry with identical `(ver, vid)` is served as
  `source=cache` with its age and no catalog/fxdata request; a changed identity drops it
  and refetches. `refresh=true` always reads the device and replaces the entry only on
  success; a failed refresh or info failure returns that error (no stale fallback, an
  expired entry is never served) and leaves the previous entry in place. Cached warnings
  repeat for the entry's lifetime.
- Internal name resolution (for later setters; no public parameter in #5): a unique
  exact case-sensitive match, else a unique case-folded trimmed match; several matches
  give `AMBIGUOUS_NAME` with at most ten `{id,name}` candidates (a later setter envelope is
  intended to carry them in `data.candidates`); no match gives `VALIDATION_ERROR`; no fuzzy match.

## Power, brightness and transition

`brightness` accepts integers 0â€“255. Reads distinguish remembered brightness from
`effective_brightness` (zero while off). Positive brightness sets the remembered
level and preserves omitted `on`; the adapter compensates coupled firmware power
behavior. `on=false` alone preserves remembered brightness. A zero request targets
off/effective zero, not a claim that raw remembered brightness was stored as zero.
To preserve omitted power, accept zero only when resolved `on` is false; otherwise
reject before POST and suggest explicit `on=false`. Reject explicit
`on=true, brightness=0`. Turning on requires a known positive remembered value or
an explicit positive brightness. Thus ordinary off/zero works with explicit power
intent, while an omitted field never silently turns the light off/on.

The reviewed firmware handles master and segment state differently: master `bri`
readback is remembered brightness while `on` reflects actual power; segment zero
brightness switches its on flag off while retaining opacity. Verify normalized
power/effective zero and retained remembered level separately. Do not demand raw
`bri=0` or treat remembered nonzero readback as failed off. Effects and unrelated
transient frames are not equality targets.

### Master power rules (`wled_set_state`)

Issue #52, [ISSUE-52-DEC-001](decisions/issue-52.md) (delegated decision). The pinned
v0.15.1 firmware couples master power to brightness (`on = root["on"] | (bri > 0)`), so a
positive `bri` alone turns an off master on. The planner applies these rules before any
write and identically in a dry run (evidence: [SOURCES.md](SOURCES.md); hardware
confirmation stays with #12).

| Input | Rule | Outcome |
| --- | --- | --- |
| `on=true` with `brightness=0` | Rejected | `VALIDATION_ERROR`, zero POSTs |
| `brightness=0`, `on` omitted | Accepted only when the master is off; otherwise pass `on=false` explicitly | Off master: `{"bri": 0}`, verified off; on master: `VALIDATION_ERROR`, zero POSTs |
| `on=true` without `brightness` | Requires a positive remembered brightness | Remembered zero: `VALIDATION_ERROR`, zero POSTs |
| `brightness > 0`, `on` omitted, master off | Targeted compensation: the resolved `on=false` is sent with `bri` and listed in `plan.targeted_compensation` as `{"on": false}`; the master stays off and remembers the new brightness | Payload `{"on": false, "bri": X}`, `applied/verified` |
| `brightness > 0`, `on` omitted, master on | `bri` is sent alone (no `on` added); the master stays on | `applied/verified` |
| Explicit `on` with `brightness` | Sent as requested; not a compensation (`targeted_compensation` is `[]`) | `applied/verified` |
| Current master `on` not a boolean | Power is unknown; the state read already fails before planning | `INVALID_RESPONSE`, zero POSTs |

`plan.targeted_compensation` is always present for `wled_set_state` (`[]` or
`[{"on": false}]`; the master has no `id`). `plan.on` keeps the requested value (`null`
when omitted) and `plan.resolved` shows the resolved `on` and `brightness`; a
postcondition names the compensation. Every master write verifies the resolved `on` in
the readback, because it sends either `on` or a power-coupled `bri`; a power flip is a
`VERIFICATION_MISMATCH` (`application=unknown`), never a silent success, and is not
replayed. One-call `tt` is unchanged by compensation: it is still sent and reported;
whether the off master shows any visible transition effect is unverified on hardware
(#12). The plan is rebuilt from a fresh read under the per-device lock; an external power
change between that read and the POST can still be undone (compensation) or carried
forward (a bri-only write) and remains a residual risk; verification compares the
readback with the resolved target of that fresh read, so such a reversal is not
detected. `wled_set_state` has no segment fields, and the
master `on=false` does not change segment power.

Master `transition_ms` affects this change only via WLED `tt`, leaving persistent
`transition` untouched. Accept integer 0â€“65500 ms; compute wire units as
`floor((transition_ms + 50) / 100)` (nearest 100 ms, half upward). Zero is immediate;
reject 1â€“49 ms because they round to zero, plus overflow/negative/fractional values
and transition-only requests. Report requested/effective milliseconds and units:
149 -> 100 ms, 150 -> 200 ms. Readback verifies target state after the effective
transition. Reject before write when the overall deadline cannot accommodate the
transition and verification; an ACK that starts a long transition is not success.
No physical timing precision is promised.

## Segments: schema and omissions

Core fields: `id`, `start`, `stop`, `on`, `brightness`, `colors`, `effect_id` or
`effect_name`, `palette_id` or `palette_name`, `speed`, `intensity`. ID/name forms
are mutually exclusive; ambiguous names return candidates. Brightness/speed/
intensity are integers 0â€“255; effects/palettes must exist in target catalogs.
Should fields: `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected`,
`name`. If exposed, offset is 0 <= offset < resulting physical range length (no
implicit wrap); grouping, spacing and names follow the shared limits below.

### Shared segment limits (`wled_patch_segments` and `wled_replace_layout`)

Issue #48, [ISSUE-48-DEC-001](decisions/issue-48.md) (human decision; supersedes the
#7-only name, 255-bound and `bri` sending points of ISSUE-7-DEC-006). Both segment tools
apply one rule set, implemented once (`src/wled_mcp/segment_rules.py`), before any write
and identically in a dry run. Evidence is the pinned v0.15.1 source
([SOURCES.md](SOURCES.md#issue-7-layout-evidence)); hardware confirmation stays with #12.

| Input | Rule | Outcome |
| --- | --- | --- |
| `name` | At most 32 UTF-8 bytes on every device (the firmware truncates by bytes; 32 is the build-independent minimum, the chip type does not prove a larger buffer), no U+0000. The input schema keeps `maxLength: 32` (characters) as a coarse bound. | Otherwise `VALIDATION_ERROR` naming the segment and the byte limit, zero POSTs |
| `grouping` / `spacing` | 1-255 / 0-255 (firmware `uint8_t`); both input schemas advertise `maximum: 255` | 256 or more fails schema validation (`VALIDATION_ERROR`), zero HTTP |
| `on=true` with `brightness=0` | Rejected (the firmware would end on) | `VALIDATION_ERROR`, zero POSTs |
| `brightness=0`, `on` omitted | Accepted only when the segment is reported off (a new #7 ID counts as on; an unreported current power also counts as not off); otherwise pass `on=false` explicitly | `VALIDATION_ERROR`, zero POSTs |
| `brightness > 0`, `on` omitted, segment off | Targeted compensation: the resolved `on=false` is sent with `bri` and listed in `plan.targeted_compensation` as `{"id": N, "on": false}`; the segment stays off with the new remembered brightness | `applied/verified` |
| `brightness > 0`, `on` omitted, segment on | `bri` is sent alone (no `on` added); the firmware keeps the segment on | `applied/verified` |
| `brightness > 0`, `on` omitted, current power not reported | The power effect cannot be predicted; pass `on` explicitly (`brightness=0` in this case follows the row above: `VALIDATION_ERROR`) | `UNSUPPORTED_CAPABILITY`, zero POSTs (unrelated fields still work) |

Whenever a positive `bri` is sent, the readback also verifies the resolved `on`, so a
power flip is a `VERIFICATION_MISMATCH`, never a silent success. For
`wled_replace_layout` none of these causes can occur after earlier removals any more:
all are rejected or compensated before the first POST; partial application remains
possible only for other causes (for example external interference or an uncertain
step), as described below.
Unsupported fields/capabilities fail explicitly. CCT/2D/pixel streaming are separate
extensions; preservation of an existing unexposed field does not expose its setter.

`colors` is a nonempty list of 1â€“3 leading slots; channels are integers 0â€“255.
Require exactly three channels for a proven RGB-only range and four for RGBW.
Do not pad white or drop it silently. Existing IDs retain omitted trailing slots;
new IDs resolve missing slots to black. Read normalization can remove a proven
synthetic zero white channel from RGB-only data while retaining raw data. Array
width/device-wide aggregate is not proof of range capability. An existing segment's
reported capability supports its unchanged range; new/moved ranges require a
validated topology/range profile. Unknown/inconsistent evidence is
`UNSUPPORTED_CAPABILITY` before write; unrelated scalar changes can still proceed.

Patch requires an existing active `id` plus at least one mutable field. Preserve
all omitted fields and unrelated segments, including unexposed extension state.
Firmware side effects (such as omitted name clearing on geometry changes or effect
parameter resets) require proven targeted compensation shown in the plan; never
round-trip the whole configuration. `wled_patch_segments` lists it in
`plan.targeted_compensation` with the same entry shapes as `wled_replace_layout`
(`{"id": N, "name": ...}` for a name resent on a geometry change, `{"id": N, "on": false}`
for the shared power compensation). Reject an unrepresentable preservation plan.
Scalar patches may retain preexisting overlaps; a range-changing patch rejects
introduced overlaps against the complete resulting layout, including untouched IDs.

Replace requires every desired `id`, `start`, `stop`. Existing desired active IDs
preserve omitted colors and other state. New/reused inactive IDs require explicit
colors and resolve omitted public fields using server defaults:

| Field | New segment default |
| --- | --- |
| on / brightness | true / 255 |
| colors | supplied leading slots, remaining slots black with proven channel width |
| effect_id / palette_id | 0 (Solid) / 0, verified in target catalogs |
| speed / intensity | 128 / 128 |
| grouping / spacing / offset | 1 / 0 / 0 |
| reverse / mirror / selected | false / false / false |
| name | empty string |

Explicitly establish defaults even in reused slots; account for ancillary inherited
state affecting output (for example freeze), or reject under the selected profile.
These are server design choices, not firmware constructor defaults. Preserve master
state. Derived selection/main-segment bookkeeping effects of removal appear in the
plan; if necessary, a proven adapter selects the lowest desired main ID, otherwise
reject. Do not silently remap segment IDs.

Before any write validate unique nonnegative IDs, known ID/count limits,
`0 <= start < stop <= led_count`, all field/capability constraints and the whole
resulting layout. Empty replacement and replacement overlaps fail. Stale IDs are
fresh active old IDs minus desired IDs; deletion uses explicit ID and `stop=0`.
Never append a fixed dummy tail.

### Firmware representability and partial writes

The [pinned source](SOURCES.md#issue-2-contract-evidence) shows that raw pass-through
cannot guarantee this contract. A supported profile must know ID allocation.
Existing IDs can be reused; new IDs can be added ascending from the known next
allocatable slot. Reject sparse new IDs that would append elsewhere; never create
speculative gap fillers. Unknown next-slot information blocks creation, not valid
existing-ID operations.

For the reviewed profile, single-object `seg` deletion avoids the array bulk-purge
path. A bounded plan can use exact-ID updates/creates and separate single-ID
removals, with interim readback. Validate intermediate ranges/ordering too, verify
final exact active IDs/ranges and preserved fields, and stop on mismatch/uncertainty.
No replay, automatic rollback or further destructive steps after uncertain dispatch.
Report completed steps, remaining IDs and last observed state. Verified partial
application uses `application=applied`, `verification=mismatch`, `ok=false`; any
uncertain step makes application `unknown`. Intermediate light output is visible,
and external clients can race. The [replacement fixture](../examples/contracts/replace.json)
includes a representable noncontiguous layout and a rejected sparse-new-ID request;
these are acceptance targets, not firmware execution evidence.

## Layout replacement (implemented in #7)

Requirements SEG-02, SEG-03, SEG-04, SEG-05, MULTI-01 and REL-03 (plus the REL-01/02
uncertain-write rules and the MCP-02 envelope); decisions
[ISSUE-7-DEC-001–007](decisions/issue-7.md) and, for the shared segment limits,
[ISSUE-48-DEC-001](decisions/issue-48.md). Evidence is mock-only and source-derived
([SOURCES.md](SOURCES.md#issue-7-layout-evidence)); hardware check H05 is
recorded for one controller in
[VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06), without stale-ID
removal by this tool on hardware.

**`wled_replace_layout(device_id, segments, dry_run=false)`**. Strict input
(`segments`: 1-64 entries, unknown fields rejected). Each entry needs `id`, `start`,
`stop`; optional: `on`, `brightness`, `colors`, `effect_id`, `palette_id`, `speed`,
`intensity`, `grouping` (1-255), `spacing` (0-255), `offset`, `reverse`, `mirror`,
`selected`, `name` (at most 32 UTF-8 bytes, no U+0000). ISSUE-7-DEC-002 says #7 follows
#6 wherever #6 defines handling. Names, grouping/spacing bounds and the power/brightness
rules (including the `brightness=0` rejections of ISSUE-7-DEC-007 and the `on=false`
compensation for a positive `bri` on an off segment) are the
[shared segment limits](#shared-segment-limits-wled_patch_segments-and-wled_replace_layout)
of ISSUE-48-DEC-001, which supersedes the #7-only exceptions of ISSUE-7-DEC-006.
Annotations: `destructive_hint=true`, not read-only, not idempotent, closed-world (hints
only; authorization belongs to the host).

Deferred (not part of #7, no setter is exposed; existing values are preserved):
CCT (`cct`), 2D geometry and matrix fields, pixel streaming (`i`), `rpt`, freeze setter,
`c1`-`c3`, `o1`-`o3`, `si`, `set`, `m12`, effect/palette *name* forms and
`AMBIGUOUS_NAME` for segments (both #6 and #7 take IDs only; name resolution is not part
of either acceptance list), presets/snapshots and master `on`/`bri`/transition.

Planning (one fresh read of state and info under the per-device lock and one deadline;
identical for dry run and live call; an earlier dry run is never a reservation):

1. Classify: `existing` = desired and active, `new` = desired and not active (including
   reused inactive slots), `stale` = active and not desired (exact set difference, any
   size, any gaps; no constant cleanup count).
2. Validate the whole request before the first POST (unique IDs, `id < maxseg`,
   `0 <= start < stop <= led_count`, no overlap in the desired layout, effect/palette IDs
   inside the catalogs, offset `0 <= offset < length`, the shared segment limits for
   names, grouping/spacing and power/brightness, color widths). New IDs need explicit `colors`. Channel evidence for a new range is the
   profile-0 uniform RGB-only rule (`leds.lc` is RGB-only and `leds.seglc` is absent or
   aligned and RGB-only); otherwise `UNSUPPORTED_CAPABILITY`, and four channels for a new
   or moved range are refused the same way. Existing unchanged ranges follow
   ISSUE-6-DEC-003. A shrinking move whose preserved offset the firmware would clamp is
   rejected unless `offset` is supplied; an unrepresentable preserved `name`/`offset` is
   `UNSUPPORTED_CAPABILITY`.
3. Allocation: new ID `n` is accepted if `n <= B`, where `B` starts at
   `max(active IDs)+1` and becomes `max(B, n+1)` after each accepted new ID; IDs below the
   first bound are reused inactive slots. Otherwise `UNSUPPORTED_CAPABILITY` ("New ID 8
   cannot be allocated as requested; the known next slot is 6."). The bound is a lower
   bound of the slot count because the single-object path never purges slots.
4. Ordered single-object steps: optional main-ID redirect, exact removals ascending
   (`{"seg":{"id":X,"stop":0}}`), then updates and creates chosen so that no step overlaps
   a segment still at an old range (creates strictly ascending). A range cycle that would
   need a temporary segment is rejected, never solved with a filler. When the old main ID
   is stale the main segment moves to the lowest desired ID: before the removals if that
   ID is active, after its creation otherwise (with a plan warning, because the firmware
   resets main to 0 on that removal).
5. Update steps send only fields that differ from the fresh read, `start`/`stop` only
   for a geometry change, plus targeted compensation shown in the plan: the existing name
   is resent after a geometry change (`{"id": N, "name": ...}`), and a positive `bri` on an
   off segment with omitted `on` is sent with `on=false` (`{"id": N, "on": false}`, shared
   limits above); on a segment that is on, `bri` is sent alone. Existing IDs without any
   difference get no POST (`unchanged_segment_ids`); a request that changes nothing is
   a no-op: `ok=true`, `application=not_attempted`, `verification=not_requested`, one
   warning, zero POSTs. Create steps send every public field explicitly (defaults table
   above) and `frz=false`; other unexposed inherited state of reused slots cannot be
   observed or reset and is reported as warning `inherited_unexposed_state`.

`data.plan` (dry run and live): `update_segment_ids`, `create_segment_ids`,
`remove_segment_ids`, `unchanged_segment_ids`, `main_segment_id`, `main_segment{current,
target,changed,step}`, `resolved_segments` (every public field plus `color_channels`),
`targeted_compensation`, `steps` (text), `step_actions` and `step_payloads` (the exact
bodies), `warnings`, `noop`; plus `data.postconditions`. A dry run performs bounded
reads only and returns `ok=true`, `application=not_attempted`, no POST, no file write.

Execution: per step exactly one POST attempt and one bounded readback (ACK content is
never proof). A step is verified when the active ID/range set equals the expected
intermediate layout and the sent fields match (leading color slots, missing name equals
empty, `bri=0` means segment off). After the last step the final check requires exactly
the desired IDs and ranges, all requested and resolved-default fields, preserved fields of
existing IDs and the planned main ID. `data.steps_report` lists `{index, action, id,
status}` (`verified|failed|uncertain|not_dispatched`). Success is `applied/verified`.
Stop rules: a possibly dispatched POST that raised stops the sequence (it is accepted as
success only for the last step with a matching final state); a POST followed by a
differing readback is `failed`; unreadable state is `uncertain`; no replay, rollback,
corrective write or further (especially removal) step follows. Mapping: unreadable ->
`unknown/unknown` + `WRITE_OUTCOME_UNKNOWN` (also when the POST raised and the readback is
readable but matches the pre-write state, because the outcome cannot be told apart from an
unapplied write); readable but differing after an uncertain or
first step -> `unknown/mismatch` + `VERIFICATION_MISMATCH`; later verified steps then a
failed step or a failed final check -> `applied/mismatch` + `VERIFICATION_MISMATCH`; budget
exhausted before a step -> `TIMEOUT` (`applied/mismatch` if earlier steps were proven,
else `not_attempted`). These failures carry `completed_steps`, `remaining_steps`,
`observed` (active `{id,start,stop}` and `mainseg` of the last read) and `no_replay`.
A `failed` step listed in `remaining_steps` may nevertheless have its own effect (fully
or partly) applied; only `observed` reflects the device, so inspect it before any new call.
Failures before the first POST have empty `data`. The per-device lock is held for the
whole sequence. See [errors.json](../examples/contracts/errors.json) for a partial
application and [replace.json](../examples/contracts/replace.json).

## Persistent presets

The reviewed profile supports integer IDs 1â€“250. Reserved key 0, temporary 255 and
251â€“254 are excluded. Missing/null/empty-object entries count as absent only when
recognized by the profile; nonempty malformed/unknown entries remain occupied.
Malformed stores must not be treated as all slots free. Preserve unknown fields,
classify state/playlist/API-command/unknown objects conservatively. Duplicate
names are labels, not allocation keys. Reject blank names, NUL/control characters
and names over 32 UTF-8 bytes in this profile; never truncate.

Save-current has no `state` input. Send storage controls only: `psave`, `n`,
`ib=true` (master power/brightness/default transition), `sb=true` (bounds),
`sc=false` (all segments). It does not activate the entry or deliberately change
output. Capture is asynchronous: report the pre-dispatch state reference and
coexistence limits, not an atomic photograph of a changing controller. Allocate
the lowest free supported ID, then recheck that exact destination immediately
before dispatch. An observed new collision is `PRESET_CONFLICT`; do not silently
choose another ID. Occupied explicit IDs require `overwrite=true` and a durable
snapshot. Free explicit IDs do not. `overwrite=true` without explicit ID is invalid.
Exhaustion fails without writing; external allocation cannot be truly atomic.

Before overwrite/delete, persist a validated exact prior object. Recheck that the
prior object still matches before dispatch; abort observed change as conflict
rather than overwrite an unbacked version. A remaining external race is explicit.
Delete requires an existing entry and targets exactly that ID. Replacement saves
may replace its unknown fields, which remain preserved in the prior backup.

Poll persistent `/presets.json` with cache bypass under one overall deadline:
initial baseline 10 seconds including reads, backup, dispatch and verification;
3-second connection bound; at most one retry per safe read and initial 100 ms poll
interval, all inside that deadline. Save verification compares name and normalized
saved fields against the pre-dispatch capture reference: master state/default
transition and all included segment states/IDs/ranges. Compare inactive/removal
markers semantically; seeing an ID/name or live state alone is insufficient.
Return observed persistent data, preserving unknown fields. Delete verifies target
absence/recognized empty entry and reports any unrelated entry changes as
interference. No repeated write or automatic reversal follows mismatch.

A timed-out write can reconcile to a verified persistent postcondition, with a
transport warning; unavailable readback is `WRITE_OUTCOME_UNKNOWN`. A readable
differing object at deadline is `VERIFICATION_MISMATCH`, not proof the command
never applied. Delayed capture/interference must not be mislabeled atomic success.
Activation verifies supported state/playlist acceptance through bounded readback;
playlist identity/status replaces invariant frame equality. Missing acceptance
observability gives uncertainty, and saved contents stay unchanged.

PRE-03 supplied-state save is not part of #9 (ISSUE-9-DEC-001). #18 implements it as
`wled_store_preset` and restore execution as `wled_restore_preset`, both through one
single-entry JSON API write with a documented live effect (ISSUE-18-DEC-001; see
[contract/presets.md](contract/presets.md)). The storage-only variant ("without
changing live output") is unsupported on WLED 16; there is no implicit apply/save/
restore workaround, no whole-file upload and no execution of stored commands.

### Persistent presets, implemented in #9

Decisions: [ISSUE-9-DEC-001](decisions/issue-9.md), ISSUE-8-DEC-001 to -003. Evidence:
mock-only (T11-T13); the firmware facts are pinned in
[SOURCES.md](SOURCES.md#issue-9-preset-evidence) and are not hardware evidence.

Inputs are strict (`extra=forbid`, booleans are not integers). `preset_id` is an
integer 1-250. `wled_save_preset(name, preset_id=None, overwrite=false)`: `overwrite=true`
without `preset_id` is rejected before any device access; there is no `state` input.
Names follow the rules above and are never trimmed or truncated.

Entry types (positive evidence only, `type` in list/get):

| Type | Recognized as | Activation |
| --- | --- | --- |
| `state` | object whose top-level keys are all within the allowlist `on`, `bri`, `transition`, `bs`, `mainseg`, `seg`, `n`, `ql`, `ledmap` (what a firmware save emits; `bs` is the WLED 16 blending style, ISSUE-66-DEC-001) and that has at least one of `on`, `bri`, `seg` (so activation is observable) | yes |
| `playlist` | object whose `playlist.ps` is a nonempty list of integers 1-250, no other stored control key (`psave`, `pdel`, `ps`, `pd`, `rb`, `win`, `live`, `time`, `bootps`) | yes, if every member (`playlist.ps` and a persistent `playlist.end` of 1-250) exists and is a `state` entry; `end=255` (restore previous preset) and any integer `end` outside 0-255 (the firmware keeps `end` in a byte, so it wraps onto another preset) are refused |
| `api-command` | object with a string-valued `win` key | `UNSUPPORTED_CAPABILITY` |
| `unknown` | any other object, including state-shaped objects with extra keys (`rmcpal`, `wifi`, `np`, `nl`, `lor`, `udpn`, vendor keys, control keys) | `UNSUPPORTED_CAPABILITY` |

A nonempty non-object entry is `unknown` with `malformed=true`: listed and readable,
but neither overwritten nor deleted (it cannot be snapshotted; `VALIDATION_ERROR`).
Store keys that are not canonical decimal IDs 0-255 are skipped by list/get with a
count warning; save and delete then fail closed with `INVALID_RESPONSE` and zero
POSTs.

- `wled_list_presets`/`wled_get_preset` (read-only): fresh GET of `/presets.json` per
  call (`Cache-Control: no-cache`), under the device lock and one deadline.
  List data: `device`, `freshness`, `presets` (`id`, `name|null`, `type`, optional
  `malformed`) ascending by ID, `count`. Get data adds the exact `preset` object.
  An empty slot is `PRESET_NOT_FOUND`.
- `wled_activate_preset`: one POST `{"ps": id}`, never any storage control; verified
  by bounded `/json/state` polling (`ps == id`, for a playlist `pl == id`). The
  firmware applies the preset in its main loop and ignores re-selecting the preset
  that is already active, so an already-active state preset adds a warning (a verified
  result then cannot prove re-application). A playlist that is already running is
  restarted by the firmware but `pl == id` is already true, so only a weaker warning
  is given. Activation changes live output, may
  interrupt current playback and clears/moves the active markers.
- `wled_save_preset`: inside the device lock: read store, choose the lowest free ID
  (or validate the explicit one), read state and info for the capture reference, take
  the snapshot if an occupied ID is replaced, recheck the destination, then exactly
  one POST `{"psave": id, "n": name, "ib": true, "sb": true, "sc": false}`. A
  destination that was free but is occupied at the recheck is `PRESET_CONFLICT`
  (no second allocation); an occupied one that no longer equals the snapshotted
  object is `PRESET_CONFLICT` (the snapshot is kept). Overwrite of an occupied `state`,
  `api-command` or `unknown` object needs `overwrite=true` and warns when the entry
  type changes; a `playlist` is never replaced (`UNSUPPORTED_CAPABILITY`, no
  snapshot, no POST). A free explicit ID with `overwrite=true` is accepted and
  takes no snapshot (`data.overwrote=false`).
- `wled_delete_preset`: snapshot of any occupied object entry (state, playlist,
  api-command, unknown), recheck equality, one POST `{"pdel": id}`, verified by
  absence (key removed, `null` or `{}`). Referencing playlists and the active-preset
  marker are named in warnings and not edited.

Verification polls the persistent file every 100 ms (default) under the one 10 second
deadline, reserving at most one second for readback. The save compares name `n`,
master `on`, `bri`, `transition`, `bs`, `mainseg` (each only when present in the
live state, so `bs` is compared on WLED 16 and not on 0.15.x) and, per active live
segment, `id`, `start`, `stop`, `on`, `bri`, `col`, `fx`, `sx`, `ix`, `pal`, `n`,
`grp`, `spc`, `of`, `rev`, `mi`, `sel` against the pre-dispatch state; inactive-slot markers
(`{"stop": 0}`) are ignored and the set of stored segment IDs must equal the live
set. Any difference at the deadline is `VERIFICATION_MISMATCH` (`unknown/mismatch`)
with `data.observed` (observed entry) and `data.differences` (field names, bounded).
A match is success with the standing warning that capture is asynchronous and not an
atomic photograph. A verified save whose stored entry does not classify as `state`
(for example because of a future firmware key) adds a warning that it will not be
activated by this server, naming only the unexpected top-level keys (no values or
preset name); the outcome is unchanged and nothing is rewritten. Unrelated entries
that differ from the pre-dispatch reading are `data.interference` plus a warning
(outcome stays verified, no corrective write).
A failed POST whose target stays unchanged is `WRITE_OUTCOME_UNKNOWN` (cannot be told
from an unapplied write); unreadable readback at the deadline is
`WRITE_OUTCOME_UNKNOWN`; a verified postcondition after a failed POST succeeds with a
transport warning. The POST is never repeated. Every post-dispatch result carries
`data.preset_id`, `name`/`deleted_type` and, when a snapshot was taken,
`data.backup_id` plus prune warnings, so a caller reconciles by reading before any
new attempt; a new call is a new invocation and may allocate the same still-unpersisted
ID. Pre-dispatch failures (conflict, unsupported, not found, validation, exhausted ID
space `PRESET_CONFLICT`, `BACKUP_FAILED`, read failures) are `not_attempted` with
zero POSTs.

Dry runs (`dry_run=true`) perform bounded reads only: zero POSTs, no snapshot, no
directory, no prune. Data: `plan`, `payload`, `postconditions`; a plan is not a
reservation.

Annotations (hints only): list/get read-only; activate non-destructive mutation;
save and delete `destructive_hint=true`, not idempotent, closed world.

Documented residual limits: other clients can change the preset file between the
final recheck and the firmware's asynchronous write, and `/presets.json` has no
transaction or compare-and-set, so a replaced entry may differ from the snapshotted
one in that window (the snapshot still holds the object that was read last); whether
saving moves the active-preset marker or briefly suspends the strip is not verified;
duplicate JSON keys in the store collapse to the last value; a store beyond the 2 MiB
response bound fails closed. `wled_get_preset` returns stored commands to the
authorized caller verbatim.

## Snapshot and explicit restoration

Implemented in #8 as a store plus a `Resources` seam. `wled_save_preset`
(overwrite), `wled_delete_preset`, `wled_store_preset` and `wled_restore_preset`
(overwrite) call the store through `OperationContext.backup_preset` (#9, #18).
Restoration execution is `wled_restore_preset` and the listing is
`wled_list_snapshots`, both in [contract/presets.md](contract/presets.md) (#18).

Format 1 contains exactly `format_version`, opaque server-generated `backup_id`,
configured `device_id`, `preset_id` (1-250), `firmware` identity (`version`, optional
`build_id`), UTC `created_at` (`YYYY-MM-DDTHH:MM:SSZ`) and exact `preset` object.
See [snapshot.json](../examples/contracts/snapshot.json). No integrity hash is
defined: validation does not authenticate tampered local storage. No MAC, URL or
credential is stored. Unknown top-level envelope keys are rejected (additions need a
new format version); unknown fields inside `preset` are preserved verbatim and never
executed. Rejected on read: unknown/boolean/string versions, malformed metadata,
unsafe IDs, files over 1 MiB, non-UTF-8, duplicate JSON keys, NaN/Infinity, and
empty or non-object `preset`. A snapshot whose envelope device, ID or timestamp
disagrees with its path is invalid.

Layout: `<data_dir>/backups/<device_id>/<backup_id>.json` (directories 0700, files
0600). `backup_id` matches `b-<YYYYMMDD>T<HHMMSS>Z-<12 hex>`, generated from the UTC
clock plus 48 random bits, never from preset names or caller text. The file is created
exclusively and never overwrites; a collision regenerates the ID. IDs resolve only
inside the data directory: no caller path, name or glob. Symlinked snapshot files and
device directories are never followed; a symlinked `backups/` root itself is an
operator choice and is followed. Non-regular files (FIFOs, devices) are rejected
without being opened.

Write sequence (`backup_preset`, blocking I/O run shielded from cancellation): same-
directory temporary file created exclusively, write, flush, `fsync`, read back and
validate, publish by hard link (never overwrite), directory `fsync`, re-read and
validate the final file. The directory `fsync` is best effort: skipped on Windows and
tolerated where unsupported, so durability there is weaker. Any failure removes the
temp/final file this call created and raises `BACKUP_FAILED` with a message free of
paths and payloads; earlier snapshots stay intact. Leftover `.tmp` files are ignored.

Ordering for destructive preset operations (the `OperationContext.backup_preset`
seam, used by `wled_save_preset` overwrite and `wled_delete_preset`): inside the device lock, read the preset fresh, validate the whole request,
snapshot the exact object, recheck the prior object (changed => `PRESET_CONFLICT`),
then POST. A raised `BACKUP_FAILED` happens in the prepare step, so `application=
not_attempted` and nothing is sent. The store does no device I/O; the caller supplies
the object. The result `data.backup_id` names the newest snapshot of the operation
and is kept even when the write later fails or is uncertain (`write_verified` and the
preset routine `write_polled` carry `backup_id` and prune warnings;
`write_sequence_verified` does not and is not used for snapshots); there is no automatic
rollback, restoration or resend (REL-02). Dry-run reports `backup_required` and an
advisory writability flag without creating directories, temp files or pruning.

Retention: default 20 valid snapshots per device (`backups.retain_per_device`,
1-1000). Only after the new snapshot is durable, the oldest valid recognized
snapshots beyond the limit are deleted, ordered by (`created_at`, `backup_id`); the
new snapshot and the source snapshot of a running `wled_restore_preset` are never
deleted. Invalid, temporary, foreign-named, symlink and other
devices' files are never deleted nor counted. Prune failure is a warning on the
result, never a failure of the operation. Listing/pruning examines at most 10,000
directory entries.

Errors (no new codes): `BACKUP_FAILED` for storage/durability/read failure,
`VALIDATION_ERROR` for malformed or unsafe IDs, corrupt, unknown-version or
mismatched-device snapshots and unrepresentable preset objects, `PRESET_NOT_FOUND`
for a well-formed missing `backup_id`, `UNSUPPORTED_CAPABILITY` when the firmware
version differs for restoration planning. `UNKNOWN_DEVICE` is raised before any
filesystem access.

Restoration planning (`SnapshotStore.plan_restore`, read-only, no device I/O, no
writes): requires the exact `device_id` and the exact firmware `version`; a target
preset ID differing from the snapshot's must be passed explicitly. An occupied
destination requires overwrite intent and a valid prior snapshot of that destination.
The helper's `as_data` describes the manual steps below with `execution: deferred`. A
plan or export is not restore evidence. `wled_restore_preset` (#18) uses the helper as
its final check after it has taken the prior snapshot itself.

Restoration execution (#18): `wled_restore_preset` writes one `state` or `playlist`
snapshot entry through a verified single-entry write; the procedure, refusals and
live effect are in [contract/presets.md](contract/presets.md#restore-wled_restore_preset).
The manual procedure below remains only for what the tool refuses (for example an
`api-command` or `unknown` snapshot, a firmware-version mismatch, or a playlist the
firmware would not store reproducibly); it is untested on hardware.
1. Read the snapshot file in the backups directory and verify `device_id`, firmware
   `version` and `preset_id` against the target controller.
2. Before changing anything, copy the destination's current entry from the
   controller's `/presets.json` verbatim into a file outside Git (`wled_get_preset`
   returns the exact object; the destructive preset tools snapshot automatically). If
   the destination is empty, note that instead.
3. Enter exactly the one `preset` object for the target ID through the WLED UI or
   API. Never upload or bulk-restore a whole presets file; activating a preset does
   not restore its storage; do not execute stored commands.
4. Read `/presets.json` back and compare the stored entry with the snapshot,
   unknown fields included. If anything differs, treat the restoration as failed or
   partial: do not retry blindly or re-enter repeatedly; keep the snapshot and the
   step 2 copy, re-read the destination, and decide a correction explicitly. After a
   timeout, read first.

## Results and errors

Domain envelopes always contain `schema_version=1`, boolean `ok`, stable
`operation`, `device_id` (null for inventory), boolean `dry_run`, `application`,
`verification`, object `data`, array `warnings`, and `error` (null on success).
Errors contain `code`, safe `message`, `read_retryable`, `write_retryable=false`,
and `reconciliation`. [Examples](../examples/contracts/README.md) include valid
plans, conflicts and uncertain writes with observable postconditions.

| Observation | application | verification | ok |
| --- | --- | --- | --- |
| Successful read / valid dry-run | not_attempted | not_requested | true |
| Validation/capability/conflict/backup failure before dispatch | not_attempted | not_requested | false |
| Definitive refusal known to have no side effect | not_applied | not_requested | false |
| Required normalized postcondition observed | applied | verified | true |
| ACK only / possible dispatch, readback unavailable | unknown | unknown | false |
| Possible dispatch, differing readable state at deadline | unknown | mismatch | false |
| Proven partial steps, final postcondition not reached | applied | mismatch | false |

A timeout/reset after possible dispatch remains possibly applied; mismatch never
proves it was never applied. Readback proves only the observed postcondition, not
causal attribution or immunity from later external change. No automatic mutation
retry (including setters, allocation, activation, delete/restore) or blind replay
suggestion. Safe reconciliation means read/inspect and decide explicitly.

Stable codes: `CONFIG_ERROR`, `UNKNOWN_DEVICE`, `UNREACHABLE`, `TIMEOUT`,
`INVALID_RESPONSE`, `VALIDATION_ERROR`, `UNSUPPORTED_CAPABILITY`, `AMBIGUOUS_NAME`,
`PRESET_NOT_FOUND`, `PRESET_CONFLICT`, `BACKUP_FAILED`, `WRITE_OUTCOME_UNKNOWN`,
`VERIFICATION_MISMATCH`. A pre-dispatch timeout is distinct from possible write
application. Offline entries in successful inventory probes are per-device data.
For a device call, `CONFIG_ERROR` means the configured device address cannot be used;
no request was sent, it is not retried and the address is not echoed.

Return the envelope through MCP `structuredContent` with an output schema and one
text content block containing the same JSON envelope for older clients.
`isError = !ok` for tool execution, including uncertain writes. Malformed JSON-RPC,
unknown methods/tools and negotiation errors use SDK protocol errors. Once a known
tool's domain validation runs, its errors use the envelope; SDK argument-shape
rejection may precede execution and is tested separately for parity. Device
failures must not become HTTP errors or apparently successful prose. Annotations
accurately describe read-only/destructive/idempotent behavior but are not barriers;
allocation is not idempotent, and animations/external clients limit setter claims.

## Transport access and lifecycle

Startup selects `--transport stdio|streamable-http`, default stdio, same domain
graph. Validate configuration before serving without probing/writing controllers.
stdio opens no listener, reserves stdout for MCP and uses sanitized stderr logs.
HTTP-only credentials are not required for stdio.

HTTP uses the fixed path `/mcp`, default `--host 127.0.0.1 --port 8000`, one worker
and no `--workers` option. Other binds are explicit; a changed host or port (also a
wildcard bind) needs at least one `--allowed-host`, which replaces the defaults.
HTTP-only options together with stdio are rejected at startup (exit 2). Repeated `--allowed-host` values are exact authorities (host and
optional port); defaults are `127.0.0.1:8000` and `localhost:8000`. Changed bind/port
requires matching explicit configuration. `--allowed-origin` values are exact
absolute origins (scheme/host/port, no path); default empty rejects supplied
browser Origins. Authenticated requests without Origin are allowed. Reject
malformed/disallowed Host/Origin as 403 before device actions, including supplied
invalid Origin when credentials are absent. No wildcard/unchecked forwarded trust:
the guard answers 403 itself (the SDK's own Host check would answer 421 and runs
only after authentication), compares exactly and case-insensitively without implied
default-port equivalence, and never consults `X-Forwarded-*`/`Forwarded`. Entries
accept no wildcard, path or userinfo; at most 16 entries of 255 characters.

Direct auth is mandatory even on loopback and every method. Configure exactly one
nonempty bearer source: runtime `WLED_MCP_HTTP_TOKEN` or protected file path
`--http-token-file`; reject missing/conflicting/invalid configuration before
listening. No token CLI value, committed secret or credential logging; compare
secrets safely (constant time over digests). After Host/Origin checks,
missing/invalid bearer gives 401 with `WWW-Authenticate: Bearer` and a fixed body
before tool/device execution, then an unknown path gives 404. The credential is
32 to 512 printable ASCII characters without whitespace; a file is absolute, at most
1 KiB, read once at startup (rotation is a restart). Exactly one `Authorization`
header with the `Bearer` scheme is accepted; there is no attempt rate limiting. Equivalent authenticated proxy requires explicit trust,
protected upstream reachability and no unauthenticated bypass. Plain HTTP is for
trusted private networks; HTTPS for untrusted links. Hub auth does not protect
direct service access; a shared credential is not per-user permission. No OAuth
server is introduced.

Use SDK stateless Streamable HTTP with JSON responses: no session-ID allocation,
event replay store, background jobs or server-initiated streams. Initialization/
version negotiation still apply. Accepted notifications get protocol 202; requests
get JSON responses; every non-POST method (GET even when an event stream is
offered, DELETE, PUT, PATCH, OPTIONS, HEAD) returns 405 with `Allow: POST` after
the access checks, because the stateless SDK would otherwise open a stream for GET.
A stale `Mcp-Session-Id` is ignored and none is ever issued, so session expiry is
vacuous. Request bodies are limited to 256 KiB (413, SDK); the unauthenticated
peer's body is never read. Invalid protocol versions,
media types/methods use SDK transport/protocol errors rather than tool envelopes.
#3 locks a compatible SDK; #14 proves actual SDK client behavior, not REST or legacy
SSE substitution.

All clients share inventory, one async WLED client, caches, snapshot store and
per-device locks for process lifetime. Stateless does not mean per-request
resources. Disconnect is not cancellation: continue bounded verification after
dispatch where possible and release locks safely; never requeue. Reconnect does
not replay mutations. A resubmission is a new invocation; JSON-RPC IDs are not
durable deduplication tokens, and exactly-once execution is not promised.
Shutdown (SIGINT/SIGTERM, SIGBREAK on Windows) stops admission, drains in-flight work within existing operation
deadlines (graceful timeout is the configured operation timeout rounded up plus
2 s), closes shared resources and exits 0; a second SIGINT forces exit. There is no
unauthenticated health route: liveness is a TCP connect or an authenticated `ping`
or `tools/list` POST, neither of which touches a device. Forced interruption leaves possibly applied writes uncertain, never
resumed on restart. Multiple workers require cross-process coordination and are
outside this baseline.

Ownership: #14 implements HTTP/access/lifecycle ([decisions](decisions/issue-14.md)); #10 verifies MCP-03/MCP-04/OPS-05
and T18â€“T21; #11 records actual integration/deployment evidence for the selected
mode. Both modes need automated parity coverage. #2 establishes no deployment or
hardware acceptance.

## Evolution

Update decisions, requirements, examples and acceptance assertions together when
semantics change. Synthetic examples are contract assertions, not executable
schemas, a server or runtime evidence. Downstream issues add schema snapshots,
mock/protocol tests and actual firmware compatibility evidence.

## Stage 2 and later files

- [contract/compatibility.md](contract/compatibility.md): support matrix and WLED
  firmware tiers (#21).
- [contract/presets.md](contract/presets.md): preset restore, supplied-state save,
  snapshot listing, playlist authoring and preset bundles (#18).
- [contract/segments.md](contract/segments.md): capability model, WLED 16 segment fields,
  CCT and 2D layouts (#19).
- [contract/versioning.md](contract/versioning.md): version source, release mapping,
  non-release build identity, contract and schema evolution, migration notes (#21, #70).
