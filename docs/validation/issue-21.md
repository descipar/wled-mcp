# Issue #21 validation: build identity, compatibility policy and CI matrix

Evidence for the build-identity part of
[#21](https://github.com/descipar/wled-mcp/issues/21) together with
[#70](https://github.com/descipar/wled-mcp/issues/70) (acceptance scenarios A21-01,
A21-02, A21-03 and A21-07 of the issue-21 requirements packet, first change) and for
the compatibility policy (A21-04, A21-05, A21-06 and A21-08, second change); decision
[ISSUE-21-DEC-002](../decisions/issue-21.md). Contracts:
[versioning](../contract/versioning.md) and
[compatibility](../contract/compatibility.md).

All evidence is automated, uses synthetic inputs and loopback only, and contacts no LAN
device. No live deployment, update or rollback was run (ISSUE-21-DEC-001: that is #25
evidence).

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| A21-01 single source | `tests/test_version_source.py`: runtime `__version__` equals the installed metadata and `pyproject.toml`; `--version` output; release directory and image tag of the current version; literal-version guard over all tracked files with its allowlist and planted negative controls. `tests/test_bootstrap.py` (stdio `serverInfo.version`) and `tests/test_state_catalogs.py` (`diagnostics.server_version`) compare with `pyproject.toml`. `scripts/check_distribution.py` derives the wheel name, dist-info path, metadata `Version:`, console and uvx `--version` and `serverInfo.version` from `pyproject.toml`. The CI `container` job checks the image's `--version` and `serverInfo.version` against `RELEASE`. |
| A21-02 non-release build | `tests/test_version_source.py`: temporary Git repository staged with `--non-release`, version `<base>+g<12hex>` in wheel name, wheel metadata, directory, `RELEASE` (`build_kind`, `label`, `source_commit`, `source_tree`, `image_tag`) and `SHA256SUMS`; tracked files unchanged; repeated staging refused before a second build; `--dirty` includes tracked changes only on request and marks `.dirty`/`modified`; label/build-kind mismatches refused; PEP 440 and OCI tag form; the image checksum step accepts one non-release wheel and rejects a second wheel (POSIX); one real offline `git archive` build of the checked-out commit. Release staging tests in `tests/test_deployment_artifacts.py` are unchanged. |
| A21-03 procedures | docs/DEPLOYMENT.md "Non-release builds" and the HTTP and stdio update/rollback steps use the directory name and `image_tag`; rollback states that it does not restore device state. The stdio hub example and the documented uvx command use the `REPLACE_WITH_VERSION` placeholder (`test_stdio_hub_example_runs_the_staged_release_with_constraints`, `test_documented_uvx_invocation_matches_the_stdio_hub_example`, README check); `check_distribution.py` substitutes it with the built version before running the example. |
| A21-07 CI matrix | `.github/workflows/ci.yml`: `checks` on `ubuntu-latest` and `ubuntu-24.04-arm` (Python 3.13); `container` on both, staging a non-release build and running `scripts/check_container.py`. Run results below. |
| A21-04 firmware tiers | `tests/test_compat.py`: `16.0.1` tested; `16.0.0`, `16.2.3`, `17.0.0`, `16.0.1-b1` unknown; `0.15.1`, `0.15.5`, `0.14.0`, `15.99.99`, `16.0.0-b1` unsupported; `v16.0.1`, `16.0`, `custom-build`, leading space and non-strings unrecognized; `wled_get_state` returns `ok=true`, `diagnostics.firmware_support` and exactly one leading warning for the last two tiers only, never echoing the device-supplied version; catalogs and the device list carry no tier; identical `wled_get_state` envelopes over a real stdio subprocess and the HTTP service for `16.0.1`, `0.15.1` and an unrecognized version; `wled_set_state`, `wled_patch_segments` and `wled_replace_layout` (dry run and live) produce identical outcomes and device POSTs on `0.15.1`, an unrecognized version and `16.0.1`. `tests/test_state_catalogs.py` checks the field on the default fixture and in `examples/contracts/state.json`. Default fixtures moved to 16.0.1; explicit 0.15.x cases remain (`tests/test_compat.py`, `tests/test_backups.py`, the S66 preset tests). |
| A21-05 contract snapshot | `tests/test_upgrade_compat.py`: the served unfiltered contract passes `contract_problems(names, "full")` and has no unannounced breaking difference to each retained `tools.json` (currently identical). Controls on mutated copies: a removed tool, renamed input field, newly required input, tightened input bound, changed annotation, removed output field and removed error code each fail without and pass with a migration note naming tool and pointer, and a note for another tool does not help; an optional input, output field, looser input, new output enum value, new tool and renamed `$defs` model pass without a note. The module contains no tool list or count. Limit: all tools share the envelope output schema with a free-form `data` object, so a removed or renamed field inside `data` is not detected; `wled_get_state` is partly covered by the envelope-superset test (A21-06), all other `data` fields rely on review and migration notes. |
| A21-06 schema compatibility | `tests/test_upgrade_compat.py`: each retained configuration loads and each retained snapshot loads and lists, with all files byte- and mtime-identical, also after the current server writes a new snapshot; a newer configuration `schema_version` and snapshot `format_version` are rejected naming the version, files unchanged; an unreadable newer snapshot is counted invalid and survives pruning; the current `wled_get_state` envelope keeps every retained value and only adds fields. Version naming: `tests/test_inventory_client.py` (integer versions named, other types keep the generic message) and `tests/test_backups.py` (plausible integers named, others generic, file unchanged). |
| A21-08 policy documents | `docs/contract/versioning.md` (contract and schema evolution, deprecation, upgrade/downgrade, machine-readable migration notes) and `docs/contract/compatibility.md` (matrix, CI, firmware tiers), linked in sorted position from docs/TOOL-CONTRACT.md; README "Compatibility" table equals the matrix (`tests/test_readme.py`, with drift controls) and keeps the DEC-013 phrases; docs/WLED-COVERAGE.md unchanged, `check_coverage.py` passes. |

## Retained 0.1.0 fixtures

`tests/fixtures/compat/0.1.0/` was generated with its `generate.py` from a `git archive`
of the 0.1.0 source commit `0da12492ba11c2b86fa44c7285031238aa1d499e` in an offline
`uv sync --frozen --no-dev` environment of that tree (package version checked as
0.1.0). A second generation reproduced `tools.json`, `config.toml` and
`get_state.json` byte for byte and the snapshot apart from its random ID suffix.
The current served contract was identical to the retained `tools.json` when the fixture
was added.

The example `examples/contracts/state.json` shows `diagnostics.server_version` as the
synthetic `0.0.0+example`: of the two options for that file (derive the value or keep a
placeholder), the placeholder was chosen in the first change so that the example never
equals, and never has to follow, a real version.

## Runs

GitHub Actions run 42420263039 on branch `stage2/issue-21-build-identity`, commit
`45e1c4f3348469ac49c0d6d5ca89ab9e17b6eea6` (push event; the `container` condition was
lifted for that one commit so that the branch push exercised it), 2026-11-07, all four
jobs passed:

| Job | Runner | Result |
| --- | --- | --- |
| `checks (ubuntu-latest, 3.13)` | amd64 | ruff, format, mypy, agent setup, lock, private identifiers; pytest 1232 passed, 1 skipped; `check_distribution.py` PASS (29 exact runtime versions) |
| `checks (ubuntu-24.04-arm, 3.13)` | arm64, native | same checks; pytest 1232 passed, 1 skipped; `check_distribution.py` PASS |
| `container (ubuntu-latest)` | amd64 | staged `0.1.0+g45e1c4f33484` (`build_kind=non-release`, `image_tag=wled-mcp:0.1.0-g45e1c4f33484`); image build, `--version`, loopback HTTP `tools/list` (12 tools), `wled_list_devices`, SIGTERM exit 0: PASS (image architecture amd64) |
| `container (ubuntu-24.04-arm)` | arm64, native | same staging and smoke: PASS (image architecture arm64, host aarch64) |

The native `ubuntu-24.04-arm` runner was available in this private repository; the
TD-21-8 fallback (`continue-on-error`) was not needed and no emulation was used.

GitHub Actions run 42420706568 for pull request #103 (head
`b42777b5d1fdc6dd6bb60dd2480ad9697e7b953d`, `pull_request` event), 2026-11-07, all four
jobs passed. For a pull request the workflow checks out GitHub's merge commit of the
branch into `main` (`refs/pull/103/merge`, here
`ef5f4ed54723a85f5578e42126782563c599e8fa`), so the `container` job staged that merge
commit and its `RELEASE` records it as `source_commit`, not the branch head:

