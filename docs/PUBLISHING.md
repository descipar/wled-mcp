# Publishing to PyPI

How the package `wled-mcp` gets to PyPI: the workflow
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml), the setup the owner does
once, and the release procedure. Decisions: ISSUE-22-DEC-001 and ISSUE-22-DEC-002 in
[decisions/issue-22.md](decisions/issue-22.md). Evidence:
[validation/issue-22.md](validation/issue-22.md).

Status: the workflow is prepared, nothing is published. Merging the workflow does not
publish anything. Registering the publisher, changing the environment, creating a tag or
release and approving an upload each need the owner's explicit instruction at that time
([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)).

## What the workflow does

Two jobs, one run per ref at a time; a running publish is never cancelled.

1. **build** (`contents: read`, no other permission):
   1. checks out the ref with full history and without stored credentials;
   2. installs the locked environment without the project (`uv sync --locked
      --no-install-project`);
   3. runs the release guard `scripts/check_distribution.py --release-ref` before anything
      is built (installing the project runs its build backend, so that comes after the
      guard). It refuses the run unless the ref is a tag, the tag is `v` +
      `project.version` of `pyproject.toml`, the version is a release version (no local
      label, no development release), the tag points at the checked-out workflow commit and
      that commit is reachable from `main`. The values come from the runner variables
      `GITHUB_REF_TYPE`, `GITHUB_REF_NAME` and `GITHUB_SHA`;
   4. builds once: `uv build --no-build-isolation` from the locked environment produces
      the sdist and, from that sdist, the wheel in `dist/`;
   5. records the SHA-256 of both files, runs `twine check --strict` with a pinned twine;
   6. smoke-tests exactly these files without building again:
      `check_distribution.py --wheel dist/<wheel> --sdist dist/<sdist>` checks the file
      names, the wheel `METADATA` and sdist `PKG-INFO` version, that the sdist contains no
      Git data, `.agent-runs/`, `.artifacts/`, `.env*` file or `devices.toml`, that `dist/`
      holds only these two files, and then installs the wheel into a clean environment with
      the runtime constraints and runs the stdio, read-only profile, HTTP restart, uvx and
      hub-example handshakes with the MCP SDK client on loopback (no device, no LAN);
   7. confirms the checksums are unchanged, writes them with the tag and commit to the job
      summary and hands them to the publish job as a job output, then uploads `dist/` as the
      artifact `python-distribution`.
2. **publish** (`id-token: write` only, environment `pypi`): waits for the environment's
   required reviewers, downloads the artifact, checks that the directory holds exactly the
   two files with the checksums from the build job, and uploads them with
   `pypa/gh-action-pypi-publish` through Trusted Publishing (OIDC). It has no checkout, no
   build or install step, no cache, no token or password and does not skip existing files.

All actions are pinned to a full commit SHA with the version as a comment, because this
workflow holds `id-token: write` (ISSUE-22-DEC-002 item 4). `ci.yml` keeps its tag pins;
aligning it is a separate change. `tests/test_publish_workflow.py` checks these properties
and `tests/test_check_distribution.py` the guard.

## Owner-side setup (once, before the first upload)

