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

## Release and registry publication 2026-11-13

Recorded by the coordinator from the main session's own commands and readbacks, each step on the
owner's explicit instruction ("everything of the release", 2026-11-13;
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)).

- **Merge:** PR #231 was merged as squash commit `5bd45b96eb4779cd73620dff2c7a1ee3c61a5e71` by
  admin merge on the owner's instruction; CI was green on head `aa34822`.
- **Tag and release:** the annotated tag `v0.4.0` on `5bd45b9` and the GitHub release `v0.4.0`
  (title only the version, notes from the CHANGELOG 0.4.0 section) were created on the owner's
  instruction.
- **Workflow:** `publish.yml` run 43414020842: all four jobs succeeded (build and smoke test,
  MCPB build, publish to PyPI, attach MCPB). The `pypi` environment deployment was approved
  through the API by the main session on the owner's instruction, after the hash comparison
  below. The job summary itself was not readable through the API; the upload job re-verifies the
  files against the build job's checksums.
- **Hash check:** wheel `wled_mcp-0.4.0-py3-none-any.whl` SHA-256
  `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3` and sdist
  `wled_mcp-0.4.0.tar.gz` SHA-256 `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc`
  from the run's artifacts equal an independent rebuild (`uv build`, macOS arm64) from a fresh
  clone of the tag. The PyPI JSON for 0.4.0 shows the same two values, and its description
  contains `mcp-name: io.github.descipar/wled-mcp`.
- **Install check:** `uvx --isolated --python 3.13 --from wled-mcp==0.4.0 wled-mcp --version` in an
  empty directory with `GH_TOKEN` and `GITHUB_TOKEN` unset printed `wled-mcp 0.4.0`.
- **MCPB (first run of the bundle jobs, [#151](issue-151.md#first-release-run)):** release assets
  `wled-mcp-0.4.0.mcpb` (15006 bytes) and `wled-mcp-0.4.0.mcpb.sha256`; SHA-256
  `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf` equals the `.sha256` file and
  the build job artifact. The `build-mcpb` job summary hash was not read via the API. No Claude
  Desktop run (unchanged).
- **Registry:** `mcp-publisher` 1.8.9 (darwin_arm64, SHA-256
  `4175f7281c42ef2f6666d086974aa01f3eecd68a067cfb8329f0a7e620db6e3a`, equal to the line of
  `registry_1.8.9_checksums.txt`) was run from a scratch directory outside the repository.
  Verification is by checksum only: `gh attestation verify` found no SLSA provenance and `cosign`
  is not installed. The owner ran `mcp-publisher login github`; `mcp-publisher publish` at the
  tagged clone (`server.json` 0.4.0 in both version fields) printed "Successfully published".
  `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.descipar/wled-mcp`
  lists 0.2.0, 0.3.0 and 0.4.0; 0.4.0 is active, `isLatest` true, `publishedAt`
  2026-11-13T11:54:32Z.

### Closure state and what is still owner-gated

- [DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release): the M6 closure
  condition (a minor release and an adapted README) is met; M3, M4 and M5 closed without releases of
  their own ([DEC-032](../DECISIONS.md#dec-032--m3-closes-without-its-own-release),
  [DEC-034](../DECISIONS.md#dec-034--m4-closes-without-its-own-release),
  [DEC-036](../DECISIONS.md#dec-036--m5-closes-without-its-own-release)). Closing the milestone
  in GitHub is not a coordinator action in [AGENT-WORKFLOW.md](../AGENT-WORKFLOW.md) (the
  coordinator prepares, the owner decides), so it is left to the owner or the main session.
- Not done: deployment of 0.4.0 on the deployed target (it still runs 0.3.0; separate instruction
  and authorization, no MCPHub reinstall, [DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).
  Upgrade and rollback evidence for 0.3.0 to 0.4.0 stays pending until that deployment.
