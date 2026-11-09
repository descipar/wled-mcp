# Issue #24 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-24-DEC-001 — Prepare registry metadata, drafts and the next patch release

- ID: ISSUE-24-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #24 only.
- Authority: human decision (owner instruction in the main coordinator session; chat is the
  normal channel for owner authority).
- Source: owner message in the main session on 2026-11-09 (no permalink): "Ja, mach so"
  (English: "Yes, do it that way"), answering the coordinator's proposed packet for #24
  (items 1 to 4 below and the technical defaults of ISSUE-24-DEC-002).
- Scope: issue #24 (S2-MARKET-01 to 03), one pull request that refers to the issue ("Refs",
  not "Closes"); the issue stays open because the fresh-MCPHub install test needs the
  published package.
- Decision: the following is authorized.
  1. A registry namespace marker in the README for `io.github.descipar/wled-mcp`.
  2. A locally validated root `server.json` for that name: the PyPI package, stdio through
     uvx, no `remotes`.
  3. Drafts only of the MCPM / local-catalog entry and of the hosted mcphub.app submission
     copy.
  4. Preparation of the next patch release in the same pull request (version bump,
     `uv.lock`, changelog).
- Not authorized: a Git tag, a GitHub release, a PyPI upload, installing, logging in to,
  validating with or publishing with `mcp-publisher`, any external issue, pull request or form
  submission, and any hardware or LAN contact. The `mcp-publisher validate` command is not used
  because it sends the file to an external service.
- Applicability / conditions / expiry: bounded to the listed work on this issue. It is not
  standing permission for publication or submission; each of those needs the owner's instruction
  at that time (DEC-023). The merge of the pull request follows DEC-022 and DEC-029 item 4
  (milestone M1, where #24 now sits per DEC-030: standing approval with a current-head PASS and
  green CI, while it is valid); a merge under it authorizes no publication step (DEC-030).
- Rationale supplied: none beyond the scope choice.
- Affected requirement IDs, files, issues and tests: S2-MARKET-01, S2-MARKET-02 (drafts),
  S2-MARKET-03 (not run); README.md, server.json, docs/listings/, docs/MARKETPLACE.md,
  docs/PUBLISHING.md, scripts/check_distribution.py, tests/test_registry_metadata.py; issue #24.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff (local packet under `.agent-runs/`).
- Revalidation needed / next action: owner merge decision; the owner actions listed in
  [PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release) after the release.
- Update 2026-11-09: the pull request was merged. Item 4 (a patch release) is superseded in
  part by DEC-030 item 4: the milestone release needs a minor version; the prepared patch
  version was never tagged or published and was replaced by a minor version in a follow-up
  change. Items 1 to 3 stand; item 3's drafts are narrowed by ISSUE-24-DEC-003.

## ISSUE-24-DEC-002 — Technical defaults for the registry packet

- ID: ISSUE-24-DEC-002
- Recorded date: 2026-11-09
- Status: active for issue #24 only; technical proposal by the coordinator under
  ISSUE-24-DEC-001, not an owner decision. The owner may overrule any item.
- Authority: technical proposal (coordinator).
- Source: issue-24 coordinator session, 2026-11-09.
- Scope: the issue-24 packet.
- Decision:
  1. `server.json` in the repository root; `$schema` is the 2025-12-11 server schema.
  2. Name `io.github.descipar/wled-mcp` (DEC-012); title "WLED MCP (unofficial)"; the
     description (at most 100 characters) says unofficial and not affiliated with the WLED
     project; repository and website URLs point to the repository.
  3. The marker `<!-- mcp-name: io.github.descipar/wled-mcp -->` follows the README intro
     paragraph and contains no link.
  4. Exactly one package entry and no `remotes`: `pypi`, identifier `wled-mcp`, the version of
     `project.version`, runtime hint `uvx`, transport stdio. Runtime arguments mirror README
     step 3; package arguments are `--transport stdio`, `--config {config_path}` and
     `--data-dir {data_dir}`, whose variables are required, `filepath`, not secret and carry a
     description only. No environment variables.
  5. The MCPM draft `docs/listings/mcpm-wled-mcp.json` follows the MCPM manifest schema, with
     an unpinned uvx installation, the two paths as `${...}` environment references, synthetic
     example paths, no `is_official` and no tools array.
  6. The hosted-directory copy `docs/listings/mcphub-app-submission.md` is English and
     impersonal, states that the form fields are unverified and that the status is draft, and
     uses no WLED logo.
  7. The published schemas are not vendored. `tests/test_registry_metadata.py` holds offline
     invariants with negative controls; `docs/validation/issue-24.md` records one live
     validation run against the published schemas and states that the publisher's own checks
     were not run.
  8. `scripts/check_distribution.py` requires `mcp-name: <name of server.json>` in the wheel
     `METADATA`, which the publish workflow's smoke test already runs.
  9. The release preparation bumps `pyproject.toml` to the next patch version, refreshes
     `uv.lock` and writes the changelog from `git log v0.1.2..HEAD`; the changes are additive,
     so this is a patch release ([versioning](../contract/versioning.md)). The default of
     bumping in this pull request (Q1) is adopted.
  10. `docs/PUBLISHING.md` documents the registry steps after the PyPI release; each needs the
     owner's instruction at that time and no automation is wired. `mcp-publisher validate` is
     not used (Q2).
  11. Currently true wording (README "no registry entry", the Status paragraph) stays
     unchanged.
