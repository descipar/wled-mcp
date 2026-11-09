# Issue #22 validation: PyPI publish workflow

Evidence for the PyPI part of [#22](https://github.com/descipar/wled-mcp/issues/22)
(acceptance scenarios AC-22P-01 to AC-22P-12 of the issue-22 requirements packet);
decisions [ISSUE-22-DEC-001 and ISSUE-22-DEC-002](../decisions/issue-22.md). Procedure and
setup: [PUBLISHING.md](../PUBLISHING.md).

Nothing was published or registered. The workflow was not run on GitHub: no tag, release,
dispatch, environment, setting or ruleset was created or changed, and no upload to PyPI or
TestPyPI was attempted. All evidence below is local, uses synthetic inputs and loopback
only, and contacts no LAN device. The release-event and dispatch paths, the environment
review and the OIDC upload are therefore not demonstrated; they first run at an
owner-instructed release.

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| AC-22P-01 triggers | `tests/test_publish_workflow.py`: `publish_workflow_problems` is empty for the real file; mutations adding `push` or `pull_request_target` or changing the release type are each reported. |
| AC-22P-02 permissions | Same function: top level `{}`, build `{contents: read}`, publish `{id-token: write}`, no `id-token` elsewhere, no `write-all`/`read-all`; mutations (top-level `write-all`, `id-token` on build, `contents: write`, extra publish permission) are reported. |
| AC-22P-03 publish job | Environment `pypi` and `needs: build` required; mutations removing or renaming the environment, removing `needs`, adding a checkout or a build command to the publish job are reported. |
| AC-22P-04 no secrets | No `secrets.` reference, no `password`/`user`/`repository-url` input, no `skip-existing: true`, checkout `persist-credentials: false`; each mutation reported. |
| AC-22P-05 pins | Raw-line check `owner/repo@<40 hex> # vX.Y.Z`; a tag pin, a SHA without comment and a short SHA are reported. The SHAs were resolved with read-only `gh api` calls (annotated tag dereferenced) and each action's `action.yml` at that version was read to confirm the inputs used (see below). |
| AC-22P-06 guard | `tests/test_check_distribution.py`: `release_ref_problems` passes `tag`/`v1.2.3`/`1.2.3` and `v1.2.3rc1`; refuses another tag, a tag without `v`, dispatch on a branch, a branch named like the tag, an unset ref, a local-label version and a development release. `tag_commit_problems` on temporary Git repositories: annotated tag on `main` passes; a tag on a side commit, a checkout other than the tag or workflow commit and a missing `origin/main` are refused. `check_release_ref` reads the runner variables. `release_directory_problems`: exact pair passes; missing sdist or wheel, a checksum file, a hidden file and another version fail. `check_sdist`: wrong `PKG-INFO` version, a `.git` entry, `devices.toml` and another file name fail. Workflow tests: guard before the build, before the project install and before the upload (moved-step mutations reported). Local run: `--release-ref` with a branch ref and with a tag not on `main` exits 1 with the reasons; the guard runs in an environment synced with `--no-install-project` (project not importable), so no build backend runs before it. |
| AC-22P-07 single build | Workflow tests: exactly one `uv build --no-build-isolation` (a second build is reported), `uv sync --locked` before it, `uvx --from twine==<exact>` with version >= 6.1.0 and `--strict` (6.0.1 and a non-strict check reported). Local build below; sdist without `.git`, `.agent-runs/`, `.artifacts/`, `.env*`, `devices.toml`. |
| AC-22P-08 smoke | Local run of `check_distribution.py --wheel ... --sdist ...` on the files built below: PASS without rebuilding (unit test: with `--wheel` the first action is the wheel inspection, no command; without options the first command is still `uv build --wheel`). Checksums before and after the smoke run identical. Job summary and the publish-job re-check are in the workflow; the shell steps are executed by `test_publish_job_accepts_only_the_tested_files` (modified, extra or missing file refused) and `test_build_job_refuses_a_third_file_in_dist`. |
| AC-22P-09 artifact handoff | Same upload and download name, `if-no-files-found: error`, download path equals `packages-dir`; mismatched names and a missing `if-no-files-found` reported; the checksum list stays in `RUNNER_TEMP`, and an extra `SHA256SUMS` in the download directory fails the publish-job check (shell test). |
| AC-22P-10 hygiene | `enable-cache: false`, uv version equal to `ci.yml` (0.11.14), `UV_PYTHON_DOWNLOADS: never`, concurrency per ref without cancel, `timeout-minutes` on both jobs; each mutation reported. |
| AC-22P-11 documentation | [PUBLISHING.md](../PUBLISHING.md): pending publisher fields, environment with required reviewers and recommended `v*` tag policy, TestPyPI not wired, trigger reasons, first-release procedure and the pre-merge tag limit, rejection as stop point, pinning/update/rollback, yank/delete/file-name reuse, uncertain and partial uploads, attestations not claimed as S2-DIST-03, open items. Version-literal, private-identifier and README tests pass. |
| AC-22P-12 evidence | This file; link lines in [VALIDATION.md](../VALIDATION.md), [DEPLOYMENT.md](../DEPLOYMENT.md) and [STAGE-5.md](../STAGE-5.md). |

## Action pins

Resolved on 2026-11-09 with `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (each the
latest release of its repository at that time); the annotated tag of
`pypa/gh-action-pypi-publish` was dereferenced with `gh api .../git/tags/<sha>`.

| Action | Version | Commit | Inputs used (present in that `action.yml`) |
| --- | --- | --- | --- |
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `fetch-depth`, `persist-credentials` |
| actions/setup-python | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` | `python-version` |
| astral-sh/setup-uv | v10.3.3 | `68559e99cc807c1eb7e9238fd43a15bba460eec2` | `version`, `enable-cache` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | `name`, `path`, `if-no-files-found` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` | `name`, `path` (`digest-mismatch` defaults to `error`) |
| pypa/gh-action-pypi-publish | v1.14.3 | `7245906fb61fa33a13554f9d5fb856fe61758086` (tag object `aef6c9b6e301dc803e1bc9133e9ce67ae9b0906b`) | `packages-dir` (attestations default on) |

## Local runs

Candidate tree of branch `stage5/22-pypi-publish` (base `origin/main`
`8b0d22812b5769e68c7a43a99d798ef7b675dfbe`), macOS arm64, Python 3.13.2, local uv 0.11.7
(the workflow pins 0.11.14), 2026-11-09. Commands from the checkout root.

| Command | Result |
| --- | --- |
| `uv sync --locked` | passes; `uv.lock` unchanged by the metadata additions |
| `uv run --frozen ruff check` / `ruff format --check` on the `ci.yml` path list | all checks passed; 108 files formatted |
| `uv run --frozen mypy` | no issues in 45 source files |
| `uv run --frozen pytest` | 2829 passed, 6 skipped (5 GNU-shell tests on macOS, 1 opt-in Docker check) |
| `pytest tests/test_publish_workflow.py` in a `python:3.13-slim` Linux container (bash, coreutils `sha256sum`, GNU find) | 43 passed, 0 skipped |
| `uv run --frozen python scripts/check_distribution.py` (no option, CI path) | PASS, 29 exact runtime versions |
| `uv build --no-build-isolation --offline --no-create-gitignore --out-dir .artifacts/issue-22-dist` | sdist, then wheel from the sdist; exactly these two files |
| `uvx --from twine==7.0.0 twine check --strict .artifacts/issue-22-dist/*` | both PASSED (also with twine 6.1.0) |
| `uv run --frozen python scripts/check_distribution.py --wheel .artifacts/issue-22-dist/<wheel> --sdist .artifacts/issue-22-dist/<sdist>` | PASS (sdist/wheel, clean install, setup commands, stdio, read-only profile, HTTP restart, uvx, stdio hub example), no build |
| same with an added `SHA256SUMS` in the directory | exit 1, `unexpected file SHA256SUMS` |
| `uvx --with shellcheck-py --from actionlint-py==1.7.12.25 actionlint .github/workflows/publish.yml .github/workflows/ci.yml` | 0 errors (actionlint 1.7.12 with shellcheck 0.11.0) |
| `uv run --frozen python scripts/check_private_identifiers.py` | no private identifiers (rule checks only; no local denylist) |
| `uv run --frozen python scripts/check_agent_setup.py` / `check_lock.py` | valid / PASS |

Files built (version 0.1.2), SHA-256 unchanged after the smoke run:

```text
87c06b2e54ac95cf88506c19f6f2493a34d81205fff77f6084d5d782bf860940  wled_mcp-0.1.2-py3-none-any.whl
fc107fa76cf3d0552a9d877f8f069bf1f2dfe4037ac9d7e8ab6eb2aa0746fbf2  wled_mcp-0.1.2.tar.gz
```

The wheel built from the sdist is byte-identical to the wheel the no-option check builds
directly from the tree. The sdist has 250 entries and no `.git` entry although this
checkout is a linked worktree with a `.git` file (the new sdist exclusion).
`PKG-INFO` is Metadata-Version 2.4 with `License-Expression: Apache-2.0`, the seven
classifiers and the `Changelog` URL. The checksums are local and differ from any future
CI build of a release commit.

actionlint was installed through `actionlint-py`, which downloads the actionlint binary
while building; on this host that needed the system CA bundle (`SSL_CERT_FILE`).

## Limits

- The GitHub-side behaviour (release and dispatch events, `GITHUB_REF_TYPE`/`GITHUB_SHA`
  values, environment review, OIDC exchange, artifact transfer, job outputs, PEP 740
  attestations, the upload) is not exercised; the shell steps were executed locally with
  synthetic files only.
- The smoke test runs on one runner architecture (`ubuntu-latest`); the package is pure
  Python.
- Not covered here and still open in #22: OCI images, SBOM/provenance, vulnerability
  review, the exact runtime pins in the published metadata, README links and wording on
  PyPI, the name check at release time and the first actual publication.
