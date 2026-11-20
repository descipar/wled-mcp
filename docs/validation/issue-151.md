# Issue #151 validation: MCPB bundle

Evidence for [#151](https://github.com/descipar/wled-mcp/issues/151) (requirement DIST-04,
scenarios D151-01 to D151-14 of [contract/mcpb-bundle.md](../contract/mcpb-bundle.md)); decisions
ISSUE-151-DEC-001 and ISSUE-151-DEC-002 in [decisions/issue-151.md](../decisions/issue-151.md).
Procedure: [PUBLISHING.md](../PUBLISHING.md#mcpb-bundle-151).

Before the first release run nothing was published, tagged or dispatched; no Claude Desktop was
installed or started (ISSUE-151-DEC-001); no device or LAN host was contacted. Local evidence is
synthetic. Candidate: branch `descipar/M6-151`.

## Scenario to evidence

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

## Local runs (2026-11-12 and 2026-11-13)

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

## One-time cross-check with the upstream tool

Scratch directory outside the checkout, not CI, not a release step: `@anthropic-ai/mcpb@2.1.2`
(Node 26.1.0) `validate` reported "Manifest schema validation passes!", `info` showed 14.65 KB and
"Not signed", and `unpack` reproduced `manifest.json` byte-identically. This shows the upstream
validator accepts the manifest and the archive opens; it does not show that Claude Desktop starts the
bundle. Repeat when the vendored schema is updated.

## Static workflow review

As implemented (independent review is separate): top-level `permissions: {}`; only `release-asset`
has `contents: write`; `release-asset` `needs: [build-mcpb, publish]` without a condition and has no
checkout or build; `GH_TOKEN` only in the upload step env; tag re-validated before `gh`; no
`--clobber`, release create/edit/delete, `gh api`, `curl`, `git push`; every action pinned by SHA,
no new action, no `secrets.` reference; PyPI job texts untouched.

## First release run

Recorded 2026-11-13 from the main session's readbacks (record:
[release-m3-m6.md](release-m3-m6.md)). `publish.yml` run 43414020842 for release `v0.4.0`: all four
jobs succeeded (build and smoke test, `build-mcpb`, publish to PyPI, `release-asset`). The release
lists `wled-mcp-0.4.0.mcpb` (15006 bytes) and its `.sha256`; the bundle SHA-256
`a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf` equals the `.sha256` asset, the
`build-mcpb` artifact and the earlier local build. The hash in the job summary itself was not read
(not readable through the API). No Claude Desktop run; the bundle stays untested in a client.