- Applicability / conditions / expiry: until the owner changes it or the listed work is
  merged.
- Rationale supplied: not supplied (coordinator proposal).
- Affected requirement IDs, files, issues and tests: as ISSUE-24-DEC-001;
  tests/test_version_source.py (`server.json` allowlisted and checked on its own),
  scripts/ci_scope.py (reader test listed).
- Supersedes / superseded by: none.
- Propagated to roles / packet references: via the coordinator handoff.
- Revalidation needed / next action: review of the pull request. Implementer note: item 4's
  `--isolated` is written as a positional argument with the fixed value `--isolated` (a bare
  named argument without a value is schema-valid but leaves clients free to prompt for a
  value); this is a deviation from "named flag" in the proposal and is reported to the
  coordinator.

## ISSUE-24-DEC-003 — Official MCP Registry only; no MCPM or hosted-directory submission for now

- ID: ISSUE-24-DEC-003
- Recorded date: 2026-11-09
- Status: active for issue #24 only.
- Authority: human decision (owner instruction in the main coordinator session; chat is the
  normal channel for owner authority).
- Source: owner message in the main session on 2026-11-09 (no permalink): once milestone M1 is
  closed, the server shall be findable in the MCPHub registry, which is the official MCP
  Registry; the MCPM contribution and the hosted mcphub.app form are not wanted for now.
- Scope: issue #24 (S2-MARKET-01 to 03), the listing routes only.
- Decision: the goal is that the server is findable through the official MCP Registry after M1
  closes. The MCPM / local-catalog contribution and the hosted mcphub.app submission are dropped
  for now; their drafts stay in `docs/listings/` as unsubmitted drafts and are not maintained
  for a submission. A tag, a GitHub release, a PyPI upload, `mcp-publisher login` and
  `mcp-publisher publish` each need the owner's explicit instruction at that time.
- Applicability / conditions / expiry: bounded to #24 and "for now"; the owner may reinstate
  either route. It is not standing permission for any publication or submission (DEC-023,
  DEC-030).
- Rationale supplied: the MCPHub registry view is the official registry; no other reason given.
- Affected requirement IDs, files, issues and tests: S2-MARKET-02 (not planned, drafts only);
  docs/MARKETPLACE.md, docs/PUBLISHING.md, tests/test_registry_metadata.py (status vocabulary).
- Supersedes / superseded by: narrows ISSUE-24-DEC-001 item 3; supersedes nothing else.
- Propagated to roles / packet references: via the coordinator handoff.
- Revalidation needed / next action: the 0.2.0 release chain in
  [PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release), step by step on
  the owner's instruction.

## ISSUE-24-DEC-004 — Per-step publication instructions for the M1 release

- ID: ISSUE-24-DEC-004
- Recorded date: 2026-11-09
- Status: executed (each instruction was used once; nothing remains authorized).
- Authority: human decision (owner chat instructions in the main coordinator session; recorded by
  the coordinator).
- Source: owner chat messages in the main session on 2026-11-09 (no permalinks): separate
  instructions for the tag and GitHub release, for approving the `pypi` environment of the
  publish run, for signing in with `mcp-publisher login github` (run by the owner) and for
  `mcp-publisher publish`.
- Scope: issue #24 and the M1 minor release only, under ISSUE-24-DEC-003 and DEC-030.
- Decision: each of these steps was authorized once, when instructed: tag and GitHub release of
  the M1 release, approval of the `pypi` environment for that publish run, the publisher login,
  and the registry publish of `server.json`.
- Applicability / conditions / expiry: bounded to that release and registry entry; consumed by
  execution. It is not standing permission: a later release, tag, upload or registry publish needs
  its own instruction (DEC-023, DEC-030).
- Rationale supplied: none beyond the instructions.
- Affected requirement IDs, files, issues and tests: S2-MARKET-01; docs/PUBLISHING.md,
  docs/MARKETPLACE.md, README.md, docs/validation/issue-24.md; issue #24.
- Supersedes / superseded by: completes the DEC-030 open question for M1 together with
  ISSUE-24-DEC-003; supersedes nothing.
- Propagated to roles / packet references: via the coordinator handoff.
- Revalidation needed / next action: none for these steps. The fresh-install test (S2-MARKET-03)
  is separate and not recorded here.
