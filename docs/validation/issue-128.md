# Issue #128: read-only behavior with a settings PIN and an OTA lock (2026-11-12)

Read-only probes of one controller in three lock states. The write set of #128 was not run; it needs
its own owner authorization. Scope and limits follow
[ISSUE-128-DEC-001](../decisions/issue-128.md). Host names, addresses and PIN or passphrase values
are omitted and were never stored in the repository; the controller is "the secured test
controller", the controller of [#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06)
and [#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). The raw outputs are local,
git-ignored files; this page is the committed evidence.

## Target

- Controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB segment; firmware tier
  `tested`.
- Path: a local stdio server (release 0.3.0 source tree), access profile `read-only`, a separate
  data directory, one configured device. The probe script called only `wled_get_state`,
  `wled_get_effects`, `wled_get_palettes`, `wled_list_presets` and `wled_get_preset` from a fixed
  allowlist. No write tool, no discovery and no other device was used. The server sent no PIN,
  passphrase or other credential.

## Authorization

Owner chat authority on 2026-11-12 (no permalink): the controller was designated, the owner set
each lock state on it, and the read-only probes were authorized for the state with both locks and
then, on the owner's confirmation that each state was set, for the two separate states. Recorded as
[ISSUE-128-DEC-001](../decisions/issue-128.md); it covers read-only probes only.

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

## Acceptance criteria of #128

| Criterion | Result |
| --- | --- |
| Separate states (PIN, later OTA lock) recorded neutrally, no PIN or passphrase value committed | Met for states A, B and C |
| Read-only probes first with each lock active | Met (table above) |
| Minimal write set with each lock, restorable state kept | Open: not authorized, not run |
| A refusal surfaces as a clear, non-retried error; no bypass; no security setting changed | Partly met: not observed on hardware because no read was refused. The behavior is covered by a mock test (HTTP 401 and 403 become `INVALID_RESPONSE` with the status code, one request, no retry); the server has no code path that sends credentials or changes a security setting |
| Result written to `docs/validation/`, README limitations and `docs/contract/compatibility.md`; planned-test note replaced | Met for the read paths; writes stay "untested" until the write set runs |
| HTTP authentication or a credentialed proxy | Out of scope, unchanged |

## Result per lock

| Lock | Reads | Writes |
| --- | --- | --- |
| Settings PIN | The five probed reads: supported, no change observed | Unknown |
| OTA lock | The five probed reads: supported, no change observed | Unknown |

## Not shown

- Every write of the server (master state, segment patch, preset save, delete, restore) under any
  lock. This matches the WLED documentation, which ties the PIN to the settings pages and the OTA
  lock to firmware updates, but it is not shown here.
- Any behavior of the settings pages or a firmware update under a lock.
- Read tools outside the five probed ones (for example export, live snapshot, effect search,
  explain, signal status).
- Other controllers or firmware versions.
- The deployed HTTP service on the hub; this run used a local stdio server.
- A refusal of a read on hardware (none occurred).
