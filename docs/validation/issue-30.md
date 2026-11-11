# Issue #30 - lighting explanation

Requirements: S3-EXPLAIN-01, S3-EXPLAIN-02; scenarios X30-1 to X30-8 of the approved work
packet. Contract: [contract/explain.md](../contract/explain.md).

Synthetic tests in `tests/test_explain.py` cover: competing explanations with capped
confidence and no actor (X30-1); missing firmware indicators including `ver` (X30-2);
stale and absent process memory (X30-3); an unattributable mismatch (X30-4); separate
categories for unreachable, timeout, out-of-range effect/palette, white on an RGB segment,
verification mismatch and a clean device (X30-5); exactly two GETs and no POST (X30-6);
registration in every profile with advisory annotations (X30-7); redaction sentinels in the
result and call log, output and cause caps, and the dispatcher hook recording only allowlisted
fields from a real control outcome while ignoring refusals, dry runs and unknown tools (X30-8).
`tests/test_diagnostics.py` covers the evidence store; `tests/test_access_profiles.py`
(read tools on capped devices, no POST) and `tests/tool_contract.py` include the new READ
tool. `tests/test_acceptance_parity.py` runs the tool through the actual stdio console and a
protected loopback Streamable HTTP console, before and after an uncertain write, comparing
both renderings after normalizing timestamps, ages and correlation IDs. No ordinary test
contacts a LAN device.

## Deviations from the work packet

- The evidence store is a separate class in `diagnostics.py` but is carried as an attribute of
  `ServiceMonitor` (`monitor.last_control`), because `create_server` receives only the monitor
  and `cli.py` is outside the authorized paths.
- `info.lm`/`info.ver` use a stricter character allowlist than "32 printable characters", so
  address- or MAC-like text becomes `other`.
- `docs/WLED-COVERAGE.md` gained a server-only entry for the tool; this is outside the
  authorized paths but required by check C7 of `scripts/check_coverage.py`.
- Premise: every call counts as a reported ineffective change, so a device without any
  explaining indicator still returns `UNATTRIBUTED_MISMATCH` and `INSUFFICIENT_EVIDENCE`.
- `SYNC_RECEIVE_ENABLED` (a firmware default) does not suppress those fallback codes or lift
  the conclusion above `insufficient_evidence`.
- Field meanings were checked against the WLED JSON API semantics; `lor` greater than zero is
  used as contradicting evidence for a realtime candidate.

## Hardware

None as part of the implementation: no live device, LAN access or write was part of the
merged candidate. The M2 read-only live run followed separately and is recorded below.

### Live read-only run (M2 exit, ISSUE-30-DEC-001)

On 2026-11-11 the coordinator ran the merged software (content identical to `main` at the
squash commit of PR #175) through an actual MCP stdio client with the `read-only` profile
against one owner-selected test controller. Exactly one `wled_explain_lighting` call was
made, which issued one `GET /json/state` and one `GET /json/info`. The call window was
08:59:09.586 to 08:59:09.648 UTC. The tool was registered in the read-only profile.

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

What this shows: the tool works against real firmware over the real transport, every
indicator in the allowlist was present, and the result stayed within the documented limits
(no actor named, the sync cause marked as a possibility, limits text present). It also
confirms the review finding that sync receive is enabled on a default-configured controller,
which is why that cause alone must not hide insufficient evidence. The run checked no
write, no other device and no repeated or stale-evidence behaviour; those remain covered by
mocks only. Because the master switch was off, the run does not exercise the
playback/realtime-override or the unattributed-mismatch paths on hardware. A second
permitted call was not needed. No physical write, configuration or firmware change,
deployment or device discovery occurred. The capture and the inventory stay in the ignored
runtime directory.
