# Release 0.4.0 (milestones M3 to M6 and all work merged since 0.3.0)

## Preparation

Scope: repository changes only. The owner asked for the 0.4.0 release pull request covering the
unreleased work of M3 to M6 and **all** work merged since `v0.3.0` (coordinator session, 2026-11-13;
paraphrased). M3, M4 and M5 close without their own release
([DEC-032](../DECISIONS.md#dec-032--m3-closes-without-its-own-release),
[DEC-034](../DECISIONS.md#dec-034--m4-closes-without-its-own-release),
[DEC-036](../DECISIONS.md#dec-036--m5-closes-without-its-own-release)). The instruction covers
preparation only; each publication step needs the owner's explicit instruction
([DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)). The preparation tagged, released,
uploaded and published nothing, contacted no hardware, hub or target, and involves no MCPHub reinstall
([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).

Changes in the pull request:

- Version `0.4.0` in `pyproject.toml` (single source), `uv.lock` (project entry only) and both
  `server.json` versions; the MCPB manifest takes it from `pyproject.toml` at build time. Synthetic
  release-candidate versions in `tests/test_mcpb_bundle.py` changed to a 1.2.3 form (the version-literal
  test forbids the real version outside the allowlist).
- Tool count 33 to 37: `wled_preview_layout` (#29), `wled_start_signal`, `wled_cancel_signal`,
  `wled_get_signal_status` (#28); none removed or renamed, no breaking change.
- CHANGELOG 0.4.0 section with migration notes (symlinked snapshot root #181, fixed HTTP transport
  error bodies, HTTP startup line without host and port, definition-directory scan cap).
- README, ROADMAP rows M3 to M6 and the VALIDATION index updated.

## Completeness check

`git log v0.3.0..origin/main` at `df5c0d8` lists 25 commits, each assigned by hand to a CHANGELOG entry
or to "documentation only, no package effect". The file-level check over `src`, `deploy`, `.github`,
`scripts`, `pyproject.toml`, `uv.lock` (31 files) found no package change without an entry. Entries
added in this PR because they were missing: #181 details, #191, #193, #194, #218, #128, #25 and the
status of #198. The M8 documents describe behavior that does not exist in `src`; the package serves 37
tools.

Left out (not merged): Dependabot pull requests #224 to #229, M7 rooms (#183), M8 (#199 to #204) and
every other feature branch.

## Verified before publication (local, macOS, Python 3.13, this branch)

| Check | Result |
| --- | --- |
| `uv run --frozen pytest -n auto` | 3545 passed, 45 skipped (platform and GNU-tool skips), 8 subtests |
| `ruff check .`, `ruff format --check .`, `ruff check src --select S --ignore S101`, `mypy` | PASS (291 files; 59 source files) |
| `check_lock.py`, `check_agent_setup.py`, `check_private_identifiers.py`, `check_traceability.py` | PASS |
| `scripts/check_distribution.py` | PASS: wheel, clean install, setup commands, stdio, read-only profile, HTTP restart, uvx, hub example; 29 runtime versions |
| `uv build --no-build-isolation --offline --no-create-gitignore`, `twine check --strict` | built and PASSED; local wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3` (release hashes come from the tagged build) |
| `deploy/build_mcpb.py --version 0.4.0` | built `wled-mcp-0.4.0.mcpb` (SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf`) |

Not run: `check_distribution.py --release-ref` (needs a tag), bash-based workflow tests that skip on
macOS (CI runs them), Windows, a live check, Claude Desktop with the bundle, the GitHub-hosted
workflow. Hardware evidence of the included features is unchanged: signals ran twice on the test
controller ([#28](issue-28.md)); layout preview and the MCPB bundle have none.

## Owner-gated steps after the merge

Each on the owner's explicit instruction at that time; merging does not authorize the next
([PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release), DEC-023, DEC-030):

1. Merge the PR (admin merge only on explicit instruction; not docs-only).
2. Dependabot pull requests are not part of the release.
3. Annotated tag `v0.4.0` on the merge commit and the GitHub release (starts `publish.yml`).
4. Approve the `pypi` environment deployment after comparing the job summary.
5. Check PyPI file names and SHA-256, the `mcp-name` marker and `uvx ... --version`.
6. Check the MCPB assets of the first bundle run (hash equal to the job summary; the bundle jobs do not
   gate PyPI).
7. Pinned `mcp-publisher`, login, publish at the tagged commit, read the registry back.
8. A deployment of the new version on the target is a separate instruction (no MCPHub reinstall,
   DEC-037; rollback checklist [issue-25-rollback-plan.md](issue-25-rollback-plan.md)).
9. Close M6 and confirm M3 to M5 in GitHub after the release (DEC-030); record the facts here like
   [release-m2.md](release-m2.md).

## Release and registry publication 2026-11-13

Recorded by the coordinator from the main session's commands and readbacks, each step on the owner's
explicit instruction ("everything of the release", 2026-11-13;
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release)).

- **Merge:** PR #231 squash-merged as `5bd45b96eb4779cd73620dff2c7a1ee3c61a5e71` by admin merge on
  the owner's instruction; CI green on head `aa34822`.
- **Tag and release:** annotated tag `v0.4.0` on `5bd45b9` and GitHub release `v0.4.0`.
- **Workflow:** `publish.yml` run 43414020842: all four jobs succeeded (build and smoke test, MCPB
  build, PyPI publish, attach MCPB). The `pypi` deployment was approved through the API by the main
  session on the owner's instruction after the hash comparison; the job summary was not readable via
  the API, the upload job re-verifies the files against the build job's checksums.
- **Hash check:** wheel SHA-256 `4c9e3c30c0f744bf9dd2f6f5f5d961bcbe1fd9a72db38144ce9a7a9a201adba3` and
  sdist `a47dacf52ecb09f86d5bfa6ed0445cee038d974d8b5e29aedb35b8a4ae265afc` from the run's artifacts
  equal an independent rebuild (macOS arm64) from a fresh clone of the tag; PyPI shows the same values
  and the `mcp-name: io.github.descipar/wled-mcp` marker.
- **Install check:** `uvx --isolated --python 3.13 --from wled-mcp==0.4.0 wled-mcp --version` in an
  empty directory without GitHub credentials printed `wled-mcp 0.4.0`.
- **MCPB (first bundle run, [#151](issue-151.md#first-release-run)):** assets `wled-mcp-0.4.0.mcpb`
  (15006 bytes) and `.sha256`; SHA-256 `a6ccec213a71193c832783a9664d164c071d7e7d1527e34eb42c1b85a0cc2daf`
  equals the `.sha256` file and the build artifact; the `build-mcpb` summary hash was not read via the
  API; no Claude Desktop run.
- **Registry:** `mcp-publisher` 1.8.9 (darwin_arm64, checksum equal to the release checksums file;
  `gh attestation verify` found no SLSA provenance, `cosign` not installed) run outside the repository.
  After the owner's `login github`, `publish` at the tagged clone printed "Successfully published".
  The registry lists 0.2.0, 0.3.0 and 0.4.0; 0.4.0 active, `isLatest` true, `publishedAt`
  2026-11-13T11:54:32Z.

### Closure state and what is still owner-gated

- [DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release): the M6 closure
  condition (a minor release and an adapted README) is met; M3 to M5 closed without own releases
  (DEC-032, DEC-034, DEC-036). Closing the milestone in GitHub is not a coordinator action
  ([AGENT-WORKFLOW.md](../AGENT-WORKFLOW.md)); it is left to the owner or the main session.
- Deployment of 0.4.0 on the target was done afterwards on a separate owner instruction
  ([deploy-0.4.0.md](deploy-0.4.0.md); update from 0.3.0 succeeded, no MCPHub reinstall). The rollback
  after 0.4.0 (to 0.3.0) was not run and stays pending.
