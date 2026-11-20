# Publishing to PyPI

How the package `wled-mcp` gets to PyPI: the workflow [`.github/workflows/publish.yml`](../.github/workflows/publish.yml), the owner's one-time setup and the release procedure. Decisions: ISSUE-22-DEC-001 and ISSUE-22-DEC-002 ([decisions/stage-2.md](decisions/stage-2.md)); for the MCPB bundle ISSUE-151-DEC-001 and ISSUE-151-DEC-002 ([decisions/m3-m6.md](decisions/m3-m6.md)). Evidence: [validation/stage-2-release.md](validation/stage-2-release.md), [validation/stage-2-release.md](validation/stage-2-release.md).

Status: the workflow has published releases. Merging a change to it publishes nothing. Registering the publisher, changing the environment, creating a tag or release and approving an upload each need the owner's explicit instruction at that time ([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)). The two MCPB bundle jobs ran for the first time with the release of 2026-11-13 ([validation/stage-2-release.md](validation/stage-2-release.md#first-release-run)).

## What the workflow does

Four jobs, one run per ref at a time, a running publish is never cancelled. `build` and `publish` are the PyPI path; `build-mcpb` and `release-asset` handle the Claude Desktop bundle.

1. **build** (`contents: read`):
   1. checks out the ref with full history and without stored credentials;
   2. installs the locked environment without the project (`uv sync --locked --no-install-project`);
   3. runs the release guard `scripts/check_distribution.py --release-ref` before anything is built. It refuses the run unless the ref is a tag, the tag is `v` + `project.version`, the version is a release version (no local label, no development release), the tag points at the checked-out workflow commit and that commit is reachable from `main` (values from `GITHUB_REF_TYPE`, `GITHUB_REF_NAME`, `GITHUB_SHA`);
   4. builds once (`uv build --no-build-isolation`): the sdist, and from it the wheel, in `dist/`;
   5. records the SHA-256 of both files and runs `twine check --strict` with a pinned twine;
   6. smoke-tests exactly these files: `check_distribution.py --wheel dist/<wheel> --sdist dist/<sdist>` checks the file names, wheel `METADATA` and sdist `PKG-INFO` version, that the sdist contains no Git data, `.agent-runs/`, `.artifacts/`, `.env*` file or `devices.toml`, that `dist/` holds only these two files, then installs the wheel into a clean environment with the runtime constraints and runs the stdio, read-only profile, HTTP restart, uvx and hub-example handshakes on loopback (no device, no LAN);
   7. confirms the checksums are unchanged, writes them with tag and commit to the job summary and the publish job's input, and uploads `dist/` as the artifact `python-distribution`.
2. **publish** (`id-token: write` only, environment `pypi`): waits for the environment's required reviewers, downloads the artifact, checks that it holds exactly the two files with the build job's checksums, and uploads them with `pypa/gh-action-pypi-publish` through Trusted Publishing (OIDC). No checkout, build, install, cache, token or password; existing files are not skipped.

All actions are pinned to a full commit SHA with the version as a comment, because the workflow holds `id-token: write` (ISSUE-22-DEC-002 item 4); `ci.yml` keeps tag pins. `tests/test_publish_workflow.py` checks these properties, `tests/test_check_distribution.py` the guard.

## Owner-side setup (once, before the first upload)

**PyPI pending Trusted Publisher** (PyPI account, "Publishing", "Add a new pending publisher", GitHub):

| Field | Value |
| --- | --- |
| PyPI project name | `wled-mcp` |
| Owner | `descipar` |
| Repository name | `wled-mcp` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

A pending publisher does not reserve the name: until the first upload creates the project, anyone can register `wled-mcp`. Check the name shortly before the first release; a 404 is an observation, not a reservation (S2-DIST-01).

**GitHub environment `pypi`** (repository settings, Environments): required reviewers (the actual barrier; the triggers are not); recommended: deployment branches and tags limited to `v*`, and a `v*` tag ruleset that blocks updating and deleting release tags. No repository or environment secret is needed. **TestPyPI** is not wired (it would need its own publisher, environment and a `repository-url` change).

## Triggers

