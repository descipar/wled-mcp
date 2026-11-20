# Temporary signals (`wled_start_signal`, `wled_get_signal_status`, `wled_cancel_signal`, #28)

Requirements S3-SIGNAL-01 and S3-SIGNAL-02 ([STAGE-3.md](../STAGE-3.md)). Decisions:
[ISSUE-28-DEC-002](../decisions/stage-3.md) (design defaults, a technical proposal accepted by
the coordinator, not a human decision) and [ISSUE-28-DEC-001](../decisions/stage-3.md) (hardware
authorization for the evidence). Evidence: [validation/stage-3.md](../validation/stage-3.md).
Examples use synthetic IDs.

A **signal** shows one RGB colour on explicitly listed existing segments of **one** configured
device for a bounded time and then puts back **only the fields it changed**, and only if they
still hold what the signal set. If someone changed them meanwhile, the server reports
`skipped_conflict` and writes nothing. Both transports use these operations.

It is **not a scheduler**: no recurrence, deferred start, queue, replace policy or persistence; no
preset is created, overwritten or activated; a write with unknown outcome is never replayed.

## Tools

| Tool | Class | Hints (read-only / destructive / idempotent / open-world) | Reachable in |
| --- | --- | --- | --- |
| `wled_start_signal` | `control` | false / false / false / false | `control`, `full` |
| `wled_cancel_signal` | `control` | false / false / true / false | `control`, `full` |
| `wled_get_signal_status` | `read` | true / false / true / false | every profile |

Live device output only; no snapshot, file or device storage is touched, so no tool is `manage`
([profiles](profiles.md)). A device whose ceiling is below `control` refuses `wled_start_signal`
with `ACCESS_DENIED`, also for `dry_run`. `wled_cancel_signal` has no `device_id`: the signal's
device passed its ceiling at start and a ceiling cannot change without a restart. Profiles are not
tenancy: any caller that can reach the tool can cancel any signal.

### Requests

| Tool | Fields |
| --- | --- |
| `wled_start_signal` | `device_id` (1-64 characters), `segment_ids` (1-16 unique integers >= 0, existing active segments), `color` (exactly three integers 0-255, RGB), `duration_seconds` (integer 1-300, required, no default), `dry_run` (default `false`) |
| `wled_get_signal_status` | optional `operation_id`; without it: all active signals and the most recent 32 ended ones, active first, each newest first |
| `wled_cancel_signal` | `operation_id` |

Unknown fields and wrong types are rejected. The operation ID is server-generated, `sig-` plus 16
lowercase hex characters (`sig-0123456789abcdef`), never client-supplied.

