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

Read-only test-controller probe: **pending**. No selected-device runtime access was
supplied for this run. Software support in W-CAT-02 does not establish hardware
acceptance or complete the M1 exit criterion; no live result is claimed.
