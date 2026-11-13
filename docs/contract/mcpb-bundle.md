# Claude Desktop MCPB bundle

Issue [#151](https://github.com/descipar/wled-mcp/issues/151), requirement DIST-04, decisions
ISSUE-151-DEC-001 and ISSUE-151-DEC-002 in [decisions/issue-151.md](../decisions/issue-151.md).
Evidence: [validation/issue-151.md](../validation/issue-151.md). Install and verification
instructions for users: [MARKETPLACE.md](../MARKETPLACE.md#claude-desktop-mcpb-bundle). Release
workflow: [PUBLISHING.md](../PUBLISHING.md#mcpb-bundle-151).

## Requirement

| ID | Requirement | Scenarios |
| --- | --- | --- |
| DIST-04 | Every release workflow run builds the Claude Desktop bundle `wled-mcp-<version>.mcpb` from the tagged version, and a separate job attaches it with its SHA-256 to the GitHub release only after the PyPI upload succeeded. The bundle contains no server code: its manifest launches the released PyPI package through `uvx`, pinned to that version, over stdio only. The bundle is built along with each release, not tested by the project and comes without warranty; README, MARKETPLACE.md and PUBLISHING.md say so. A failure of the bundle jobs never prevents or changes the PyPI upload. | D151-01 to D151-14 |

DIST-04 was first named in the [architecture review](../ARCHITECTURE-REVIEW-2026-11-09.md); its
"one actual install check" wording is superseded for #151 by ISSUE-151-DEC-001 (no Claude
Desktop run, no test of the bundle by the project).

## Scenarios

All scenarios are offline and synthetic. The packed bundle is inspected as a file; nothing is
started in Claude Desktop, nothing is uploaded and no device is contacted.

| ID | Scenario | Evidence |
| --- | --- | --- |
| D151-01 | The rendered manifest validates against the vendored upstream schema; a mutated copy (missing `entry_point`, extra key, `server.type: "uv"`, option without `title`, other `manifest_version`, non-https link, unresolved `user_config` reference) is reported | `tests/test_mcpb_bundle.py` |
| D151-02 | The vendored schema is byte-identical to the recorded upstream file | `tests/test_mcpb_bundle.py` (SHA-256 and size) |
| D151-03 | The packed archive holds exactly `LICENSE`, `NOTICE`, `manifest.json`, `server/main.py`; no directory entry, no unsafe name, no inventory or secret | `tests/test_mcpb_bundle.py` |
| D151-04 | The manifest `version` and the `uvx` pin equal `project.version` (release candidates map to semver in `version` only); a different requested version fails before anything is written; no placeholder is left | `tests/test_mcpb_bundle.py` |
| D151-05 | The launch is the documented stdio command: `uvx --isolated --python 3.13 --from wled-mcp==<version> wled-mcp --transport stdio --config <path> --data-dir <path>`; no HTTP option, no token, no `env` | `tests/test_mcpb_bundle.py` (against `server.json`) |
| D151-06 | `user_config` has exactly the two required, non-secret paths without defaults; each is one argument; no private value, links only to known hosts | `tests/test_mcpb_bundle.py` |
| D151-07 | The identity is unofficial and not affiliated with the WLED project, has no icon, and license, links, keywords and author follow `pyproject.toml` | `tests/test_mcpb_bundle.py` |
| D151-08 | Two builds are byte-identical (stored entries, fixed time, sorted names); the printed checksum line is the `sha256sum` format of the file | `tests/test_mcpb_bundle.py` |
| D151-09 | The workflow has exactly the jobs `build`, `publish`, `build-mcpb`, `release-asset`: `contents: write` only in `release-asset`, which needs `publish` and `build-mcpb`, has no condition, no checkout, no build step, no third-party action, the token only in its upload step, and none of the forbidden commands; `build` and `publish` do not mention the bundle | `tests/test_publish_workflow.py` (static, with mutations) |
| D151-10 | The checksum hand-over and the upload are executed with a shell: the tested file is accepted, a modified, extra or missing file and a hostile tag are rejected; the upload never uses `--clobber`, accepts an identical existing asset, fails on a different one and replaces nothing | `tests/test_publish_workflow.py` (needs bash, GNU tools; stubbed `gh`) |
| D151-11 | README, MARKETPLACE.md and PUBLISHING.md state "built along with each release, not tested by the project, no warranty"; the README link resolves | `tests/test_mcpb_bundle.py` |
| D151-12 | The manifest template names the version only by `REPLACE_WITH_VERSION`, the author only by `REPLACE_WITH_AUTHOR` | `tests/test_mcpb_bundle.py` |
| D151-13 | The release job is first executed with the next release the owner publishes; until then it is verified by review, the static and shell tests and a local dry run | `docs/validation/issue-151.md` (first release run recorded afterwards, not blocking) |
| D151-14 | The command line writes one file, prints one checksum line, never replaces an existing bundle, and writes nothing on a version mismatch, a validation failure or an unusable location | `tests/test_mcpb_bundle.py` |

## Manifest design

MCPB manifest version `0.3`, the current version of the upstream specification and the one the
published `latest` schema validates. `server.type` is `python` and `mcp_config.command` is `uvx`
with the arguments above, so the bundle starts exactly the command that the README and
`server.json` document. The experimental `uv` server type of manifest 0.4 runs a bundled
`pyproject.toml` project and cannot express "run the PyPI package X at version Y"; it is not
used. The `python` type is the only 0.3 type whose command is free.

The schema requires `server.entry_point`. The bundle therefore carries `server/main.py`, a
placeholder that exits with a message and is never run by the manifest's launch.

`user_config` asks for the two paths the stdio command requires (the inventory file and an
existing data directory), as `server.json` does. Each `${user_config.*}` reference is its own
argument, so a path with spaces needs no quoting. No secret, token, device address or inventory
is bundled, and no HTTP option exists. `compatibility.platforms` lists all three platforms
because the bundle only calls `uvx`; the support tiers of [compatibility.md](compatibility.md)
apply to the server. `claude_desktop` and `runtimes` are omitted: no authoritative minimum
version was found, and `uvx` provisions its own Python. `tools` and `prompts` are omitted
(a static list would drift from the served tools).

The author is injected from `project.authors[0]` of `pyproject.toml` at build time, so the
template holds no personal name; the redistributed artifact keeps the attribution that
[DEC-011](../DECISIONS.md#dec-011--apache-20-license-with-notice-attribution) asks for. A release candidate
`X.Y.ZrcN` becomes `X.Y.Z-rc.N` in the manifest `version` only; the `uvx` pin and the file name
keep the PEP 440 form.

**Limit.** The manifest is schema-valid, but a `python`-type bundle whose command is `uvx` is not
a first-class form in the specification, and it needs `uv` on the PATH that Claude Desktop sees.
Whether Claude Desktop accepts and starts such a bundle was not verified: the project does not
test the bundle (ISSUE-151-DEC-001).

## Build and validation

`deploy/build_mcpb.py --output DIR [--version X]` renders the template, validates it with
`jsonschema.Draft7Validator` against the vendored schema and the checks the schema does not make
(semver `version`, plain https URLs, every `${user_config.*}` reference defined and every option
used, no placeholder left, `entry_point` present in the archive), and packs
`DIR/wled-mcp-<project.version>.mcpb`. It reads the checkout only, writes exactly that one file,
never replaces an existing one and prints `<sha256>  <name>`. A `--version` that differs from
`project.version` exits non-zero before anything is written.

The archive is deterministic: stored (not deflated) entries, fixed 1980-01-01 timestamps,
names sorted, no directory entries, fixed permissions. A third party can rebuild the bundle from
the tag with the same script and compare the SHA-256 (build on the platform that releases it,
[DEC-026](../DECISIONS.md#dec-026--stage-releases-on-the-target-machine); a rebuild on
another operating system is non-release evidence).

The Node `mcpb` tool is not part of the release path (ISSUE-151-DEC-002 item 2). One local
cross-check with the pinned `@anthropic-ai/mcpb` 2.1.2 CLI is recorded in
[validation/issue-151.md](../validation/issue-151.md); repeat it when the vendored schema is
updated.

### Vendored schema

`deploy/mcpb/schema/mcpb-manifest-v0.3.schema.json` is an unmodified copy of
`schemas/mcpb-manifest-v0.3.schema.json` at tag `v2.1.2` (commit
`2a788100a60db19a6b1c018fb1cf84ae85de9537`) of `modelcontextprotocol/mcpb`, 7902 bytes, SHA-256
`3a0ac9d845711a1b9b17dfa5a52f8b60628239d6a86a9db417206a9efc78592d`. It is identical to
`mcpb-manifest-latest.schema.json` of that tag. Its source header calls the 0.3 schema a work in
progress; the check validates against that published form. Licence review and the preserved
notice: [SOURCES.md](../SOURCES.md#issue-151-mcpb-manifest-schema).

## Release flow

`.github/workflows/publish.yml` has four jobs; the first two are the unchanged PyPI path
([PUBLISHING.md](../PUBLISHING.md)).

1. `build-mcpb` (`contents: read`) runs independently of `build` and `publish`: it checks out
   the ref without stored credentials, runs the same release guard, builds the bundle with
   `--version "${GITHUB_REF_NAME#v}"`, records its SHA-256 as a job output and uploads the
   artifact `mcpb-bundle`.
2. `release-asset` (`contents: write`, the only job with a write permission) needs `build-mcpb`
   and `publish` and has no condition, so it runs only when the PyPI upload and the bundle build
   both succeeded. It downloads the artifact, verifies it against the checksum from the build
   job, writes `wled-mcp-<version>.mcpb.sha256` in `sha256sum` format and attaches both files
   with `gh release upload`.

A failure of `build-mcpb` or `release-asset` never prevents or changes the PyPI upload, because
`publish` needs only `build`. An asset is never replaced (`--clobber` is not used): an existing
asset with identical bytes is accepted as a no-op, a different one fails the job.

## What this does not claim

- The bundle is unsigned and has no attestation. The SHA-256 asset is published by the same
  workflow, so it checks transport only and does not prove origin.
- No Claude Desktop install, start or tool call was made by the project.
- The release job has not run: its first execution is the next release the owner publishes, and
  submitting the bundle to any directory is an owner action
  ([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)) that is not planned.
- Not in scope: an icon (DEC-012, no WLED logo), HTTP transport, signing, bundled configuration,
  Node tooling in CI.
