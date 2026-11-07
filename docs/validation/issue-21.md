# Issue #21 validation: version source, non-release builds and CI matrix

Evidence for the build-identity part of
[#21](https://github.com/descipar/wled-mcp/issues/21) together with
[#70](https://github.com/descipar/wled-mcp/issues/70) (acceptance scenarios A21-01,
A21-02, A21-03 and A21-07 of the issue-21 requirements packet; decision
[ISSUE-21-DEC-002](../decisions/issue-21.md)). Contract:
[versioning](../contract/versioning.md). The compatibility policy, firmware tiers,
upgrade/rollback compatibility tests and the support matrix document (A21-04 to A21-06,
A21-08) follow in the second #21 change and are not covered here.

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