The signal always uses the **Solid** effect (resolved by name from the device's effect catalog)
and the device's own brightness. A four-channel target gets white 0 appended; a white-only segment
or one without capability evidence is refused (`UNSUPPORTED_CAPABILITY`). There are no brightness,
effect or palette options.

## Owned fields

The signal captures these fields before the write, compares them before restoring and restores
only them.

| Scope | Field (wire key) | Written when | Compared before restore | Restored to |
| --- | --- | --- | --- | --- |
| master | `on` | the master was off | still `true` | `false` |
| segment | `col[0]` | always (slot 0, full channel width) | still the written colour | the captured slot 0 |
| segment | `fx` | always | still the Solid effect ID | the captured effect ID |
| segment | `on` | the segment was off | still `true` | `false` |

The comparison has the semantics of the apply verification (`matches_segments`,
`matches_set_state`; a test pins the agreement) plus three side-effect checks (a playlist,
realtime data or nightlight started meanwhile) and the target geometry (a removed or resized
target is a conflict). **Not compared and never written:** master brightness, transition, segment
brightness, speed, intensity, palette, custom sliders, checkboxes, colour temperature, colour
slots 1 and 2, names, selection, untargeted segments, the running preset marker and counters or
animation progress; an external change there is preserved. The animation phase restarts with the
effect change.

The apply is one combined state write (`on` only when the master was off, plus the segment
objects) built by the existing planners and read back before the timer starts.

## Unsupported device states

Refused at start, before any write, as `VALIDATION_ERROR` with `application` = `not_attempted` and
a stable `data.reason` (no new error code):

| `data.reason` | Condition (fresh read under the device lock) |
| --- | --- |
| `segment_unknown` | a target ID is not an existing active segment |
| `capture_incomplete` | a target does not report `on`, colour slot 0 and the effect (`UNSUPPORTED_CAPABILITY`) |
| `color_capability` | a white-only segment or one without capability evidence (`UNSUPPORTED_CAPABILITY`) |
| `playlist_active` | a playlist is running |
| `realtime_active` | the device receives realtime data |
| `nightlight_active` | a nightlight is running |
| `segment_frozen` | a target is frozen, or the master is off and any segment is frozen (turning the master on unfreezes every segment) |
| `master_off_other_segments` | the master is off and another active segment would light up when it turns on |
| `brightness_zero` | the master's remembered brightness is 0, or a target is off with brightness 0 |
| `effect_unavailable` | the device has no unambiguous `Solid` effect (`UNSUPPORTED_CAPABILITY`) |

A running preset marker is allowed: any state write clears it and the restore does not re-activate
the preset (a warning says so).

## Overlap and limits

At most **one signal per device** (starting, active or restoring) and **eight per process**. A
second start on a device is refused with `reason` `signal_active` and `data.active_operation_id`;
the ninth with `signal_limit`; a start during shutdown with `shutting_down`. Signals are never
queued or replaced. The slot is reserved before the first read and freed when the start fails
before dispatch, when the apply is uncertain, and when the signal ends. Other tools may still
write to the device during a signal; the conflict check exists for that.

## Results

### `wled_start_signal`

Success is `ok=true`, `applied` / `verified`, with `data.operation_id`, `status` (`active`),
`segment_ids`, `started_at`, `expires_at`, `duration_seconds`, `owned` (each field with its
`captured` and `applied` value), `restoration_plan`, `unowned_observed` (display only), `timing`
and `plan` (the exact payload). A start failure before dispatch creates no record and no ID.

If the apply was sent but not verified (`WRITE_OUTCOME_UNKNOWN`, `VERIFICATION_MISMATCH`), no
timer starts and **nothing is restored automatically**: the envelope is the engine's uncertain
envelope with `data.operation_id`, `data.reason` `apply_unverified` and `data.captured`, and a
terminal `uncertain` record is kept. Read the state and decide, using the captured values.

`dry_run` reads the device (bounded reads under the lock) and returns the same plan, owned fields
and restoration plan, or the same refusal; it creates no record and reserves nothing.

### Status and restoration

| `status` | Meaning |
| --- | --- |
| `active` | applied, timer running |
| `restoring` | ended by `ended_by` = `expired`, `cancelled` or `shutdown`; the restore is in progress |
| `restored` | the owned fields matched and one verified restore write was made |
| `skipped_conflict` | a compared field, the geometry or a side-effect check differs; nothing was written; the device keeps the external state |
| `uncertain` | the restoration could not be established |

`data.restoration` carries `result`, `application`, `verification`, `error_code`, `differences`
(at most 20 entries `{scope, id, field, expected, observed}`), `write_attempted` (did a POST
leave) and `attempts`. An `uncertain` restoration keeps the `captured` values in `owned` for an
explicit restore. Timestamps: `started_at`, `expires_at`, `ended_at`.

`wled_get_signal_status` reads process memory only and contacts no device. An unknown ID is
`VALIDATION_ERROR` with `reason` `unknown_signal`, which is every ID after a restart.

### `wled_cancel_signal`

Ends the signal now and restores if the fields are still ours: the same conditional restore as
expiry, waiting for the result. There is no cancel-without-restore (patch the segment to keep a
colour). `restored` is `ok=true` `applied` / `verified`; `skipped_conflict` is `ok=true`
`not_attempted` with a warning (device left as found); `uncertain` is `ok=false` with the engine's
error. Cancelling an ended signal is `ok=true`, `not_attempted`, with the terminal record and a
warning; cancelling one already restoring waits for that result and never starts a second restore.

## Retry policy: re-read and decide, never replay

Only an **expiry-driven** restore that failed **before any POST left** (device unreachable, or the
operation deadline expired while reading or waiting for the lock) is retried once after 5 seconds
as a fresh attempt (fresh read, comparison, write). A restore whose POST left (readback
unreadable, mismatch, transport error) is never retried. A cancel or shutdown restore makes one
attempt. A device that returns later receives no further write.

## Locks and access context

- Capture and apply are one `write_verified` call (one lock hold for fresh read, checks, capture,
  planning, POST and readback); the lock is **not** held while waiting. The restore is again one
  `write_verified` call: re-acquire the lock within the operation deadline, re-read, compare, write.
- Each signal is run by **one manager task**; a start or cancel only hands work to it and awaits the
  result, so a dropped request never orphans an applied signal. Cancel, expiry and shutdown race
  through one synchronous check-and-set: exactly one restore per signal.
- The task sets the access class `control` itself for its whole life, so the delayed restore is
  evaluated as `control` against the device's effective ceiling (which allowed `control` at start);
  never `manage` and never the ambient "class unknown, assume the highest" case a restricted
  deployment refuses ([profiles](profiles.md)).

## Shutdown and restart

**No persistence.** Signals live in process memory; nothing is written to the data directory or
recovered after a restart.

- **Orderly shutdown** (stdio end of input or interrupt, HTTP SIGTERM or SIGINT after the listener
  drained): new starts are refused and every active signal makes **one** conditional restore attempt
  (same comparison, no retry), concurrently, within a total budget of 5 seconds. Unfinished restores
  are abandoned and may stay applied (logged `shutdown_incomplete`; an abandoned POST is uncertain; a
  start whose apply is in flight is awaited up to the operation timeout, so the exit can exceed the
  budget). The budget stays inside the HTTP grace period ([DEPLOYMENT.md](../DEPLOYMENT.md)).
- **Crash, kill, second interrupt, power loss:** an active signal stays applied until someone changes
  it, and after the next start its ID is `unknown_signal`. Manual recovery: read the state with
  `wled_get_state`, compare with the `captured` values from the start, and restore segment colour,
  effect and, if the signal turned it on, the power ([segments](segments.md)).
- **Lost connection:** a dropped client causes no write; the timer runs on and the restore happens at
  expiry. A reconnecting client reads the status by operation ID.

A forced interruption leaves possibly applied writes uncertain and never resumed
([TOOL-CONTRACT.md](../TOOL-CONTRACT.md#transport-access-and-lifecycle)).

## Timing and limits of the guarantee

The duration runs on the monotonic clock from the verified apply; the restore starts at expiry plus
lock wait and round trips, so a signal can last longer, and an unreachable device may never be
restored (`uncertain`). A client writing to the device directly (not through this server) between
the comparison read and the restore POST is not detected: WLED has no compare-and-set; the window is
one device round trip.

## Diagnostics and compatibility

One bounded INFO line per event (`started`, `restored`, `skipped_conflict`, `uncertain`,
`shutdown_incomplete`) goes to stderr with operation ID, status, error code and configured device
ID; never a colour, address or state body ([diagnostics](diagnostics.md)). A delayed restore is
recorded as `wled_signal_restore` in the last-control evidence, so `wled_explain_lighting`
([explain](explain.md)) can attribute a change to it. Additive: three tools, no new error code or
enum value, no persistent format ([versioning](versioning.md)). A zone as target is a possible
follow-up ([zones](zones.md)).
