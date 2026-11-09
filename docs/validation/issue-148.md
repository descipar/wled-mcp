# Issue #148 — parsed effect metadata evidence

Requirements: W-CAT-02, CAT-01; M1. All checks use mocks or loopback, without LAN
access or device writes.

Six compact fixtures in `tests/fixtures/fxdata/wled-16.0.1.json` record their exact
WLED 16.0.1 source commit and declaration lines. They are interoperability metadata
examples, not captures from a controller or copied firmware implementation.
`tests/test_effect_metadata.py` covers empty/default/custom labels, sparse colors,
options and boolean defaults, fixed palettes, 0D/1D/2D and both audio flags,
malformed/unknown metadata, conservative filtering, case folding, sparse IDs and
placeholder exclusion. Its actual loopback HTTP client checks served filters,
unchanged palette inputs and zero POSTs. Existing `test_state_catalogs.py` retains
stdio, cache, identity, timeout and optional-fxdata failure evidence.

Validation on Python 3.13/macOS:

- `uv run --frozen pytest -q tests/test_effect_metadata.py tests/test_state_catalogs.py tests/test_agent_guidance.py tests/test_effect_search.py tests/test_upgrade_compat.py --basetemp=.artifacts/pytest-148-final`: 189 passed.
- `uv run --frozen mypy`: passed (51 source files).
- Repository CI-equivalent ruff check/format and private-identifier checks: passed.
- `uv run --frozen python scripts/check_coverage.py --update`: 89 features, 59 % of
  planned scope, 47 % overall; W-CAT-02 is supported.

The complete suite, distribution and container checks remain for required CI.

Read-only test-controller probe (2026-11-09): **done**. The owner named the same single
test controller as earlier live checks and authorized read-only testing for this run only; it is
not standing permission. The code was `main` at `ebe4711` (after #148 and #149), run locally over
stdio from a checkout with `scripts/hw_read_only_probe.py` plus one extra `wled_search_effects`
call; no hub, deployment or write was involved, and the address stays in an ignored local
configuration. The device ran WLED 16.0.1 (build 2606300).

| Check | Result |
| --- | --- |
| `wled_list_devices(probe=true)` | `reachable` |
| `wled_get_state`, `wled_get_palettes` | succeeded, no errors |
| `wled_get_effects` | 216 effects; effect metadata status `available`; 214 effects carry fxdata (all but IDs 0 and 62); two of these (IDs 122 and 179) produced a "partially parsed" warning and were still returned with their raw fxdata, so the lenient parser did not drop them |
| `wled_search_effects` (calm, no flashing, palette-using, limit 5) | succeeded; results carry exact device IDs and names with per-property confidence and basis (first result: Breathe) |

Limits: one controller, one firmware, read-only; no write, no preset or segment change, and no
comparison against the device UI beyond the catalog size. The two partial-parse effects are
accepted behavior of the lenient parser; whether their fxdata forms need dedicated handling is
left to a later fixture update, not a blocker. This is the live fxdata check of the M1 exit
criterion; the #147 criterion is met separately by a local stdio client check
([ISSUE-147-DEC-001](../decisions/issue-147.md)); MCPHub forwarding was not observed.
