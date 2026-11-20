# Issue #22 validation: PyPI publish workflow

Evidence for the PyPI part of [#22](https://github.com/descipar/wled-mcp/issues/22) (AC-22P-01 to
AC-22P-12 of the issue-22 packet); decisions
[ISSUE-22-DEC-001 and ISSUE-22-DEC-002](../decisions/issue-22.md). Procedure:
[PUBLISHING.md](../PUBLISHING.md).

At the time of PR #141 nothing was published and the workflow had not run on GitHub; all evidence in
the first sections is local, synthetic and loopback-only. The release-event and dispatch paths, the
environment review and the OIDC upload first ran at the owner-instructed release (see
[First upload](#first-upload-2026-11-09)).

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| AC-22P-01 triggers | `tests/test_publish_workflow.py` `publish_workflow_problems` is empty for the real file; adding `push` or `pull_request_target` or changing the release type is reported. |
| AC-22P-02 permissions | Top level `{}`, build `{contents: read}`, publish `{id-token: write}`, no `id-token` elsewhere, no `write-all`/`read-all`; each mutation reported. |
| AC-22P-03 publish job | Environment `pypi` and `needs: build` required; removing them or adding checkout or a build command to the publish job is reported. |
| AC-22P-04 no secrets | No `secrets.` reference, no `password`/`user`/`repository-url`, no `skip-existing: true`; checkout with `persist-credentials: false`. |
| AC-22P-05 pins | Raw-line check `owner/repo@<40 hex> # vX.Y.Z`; tag pins and short SHAs reported. SHAs resolved with read-only `gh api` calls and each `action.yml` read to confirm the inputs. |
| AC-22P-06 guard | `tests/test_check_distribution.py`: `release_ref_problems`, `tag_commit_problems` (temporary repositories: tag on `main` passes, side commit and missing `origin/main` refused), `check_release_ref`, `release_directory_problems`, `check_sdist`; guard runs before build, project install and upload. Local `--release-ref` with a branch ref and with a tag not on `main` exits 1. |
| AC-22P-07 single build | Exactly one `uv build --no-build-isolation`, `uv sync --locked` before it, `uvx --from twine==<exact>` >= 6.1.0 with `--strict`; sdist without `.git`, `.agent-runs/`, `.artifacts/`, `.env*`, `devices.toml`. |
| AC-22P-08 smoke | `check_distribution.py --wheel ... --sdist ...` PASS without rebuilding; checksums identical before and after; shell steps run by `test_publish_job_accepts_only_the_tested_files` and `test_build_job_refuses_a_third_file_in_dist`. |
| AC-22P-09 artifact handoff | Same upload and download name, `if-no-files-found: error`, download path equals `packages-dir`; checksum list stays in `RUNNER_TEMP`; an extra `SHA256SUMS` fails the publish check. |
| AC-22P-10 hygiene | `enable-cache: false`, uv version equal to `ci.yml`, `UV_PYTHON_DOWNLOADS: never`, concurrency per ref without cancel, `timeout-minutes` on both jobs. |
| AC-22P-11 documentation | [PUBLISHING.md](../PUBLISHING.md) covers pending publisher, environment reviewers, tag policy, first-release procedure, rollback, yank, uncertain uploads; attestations not claimed as S2-DIST-03. |
| AC-22P-12 evidence | This file; link lines in [VALIDATION.md](../VALIDATION.md), [DEPLOYMENT.md](../DEPLOYMENT.md), [STAGE-5.md](../STAGE-5.md). |

## Action pins

Resolved on 2026-11-09 (latest release of each; annotated tag of the publish action dereferenced).

| Action | Version | Commit |
| --- | --- | --- |
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/setup-python | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| astral-sh/setup-uv | v10.3.3 | `68559e99cc807c1eb7e9238fd43a15bba460eec2` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |
| pypa/gh-action-pypi-publish | v1.14.3 | `7245906fb61fa33a13554f9d5fb856fe61758086` |

## Local runs

Branch `stage5/22-pypi-publish`, macOS arm64, Python 3.13.2, local uv 0.11.7 (workflow pins 0.11.14),
2026-11-09.

| Command | Result |
| --- | --- |
| `uv sync --locked` | passes; `uv.lock` unchanged |
| `ruff check` / `ruff format --check` (`ci.yml` list), `mypy` | pass; 45 source files |
| `uv run --frozen pytest` | 2829 passed, 6 skipped (5 GNU-shell tests on macOS, 1 opt-in Docker) |
| `pytest tests/test_publish_workflow.py` in a `python:3.13-slim` container | 43 passed, 0 skipped |
| `check_distribution.py` (CI path) and with `--wheel/--sdist` on the local build | PASS, 29 exact runtime versions; an added `SHA256SUMS` exits 1 |
| `uvx --from twine==7.0.0 twine check --strict` (also 6.1.0) | both PASSED |
| actionlint 1.7.12 with shellcheck on `publish.yml` and `ci.yml` | 0 errors |
| `check_private_identifiers.py`, `check_agent_setup.py`, `check_lock.py` | pass |

The wheel built from the sdist is byte-identical to the wheel built from the tree; the sdist has no
`.git` entry although the checkout is a linked worktree. Local checksums differ from any future CI
build.

## Limits

GitHub-side behavior (release and dispatch events, environment review, OIDC exchange, artifact
transfer, attestations, the upload) was not exercised before the first upload; one runner
architecture; the package is pure Python. Still open in #22 at PR #141 (runtime pins and README done
below): OCI images, SBOM/provenance, vulnerability review, the first publication.

## Runtime dependency ranges

Evidence for #22 acceptance item 4 (AC-22R-01 to AC-22R-14, AC-22R-README-01 to -08); decisions
ISSUE-22-DEC-003 to ISSUE-22-DEC-005 ([decision log](../decisions/issue-22.md)); contract
[dependencies.md](../contract/dependencies.md). Branch `stage5/22-runtime-dependency-ranges`, macOS
arm64, Python 3.13.2, uv 0.11.7, 2026-11-09. Nothing published or released; resolution and installs
reached PyPI only.

- Declaration, lock and export: only the project's own metadata changed in `uv.lock`; no package
  version, source or hash changed. Wheel `Requires-Dist`: `anyio<5,>=4.10`, `httpx2<3,>=2.16`,
  `mcp<3,>=2.3.0`, `pydantic<3,>=2.12.0`, `starlette<2,>=1.0.0`, `uvicorn<0.55,>=0.31.1`.
  `tests/test_dependency_ranges.py` (bounded ranges, every third-party import declared, lock and
  export inside the ranges) and `tests/test_check_distribution.py` (`requires_dist_problems`) cover it.
- Lowest and highest combinations were installed into two new virtual environments (lowest via
  `uv pip compile --resolution lowest-direct`, highest by default resolution), `uv pip check` passes.

| Distribution | Lowest | Highest | Lock |
| --- | --- | --- | --- |
| mcp | 2.3.0 | 2.3.0 | 2.3.0 |
| pydantic | 2.12.0 | 2.14.3 | 2.14.2 |
| httpx2 | 2.16.0 | 2.16.0 | 2.16.0 |
| starlette | 1.0.0 | 1.10.0 | 1.10.0 |
| uvicorn | 0.31.1 | 0.54.0 | 0.54.0 |
| anyio | 4.10.0 | 4.16.0 | 4.16.0 |
| sse-starlette | 3.7.0 | 3.7.0 | 3.6.0 |

The highest set differs from the lock (pydantic, sse-starlette): the lock is the tested set. Each
floor equals the declared lower bound.

| Run | Result |
| --- | --- |
| Highest, full suite (installed package, not the source tree) | 2867 passed, 6 skipped |
| Lowest, full suite | 2867 passed, 6 skipped; `tests/test_tools_list_cache.py` now pins `anyio_backend` to asyncio (anyio 4.10.0 also parametrized an uninstalled trio variant) |
| Wheel smoke in both environments | `--version`, setup commands, stdio handshake, read-only profile, HTTP start, authenticated `tools/list`, restart: PASS |
| Locked environment: ruff, mypy, `pytest` (2867 passed, 6 skipped), `check_distribution.py` (29 versions), coverage, identifiers, traceability, agent setup | pass |

`deploy/stage_release.py`, the HTTP Dockerfile, `examples/mcphub.example.json` are unchanged;
`tests/test_deployment_artifacts.py` and the opt-in Docker `compose config` check pass; no image was
built or pushed.

Limits: only the lowest and highest combination ran; one host (macOS arm64); floor runs are not in CI,
so the floor claim can decay unless a lowest-direct CI job is added.

## First upload (2026-11-09)

After PR #141 (workflow) and PR #143 (ranges and PyPI README) the owner instructed the tag and release
of 0.1.2 and approved the `pypi` environment deployment in the GitHub UI (chat instructions, no
permalink).

- Release `v0.1.2` on `main` commit `91736b4` (CI green). The `release: published` run built and
  smoke-tested the distribution, waited at the `pypi` environment, and the publish job succeeded after
  approval.
- PyPI lists `wled-mcp` 0.1.2 with `wled_mcp-0.1.2-py3-none-any.whl` (sha256
  `3177df4bd68f1e4362f16b6519b72c2748847bbd58713cc2e8e41e02d5940c3e`) and `wled_mcp-0.1.2.tar.gz`
  (sha256 `0db94687f9de49b56dd50ce97fe415b7d892cae3785b16e24c27acee7cce4ce4`); metadata names the
  project unofficial, Apache-2.0, and the dependency ranges.
- Clean install: `uvx wled-mcp==0.1.2 --version` without cache printed `wled-mcp 0.1.2`.
- Not done: digests not compared with the build job summary (only file names and the install); no
  TestPyPI rehearsal (owner declined); the image, SBOM and provenance parts of #22 stay open.
