# Issue #30 - lighting explanation

Requirements: S3-EXPLAIN-01, S3-EXPLAIN-02; scenarios X30-1 to X30-8 of the approved work
packet. Contract: [contract/explain.md](../contract/explain.md).

Synthetic tests in `tests/test_explain.py` cover: competing explanations with capped confidence and no
actor (X30-1); missing firmware indicators including `ver` (X30-2); stale and absent process memory
(X30-3); an unattributable mismatch (X30-4); separate categories for unreachable, timeout, out-of-range
effect/palette, white on an RGB segment, verification mismatch and a clean device (X30-5); exactly two
GETs and no POST (X30-6); registration in every profile with advisory annotations (X30-7); redaction
sentinels, output and cause caps, and the dispatcher hook recording only allowlisted fields from a real
control outcome (X30-8). `tests/test_diagnostics.py` covers the evidence store,
`tests/test_access_profiles.py` and `tests/tool_contract.py` the READ tool, and
`tests/test_acceptance_parity.py` runs it through the stdio console and a protected loopback HTTP
console before and after an uncertain write. No ordinary test contacts a LAN device.

## Deviations from the work packet

- The evidence store is a class in `diagnostics.py` carried as `ServiceMonitor.last_control`
  (`create_server` receives only the monitor and `cli.py` was outside the authorized paths).
- `info.lm`/`info.ver` use a stricter character allowlist than "32 printable characters", so address-
  or MAC-like text becomes `other`.
- `docs/WLED-COVERAGE.md` gained a server-only entry (required by check C7).
- Every call counts as a reported ineffective change, so a device without an explaining indicator still
  returns `UNATTRIBUTED_MISMATCH` and `INSUFFICIENT_EVIDENCE`; `SYNC_RECEIVE_ENABLED` (a firmware
  default) neither suppresses those codes nor lifts the conclusion above `insufficient_evidence`.
- `lor` greater than zero is contradicting evidence for a realtime candidate.

## Hardware

None as part of the implementation. The M2 read-only live run followed separately.

### Live read-only run (M2 exit, ISSUE-30-DEC-001)

On 2026-11-11 the coordinator ran the merged software (content identical to `main` at the squash commit
of PR #175) through an MCP stdio client with the `read-only` profile against one owner-selected test
controller: exactly one `wled_explain_lighting` call (one `GET /json/state`, one `GET /json/info`).

| Field | Observed result |
| --- | --- |
| Envelope `ok` / `application` / `verification` | true / `not_attempted` / `not_requested` |
| Firmware | WLED 16.0.1, build 2606300, 133 LEDs, 220 effects, 72 palettes |
| Master power / brightness | off / 47 |
| Playlist `pl` / preset `ps` | -1 / -1 (none active) |
| Nightlight / realtime `lor` / `live` / `lm` | off / 0 / false / empty |
| Sync receive `udpn.recv` | true |
| Last control (process memory) | unknown, no write in this process |
| Inferred causes | `MASTER_OFF_OR_ZERO_BRIGHTNESS` (high, observed); `SYNC_RECEIVE_ENABLED` (low, possibility only) |
| Conclusion | `observed_blocker` |

Result: the tool works against real firmware over the real transport, every allowlisted indicator was
present, and the result stayed within the documented limits (no actor named, sync cause marked as a
possibility). It confirms that sync receive is enabled on a default controller. Not checked on hardware:
writes, other devices, repeated or stale-evidence behavior, playback/realtime override and
unattributed-mismatch paths (master was off); those are mock-only. No physical write, configuration or
firmware change, deployment or discovery occurred.
