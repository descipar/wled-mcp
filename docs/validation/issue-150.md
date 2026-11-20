# Issue #150 — bounded read-only live snapshot

Requirements: LIVE-01; scenarios L150-1–6 in the approved issue work packet.

Synthetic tests in `tests/test_live_snapshot.py` cover dedicated object decoding, strict budgets,
malformed/oversized input, sampled indices, downsampling, sparse IDs, gaps/overlaps,
no-sample/missing/stale geometry, run/segment budgets, bounded byte output, matrix/empty observations,
HTTP 404/501 versus malformed/500/timeout/unreachable failures and no raw sensitive diagnostics; the
read router refuses any POST. `tests/test_acceptance_parity.py` runs a positive snapshot through the
stdio and protected loopback HTTP consoles; profile and tool-contract tests include the READ operation.
No ordinary test contacts a LAN device.

Focused local evidence (Python 3.13/macOS): the seven related test modules, 481 passed in 33.64 s; mypy
52 source files and Ruff check/format passed; private-identifier, agent setup, lock/export and coverage
checks passed. Full suite, distribution and container checks remain CI evidence.

## Hardware

Selected-controller read-only authorization is ISSUE-150-DEC-001. An initial bounded GET observation
found WLED 16.0.1 build 2606300, 133 LEDs; info/state worked but `/json/live` returned HTTP 501. This is
unavailable-endpoint evidence, not evidence of positive color accuracy or animation.

The coordinator ran candidate `c3e33412cf04472c28028f3a0a6cefabaf6b7d5e` on 2026-11-10 through an MCP
stdio client with the `read-only` profile: exactly one `wled_get_live_snapshot` call against the
selected controller (about 136 ms).

| Field | Observed result |
| --- | --- |
| MCP `is_error` / envelope `ok` | false / true |
| `application` / `verification` | `not_attempted` / `not_requested` |
| Snapshot status / HTTP status | `unavailable` / 501 |
| Source / segments | `/json/live` / empty array |
| Reported cause | Missing, disabled or unsupported endpoint; exact cause unknown |

The negative probe shows the tool reports this controller's unavailable endpoint honestly; it does not
validate positive live colors on hardware (positive mapping stays synthetic/loopback evidence). No
writes, configuration/firmware changes, deployment or discovery. The final documentation-only commit
leaves the probed code and tests unchanged. Captures and the real inventory stay in ignored runtime
storage.
