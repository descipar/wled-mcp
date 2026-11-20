# Issue #148 — parsed effect metadata evidence

Requirements: W-CAT-02, CAT-01; M1. All checks use mocks or loopback, without LAN access or device
writes.

Six compact fixtures in `tests/fixtures/fxdata/wled-16.0.1.json` record their WLED 16.0.1 source commit
and declaration lines; they are interoperability examples, not controller captures.
`tests/test_effect_metadata.py` covers labels, sparse colors, options, boolean defaults, fixed palettes,
0D/1D/2D and audio flags, malformed/unknown metadata, conservative filtering, case folding, sparse IDs
and placeholder exclusion, plus a loopback HTTP client check of served filters, unchanged palette inputs
and zero POSTs. `test_state_catalogs.py` retains stdio, cache, identity, timeout and optional-fxdata
failure evidence.

Validation (Python 3.13/macOS): five related test modules, 189 passed; mypy passed (51 source files);
ruff and private-identifier checks passed; `scripts/check_coverage.py --update`: 89 features, 59 % of
planned scope, 47 % overall, W-CAT-02 supported. Full suite, distribution and container checks remain CI
evidence.

Read-only test-controller probe (2026-11-09): **done**. The owner named the single test controller and
authorized read-only testing for this run only. Code: `main` at `ebe4711`, run locally over stdio with
`scripts/hw_read_only_probe.py` plus one `wled_search_effects` call; no hub, deployment or write. WLED
16.0.1 (build 2606300).

| Check | Result |
| --- | --- |
| `wled_list_devices(probe=true)` | `reachable` |
| `wled_get_state`, `wled_get_palettes` | succeeded |
| `wled_get_effects` | 216 effects; metadata `available`; 214 carry fxdata (all but IDs 0 and 62); IDs 122 and 179 gave a "partially parsed" warning and were still returned with raw fxdata |
| `wled_search_effects` (calm, no flashing, palette-using, limit 5) | succeeded; exact device IDs and names with per-property confidence and basis |

Limits: one controller, one firmware, read-only; no comparison against the device UI beyond catalog
size. The two partial-parse effects are accepted lenient-parser behavior; dedicated handling is left to a
later fixture update. This is the live fxdata check of the M1 exit criterion; the #147 criterion is met
separately by a local stdio client check ([ISSUE-147-DEC-001](../decisions/issue-147.md)); MCPHub
forwarding was not observed.
