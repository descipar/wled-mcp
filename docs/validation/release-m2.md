# Release 0.3.0 (milestone M2)

## Preparation

Scope: repository changes only ([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).
In this preparation nothing was tagged, released, uploaded or published, `mcp-publisher` was
not used and no hardware or hub was contacted; the publication followed as recorded below.

- Version `0.3.0` in `pyproject.toml` (single source), `uv.lock` (project entry only) and both
  version fields of `server.json`. Historical mentions of 0.2.0 are unchanged.
- Tool count 31 to 33, taken from the tool contract's table and the expected-tool list in
  `tests/tool_contract.py` (both 33; 31 at tag `v0.2.0`): the additions are
  `wled_get_live_snapshot` (#150) and `wled_explain_lighting` (#30).
- CHANGELOG 0.3.0 section, README capability entry and limits, ROADMAP M2 row, PUBLISHING note.
- Live evidence is unchanged and summarized honestly: [#150](issue-150.md) (snapshot endpoint
  unavailable, HTTP 501) and [#30](issue-30.md) (one read-only explanation call).
- Owner-gated steps, each on explicit instruction: tag `v0.3.0`, GitHub release, PyPI upload,
  registry publication ([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release)).

## Release and registry publication 2026-11-11

Recorded by the coordinator from its own commands and readbacks in the owner's session
([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).

- **Tag and release:** the annotated tag `v0.3.0` and the GitHub release `v0.3.0` (title only
  the version, notes from the changelog section) were created on the merge commit
  `64615a89d83d96f8ed4643f7c3419899f1fdbac0` of PR #178 (main, CI green) on the owner's
  instruction.
- **PyPI upload:** publishing the release started `publish.yml` (run 42999302357). The build
  and smoke-test job succeeded. The `pypi` environment approval was recorded in the GitHub UI
  by the owner's account (not by an agent) and the publish job succeeded. The coordinator had
  not announced that publishing the release also starts the upload workflow; the owner's
  later instruction covered the remaining steps. PyPI serves the 0.3.0 files with SHA-256
  `84050ec257b0c95222bf728b288d25b81862f97384e71d15da29da888276218f` (wheel) and
  `d1cc52e6c59b6b84703588705606257826da48f944a48278e347ff069bac1ac4` (sdist), identical to the
  `SHA256SUMS` the publish job verified; no file is yanked.
- **Marker:** `https://pypi.org/pypi/wled-mcp/0.3.0/json`, `info.description`, contains
  `mcp-name: io.github.descipar/wled-mcp`; `requires_python` is `<3.14,>=3.13`.
- **Install check:** `uvx --isolated --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version`
  from an empty directory printed `wled-mcp 0.3.0`.
- **Registry publish:** `mcp-publisher` 1.8.9 (asset `mcp-publisher_darwin_arm64.tar.gz`,
  SHA-256 `4175f7281c42ef2f6666d086974aa01f3eecd68a067cfb8329f0a7e620db6e3a`, equal to the line
  of `registry_1.8.9_checksums.txt`; the Sigstore bundle was not verified) was downloaded into
  an empty scratch directory, outside the repository. The owner ran `mcp-publisher login
  github`; `mcp-publisher publish` in the repository root at the tagged commit printed
  "Successfully published io.github.descipar/wled-mcp version 0.3.0".
- **Readback:** `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.descipar/wled-mcp`
  returns the entries 0.2.0 (status active, `isLatest` false) and 0.3.0 (status active,
  `isLatest` true, `publishedAt` 2026-11-11T10:02:17Z).

Not done: no hub deployment, no MCPHub install test and no other listing. No private address
or device name is part of the release files or notes.
