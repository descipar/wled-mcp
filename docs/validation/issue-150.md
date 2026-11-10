# Issue #150 — bounded read-only live snapshot

Requirements: LIVE-01; scenarios L150-1–6 in the approved issue work packet.

Synthetic tests in `tests/test_live_snapshot.py` cover dedicated object decoding,
strict budgets, malformed/oversized input, actual sampled indices, downsampling,
nondivisible length, sparse IDs, gaps/overlaps, no-sample/missing/stale geometry,
global run/segment budgets, bounded byte output, matrix/empty observations,
HTTP 404/501 versus malformed/HTTP500/timeout/unreachable failures and no raw
sensitive diagnostic values. The read router refuses any POST.

`tests/test_acceptance_parity.py` exercises a positive sampled snapshot through
the actual stdio and protected loopback HTTP console, comparing both result
renderings after validating/normalizing timestamps and correlation IDs. Profile
and tool-contract tests include the new READ operation through the independent
`tests/tool_contract.py` helper. No ordinary test contacts a LAN device.

Focused local checks and exact candidate are recorded in the implementation
handoff and PR. Required full suite, distribution and container checks run in CI.

## Hardware

Selected-controller read-only authorization is ISSUE-150-DEC-001. An initial
bounded GET observation found WLED 16.0.1 build 2606300, 133 LEDs; info/state reads
worked but `/json/live` returned HTTP 501. This is unavailable-endpoint evidence,
not evidence of positive physical color accuracy or animation. No writes,
firmware/configuration changes, deployment or discovery are part of this check.

Final-candidate tool probe: pending coordinator execution. Its exact outcome will
be added before independent review; captures and actual inventory remain ignored.
