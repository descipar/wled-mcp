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

Focused local evidence on Python 3.13/macOS:

- `uv run --frozen pytest -q tests/test_live_snapshot.py tests/test_acceptance_parity.py tests/test_inventory_client.py tests/test_state_catalogs.py tests/test_access_profiles.py tests/test_tool_contract.py tests/test_coverage.py --basetemp=.artifacts/pytest-150-final`: 481 passed in 33.64s.
- mypy: 52 source files passed; CI-equivalent Ruff check/format: passed.
- Private-identifier, agent setup, lock/export and coverage checks passed.
- Full suite, distribution and container checks remain required CI evidence.

## Hardware

Selected-controller read-only authorization is ISSUE-150-DEC-001. An initial
bounded GET observation found WLED 16.0.1 build 2606300, 133 LEDs; info/state reads
worked but `/json/live` returned HTTP 501. This is unavailable-endpoint evidence,
not evidence of positive physical color accuracy or animation. No writes,
firmware/configuration changes, deployment or discovery are part of this check.

The coordinator ran the committed software candidate
`c3e33412cf04472c28028f3a0a6cefabaf6b7d5e` on 2026-11-10 through an actual MCP
stdio client with the `read-only` profile. Exactly one
`wled_get_live_snapshot` call was made against the selected controller. Read start
was 20:48:03.678543 UTC and capture completion was 20:48:03.814119 UTC.

| Field | Observed result |
| --- | --- |
| MCP `is_error` / envelope `ok` | false / true |
| `application` / `verification` | `not_attempted` / `not_requested` |
| Snapshot status / HTTP status | `unavailable` / 501 |
| Source / segments | `/json/live` / empty array |
| Reported cause | Missing, disabled or unsupported endpoint; exact cause unknown |

The negative probe confirms that the new tool exposes this controller's actual
unavailable endpoint honestly; it does not validate positive live colors on
hardware. Positive mapping remains synthetic/loopback evidence. No physical
writes, configuration/firmware changes, deployment or device discovery occurred.
The final documentation-only evidence commit leaves the probed production code
and tests unchanged. Captures and the real inventory stay in ignored runtime
storage; no private controller identifier is published.