- `release: published` is the normal path: publishing a GitHub release for `v<version>`.
- `workflow_dispatch` on the tag `v<version>` re-runs it, for example after a rejected deployment or a failure before the upload. The guard refuses a branch or another tag.
- No `push`, `pull_request`, `pull_request_target`, `schedule` or `workflow_run` trigger.

A release marked pre-release also fires `release: published` and would publish `v<version>` as the final version; a draft does not trigger it. GitHub runs the workflow file of the ref's commit, so a tag on a commit without `publish.yml` starts nothing and cannot be dispatched: such a version needs a new version on a `main` commit that has the workflow. Rejecting the deployment in the `pypi` review ends the run without an upload; the build job's checksums and artifact stay visible.

## First release

Each step needs the owner's instruction at that time. Done for the first PyPI release on 2026-11-09 ([validation/stage-2-release.md](validation/stage-2-release.md#first-upload-2026-11-09)).

1. The workflow PR is merged into `main`.
2. The release commit on `main` carries `project.version`, the changelog entry and a README suitable for PyPI (it cannot be changed for an uploaded version; relative links do not resolve on PyPI, and it must not say the package is unpublished).
3. Pending publisher and environment are set up; the name is checked.
4. Create the tag `v<version>` on that commit (for example `git tag -a v1.2.3 <commit>`, push) and publish a GitHub release for it, or create both in the release form with target `main`. Title the release only `v<version>`, no description after it (owner rule, 2026-11-09).
5. Wait for the build job. Compare the job summary (tag, commit, SHA-256 of both files) with the intended release, then approve or reject the `pypi` deployment.
6. After the upload, compare file names and SHA-256 on the PyPI page with the summary and check a clean install: `uvx --from wled-mcp==<version> wled-mcp --version`.
7. After the `release-asset` job, check that the GitHub release lists `wled-mcp-<version>.mcpb` and `wled-mcp-<version>.mcpb.sha256` and that the hash matches the `build-mcpb` summary. The bundle jobs do not gate the PyPI files; a wrong asset is removed by hand.

## Pinning, update and rollback

- Pin an exact version: `uvx --from wled-mcp==<version> wled-mcp`; unpinned `uvx wled-mcp` resolves the newest version that is not yanked.
- For the tested dependency versions add the release's constraints: `uvx --constraints https://raw.githubusercontent.com/descipar/wled-mcp/v<version>/requirements-runtime.txt --from wled-mcp==<version> wled-mcp`. Without them, dependencies resolve within the ranges `pyproject.toml` declares ([dependency policy](contract/dependencies.md)).
- Update: change the pinned version. Rollback: pin the previous version (a yanked version still installs with its exact pin; a deleted one does not).

## Yank, delete, file names and uncertain uploads

- PyPI never accepts different content under an existing file name, nor the name of a deleted file again. A broken release is fixed with a new version, not a re-upload.
- Yanking (PEP 592) keeps the files: an exact `==<version>` pin still installs, unpinned resolution skips it. Prefer yanking. Deleting is irreversible and breaks pins. Both are owner actions on PyPI; the workflow does neither.
- Treat a timed-out, cancelled or failed publish step as possibly applied: check the project page or `https://pypi.org/pypi/wled-mcp/<version>/json` before running anything again. An upload whose file name and digests equal an existing file is a no-op; the same name with different content is refused ("File already exists").
- Nothing, one of two files, or unclear: re-run only the failed publish job ("Re-run failed jobs"); it uses the same artifact and checksums, existing files are accepted as a no-op and the missing one is uploaded.
- Do not start a new release or dispatch run for a version that already has files on PyPI (a rebuild with different bytes is refused) and do not add `skip-existing`.
- Both uploaded: nothing to repeat; compare checksums with the summary.

With Trusted Publishing the publish action creates PEP 740 attestations by default (the PyPI provenance). A separate SBOM file is not produced.

## MCPB bundle (#151)

