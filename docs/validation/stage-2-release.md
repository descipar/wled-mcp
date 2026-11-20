# Validation: stage 2 release path (issues #21, #22, #24, #151)

## Issue #21 validation: build identity, compatibility policy and CI matrix

Evidence for the build-identity part of [#21](https://github.com/descipar/wled-mcp/issues/21)
together with [#70](https://github.com/descipar/wled-mcp/issues/70) (scenarios A21-01, A21-02,
A21-03, A21-07, first change) and the compatibility policy (A21-04, A21-05, A21-06, A21-08, second
change); decision [ISSUE-21-DEC-002](../decisions/stage-2.md). Contracts:
[versioning](../contract/versioning.md), [compatibility](../contract/compatibility.md).

All evidence is automated, synthetic and loopback only. No live deployment, update or rollback was
run (ISSUE-21-DEC-001: that is #25 evidence).

### Scenario to evidence

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

### Retained 0.1.0 fixtures

`tests/fixtures/compat/0.1.0/` was generated with its `generate.py` from a `git archive` of the 0.1.0
source commit in an offline `uv sync --frozen --no-dev` environment; a second generation reproduced
`tools.json`, `config.toml` and `get_state.json` byte for byte and the snapshot apart from its random
ID suffix. `examples/contracts/state.json` uses the synthetic `0.0.0+example` server version so the
example never has to follow a real version.

### Runs

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

### Limits

- Required-check enforcement follows the DEC-018 ruleset, which needs the visibility change (owner
  action, #90); until then review treats the jobs as required. The arm64 and container jobs belong
  in the ruleset.
- The `container` job runs for pull requests and pushes to `main` only.
- The container smoke uses an empty synthetic inventory: it proves build, startup, authentication,
  tool list and graceful stop per architecture, not device behavior or hardware performance.
- Windows and macOS are experimental and have no CI job (docs/DEVELOPMENT.md "Platform notes").

## Issue #22 validation: PyPI publish workflow

Evidence for the PyPI part of [#22](https://github.com/descipar/wled-mcp/issues/22) (AC-22P-01 to
AC-22P-12 of the issue-22 packet); decisions
[ISSUE-22-DEC-001 and ISSUE-22-DEC-002](../decisions/stage-2.md). Procedure:
[PUBLISHING.md](../PUBLISHING.md).

At the time of PR #141 nothing was published and the workflow had not run on GitHub; all evidence in
the first sections is local, synthetic and loopback-only. The release-event and dispatch paths, the
environment review and the OIDC upload first ran at the owner-instructed release (see
[First upload](#first-upload-2026-11-09)).

### Scenario to evidence

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

### Action pins

Resolved on 2026-11-09 (latest release of each; annotated tag of the publish action dereferenced).

| Action | Version | Commit |
| --- | --- | --- |
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/setup-python | v7.1.0 | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| astral-sh/setup-uv | v10.3.3 | `68559e99cc807c1eb7e9238fd43a15bba460eec2` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| actions/download-artifact | v8.0.2 | `9000827ccba6bdab643e8b6fd33ac0654aef8333` |
| pypa/gh-action-pypi-publish | v1.14.3 | `7245906fb61fa33a13554f9d5fb856fe61758086` |

### Local runs

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

### Limits

GitHub-side behavior (release and dispatch events, environment review, OIDC exchange, artifact
transfer, attestations, the upload) was not exercised before the first upload; one runner
architecture; the package is pure Python. Still open in #22 at PR #141 (runtime pins and README done
below): OCI images, SBOM/provenance, vulnerability review, the first publication.

### Runtime dependency ranges

Evidence for #22 acceptance item 4 (AC-22R-01 to AC-22R-14, AC-22R-README-01 to -08); decisions
ISSUE-22-DEC-003 to ISSUE-22-DEC-005 ([decision log](../decisions/stage-2.md)); contract
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

### First upload (2026-11-09)

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

## Issue #24 validation: registry metadata and listing drafts

Evidence for the bounded packet of [#24](https://github.com/descipar/wled-mcp/issues/24) (AC-24-01 to
AC-24-10); decisions [ISSUE-24-DEC-001 and ISSUE-24-DEC-002](../decisions/stage-2.md). Listing
status per route: [MARKETPLACE.md](../MARKETPLACE.md#status-per-route).

At the time of the packet nothing was published, tagged, uploaded or submitted; no `mcp-publisher`
was used; only plain `GET` requests (two schemas, one GitHub API read, package downloads) were made.
Publication happened later ([below](#release-and-registry-publication-2026-11-09)).

### Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| AC-24-01 marker | `tests/test_registry_metadata.py`: README holds exactly one `mcp-name:` marker outside a code fence, before the status paragraph, equal to the `server.json` name (negative controls: removed, other name, duplicate, in a fence). `scripts/check_distribution.py` requires it in the wheel `METADATA`; `tests/test_check_distribution.py` covers missing and wrong marker on synthetic wheels. |
| AC-24-02 shape | `server_problems` over the real file: current `$schema`, name pattern, description 1 to 100 characters with "Unofficial" and "not affiliated with the WLED project", exactly one `pypi` package (`uvx`, `stdio`), `repository.url` equal to pyproject, no `remotes`, no environment variables; 24 mutated copies reported. |
| AC-24-03 versions | `tests/test_version_source.py`: `server.json` `version` and `packages[0].version` equal `project.version`; mutations reported; drafts and documents use `<version>`. |
| AC-24-04 stdio launch | Command line composed from arguments: runtime `--isolated --python 3.13`, package `--transport stdio --config <path> --data-dir <path>`; variables required, `filepath`, not secret, no default; no absolute path, IP, host name, credential word or e-mail; `https://` only on allowed hosts; mutations reported. |
| AC-24-05 HTTP | `remotes` absent; `docs/MARKETPLACE.md` has "HTTP is self-hosted" with the quickstart link; listing URLs only on `github.com`, `pypi.org` or the schema host. |
| AC-24-06 MCPM draft | `mcpm_problems`: required fields, kebab-case name, no `is_official`, repository and licence equal to pyproject, unofficial wording, uvx arguments ending in `--transport stdio`, no pinned version, paths only via `${WLED_MCP_CONFIG}` / `${WLED_MCP_DATA_DIR}`; 18 mutations reported. |
| AC-24-07 hosted copy | `hosted_problems`: status draft, unofficial wording, no image, form fields stated as unverified, no endorsement, `<version>` placeholder, allowed link hosts; 9 mutations reported. |
| AC-24-08 status table (historical, superseded, see [Release and registry publication](#release-and-registry-publication-2026-11-09)) | `status_rows`: one row per route, state in the vocabulary (or "not run"), none later than "validated locally" at that time. |
| AC-24-09 release preparation | Version bumped, `uv.lock` refreshed (project entry only), CHANGELOG from `git log v0.1.2..HEAD`. |
| AC-24-10 no external effect | Statement at the top of this file. |

### Live schema validation (one run, 2026-11-09)

Plain `GET` of both schemas outside the repository, checked with `jsonschema` 4.26.0 from the locked
dev environment (`python -I`).

| Item | Observation |
| --- | --- |
| Official schema | `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`, draft-07, SHA-256 `3fba09590c99f61735d234822279f4223fab9e300c0a81e81c91ab62a4114de0`; `server.json` 0 errors, `$schema` equals `$id` |
| MCPM schema | `mcp-registry/schema/server-schema.json`, 2020-12, SHA-256 `db6a9e57a91c82a22c9ad6d57f65b8255dedb76e6dc24e9376501f821aa11b18`, last changed 2025-07-08; MCPM draft 0 errors |
| Negative controls | a `server.json` copy (101-character description, no transport) and an MCPM copy (name `WLED_MCP`, no licence) were rejected with 2 errors each |

Limits: `format` keywords not enforced, unknown properties are not forbidden by the schema, and the
publisher's own checks (namespace ownership, package verification, `mcp-publisher validate`) were
**not run**; schema-valid does not mean registry-accepted.

### Local checks

Windows 11, Python 3.13.2, uv 0.11.14, on the branch merged with `origin/main`.

| Command | Result |
| --- | --- |
| `uv sync --locked`, `check_lock.py` | passes (45 packages) |
| `ruff check` / `format --check`, `mypy` | pass (124 files; 51 source files) |
| `check_agent_setup.py`, `check_private_identifiers.py` | pass (286 files) |
| `uv run --frozen pytest` | 3147 passed, 30 skipped, 6 failed, 5 errors (known local Windows failures in `test_hw_http_probe.py` and `test_inventory_client.py`, identical on unchanged `origin/main`; Linux CI is authoritative, DEC-020) |
| `check_distribution.py` (checkout path without spaces) | PASS, 30 exact runtime versions incl. registry marker, stdio, HTTP restart, uvx |

In a checkout whose path contains a space the last step (stdio hub example) fails identically on
unchanged `origin/main`; it is environmental, not part of this change.

### Not run and limits

- No registry publication, listing or submission at that time; no MCPHub install test (S2-MARKET-03);
  the hosted directory's form (sign-in) was not seen, so its fields stay unverified.
- That a client turns the argument list into the intended command is not tested (`--isolated` is a
  positional argument with a fixed value; that is a reading of the schema).
- MCPM's handling of `${...}` in `env` was not observed. Only the Windows machine ran these checks.

### Follow-up: release 0.2.0 preparation (2026-11-09)

The 0.1.3 preparation was never published; [DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)
requires a minor release for M1, so the version became 0.2.0 (`pyproject.toml`, `uv.lock` project entry,
both `server.json` versions) and the changelog was rewritten.
[ISSUE-24-DEC-003](../decisions/stage-2.md) narrows listing routes to the official MCP Registry; the
MCPM and hosted drafts stay unsubmitted.

- Schema run repeated: same SHA-256 values, `server.json` 0 errors, MCPM draft 0 errors, both negative
  controls rejected; the stated limits apply.
- The status-vocabulary test accepts "not planned" only for a row citing ISSUE-24-DEC-003; the official
  registry row stays "validated locally" and the install test "not run" (at that time).
- README: M1 features and tool count 27 to 31. Nothing was tagged, released, uploaded or submitted.

### Release and registry publication 2026-11-09

Recorded from the coordinator's verification in the owner's #24 session, each step instructed
separately ([ISSUE-24-DEC-004](../decisions/stage-2.md)); a copy of what was reported, not a re-run.

- **Tag and release:** `v0.2.0` and a GitHub release at commit `b27180930febcee7985dce35282a05d8be0dc137`
  (main, CI green).
- **PyPI:** `publish.yml` run 42715819076 succeeded after the owner approved the `pypi` environment.
  Wheel SHA-256 `383cc49fb73f28bca2ffe2a4c1e2afa85f0d8ed0cc815a2c7dacdac47ec617e8`, sdist
  `67128a688faa27b10d717c336fa3ffd9c496d8b63f97213144b6d90c12550508`, identical to the job's
  `SHA256SUMS`. The PyPI description carries `mcp-name: io.github.descipar/wled-mcp`.
- **Install check:** `uvx --no-cache --isolated --python 3.13 --from wled-mcp==0.2.0 wled-mcp --version`
  printed `wled-mcp 0.2.0` (a first attempt failed only on a stale local index cache).
- **Registry publish:** `mcp-publisher` 1.8.8 (checksum equal to the release checksums file) after the
  owner's `mcp-publisher login github`; it printed "Successfully published
  io.github.descipar/wled-mcp version 0.2.0" with the `server.json` identical to main. This repository
  did not run `mcp-publisher validate`.
- **Readback:** the registry search API returns exactly one entry: version 0.2.0, pypi package, no
  `remotes`, status active, `isLatest` true, `publishedAt` 2026-11-09T22:58:41Z.

Status per route afterwards: official registry **accepted** and **visible** in the registry's search
API; MCPM and hosted directory not planned (ISSUE-24-DEC-003); fresh-install test **not run**. Not
observed: an MCPHub registry tab showing the entry, or how a host turns the entry into a launch
configuration. #24 item 6 is run separately and not claimed here.

#### Launch check of the composed command (2026-11-10)

Reported by the coordinator, Windows, with a real stdio client from the locked `mcp` SDK (script not
in the repository). Command composed from `packages[0]` of `server.json`:

```text
uvx --isolated --python 3.13 wled-mcp==0.2.0 --transport stdio --config <copy of examples/devices.example.toml> --data-dir <existing empty directory>
```

It started the published package; `initialize` returned `wled-mcp 0.2.0`; `tools/list` returned 31
tools; `wled_list_devices` returned `ok: true` with the two synthetic devices (`probe_status`
"untested", no network contact). Two earlier attempts failed only on the stale uv index cache. This
shows that the argument composition, including the positional `--isolated`, gives a working command
for a generic composer; it is partial evidence, not the install test (no MCPHub involved).

#### MCPHub Registry tab, observed install dialog (2026-11-10)

Observed by the owner in their MCPHub (admin only) from a screenshot of the Install dialog; not re-run
by an agent. The dialog was prefilled with type STDIO, command `uvx` and arguments `wled-mcp@0.2.0`,
`----transport`, `stdio`, `----config`, `{config_path}`, `----data-dir`, `{data_dir}`.

- This MCPHub prepends `--` to argument names that already start with `--`, leaves `{config_path}` and
  `{data_dir}` unresolved and drops the runtime arguments (`--isolated`, `--python 3.13`). The
  coordinator read the MCPHub source (`getArgs()`, main branch, 2026-11-10), which matches the dialog;
  whether the owner's build equals that revision was not checked.
- `server.json` conforms to the registry schema and was not changed; the deployment guide tells users to
  edit the dialog ([DEPLOYMENT](../DEPLOYMENT.md#installing-from-the-mcphub-registry-tab)).

Result for #24 item 6: a documented finding; the configuration this MCPHub generates is not runnable
without a manual edit. The hand-corrected entry was **not** started inside MCPHub: the owner decided on
2026-11-10 that this is not wanted ([ISSUE-24-DEC-005](../decisions/stage-2.md), waiver). Item 6 is
closed by that waiver, not by an observation; the install-test state stays "not run". The AC wording of
S2-MARKET-03 ("metadata-generated uvx configuration") is not met for this hub build.

## Issue #151 validation: MCPB bundle

Evidence for [#151](https://github.com/descipar/wled-mcp/issues/151) (requirement DIST-04,
scenarios D151-01 to D151-14 of [contract/mcpb-bundle.md](../contract/mcpb-bundle.md)); decisions
ISSUE-151-DEC-001 and ISSUE-151-DEC-002 in [decisions/m3-m6.md](../decisions/m3-m6.md).
Procedure: [PUBLISHING.md](../PUBLISHING.md#mcpb-bundle-151).

Before the first release run nothing was published, tagged or dispatched; no Claude Desktop was
installed or started (ISSUE-151-DEC-001); no device or LAN host was contacted. Local evidence is
synthetic. Candidate: branch `descipar/M6-151`.

### Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| D151-01 manifest validates | `tests/test_mcpb_bundle.py`: no `Draft7Validator` error against the vendored schema; 22 mutated copies each reported; upstream cross-check below |
| D151-02 schema provenance | SHA-256 `3a0ac9d8...592d`, 7902 bytes, no CR; equals the upstream file at tag v2.1.2 (read with `gh api`) |
| D151-03 contents | exactly `LICENSE`, `NOTICE`, `manifest.json`, `server/main.py`, byte-equal to the repository files; unsafe names and a missing entry point refused |
| D151-04 version | manifest `version` and `--from wled-mcp==<v>` equal `project.version`; a requested `9.9.9` fails before any write; rc `0.4.0rc1` becomes `0.4.0-rc.1` in `version` only; non-release versions refused |
| D151-05 launch | args equal the composed `server.json` arguments plus `--from wled-mcp==<v> wled-mcp`; no HTTP, token or `env` |
| D151-06 `user_config` | exactly two required, non-secret paths without defaults; links only to known hosts |
| D151-07 identity | unofficial and not-affiliated wording, no icon; license, links, keywords, author from `pyproject.toml` |
| D151-08 determinism | two builds byte-identical (stored entries, 1980 timestamps, sorted names, fixed modes); checksum line equals the file hash |
| D151-09 workflow, static | `tests/test_publish_workflow.py`: `publish_workflow_problems` empty for the real file; 55 mutations of the bundle jobs each reported |
| D151-10 hand-over, executed | bash steps run on Linux with a stubbed `gh`: tested file accepted; modified/extra/missing/other-name files and ten hostile tags rejected before `gh`; no `--clobber`; identical existing asset accepted, different one fails and nothing is replaced; failing upload fails the job |
| D151-11 wording | README, MARKETPLACE.md, PUBLISHING.md checked for "built along with each release, not tested by the project, no warranty"; README anchor resolves |
| D151-12 template | placeholders `REPLACE_WITH_VERSION` and `REPLACE_WITH_AUTHOR` only |
| D151-13 first run | ran with release 0.4.0 on 2026-11-13, see "First release run" |
| D151-14 command line | one bundle, one checksum line, empty stderr; existing bundle kept; validation failure, version mismatch, unusable location write nothing |

### Local runs (2026-11-12 and 2026-11-13)

Windows 11, Python 3.13.2, uv 0.11.14, checkout path with a space; a bundle built here is
non-release evidence only ([DEC-026](../DECISIONS.md#dec-026--stage-releases-on-the-target-machine)).
Two `deploy/build_mcpb.py` builds of 0.3.0 produced identical hashes with only the four entries
(all dated 1980-01-01); `--version 9.9.9` exited 1 without creating a directory; a rebuild into an
existing directory exited 1 without replacing it.

| Command | Result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3507 passed, 70 skipped (second run; the first had one failure of `tests/test_hw_http_probe.py::test_body_bound_under_probe_needs_a_successful_ping[400]`, passed alone and on repeat, outside this change) |
| `tests/test_mcpb_bundle.py tests/test_publish_workflow.py` (Windows) | 172 passed, 44 skipped (shell tests need bash, GNU `find`, `sha256sum`; DEC-033) |
| same on Linux (WSL Ubuntu, Python 3.13.18) | 216 passed, 0 skipped (workflow shell steps run with a stubbed `gh`) |
| ruff check/format, strict mypy (59 files) | passed |
| traceability, private identifiers (334 files), agent setup and sync | pass |
| `scripts/check_distribution.py` | fails only in the checkout path with a space at the hub-example launch (script unchanged); passes ("30 exact runtime versions verified") from a copy in a path without spaces |
| `actionlint` on `publish.yml` | exit 0 |

A deliberate regression check (deleting the `cmp` line of the upload step) made
`test_a_different_existing_asset_fails_and_nothing_is_replaced` fail on Linux; the file was restored.

### One-time cross-check with the upstream tool

Scratch directory outside the checkout, not CI, not a release step: `@anthropic-ai/mcpb@2.1.2`
(Node 26.1.0) `validate` reported "Manifest schema validation passes!", `info` showed 14.65 KB and
"Not signed", and `unpack` reproduced `manifest.json` byte-identically. This shows the upstream
validator accepts the manifest and the archive opens; it does not show that Claude Desktop starts the
bundle. Repeat when the vendored schema is updated.

### Static workflow review

As implemented (independent review is separate): top-level `permissions: {}`; only `release-asset`
has `contents: write`; `release-asset` `needs: [build-mcpb, publish]` without a condition and has no
checkout or build; `GH_TOKEN` only in the upload step env; tag re-validated before `gh`; no
`--clobber`, release create/edit/delete, `gh api`, `curl`, `git push`; every action pinned by SHA,
no new action, no `secrets.` reference; PyPI job texts untouched.

### First release run

Recorded 2026-11-13 from the main session's readbacks (record:
[release-m3-m6.md](releases.md)). `publish.yml` run 43414020842 for release `v0.4.0`: all four
jobs succeeded (build and smoke test, `build-mcpb`, publish to PyPI, `release-asset`). The release
lists `wled-mcp-0.4.0.mcpb` (15006 bytes) and its `.sha256`; the bundle SHA-256
`a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf` equals the `.sha256` asset, the
`build-mcpb` artifact and the earlier local build. The hash in the job summary itself was not read
(not readable through the API). No Claude Desktop run; the bundle stays untested in a client.
