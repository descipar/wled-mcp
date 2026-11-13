# Issue #151 validation: MCPB bundle

Evidence for [#151](https://github.com/descipar/wled-mcp/issues/151) (requirement DIST-04,
scenarios D151-01 to D151-14 of [contract/mcpb-bundle.md](../contract/mcpb-bundle.md)); decisions
ISSUE-151-DEC-001 and ISSUE-151-DEC-002 in [decisions/issue-151.md](../decisions/issue-151.md).
Procedure: [PUBLISHING.md](../PUBLISHING.md#mcpb-bundle-151).

Nothing was published, tagged, released, uploaded or dispatched, and no repository setting was
changed. The two workflow jobs (`build-mcpb`, `release-asset`) were not run on GitHub. No
Claude Desktop was installed or started (ISSUE-151-DEC-001), no device or LAN host was contacted.
All evidence below is local and synthetic. Candidate: branch `descipar/M6-151`.

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| D151-01 manifest validates | `tests/test_mcpb_bundle.py`: the rendered manifest has no `Draft7Validator` error against the vendored schema; 22 mutated copies are each reported. One-time cross-check below |
| D151-02 schema provenance | SHA-256 `3a0ac9d8...592d`, 7902 bytes, no CR; equals the upstream file read with `gh api` at tag v2.1.2 and `mcpb-manifest-latest.schema.json` of that tag |
| D151-03 contents | exactly `LICENSE`, `NOTICE`, `manifest.json`, `server/main.py`; byte-equal to the repository files; unsafe names and a missing entry point refused by `pack` |
| D151-04 version | manifest `version` and `--from wled-mcp==<v>` equal `project.version`; a requested `9.9.9` fails before any write (function and command line); rc `0.4.0rc1` becomes `0.4.0-rc.1` in `version` only, also through a full build in a synthetic root; non-release versions refused |
| D151-05 launch | args equal the composed `server.json` runtime and package arguments plus `--from wled-mcp==<v> wled-mcp`; no HTTP, token or `env` |
| D151-06 `user_config` | exactly two required, non-secret paths without defaults; no private value; links only to known hosts |
| D151-07 identity | unofficial and not-affiliated wording, no icon, license, links, keywords and author from `pyproject.toml` |
| D151-08 determinism | two builds byte-identical; stored entries, 1980 timestamps, sorted names, fixed modes; checksum line equals the file hash |
| D151-09 workflow, static | `tests/test_publish_workflow.py`: `publish_workflow_problems` is empty for the real file; 55 mutations of the bundle jobs are each reported (permissions, `needs`, conditions, token exposure, forbidden commands, untrusted input, artifact names, guard order, PyPI jobs mentioning the bundle) |
| D151-10 hand-over, executed | same file, bash steps run on Linux (see below): tested file accepted, modified/extra/missing/other-name and ten hostile tags rejected before `gh`; upload without `--clobber`; identical existing asset accepted; different existing asset fails and nothing is replaced; failing upload fails the job; missing local file stops before any upload |
| D151-11 wording | README, MARKETPLACE.md and PUBLISHING.md checked for "built along with each release, not tested by the project, no warranty" (README: "without warranty"); the README link anchor resolves; removed phrases are reported |
| D151-12 template | placeholders `REPLACE_WITH_VERSION` and `REPLACE_WITH_AUTHOR` only; no version literal, no author name |
| D151-13 first run | ran with release 0.4.0 on 2026-11-13, see "First release run" |
| D151-14 command line | one bundle, one checksum line, empty stderr; existing bundle kept; validation failure, version mismatch and unusable location write nothing |

## Local runs (2026-11-12 and 2026-11-13)

Windows 11, Python 3.13.2, uv 0.11.14, checkout path with a space. A bundle built here is
non-release evidence only ([DEC-026](../DECISIONS.md#dec-026--stage-releases-on-the-target-machine)).

```text
uv run --frozen python deploy/build_mcpb.py --output .artifacts/mcpb-dry-run
  48f1231cd63d43259d370edbc78f66bf5180c7a2d459f09630598385b3c1760d  wled-mcp-0.3.0.mcpb   (exit 0)
uv run --frozen python deploy/build_mcpb.py --output .artifacts/mcpb-dry-run2
  identical hash; each directory holds only the bundle
uv run --frozen python -I -m zipfile -l .artifacts/mcpb-dry-run/wled-mcp-0.3.0.mcpb
  LICENSE, NOTICE, manifest.json, server/main.py (all dated 1980-01-01)
uv run --frozen python deploy/build_mcpb.py --version 9.9.9 --output .artifacts/mcpb-bad
  build_mcpb: requested version '9.9.9' differs from project.version '0.3.0'   (exit 1, directory not created)
uv run --frozen python deploy/build_mcpb.py --output .artifacts/mcpb-dry-run     (second time)
  build_mcpb: ... already exists and is not replaced   (exit 1)
```

Checks on the candidate tree:

| Command | Result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3507 passed, 70 skipped (second run; the first run had one failure of `tests/test_hw_http_probe.py::test_body_bound_under_probe_needs_a_successful_ping[400]`, which passed alone and on the repeat, and is outside this change) |
| `uv run --frozen pytest tests/test_mcpb_bundle.py tests/test_publish_workflow.py` (Windows) | 172 passed, 44 skipped: the shell tests need bash, GNU `find` and `sha256sum` and skip with their stated reason on a plain Windows checkout (DEC-033) |
| same two files on Linux (WSL Ubuntu, Python 3.13.18, locked environment in a separate directory) | 216 passed, 0 skipped: the workflow shell steps are executed there with a stubbed `gh` |
| `tests/test_readme.py tests/test_registry_metadata.py tests/test_version_source.py tests/test_gitattributes.py tests/test_ci_scope.py` (Windows) | passed in the full run; on the WSL checkout their git-based tests fail because the worktree's `.git` file points to a Windows path (environment, not the change) |
| `ruff check` and `ruff format --check` over the paths of `ci.yml` | passed (143 files) |
| `uv run --frozen mypy` | no issues in 59 source files, `deploy/build_mcpb.py` strict; the `jsonschema` import needs `type: ignore[import-untyped]` |
| `scripts/check_traceability.py` | 26 Must requirements and T01-T21 mapped (unchanged) |
| `scripts/check_private_identifiers.py` | no private identifiers in 334 files |
| `scripts/check_agent_setup.py`, `scripts/sync_agents.py --check` | valid, synchronized |
| `scripts/check_distribution.py` | fails in the checkout path with a space at the hub-example launch (uv reports `File not found` for the part of the path before the space, that script is not changed by this branch, and the same tree passes without the space); passes (exit 0, "PASS; 30 exact runtime versions verified") from a copy of the tree in a path without spaces |
| `uvx --from actionlint-py actionlint .github/workflows/publish.yml` | exit 0 (actionlint-py 1.7.12.25) |
| `wc -l README.md` | 200 |

A deliberate regression check: deleting the `cmp` line of the upload step from the workflow made
`test_a_different_existing_asset_fails_and_nothing_is_replaced` fail on Linux; the file was
restored.

## One-time cross-check with the upstream tool

Scratch directory outside the checkout, not CI, not a release step. `npm install --prefix
<scratch> --ignore-scripts --no-audit --no-fund @anthropic-ai/mcpb@2.1.2` (Node 26.1.0, npm
11.13.0) added 55 packages; the lock entry records the integrity
`sha512-goRbBC8ySo7SWb7tRzr+tL6FxDc4JPTRCdgfD2omba7freofvjq5rom1lBnYHZHo6Mizs1jAHJeN53aZbDoy8A==`.

```text
node <scratch>/node_modules/@anthropic-ai/mcpb/dist/cli/cli.js validate <dir with the packed manifest.json>
  Manifest schema validation passes!                                  (exit 0)
node ... cli.js info wled-mcp-0.3.0.mcpb
  File: wled-mcp-0.3.0.mcpb, Size: 14.65 KB, WARNING: Not signed      (exit 0)
node ... cli.js unpack wled-mcp-0.3.0.mcpb <dir>
  unpacked successfully; manifest.json byte-identical to the packed one   (exit 0)
```

The tool reads the stored (uncompressed) entries. This shows that the upstream validator accepts
the manifest and that the archive opens; it does not show that Claude Desktop starts the bundle.
Repeat the check when the vendored schema is updated.

## Static workflow review

Review items of the packet's checklist, as implemented (the independent review is separate):
top-level `permissions: {}`; `release-asset` the only job with `contents: write`, `build-mcpb`
`contents: read`, `build` and `publish` unchanged; `release-asset` `needs: [build-mcpb, publish]`
without a condition; no checkout, build, cache or environment in it and only
`actions/download-artifact`; `GH_TOKEN` (the workflow token) only in the env of the upload step;
tag re-validated with a bash regex before `gh`; values reach scripts through `env:` and runner
variables; no `--clobber`, release create/edit/delete, `gh api`, `curl`, `git push` or unpacking;
every action pinned by SHA with `# vX.Y.Z` and no new action; no `secrets.` reference;
`dist/` and the PyPI job texts are untouched (the workflow diff only adds lines).

## First release run

Recorded 2026-11-13 from the main session's readbacks (full release record:
[release-m3-m6.md](release-m3-m6.md)). `publish.yml` run 43414020842 for release `v0.4.0`: all
four jobs succeeded (build and smoke test, `build-mcpb`, publish to PyPI, `release-asset`). The
release lists `wled-mcp-0.4.0.mcpb` (15006 bytes) and `wled-mcp-0.4.0.mcpb.sha256`; the bundle
SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf` equals the `.sha256`
asset and the `build-mcpb` job artifact. The hash printed in the `build-mcpb` job summary itself
was not read (the job summary was not readable through the API); the upload job checks the files
against the build job's checksums. The hash also equals the local build recorded before the
release. No Claude Desktop run; the bundle stays untested in a client.
