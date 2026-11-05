# Issue #55 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-55-DEC-001 — Deterministic deadline/retry test with controlled time

- ID: ISSUE-55-DEC-001
- Recorded date: 2026-11-05
- Status: active for issue #55 only.
- Authority: technical decision by the coordinator within the human's instruction to
  implement #55 following the workflow (2026-11-05, no permalink). The earlier human
  delegation for #52/#53 is not reused or generalized; no product behavior changes.
- Source: requirements packet `.agent-runs/issue-55/packet.md` with Windows 11 / CPython
  3.13.2 diagnostics: every failure was `len(calls) == 1`; `anyio.sleep(0.04)` took up to
  54.8 ms, exhausting the 50 ms deadline before the retry (Windows timer step about
  15.6 ms). The client behaved correctly (REL-01, ISSUE-4-DEC-003).
- Scope: `tests/test_inventory_client.py` deadline/retry tests only.
- Decision: replace the wall-clock sleep with controlled time (advance
  `anyio.current_time` inside the mocked handler) and assert per-attempt budgets from
  `request.extensions["timeout"]["read"]` against a 5 s deadline: (a) first attempt uses
  4.9 s -> exactly one retry with the remaining 0.1 s; (b) each attempt uses 1 s -> still
  two calls; (c) first attempt uses 5.1 s -> no retry. Keep one real-hang test proving the
  shared remainder cancels the retry well before a fresh per-attempt deadline. No
  docs/VALIDATION.md change, to avoid overlap with the parallel #10 work; evidence goes in
  the PR.
- Applicability / conditions: test-only; a minimum read budget or Windows deadline
  overshoot are separate product questions, not decided here.
- Rationale: deterministic on coarse timers while still failing if the deadline is
  per-attempt or more than one read retry is allowed.
- Affected: REL-01 evidence, tests/test_inventory_client.py.
- Supersedes: none.
- Propagated to: packet, implementer and reviewer handoffs.
