# Issue #149 validation — effect and palette names

NAME-01 implements device-specific catalog names in segment patch and complete
layout replacement requests. Automated evidence uses mocks and a synthetic
loopback controller only; no LAN access, physical writes or deployment occurred.

- `tests/test_segment_names.py` covers exact/case-folded resolution, identical
  dry-run/actual numeric plans, the device lock during catalog reads, bounded
  suggestions and ambiguity, placeholder exclusion, ID/name conflicts, blank
  names, and resolved-ID readback mismatches. A bad later segment prevents every
  POST, including removal of stale layout IDs. Each needed catalog is loaded
  once per invocation; numeric-only behavior retains the existing tests.
- `tests/test_acceptance_parity.py` adds a named segment preview and an unknown-name
  layout request through the actual stdio and protected Streamable HTTP consoles.
  Results, resolved IDs and diagnostic candidates agree; neither case writes.
- Existing patch, layout, catalog and access-profile tests protect omission,
  preservation, layout removal, cache identity, restrictions and uncertain-write
  semantics. Names use the same existing verified-write engines.

Validation run (2026-11-09):

```text
uv run --frozen pytest -q tests/test_segment_names.py tests/test_patches.py tests/test_layouts.py tests/test_acceptance_parity.py tests/test_state_catalogs.py --basetemp=.artifacts/pytest-149-all
358 passed
uv run --frozen pytest -q tests/test_access_profiles.py --basetemp=.artifacts/pytest-149-access
93 passed
```

Ruff, mypy and the private-identifier check passed. Required full-suite and
container checks run in PR CI. Hardware validation is not part of this issue's
specified mocked evidence; no physical behavior claim follows from these checks.
