# Issue #21 validation: build identity, compatibility policy and CI matrix

Evidence for the build-identity part of [#21](https://github.com/descipar/wled-mcp/issues/21)
together with [#70](https://github.com/descipar/wled-mcp/issues/70) (scenarios A21-01, A21-02,
A21-03, A21-07, first change) and the compatibility policy (A21-04, A21-05, A21-06, A21-08, second
change); decision [ISSUE-21-DEC-002](../decisions/issue-21.md). Contracts:
[versioning](../contract/versioning.md), [compatibility](../contract/compatibility.md).

All evidence is automated, synthetic and loopback only. No live deployment, update or rollback was
run (ISSUE-21-DEC-001: that is #25 evidence).

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| A21-01 single source | `tests/test_version_source.py` (runtime `__version__` equals metadata and `pyproject.toml`, `--version`, release directory and image tag, literal-version guard over tracked files with negative controls); `tests/test_bootstrap.py` and `tests/test_state_catalogs.py` compare served versions; `scripts/check_distribution.py` derives wheel, metadata, console/uvx versions from `pyproject.toml`; the CI `container` job checks the image against `RELEASE` |
| A21-02 non-release build | `tests/test_version_source.py`: temporary Git repo staged with `--non-release`, version `<base>+g<12hex>` everywhere (wheel, metadata, directory, `RELEASE`, `SHA256SUMS`); tracked files unchanged; repeated staging refused; `--dirty` only on request; label/build-kind mismatch refused; one real offline `git archive` build; release staging tests in `tests/test_deployment_artifacts.py` unchanged |
| A21-03 procedures | docs/DEPLOYMENT.md "Non-release builds" and the update/rollback steps use the directory name and `image_tag`; rollback does not restore device state; the stdio hub example and documented uvx command use the `REPLACE_WITH_VERSION` placeholder (deployment-artifact and README tests), substituted by `check_distribution.py` |
| A21-07 CI matrix | `.github/workflows/ci.yml`: `checks` on `ubuntu-latest` and `ubuntu-24.04-arm` (Python 3.13); `container` on both, staging a non-release build and running `scripts/check_container.py`; run results below |
| A21-04 firmware tiers | `tests/test_compat.py`: `16.0.1` tested; `16.0.0`, `16.2.3`, `17.0.0`, `16.0.1-b1` unknown; `0.15.x`, `0.14.0`, `15.99.99`, `16.0.0-b1` unsupported; malformed versions unrecognized; `wled_get_state` carries `diagnostics.firmware_support` and one leading warning for the last two tiers only, never echoing the device-supplied version; identical envelopes over stdio and HTTP; writes behave identically on `0.15.1`, unrecognized and `16.0.1`; `tests/test_state_catalogs.py` and `examples/contracts/state.json` carry the field |
| A21-05 contract snapshot | `tests/test_upgrade_compat.py`: served contract passes `contract_problems(names, "full")` with no unannounced breaking difference to each retained `tools.json`; mutated copies (removed tool, renamed field, newly required input, tightened bound, changed annotation, removed output field/error code) fail without and pass with a migration note naming tool and pointer; additive changes pass. Limit: tools share an envelope schema with free-form `data`, so a removed field inside `data` is not detected (partly covered by the A21-06 envelope-superset test; otherwise review and migration notes) |
| A21-06 schema compatibility | `tests/test_upgrade_compat.py`: retained configuration and snapshots load unchanged (byte- and mtime-identical, also after a new snapshot); newer `schema_version`/`format_version` rejected naming the version, files unchanged; unreadable newer snapshot counted invalid and survives pruning; `wled_get_state` keeps every retained value and only adds fields; version naming in `tests/test_inventory_client.py` and `tests/test_backups.py` |
| A21-08 policy documents | `docs/contract/versioning.md` and `docs/contract/compatibility.md` linked from docs/TOOL-CONTRACT.md; README "Compatibility" table equals the matrix (`tests/test_readme.py`, drift controls); `check_coverage.py` passes |

## Retained 0.1.0 fixtures

`tests/fixtures/compat/0.1.0/` was generated with its `generate.py` from a `git archive` of the 0.1.0
source commit in an offline `uv sync --frozen --no-dev` environment; a second generation reproduced
`tools.json`, `config.toml` and `get_state.json` byte for byte and the snapshot apart from its random
ID suffix. `examples/contracts/state.json` uses the synthetic `0.0.0+example` server version so the
example never has to follow a real version.

## Runs

GitHub Actions, 2026-11-07, all four jobs passed in each run:

| Run | Event / commit | Result |
| --- | --- | --- |
| 42420263039 | push, branch `stage2/issue-21-build-identity` (container condition lifted for that commit) | pytest 1232 passed, 1 skipped on amd64 and native arm64; `check_distribution.py` PASS (29 exact runtime versions); container staged a non-release build, image build, `--version`, loopback HTTP `tools/list` (12 tools), `wled_list_devices`, SIGTERM exit 0 on both architectures |
| 42420706568 | PR #103 (merge commit staged, recorded as `source_commit`) | same results, 1232 passed |
| 42425044074 | PR #105 (compatibility policy) | same, pytest 1322 passed, 1 skipped |

The native `ubuntu-24.04-arm` runner was available; the TD-21-8 fallback was not needed and no
emulation was used.

Local (Windows, Python 3.13, experimental platform): `pytest` 1207 passed, 20 skipped, with the 6
failures and 5 errors in `tests/test_inventory_client.py` and `tests/test_hw_http_probe.py` that also
occur on `main`; ruff, format, mypy, traceability, private identifiers, lock, agent setup, coverage
and agent sync passed.

## Limits

- Required-check enforcement follows the DEC-018 ruleset, which needs the visibility change (owner
  action, #90); until then review treats the jobs as required. The arm64 and container jobs belong
  in the ruleset.
- The `container` job runs for pull requests and pushes to `main` only.
- The container smoke uses an empty synthetic inventory: it proves build, startup, authentication,
  tool list and graceful stop per architecture, not device behavior or hardware performance.
- Windows and macOS are experimental and have no CI job (docs/DEVELOPMENT.md "Platform notes").
