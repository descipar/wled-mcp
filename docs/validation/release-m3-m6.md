# Release 0.4.0 (milestones M3 to M6 and all work merged since 0.3.0)

## Preparation

Scope: repository changes only. The owner asked for the 0.4.0 release pull request, covering
the unreleased work of M3 to M6, and added that **all** work merged since `v0.3.0` belongs in
the release (coordinator session, 2026-11-13; paraphrased, no verbatim quote). M3, M4 and M5 close
without their own release ([DEC-032](../DECISIONS.md#dec-032--m3-closes-without-its-own-release),
[DEC-034](../DECISIONS.md#dec-034--m4-closes-without-its-own-release),
[DEC-036](../DECISIONS.md#dec-036--m5-closes-without-its-own-release)). That instruction covers the
preparation only; each publication step needs the owner's explicit instruction at that time
([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)), and no new decision was
recorded. In this preparation nothing was tagged, released, uploaded or published, the release
workflow and `mcp-publisher` were not run, no hardware, hub or deployed target was contacted and
no MCPHub reinstall is part of it ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).

Changes in this pull request:

- Version `0.4.0` in `pyproject.toml` (single source), `uv.lock` (project entry only, via
  `uv lock`) and both version fields of `server.json`. The MCPB manifest takes the version from
  `pyproject.toml` at build time (placeholder in the template). Synthetic release-candidate
  versions in `tests/test_mcpb_bundle.py` changed from a 0.4.0 form to a 1.2.3 form, because the
  version-literal test forbids the real version outside the allowlist.
- Tool count 33 to 37: `wled_preview_layout` (#29), `wled_start_signal`, `wled_cancel_signal`,
  `wled_get_signal_status` (#28). `tests/tool_contract.py` lists 37 tools (33 at tag `v0.3.0`; its
  diff against the tag adds exactly these four). No tool was removed or renamed; no breaking
  tool or schema change, so 0.4.0 under the `0.x` policy is sufficient.
- CHANGELOG 0.4.0 section (replaces "Unreleased") with migration notes: the symlinked snapshot
  root (#181), the fixed HTTP transport error bodies, the HTTP startup line without host and port,
  and the definition-directory scan cap. Behavior changes are listed under "Migration".
- README: layout preview and signals no longer marked unreleased, the MCPB sentence in the present
  tense, signals hardware limit, review note (200-line budget kept, README tests pass). ROADMAP rows
  M3 to M6 and the VALIDATION index point at this record.

## Completeness check

`git log v0.3.0..origin/main` at `df5c0d8` lists 25 commits. Each was assigned by hand to a
CHANGELOG 0.4.0 entry or to "documentation only, no package effect":

| Commits (PR) | Where it is in the changelog |
| --- | --- |
| #185 layout preview, #187 and #189 `colour_basis` | Added (preview), Changed (`colour_basis`) |
| #196 signals (#28) | Added (signals); #197 README bullet: README |
| #219 MCPB bundle (#151) | Added (bundle) |
| #209 parallel CI (#154) | Changed |
| #221 security review (#181) | Migration, Added (CI checks), Changed (fixes, snapshot root) |
| #212 Windows test suite (#191) | Changed (added in this PR; it was missing) |
| #193 usage feedback template | Added (added in this PR; it was missing) |
| #218 troubleshooting and architecture (#23) | Added (added in this PR; it was missing) |
| #194 README trim | Changed (added in this PR; it was missing) |
| #210 settings PIN and OTA lock record (#128), #230 launch report (#25) | Documentation and evidence |
| #208 discovery and enrollment contract (#198) | Documentation and evidence, stated as not implemented |
| #179, #182, #184, #186, #192, #195, #205, #206, #207, #211 (decisions, roadmap, role and workflow documents) | Documentation and evidence, one line; no package effect |

Items that were merged but missing from the earlier Unreleased text, now added: #181 beyond the
symlink note (error-body sanitising, startup diagnostics, unknown-key redaction, scan cap, CI
checks), #191, #193, #194, #218, #128, #25 and the status of #198. The file-level check
(`git diff v0.3.0..origin/main --stat` over `src`, `deploy`, `.github`, `scripts`, `pyproject.toml`,
`uv.lock`: 31 files) found no package change without an entry. The documents of M8 describe
behavior that does not exist in `src` (no `wled_discover_devices`, `wled_add_device` or
`wled_set_discovery_ranges`); the released package serves 37 tools.

Deliberately left out (not merged): open Dependabot pull requests #224 to #229 (setup-python,
checkout, CodeQL init, click, pydantic-core, hatchling), the M7 (rooms, #183) and M8 (#199 to
#204) implementation work, and every local or remote feature branch except this one.

## Verified before publication (local, macOS, Python 3.13, this branch)

| Check | Result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3545 passed, 45 skipped (platform and GNU-tool skips), 8 subtests |
| `ruff check .`, `ruff format --check .`, `ruff check src --select S --ignore S101` | PASS (291 files formatted) |
| `mypy` | PASS (59 source files) |
| `check_lock.py`, `check_agent_setup.py`, `check_private_identifiers.py`, `check_traceability.py` | PASS |
| `scripts/check_distribution.py` | PASS: wheel, clean install, setup commands, stdio, read-only profile, HTTP restart, uvx, hub example; 29 runtime versions |
| `uv build --no-build-isolation --offline --no-create-gitignore` (as in `publish.yml`) | sdist and wheel built; SHA-256 wheel `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3`, sdist `3c2a576e874dd916a601e7f2db66d1b3c7acc8a0f66699a8561284776d0425d9` (local build before the commit; the release hashes come from the tagged build and are not expected to equal these) |
| `twine check --strict` (twine 7.0.0) | PASS for both files |
| `deploy/build_mcpb.py --version 0.4.0` | built `wled-mcp-0.4.0.mcpb` (SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf`); the version check accepts the match |

Not run: the release guard `check_distribution.py --release-ref` (needs a tag), the bash-based
workflow tests that skip on macOS (they run in CI), Windows, a live check, Claude Desktop with
the bundle, the GitHub-hosted release workflow. No hardware evidence is needed for this change.
Hardware evidence of the included features is unchanged: signals ran twice on the test controller
([#28](issue-28.md)), the layout preview and the MCPB bundle have none.

## Owner-gated steps after the merge

Each on the owner's explicit instruction at that time; none is done, merging does not authorize
the next ([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release), DEC-023, DEC-030):

1. Merge this pull request (owner; admin merge only on explicit instruction, it is not docs-only).
2. Optionally refresh the open Dependabot pull requests first or leave them for later; they are not
   part of the release.
3. Create the annotated tag `v0.4.0` on the merge commit and publish the GitHub release (title only
   the version, notes from the changelog section). Publishing the release starts `publish.yml`.
4. Approve the `pypi` environment deployment in the GitHub UI after comparing the job summary
   (tag, commit, SHA-256 of both files).
5. Check PyPI: file names and SHA-256, the marker `mcp-name: io.github.descipar/wled-mcp` in
   `info.description`, and `uvx --isolated --python 3.13 --from wled-mcp==0.4.0 wled-mcp --version`.
6. Check the release assets of the first MCPB run: `wled-mcp-0.4.0.mcpb` and its `.sha256`, hash equal
   to the `build-mcpb` job summary (first run of the two bundle jobs; they do not gate PyPI).
7. Install a pinned `mcp-publisher`, verify it, `mcp-publisher login github`, `mcp-publisher publish`
   at the tagged commit, read the registry back.
8. Decide on a hub or service deployment of the new version on the deployed target (separate
   instruction and authorization; no MCPHub reinstall, DEC-037; the rollback checklist is
   [issue-25-rollback-plan.md](issue-25-rollback-plan.md)).
9. Close milestone M6 and confirm the M3 to M5 closure state in GitHub, after the release is done
   (DEC-030); record the publication facts in this file like [release-m2.md](release-m2.md).
