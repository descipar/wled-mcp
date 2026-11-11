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
- Field meanings were checked against the WLED JSON API semantics; `lor` greater than zero is
  used as contradicting evidence for a realtime candidate.

## Hardware

None. No live device, LAN access or write was part of this implementation. The M2 read-only
live run needs separate owner authorization and is not claimed here; mocks and loopback do
not establish firmware behaviour on a controller.