Each run also builds a Claude Desktop bundle (`wled-mcp-<version>.mcpb`) and attaches it to the GitHub release. **The bundle is built along with each release, not tested by the project, no warranty** ([ISSUE-151-DEC-001](decisions/m3-m6.md)). It contains no server code: its manifest starts the released PyPI package through `uvx`. Format and limits: [contract/mcpb-bundle.md](contract/mcpb-bundle.md); user view: [MARKETPLACE.md](MARKETPLACE.md#claude-desktop-mcpb-bundle). No Claude Desktop run was made; the bundle jobs ran first with the release of 2026-11-13 (DEC-023; recorded in [validation/stage-2-release.md](validation/stage-2-release.md#first-release-run)). Submitting the bundle to any directory is an owner action and not planned.

Both jobs are outside the PyPI path (`publish` needs only `build`; a failure of either never changes the PyPI upload; ISSUE-151-DEC-002 item 4):

1. **build-mcpb** (`contents: read`, no `needs`, no environment): same checkout and release guard, then `deploy/build_mcpb.py --version "${GITHUB_REF_NAME#v}" --output mcpb-dist`. It fails unless the version equals `project.version`, the manifest validates against the vendored upstream schema and the archive has the four expected members. SHA-256 goes to the job summary and a job output; `mcpb-dist/` is uploaded as the artifact `mcpb-bundle`.
2. **release-asset** (`contents: write`, the only write permission): `needs: [build-mcpb, publish]` and no `if:`, so it runs only after the PyPI upload and the bundle build both succeeded, never after a rejected, cancelled or failed deployment. No checkout, build or install; only `actions/download-artifact`. It verifies the download against the `build-mcpb` checksum (exactly that one file) and writes `wled-mcp-<version>.mcpb.sha256` in `sha256sum` format. The upload step, the only one that sees the token (`GH_TOKEN` from `github.token`), re-checks the tag against `^v<digits>.<digits>.<digits>(rc<digits>)?$` and attaches both files with `gh release upload`. No `gh release create`, `edit` or `delete`, no `gh api`, `curl` or `git push`, no unpacking of the bundle, no `--clobber`.

**Re-runs.** "Re-run failed jobs" re-runs only `release-asset`. An existing asset with identical bytes is a no-op; different bytes fail the job and are never replaced. A full new run on the same tag rebuilds a deterministic archive (a difference fails the job for the owner to decide). Remove a wrong asset by hand on the release page; fix a broken bundle with a new release. `workflow_dispatch` on a tag without a release makes `gh release view` fail; the job never creates a release.

**Residual risk.** `contents: write` is broad (releases, tags, branches; not workflow files). The main-branch rulesets ([DEC-024](DECISIONS.md#dec-024--main-branch-rules-with-review-for-external-pull-requests)) block a direct push by this token because it is not a bypass actor (not re-verified); tag creation and deletion is restricted only if the owner set the recommended `v*` ruleset. The `gh` CLI is the runner image's version (the job prints it). The bundle is unsigned and has no attestation; the `.sha256` asset comes from the same workflow, so it checks a download against damage and does not prove origin.

## Dependency and licence inventory, vulnerability review

Checked on 2026-11-09 for the `requirements-runtime.txt` set of the first release (28 packages on Python 3.13 on macOS; other platforms can add packages). Licences come from installed metadata; users resolve the declared ranges, so this is the tested set, not a promise.

| Licence | Packages |
| --- | --- |
| MIT / MIT-0 | annotated-types, anyio, attrs, cffi, h11, jsonschema, jsonschema-specifications, mcp, mcp-types, pydantic, pydantic_core, pyjwt, referencing, rpds-py, truststore, typing-inspection |
| BSD-3-Clause | click, httpcore2, httpx2, idna, pycparser, sse-starlette, starlette, uvicorn |
| Apache-2.0 | opentelemetry-api, python-multipart |
| Apache-2.0 OR BSD-3-Clause | cryptography |
| PSF-2.0 | typing_extensions |

All are permissive and compatible with the project's Apache-2.0 licence; none is copyleft. Repeat with a release (`uvx pip-audit -r requirements-runtime.txt --no-deps --disable-pip`) and record material changes in the release notes. `pip-audit` reported no known vulnerabilities on 2026-11-09; later advisories follow [SECURITY.md](../SECURITY.md).

## Registry listing after the PyPI release

Prepared for [#24](https://github.com/descipar/wled-mcp/issues/24): the README marker `mcp-name: io.github.descipar/wled-mcp` (inside the package description, required by `scripts/check_distribution.py`) and the root [`server.json`](../server.json) (see [MARKETPLACE.md](MARKETPLACE.md); evidence in [validation/stage-2-release.md](validation/stage-2-release.md)). The goal is findability in the MCPHub registry, which is the official MCP Registry ([ISSUE-24-DEC-003](decisions/stage-2.md); the MCPM and hosted-directory routes are not planned). The workflow does not touch the registry, and no registry automation is wired.

**Release chain for a milestone release (`<version>` from `pyproject.toml`).** Done for M1 on 2026-11-09 on the owner's instructions ([ISSUE-24-DEC-004](decisions/stage-2.md); facts in [validation/stage-2-release.md](validation/stage-2-release.md#release-and-registry-publication-2026-11-09)) and for the M2 minor release on 2026-11-11 ([DEC-031](DECISIONS.md#dec-031--release-scope-for-milestone-m2), [record](validation/releases.md#release-and-registry-publication-2026-11-11)). For every later release each step needs the owner's explicit instruction at that time; completing or merging one step never authorizes the next ([DEC-023](DECISIONS.md#dec-023--staged-first-public-release), [DEC-030](DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)):

1. After the release PR is merged: create the tag `v<version>` on that `main` commit and publish the GitHub release (see "First release").
2. `publish.yml` builds, smoke-tests and, after the `pypi` review, uploads.
3. Check that PyPI serves the marker (`info.description` of `https://pypi.org/pypi/wled-mcp/<version>/json` contains `mcp-name: io.github.descipar/wled-mcp`) and that `server.json` carries `<version>` twice.
4. Install `mcp-publisher` from a pinned release (re-check the version; v1.8.8 on 2026-11-06) and verify the download against the release's checksum or signature before running it.
5. Run `mcp-publisher login github` as the account that owns the `descipar` namespace, then `mcp-publisher publish` in the repository root. `validate` sends the file to the registry service, so it is an external call, not a local check.
6. Verify with `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.descipar/wled-mcp` and record it. Whether a published entry can be corrected under the same version was not checked.
7. Check the bundle assets on the GitHub release (see "MCPB bundle (#151)").

**`mcp-publisher` on Windows (M1 recipe).** Download `mcp-publisher_windows_amd64.tar.gz` and `registry_<publisher version>_checksums.txt` of the pinned release (1.8.8), compare `Get-FileHash -Algorithm SHA256` of the archive with the checksums line, extract, and run the executable from a directory outside the checkout. `uvx` may not know a version published a moment earlier (local index cache): add `--no-cache` to the first check (`uvx --no-cache --isolated --python 3.13 --from wled-mcp==<version> wled-mcp --version`).

## What stays open

The container image pipeline, image SBOM/provenance, image name check and OCI pinning documentation moved to [#156](https://github.com/descipar/wled-mcp/issues/156) (ISSUE-22-DEC-006). The inventory above and the PEP 740 attestations are the documented equivalents of a PyPI SBOM.

## Checking the workflow locally

```text
uv sync --locked
uv run --frozen pytest tests/test_publish_workflow.py tests/test_check_distribution.py
uv build --no-build-isolation --offline --no-create-gitignore --out-dir .artifacts/dist-check
uvx --from twine==7.0.0 twine check --strict .artifacts/dist-check/*
uv run --frozen python scripts/check_distribution.py --wheel .artifacts/dist-check/<wheel> --sdist .artifacts/dist-check/<sdist>
uvx --from actionlint-py actionlint .github/workflows/publish.yml
uv run --frozen pytest tests/test_mcpb_bundle.py tests/test_publish_workflow.py
uv run --frozen python deploy/build_mcpb.py --output .artifacts/mcpb-dry-run
uv run --frozen python -I -m zipfile -l .artifacts/mcpb-dry-run/wled-mcp-<version>.mcpb
```

`--release-ref` fails outside a tagged workflow run by design. The bundle dry run prints `<sha256>  wled-mcp-<version>.mcpb`, writes only that file and lists `LICENSE`, `NOTICE`, `manifest.json` and `server/main.py`; on another operating system it is non-release evidence ([DEC-026](DECISIONS.md#dec-026--stage-releases-on-the-target-machine)). Tests that run the workflow's shell steps need bash, GNU `find` and `sha256sum` and are skipped with a stated reason on a plain Windows checkout.
