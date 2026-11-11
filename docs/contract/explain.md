# Lighting explanation (S3-EXPLAIN-01/-02, #30)

`wled_explain_lighting(device_id, segment_id?, requested?)` is a read-class, idempotent,
non-destructive tool in every profile and under every per-device ceiling. It explains why a
light change may not appear or persist on one configured controller. Both transports use the
same operation and contract. Calling it means a change was reported as ineffective; the tool
never decides that on its own.

It reads one fresh `/json/state` and then one fresh `/json/info` under the per-device lock
and one total deadline, combines them with process-local evidence and returns observed facts,
inferred candidate causes and explicit uncertainty. It never writes, polls, caches, opens a
stream, stops playback, disables an input or applies a corrective change. The envelope has
`application=not_attempted` and `verification=not_requested`.

## Request

- `device_id` (required), `segment_id` (optional, must exist in the device state, else
  `VALIDATION_ERROR`) and `requested` (optional): `white_channel` (boolean), `effect_id`,
  `palette_id` (integers). Unknown fields are `VALIDATION_ERROR`.
- `requested` is checked only against ranges and capabilities the device reports
  (`info.fxcount`, `info.palcount`, the segment's reported colour capability). No catalog is
  read and effect behaviour or colour accuracy is not judged.

## Result (`data`)

`device_id`, `read_started_at` and `captured_at` (UTC), `firmware` (`version`, `build_id`
only), `observations`, `inferred_causes`, `conclusion` and `limits`. `data` is capped at
32 KiB and 16 causes; exceeding either returns a safe `INVALID_RESPONSE`.

**Observations** carry `id`, `kind` (`reachability`, `device_state`, `playback`, `realtime`,
`nightlight`, `sync`, `capability`, `last_control`), `source` (`/json/state`, `/json/info`
or `process_memory`), `observed_at`, `age_seconds`, `stale`, `status` (`observed`,
`unknown`, `unavailable`), a small bounded `value` and `missing_indicator`. A key the
device does not report is `unknown` with `missing_indicator=true`, never `false`; a key of
the wrong type is `unavailable`.

Allowlisted indicators (nothing else is read or returned): `state.on`, `state.bri`,
`state.pl`, `state.ps`, `state.nl.on`, `state.lor`, `state.udpn.recv`, `info.live`,
`info.lm`, `info.ver`, `info.leds.count`, `info.fxcount`, `info.palcount` and `info.vid`
(as `firmware.build_id`). Addresses, MAC, BSSID, sync group masks, Wi-Fi or network
configuration and raw state/info are never returned. `info.lm` and `info.ver` are bounded
to 32 characters from a restricted character set and not address-like; anything else is
reported as `other`.

Field meanings follow the WLED JSON API: `pl` is the running playlist preset ID (-1: none),
`lor` the realtime override (0: realtime may override the lights; 1 or 2: the local state
overrides realtime), `info.live` whether realtime data is being received, `udpn.recv` whether
UDP sync receive is enabled and `nl.on` an active nightlight.

**Inferred causes** carry `code`, `confidence` (`high`, `medium`, `low`, `unknown`),
`evidence` (observation IDs), `contradicting_evidence`, a fixed `statement` and
`next_checks`. Statements and checks are fixed texts; no device text is copied. Next checks
are suggestions naming read tools or manual steps and are never executed.

| Code | Basis | Confidence |
| --- | --- | --- |
| `MASTER_OFF_OR_ZERO_BRIGHTNESS` | `state.on` false or `state.bri` 0 (observed) | high |
| `REQUESTED_CAPABILITY_UNSUPPORTED` | requested ID outside the reported range, or no white channel on the segment (observed) | high |
| `PLAYBACK_ACTIVE` | `state.pl` >= 0 | medium |
| `REALTIME_INPUT_ACTIVE` | `info.live` true; `state.lor` > 0 is contradicting evidence | medium, low when contradicted |
| `NIGHTLIGHT_ACTIVE` | `state.nl.on` true | medium |
| `SYNC_RECEIVE_ENABLED` | `state.udpn.recv` true (a possibility, not an event) | low |
| `LAST_WRITE_VERIFICATION_MISMATCH` | last recorded control outcome had `verification=mismatch` | medium |
| `LAST_WRITE_UNCERTAIN` | last recorded control outcome had `application=unknown` | medium |
| `UNATTRIBUTED_MISMATCH`, `INSUFFICIENT_EVIDENCE` | present together whenever no indicator-based cause above the last-write codes exists | unknown |
| `DEVICE_UNREACHABLE`, `DEVICE_TIMEOUT` | the read failed (see below) | medium |

Rules: all competing candidates are listed; there is no single root cause and no
probability ranking. An inferred cause from one snapshot is never above `medium`; only a
directly observed fact may be `high`. No cause names an external actor. Process-memory
evidence older than 300 seconds has `stale=true` and limits its cause to `low`.
`conclusion` is `observed_blocker` (a high-confidence observed fact), `candidates_only`
(indicator-based candidates only) or `insufficient_evidence`. The last-write causes alone do
not make a conclusion: the mismatch is a fact, its explanation is not.

`limits` are fixed texts: single non-atomic snapshot, no causality proof or actor
attribution, process memory lost on restart, allowlisted indicators only. When no indicator
explains the change, a further limit says that absence of an indicator does not prove absence
of a cause.

## Process-local control evidence

The dispatcher records, per configured device, only the latest control or manage call that
may have reached it (`application` applied, not applied or unknown, including a crashed
call): operation name, finish time, `application`, `verification` and error code from the
fixed vocabulary. No argument, light value or request body is kept. Refusals, validation
errors, dry runs and reads are not recorded. The store is bounded by the configured devices
and lost on restart, after which `last_control` is `unknown`.

## Failures

`UNREACHABLE` and `TIMEOUT` keep the existing safe error envelope and additionally return
`data` with process-memory observations only (the last observed reachability and the last
control outcome) and the matching cause; no device observation is invented. Other failures
return the error envelope without `data`.

## Interpretation

This is a read-only observation aid, not a diagnosis. It does not prove why a change failed,
who or what issued a competing input, or that the light output matches any request. The
selected-controller behaviour is not validated by hardware (see the validation record).