**PyPI pending Trusted Publisher** (PyPI account, "Publishing", "Add a new pending
publisher", GitHub):

| Field | Value |
| --- | --- |
| PyPI project name | `wled-mcp` |
| Owner | `descipar` |
| Repository name | `wled-mcp` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

A pending publisher does not reserve the name: until the first successful upload creates
the project, anyone can register `wled-mcp`, and the pending publisher then becomes
unusable. Check the name shortly before the first release; a 404 for the project page is an
observation, not a reservation (S2-DIST-01).

**GitHub environment `pypi`** (repository settings, Environments):

- required reviewers: the people who may approve an upload. The review is the actual
  barrier; the workflow triggers are not.
- recommended: deployment branches and tags limited to the tag pattern `v*`, so a run on a
  branch cannot even request the deployment;
- recommended: a tag ruleset for `v*` that blocks updating and deleting release tags.

The workflow does not need any repository or environment secret.

**TestPyPI** is optional and not wired. A trial upload there would need its own pending
publisher, its own environment and a change of the workflow (`repository-url`); it is not
part of this packet.

## Triggers and why

- `release: published` is the normal path: publishing a GitHub release for the tag
  `v<version>` starts the run.
- `workflow_dispatch` on the tag `v<version>` runs it again for the same tag, for example
  after a rejected deployment or a failure before the upload. The guard refuses a dispatch
  on a branch or on any other tag.
- No `push`, `pull_request`, `pull_request_target`, `schedule` or `workflow_run` trigger.

GitHub runs the workflow file of the ref the run is for. A tag whose commit does not
contain `publish.yml` therefore starts nothing and cannot be selected for a dispatch: a
tag on a commit from before the merge of this workflow, such as an existing release tag,
cannot be published by it. Such a version needs a new version on a `main` commit that
contains the workflow.

**Stop point:** rejecting the deployment in the `pypi` environment review ends the run
without an upload. The build job's checksums and artifact stay visible in the run.

## First release

Each step needs the owner's instruction at that time.

1. The PR adding the workflow is merged into `main`.
2. The release commit on `main` carries the version in `project.version`, the changelog
   entry and a README suitable for PyPI: PyPI shows the README of the uploaded files and it
   cannot be changed for an uploaded version. Relative links in the README do not resolve
   on PyPI, and the README must no longer say the package is not published to PyPI. This
   is release work in the release commit, not part of this workflow.
3. The pending publisher and the environment are set up as above; the name is checked.
4. Create the tag `v<version>` on that `main` commit (for example `git tag -a v1.2.3
   <commit>` and push it) and publish a GitHub release for it, or create both in the
   release form with the target `main` at that commit.
5. Wait for the build job. Compare the job summary (tag, commit, SHA-256 of both files)
   with the intended release, then approve or reject the `pypi` deployment.
6. After the upload, compare the file names and SHA-256 on the PyPI project page with the
   job summary and check a clean install:
   `uvx --from wled-mcp==<version> wled-mcp --version`.

## Pinning, update and rollback

- Users pin an exact version: `uvx --from wled-mcp==<version> wled-mcp`. An unpinned
  `uvx wled-mcp` resolves the newest version that is not yanked.
- For the dependency versions the release was tested with, add the constraints of that
  release: `uvx --constraints
  https://raw.githubusercontent.com/descipar/wled-mcp/v<version>/requirements-runtime.txt
  --from wled-mcp==<version> wled-mcp`. Without constraints, the dependencies that
  `pyproject.toml` does not pin exactly are resolved when the tool environment is first
  created; the development lock does not freeze them for PyPI users.
- Update: change the pinned version. Rollback: pin the previous version again (it must
  not have been deleted; a yanked version still installs with its exact pin).

## Yank, delete and file names

- PyPI never accepts a file name a second time, even after the file or the release was
  deleted. A broken release is fixed with a new version, not a re-upload.
- Yanking (PEP 592) keeps the files: an exact `==<version>` pin still installs it, only
  unpinned resolution skips it. Prefer yanking.
- Deleting a release is irreversible, breaks existing pins and frees nothing for reuse.
- Yank and delete are owner actions on PyPI; the workflow does neither.

## Uncertain or partial uploads

Treat a timed-out, cancelled or failed publish step as possibly applied. Before running
anything again, check the project page or `https://pypi.org/pypi/wled-mcp/<version>/json`
for the files of that version.

- Nothing uploaded: re-run the failed publish job ("Re-run failed jobs"); it uses the same
  tested artifact and checksums of that run. A new dispatch run builds again.
- One of the two files uploaded: a re-run stops at the existing file, because the
  workflow does not skip existing files. How to complete the version (or to release a new
  one) is an owner decision; do not add `skip-existing` to force it.
- Both uploaded: nothing to repeat; compare the checksums with the job summary.

## Attestations

With Trusted Publishing, `pypa/gh-action-pypi-publish` creates PEP 740 attestations for the
uploaded files by default. They are not claimed here as the SBOM, provenance or
attestation work of S2-DIST-03; that stays open.

## What stays open in #22

- The first actual publication and its proof that a clean user can run a pinned
  distribution without GitHub credentials (acceptance item 1); it needs the owner's release
  instruction.
- The multi-architecture OCI image pipeline (S2-DIST-02).
- SBOM, provenance or documented equivalents, dependency/license inventory and the
  vulnerability review (S2-DIST-03).
- The exact runtime pins (`mcp`, `starlette`, `uvicorn`) in the published metadata
  (acceptance item 4) and the README links and wording for PyPI, reported to the owner.
- The name and ownership check at release time.

## Checking the workflow locally

Without running the workflow:

```text
uv sync --locked
uv run --frozen pytest tests/test_publish_workflow.py tests/test_check_distribution.py
uv build --no-build-isolation --offline --no-create-gitignore --out-dir .artifacts/dist-check
uvx --from twine==7.0.0 twine check --strict .artifacts/dist-check/*
uv run --frozen python scripts/check_distribution.py --wheel .artifacts/dist-check/<wheel> --sdist .artifacts/dist-check/<sdist>
uvx --from actionlint-py actionlint .github/workflows/publish.yml
```

`--release-ref` fails outside a tagged workflow run by design.
