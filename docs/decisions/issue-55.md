# Issue #55 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-55-DEC-001 — Deterministic deadline/retry test with controlled time

- ID: ISSUE-55-DEC-001
- Status: active for issue #55 only.
- Authority: technical decision by the coordinator within the owner's instruction to implement #55
  (2026-11-05, no permalink); the #52/#53 delegation is not reused. No product behavior changes.
- Source: #55 packet with Windows 11 / CPython 3.13.2 diagnostics: `anyio.sleep(0.04)` took up to
  54.8 ms (timer step about 15.6 ms), exhausting the 50 ms deadline before the retry; the client
  behaved correctly (REL-01, ISSUE-4-DEC-003).
- Scope: `tests/test_inventory_client.py` deadline/retry tests only.
- Decision: replace the wall-clock sleep with controlled time (advance `anyio.current_time` in the
  mocked handler) and assert per-attempt budgets from `request.extensions["timeout"]["read"]` against
  a 5 s deadline: first attempt 4.9 s gives one retry with the remaining 0.1 s; 1 s per attempt still
  gives two calls; 5.1 s gives no retry. Keep one real-hang test proving the shared remainder cancels
  the retry. No VALIDATION.md change (parallel #10 work); evidence goes in the PR.
- Conditions: test-only; a minimum read budget or Windows deadline overshoot are separate questions.
- Affected: REL-01 evidence. Supersedes: none.
