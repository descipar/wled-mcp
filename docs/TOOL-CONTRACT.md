# V1 MCP tool contract

Implementation status: #4 exposes only `wled_list_devices` from this table. Its
network-free default, bounded explicit probes and internal client foundations are
described in [INVENTORY-CLIENT.md](INVENTORY-CLIENT.md). Remaining tools and the
protected HTTP service are design requirements, not executable behavior yet.

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
| `wled_restore_preset` | `device_id`, `backup_id`, `preset_id`, `overwrite=false`, `dry_run` | Explicit single-entry storage restoration | Should; execution deferred pending safe adapter |
| `wled_patch_raw_state` | `device_id`, JSON object `patch`, `dry_run` | Restricted advanced state patch | Should; default disabled, allowlist belongs to #13 |

Tool descriptions state physical output, playback and storage effects. State/layout
changes may clear the active-preset marker or interrupt playback without editing
saved objects. Never silently disable timers, realtime inputs or another client.
Activation is restricted to verified state/playlist shapes and safe referenced
entries. API-command/unknown presets remain readable and backupable, but activation
returns `UNSUPPORTED_CAPABILITY` until their effects are validated. No arbitrary
command forwarding or implicit playlist editing.

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
`name`. If exposed, grouping is positive, spacing nonnegative (both within known
firmware limits), offset is 0 <= offset < resulting physical range length (no
implicit wrap), and names respect the profile's UTF-8 byte limit (no truncation).
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
round-trip the whole configuration. Reject an unrepresentable preservation plan.
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

PRE-03 supplied-state save remains a capability-gated Should deferred to #13:
no proven no-live-output route in the reviewed source, no implicit apply/save/
restore workaround. Restore execution is also deferred until a safe single-entry
storage adapter exists; do not upload a whole filesystem or execute stored commands
as a shortcut.

## Snapshot and explicit restoration

Format 1 contains `format_version`, opaque server-generated `backup_id`, configured
`device_id`, `preset_id`, `firmware` identity, UTC `created_at` and exact `preset`
object. See [snapshot.json](../examples/contracts/snapshot.json). No integrity hash
is defined in format 1: validation does not authenticate tampered local storage.
Reject unknown envelope versions, malformed metadata, unsafe IDs, oversize or
empty/nonobject preset payloads; preserve unknown object fields without executing them.

IDs resolve only inside the configured data directory; no caller paths/name-based
filenames. Same-directory temporary write, flush/close, atomic replace and
read/validation precede durable success; use supported filesystem durability
primitives. Retain 20 valid snapshots per device by default, configurable. Prune
only recognized older snapshots after new durable success, protecting the snapshot
needed by this operation. Backup failure aborts destructive writes (`BACKUP_FAILED`).
Dry-run reports required backup without filesystem mutation.

Restore steps: inspect envelope/object, resolve source and explicit target, require
matching device and supported firmware/profile (or a separately reviewed compatible
path), recheck destination, require overwrite intent and prior snapshot if occupied,
store exactly one object through a proven storage-only path, verify persistent
object equality including unknown fields and no deliberate live-output change.
No automatic rollback. Until implemented, the supported manual boundary is export/
inspection and planning explicit single-entry restoration; actual restoration
remains pending and untested. Activating a preset does not restore its storage.
Bulk WLED UI restore may replace unrelated entries and is outside this workflow.

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

HTTP uses `/mcp`, default `--host 127.0.0.1 --port 8000`, one worker. Other binds
are explicit. Repeated `--allowed-host` values are exact authorities (host and
optional port); defaults are `127.0.0.1:8000` and `localhost:8000`. Changed bind/port
requires matching explicit configuration. `--allowed-origin` values are exact
absolute origins (scheme/host/port, no path); default empty rejects supplied
browser Origins. Authenticated requests without Origin are allowed. Reject
malformed/disallowed Host/Origin as 403 before device actions, including supplied
invalid Origin when credentials are absent. No wildcard/unchecked forwarded trust.

Direct auth is mandatory even on loopback and every method. Configure exactly one
nonempty bearer source: runtime `WLED_MCP_HTTP_TOKEN` or protected file path
`--http-token-file`; reject missing/conflicting/invalid configuration before
listening. No token CLI value, committed secret or credential logging; compare
secrets safely. After Host/Origin checks, missing/invalid bearer gives 401 before
tool/device execution. Equivalent authenticated proxy requires explicit trust,
protected upstream reachability and no unauthenticated bypass. Plain HTTP is for
trusted private networks; HTTPS for untrusted links. Hub auth does not protect
direct service access; a shared credential is not per-user permission. No OAuth
server is introduced.

Use SDK stateless Streamable HTTP with JSON responses: no session-ID allocation,
event replay store, background jobs or server-initiated streams. Initialization/
version negotiation still apply. Accepted notifications get protocol 202; requests
get JSON responses; GET without offered stream and unsupported session DELETE
return 405. Apply access checks to these methods too. Invalid protocol versions,
media types/methods use SDK transport/protocol errors rather than tool envelopes.
#3 locks a compatible SDK; #14 proves actual SDK client behavior, not REST or legacy
SSE substitution.

All clients share inventory, one async WLED client, caches, snapshot store and
per-device locks for process lifetime. Stateless does not mean per-request
resources. Disconnect is not cancellation: continue bounded verification after
dispatch where possible and release locks safely; never requeue. Reconnect does
not replay mutations. A resubmission is a new invocation; JSON-RPC IDs are not
durable deduplication tokens, and exactly-once execution is not promised.
Shutdown stops admission, drains in-flight work within existing operation
deadlines (bounded by the maximum configured deadline), closes shared resources
and exits. Forced interruption leaves possibly applied writes uncertain, never
resumed on restart. Multiple workers require cross-process coordination and are
outside this baseline.

Ownership: #14 implements HTTP/access/lifecycle; #10 verifies MCP-03/MCP-04/OPS-05
and T18â€“T21; #11 records actual integration/deployment evidence for the selected
mode. Both modes need automated parity coverage. #2 establishes no deployment or
hardware acceptance.

## Evolution

Update decisions, requirements, examples and acceptance assertions together when
semantics change. Synthetic examples are contract assertions, not executable
schemas, a server or runtime evidence. Downstream issues add schema snapshots,
mock/protocol tests and actual firmware compatibility evidence.
