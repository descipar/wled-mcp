# Issue #149 validation — effect and palette names

NAME-01 implements device-specific catalog names in segment patch and complete layout replacement
requests. Evidence uses mocks and a synthetic loopback controller only; no LAN access, physical writes
or deployment.

- `tests/test_segment_names.py`: exact/case-folded resolution, identical dry-run/actual numeric plans,
  the device lock during catalog reads, bounded suggestions and ambiguity, placeholder exclusion,
  ID/name conflicts, blank names, resolved-ID readback mismatches. A bad later segment prevents every
  POST, including removal of stale layout IDs. Each catalog is loaded once per invocation.
- `tests/test_acceptance_parity.py`: a named segment preview and an unknown-name layout request through
  the stdio and protected Streamable HTTP consoles agree; neither writes.
- Existing patch, layout, catalog and access-profile tests protect omission, preservation, cache
  identity, restrictions and uncertain-write semantics; names use the same verified-write engines.

Validation (2026-11-09): `tests/test_segment_names.py`, `test_patches.py`, `test_layouts.py`,
`test_acceptance_parity.py`, `test_state_catalogs.py`: 358 passed; `tests/test_access_profiles.py`: 93
passed; Ruff, mypy and the private-identifier check passed. Full-suite and container checks run in PR CI.
Hardware validation is not part of this issue; no physical behavior claim follows.
