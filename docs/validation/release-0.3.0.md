# Release 0.3.0 preparation (milestone M2)

Scope: repository changes only ([DEC-031](../DECISIONS.md#dec-031--release-scope-for-milestone-m2)).
Nothing was tagged, released, uploaded or published, `mcp-publisher` was not used and no
hardware or hub was contacted.

- Version `0.3.0` in `pyproject.toml` (single source), `uv.lock` (project entry only) and both
  version fields of `server.json`. Historical mentions of 0.2.0 are unchanged.
- Tool count 31 to 33, taken from the tool contract's table and the expected-tool list in
  `tests/tool_contract.py` (both 33; 31 at tag `v0.2.0`): the additions are
  `wled_get_live_snapshot` (#150) and `wled_explain_lighting` (#30).
- CHANGELOG 0.3.0 section, README capability entry and limits, ROADMAP M2 row, PUBLISHING note.
- Live evidence is unchanged and summarized honestly: [#150](issue-150.md) (snapshot endpoint
  unavailable, HTTP 501) and [#30](issue-30.md) (one read-only explanation call).
- Remaining owner-gated steps, each on explicit instruction: tag `v0.3.0`, GitHub release, PyPI
  upload, registry publication ([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release)).
