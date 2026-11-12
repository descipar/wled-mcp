# Issue #128: behavior with a settings PIN and an OTA lock (2026-11-12)

Read-only probes and a minimal write set on one controller in three lock states. Scope and limits
follow [ISSUE-128-DEC-001](../decisions/issue-128.md) (read-only probes) and
[ISSUE-128-DEC-002](../decisions/issue-128.md) (write set). Host names, addresses and PIN or passphrase values
are omitted and were never stored in the repository; the controller is "the secured test
controller", the controller of [#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06)
and [#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). The raw outputs are local,
git-ignored files; this page is the committed evidence.

## Target

- Controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB segment; firmware tier
  `tested`.
- Path: a local stdio server (release 0.3.0 source tree) with a separate data directory and one
  configured device. The read-only probes used access profile `read-only` and called only
  `wled_get_state`, `wled_get_effects`, `wled_get_palettes`, `wled_list_presets` and
  `wled_get_preset` from a fixed allowlist. The write runs used profile `full` and a fixed allowlist
  of the tools named below. No discovery and no other device was used. The server sent no PIN,
  passphrase or other credential.

## Authorization

Owner chat authority on 2026-11-12 (no permalink): the controller was designated, the owner set
each lock state on it, and the read-only probes were authorized for the state with both locks and
then, on the owner's confirmation that each state was set, for the two separate states. The owner
then authorized the minimal write set in all three states, one run each, after confirming each
state. Recorded as [ISSUE-128-DEC-001](../decisions/issue-128.md) (probes) and
[ISSUE-128-DEC-002](../decisions/issue-128.md) (write set); neither is standing permission.

## States and results

The owner configured each state in the controller's settings and stated it in chat. The lock
configuration cannot be read through the JSON API, so it rests on that statement.

| State | Settings PIN | OTA lock |
| --- | --- | --- |
| A | on | on |
| B | on | off |
| C | off | on |

Each state ran the same five probes once.

| Probe | A | B | C |
| --- | --- | --- | --- |
| `wled_get_state` (`/json/info`, `/json/state`) | ok, firmware 16.0.1 | ok, same | ok, same |
| `wled_get_effects` | ok, 216 effects | ok, same | ok, same |
| `wled_get_palettes` | ok, 72 palettes | ok, same | ok, same |
| `wled_list_presets` | ok, 1 preset | ok, same | ok, same |
| `wled_get_preset` (slot 1) | ok | ok | ok |

No probe was refused, so no HTTP status other than 200 and no error envelope occurred. The two
effect-metadata warnings (IDs 122 and 179 partially parsed) are identical in all three states and
are the same without any lock.

## Write set and results

The baseline was the same in all three runs: master off, brightness 47, segment 0 speed 128, one
preset (slot 1), no active preset or playlist. The master stayed off in every readback, so no light output was expected. Each run
used the same steps, a dry run before every write, no retry:

1. `wled_set_state`: master brightness changed, then restored (power untouched).
2. `wled_patch_segments`: segment 0 speed changed, then restored.
3. `wled_store_preset` into the unused slot 5 with a state equal to the baseline and power off, then
   `wled_list_presets` (slots 1 and 5), then `wled_delete_preset` of slot 5 (snapshot taken).
4. A final read: state and preset list compared with the baseline.

| Step | A | B | C |
| --- | --- | --- | --- |
| Master state write and restore | applied, verified | applied, verified | applied, verified |
| Segment patch and restore | applied, verified | applied, verified | applied, verified |
| Preset store, slot 5 | applied, verified | applied, verified | applied, verified |
| Preset delete, slot 5 (snapshot) | applied, verified | applied, verified | applied, verified |
| State and presets equal the baseline | yes | yes | yes |

Every write was checked by the server's readback; no write was refused, failed or uncertain, and
none was retried. The three delete snapshots stay in the local data directory of the probe server,
not on the controller.

## Acceptance criteria of #128

| Criterion | Result |
| --- | --- |
| Separate states (PIN, later OTA lock) recorded neutrally, no PIN or passphrase value committed | Met for states A, B and C |
| Read-only probes first with each lock active | Met (table above) |
| Minimal write set with each lock, restorable state kept | Met for states A, B and C (write results above); the state was restored and checked each time |
| A refusal surfaces as a clear, non-retried error; no bypass; no security setting changed | Partly met: not observed on hardware because no read was refused. The behavior is covered by a mock test (HTTP 401 and 403 become `INVALID_RESPONSE` with the status code, one request, no retry); the server has no code path that sends credentials or changes a security setting |
| Result written to `docs/validation/`, README limitations and `docs/contract/compatibility.md`; planned-test note replaced | Met |
| HTTP authentication or a credentialed proxy | Out of scope, unchanged |

## Result per lock

| Lock | Reads | Writes |
| --- | --- | --- |
| Settings PIN | The five probed reads: supported, no change observed | The minimal write set: supported, no change observed |
| OTA lock | The five probed reads: supported, no change observed | The minimal write set: supported, no change observed |
| Both | As above | As above |

No lock refused or changed any probed read or write. This matches the WLED documentation, which ties
the PIN to the settings pages and the OTA lock to firmware updates.

## Not shown

- Writes outside the minimal set (layout replacement, preset restore, import, playlists, signals,
  groups and scenes) under a lock; they use the same HTTP interface, but were not run here.
- Any behavior of the settings pages or a firmware update under a lock.
- Read tools outside the five probed ones (for example export, live snapshot, effect search,
  explain, signal status).
- Other controllers or firmware versions.
- The deployed HTTP service on the hub; this run used a local stdio server.
- A refusal of a read on hardware (none occurred).
