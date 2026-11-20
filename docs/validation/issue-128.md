# Issue #128: behavior with a settings PIN and an OTA lock (2026-11-12)

Read-only probes and a minimal write set on one controller in three lock states, within
[ISSUE-128-DEC-001](../decisions/issue-128.md) (read-only probes) and
[ISSUE-128-DEC-002](../decisions/issue-128.md) (write set); neither is standing permission. The
controller is "the secured test controller" of
[#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06) and
[#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). No host names, addresses or PIN or
passphrase values were stored; raw outputs are local, git-ignored files.

## Target and authorization

- WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB segment; firmware tier `tested`.
- A local stdio server (release 0.3.0 source tree) with a separate data directory and one configured
  device; read-only probes used profile `read-only` and five tools (`wled_get_state`,
  `wled_get_effects`, `wled_get_palettes`, `wled_list_presets`, `wled_get_preset`); write runs used
  profile `full` and a fixed allowlist. No discovery, no other device, no credential sent.
- Owner chat authority 2026-11-12 (no permalink): the owner set each lock state and confirmed it
  before each run. The lock configuration cannot be read through the JSON API, so it rests on that
  statement.

| State | Settings PIN | OTA lock |
| --- | --- | --- |
| A | on | on |
| B | on | off |
| C | off | on |

## Results

Read probes (one run per state): all five calls succeeded in A, B and C (firmware 16.0.1, 216
effects, 72 palettes, 1 preset, slot 1 readable). No read was refused; the two effect-metadata
warnings (IDs 122 and 179) are identical in all states and without any lock.

Write set (one run per state, dry run before every write, no retry), baseline master off,
brightness 47, segment 0 speed 128, one preset (slot 1): master brightness change and restore,
segment 0 speed change and restore, `wled_store_preset` into unused slot 5 then
`wled_delete_preset` of slot 5 (snapshot taken), final read compared with the baseline. Every step
was applied and verified by readback in A, B and C; state and presets equal the baseline each time;
nothing was refused, failed, uncertain or retried. The delete snapshots stay in the local probe data
directory.

## Acceptance criteria of #128

| Criterion | Result |
| --- | --- |
| Separate states (PIN, later OTA lock) recorded neutrally, no PIN or passphrase committed | Met for A, B and C |
| Read-only probes first with each lock active | Met |
| Minimal write set with each lock, restorable state kept | Met for A, B and C; state restored and checked each time |
| A refusal surfaces as a clear, non-retried error; no bypass; no security setting changed | Partly met: not observed on hardware because no read was refused. A mock test covers HTTP 401 and 403 as `INVALID_RESPONSE` with the status, one request, no retry; the server has no path that sends credentials or changes a security setting |
| Result in `docs/validation/`, README limitations and `docs/contract/compatibility.md`; planned-test note replaced | Met |
| HTTP authentication or a credentialed proxy | Out of scope, unchanged |

Result per lock (settings PIN, OTA lock, both): the five probed reads and the minimal write set are
supported with no change observed, matching the WLED documentation (PIN for the settings pages, OTA
lock for firmware updates).

## Not shown

Writes outside the minimal set (layout replacement, preset restore, import, playlists, signals,
groups, scenes) under a lock; settings pages or firmware update under a lock; read tools outside
the five; other controllers or firmware; the deployed HTTP service on the hub; a refusal of a read
on hardware (none occurred).
