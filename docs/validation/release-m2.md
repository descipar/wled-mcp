# Release 0.3.0 (milestone M2)

## Preparation

Scope: repository changes only ([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).
Nothing was tagged, released, uploaded or published in this step; no hardware or hub was contacted.

- Version `0.3.0` in `pyproject.toml` (single source), `uv.lock` (project entry) and both
  `server.json` version fields.
- Tool count 31 to 33 (tool contract table and `tests/tool_contract.py`): `wled_get_live_snapshot`
  (#150) and `wled_explain_lighting` (#30).
- CHANGELOG 0.3.0 section, README capability entry and limits, ROADMAP M2 row, PUBLISHING note.
- Live evidence unchanged: [#150](issue-150.md) (snapshot endpoint unavailable, HTTP 501) and
  [#30](issue-30.md) (one read-only explanation call).
- Owner-gated steps, each on explicit instruction: tag, GitHub release, PyPI upload, registry
  publication ([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release)).

## Release and registry publication 2026-11-11

Recorded by the coordinator from its own commands and readbacks in the owner's session
([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).

- **Tag and release:** annotated tag `v0.3.0` and GitHub release `v0.3.0` on merge commit
  `64615a89d83d96f8ed4643f7c3419899f1fdbac0` of PR #178 (main, CI green), on the owner's instruction.
- **PyPI upload:** publishing the release started `publish.yml` (run 42999302357); build and smoke-test
  succeeded, the `pypi` environment approval was given by the owner's account in the GitHub UI, the
  publish job succeeded. The coordinator had not announced that the release also starts the upload; the
  owner's later instruction covered the remaining steps. PyPI wheel SHA-256
  `84050ec257b0c95222bf728b288d25b81862f97384e71d15da29da888276218f`, sdist
  `d1cc52e6c59b6b84703588705606257826da48f944a48278e347ff069bac1ac4`, identical to the verified
  `SHA256SUMS`; nothing yanked.
- **Marker:** PyPI `info.description` contains `mcp-name: io.github.descipar/wled-mcp`;
  `requires_python` `<3.14,>=3.13`.
- **Install check:** `uvx --isolated --python 3.13 --from wled-mcp==0.3.0 wled-mcp --version` printed
  `wled-mcp 0.3.0`.
- **Registry publish:** `mcp-publisher` 1.8.9 (SHA-256 equal to the published checksum line; Sigstore
  bundle not verified) downloaded into an empty scratch directory; the owner ran `mcp-publisher login
  github`; `publish` at the tagged commit printed "Successfully published io.github.descipar/wled-mcp
  version 0.3.0".
- **Readback:** the registry search returns 0.2.0 (active, not latest) and 0.3.0 (active, latest,
  `publishedAt` 2026-11-11T10:02:17Z).

Not done: no hub deployment, no MCPHub install test, no other listing. No private address or device name
is part of the release files or notes.