| Job | Runner | Result |
| --- | --- | --- |
| `checks (ubuntu-latest, 3.13)` | amd64 | all checks passed; pytest 1232 passed, 1 skipped; `check_distribution.py` PASS (29 exact runtime versions) |
| `checks (ubuntu-24.04-arm, 3.13)` | arm64, native | same; pytest 1232 passed, 1 skipped; `check_distribution.py` PASS |
| `container (ubuntu-latest)` | amd64 | staged `0.1.0+gef5f4ed54723` (`source_commit=ef5f4ed5...`, `image_tag=wled-mcp:0.1.0-gef5f4ed54723`); build, `--version`, loopback HTTP `tools/list` (12 tools), `wled_list_devices`, SIGTERM exit 0: PASS (amd64, host x86_64) |
| `container (ubuntu-24.04-arm)` | arm64, native | same staging and smoke: PASS (arm64, host aarch64) |

GitHub Actions run 42425044074 for pull request #105 (the compatibility-policy change,
head `4889f3b39d82b65a955bb311046fc2f8e2762f93`, `pull_request` event), 2026-11-07, all
four jobs passed; the `container` jobs staged the merge commit
`8d5db4e31c6dd40ef1102c165ac24a77a846e9e4`:

| Job | Runner | Result |
| --- | --- | --- |
| `checks (ubuntu-latest, 3.13)` | amd64 | all checks passed; pytest 1322 passed, 1 skipped; `check_distribution.py` PASS (29 exact runtime versions) |
| `checks (ubuntu-24.04-arm, 3.13)` | arm64, native | same; pytest 1322 passed, 1 skipped; `check_distribution.py` PASS |
| `container (ubuntu-latest)` | amd64 | staged `0.1.0+g8d5db4e31c6d`; build, `--version`, loopback HTTP `tools/list` (12 tools), `wled_list_devices`, SIGTERM exit 0: PASS (amd64, host x86_64) |
| `container (ubuntu-24.04-arm)` | arm64, native | same staging and smoke: PASS (arm64, host aarch64) |

Local run (Windows, Python 3.13, experimental platform): `uv run --frozen pytest` 1207
passed, 20 skipped, with the 6 failures and 5 errors in `tests/test_inventory_client.py`
and `tests/test_hw_http_probe.py` that also occur on `main`; ruff, ruff format, mypy,
`check_traceability.py`, `check_private_identifiers.py`, `check_lock.py`,
`check_agent_setup.py`, `check_coverage.py` and `sync_agents.py --check` passed.

## Limits

- Required-check enforcement follows the DEC-018 ruleset, which needs the visibility
  change (owner action, #90); until then no check is technically required and review
  treats the jobs as required. When the ruleset is created, the arm64 and container
  jobs belong in it.
- The `container` job runs for pull requests and pushes to `main` only; branch pushes
  run `checks` on both architectures. The commit that restored this condition changed
  only the condition and this record, so its container jobs first run on the pull
  request.
- The container smoke uses an empty synthetic inventory: it proves image build,
  startup, authentication, the served tool list and graceful stop on each
  architecture, not device behavior or hardware performance.
- Windows and macOS are experimental and have no CI job (docs/DEVELOPMENT.md
  "Platform notes").
