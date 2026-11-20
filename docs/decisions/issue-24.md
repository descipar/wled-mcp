# Issue #24 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09. Human sources are owner chat messages in the main coordinator session, no permalinks.

## ISSUE-24-DEC-001 — Prepare registry metadata, drafts and the next patch release

- ID: ISSUE-24-DEC-001
- Status: active for issue #24 only.
- Authority: human decision ("Ja, mach so" (English: "Yes, do it that way")), answering the coordinator's proposed packet (items 1 to 4 and ISSUE-24-DEC-002).
- Scope: #24 (S2-MARKET-01 to 03), one PR with "Refs" (not "Closes"); the issue stays open because the fresh-MCPHub install test needs the published package.
- Decision: authorized: (1) a registry namespace marker in the README for `io.github.descipar/wled-mcp`; (2) a locally validated root `server.json` (PyPI package, stdio through uvx, no `remotes`); (3) drafts only of the MCPM / local-catalog entry and the hosted mcphub.app submission copy; (4) preparing the next patch release in the same PR (version bump, `uv.lock`, changelog).
- Not authorized: Git tag, GitHub release, PyPI upload, installing, logging in to, validating with or publishing with `mcp-publisher` (`validate` sends the file to an external service), any external issue, PR or form submission, hardware or LAN contact.
- Conditions: not standing permission for publication; each step needs an instruction at that time (DEC-023). Merge follows DEC-022 and DEC-029 item 4 (M1, #24 per DEC-030) and authorizes no publication step.
- Update 2026-11-09: the PR was merged. Item 4 is superseded in part by DEC-030 item 4 (the milestone release needs a minor version); the prepared patch version was never tagged or published. Items 1 to 3 stand; item 3 is narrowed by ISSUE-24-DEC-003.

## ISSUE-24-DEC-002 — Technical defaults for the registry packet

- ID: ISSUE-24-DEC-002
- Status: active for issue #24 only; technical proposal by the coordinator under ISSUE-24-DEC-001, not an owner decision.
- Authority: technical proposal (coordinator).
- Scope: the issue-24 packet (S2-MARKET-01 to 03).
- Decision:
  1. Root `server.json`, `$schema` the 2025-12-11 server schema.
  2. Name `io.github.descipar/wled-mcp` (DEC-012); title "WLED MCP (unofficial)"; description at most 100 characters, unofficial and not affiliated; repository and website URLs to the repository.
  3. Marker `<!-- mcp-name: io.github.descipar/wled-mcp -->` after the README intro paragraph, no link.
  4. One package entry, no `remotes`: `pypi`, `wled-mcp`, version of `project.version`, runtime hint `uvx`, stdio; runtime arguments mirror README step 3; package arguments `--transport stdio`, `--config {config_path}`, `--data-dir {data_dir}` (required, `filepath`, not secret); no environment variables. `--isolated` is a positional argument with the fixed value (deviation from "named flag", reported).
  5. MCPM draft `docs/listings/mcpm-wled-mcp.json`: unpinned uvx, paths as `${...}` references, synthetic paths, no `is_official`, no tools array.
  6. Hosted-directory copy `docs/listings/mcphub-app-submission.md`: English, impersonal, fields unverified, draft status, no WLED logo.
  7. Published schemas are not vendored; `tests/test_registry_metadata.py` holds offline invariants with negative controls; `docs/validation/issue-24.md` records one live schema validation and that the publisher's checks were not run.
  8. `scripts/check_distribution.py` requires `mcp-name: <name of server.json>` in the wheel `METADATA`.
  9. Release preparation: patch bump, `uv.lock`, changelog from `git log v0.1.2..HEAD` (additive, [versioning](../contract/versioning.md)); bump in this PR.
  10. `docs/PUBLISHING.md` documents registry steps after the PyPI release; no automation; `mcp-publisher validate` not used.
  11. Currently true wording (README "no registry entry", Status paragraph) stays.
- Conditions: until the owner changes it or the work is merged.

## ISSUE-24-DEC-003 — Official MCP Registry only; no MCPM or hosted-directory submission for now

- ID: ISSUE-24-DEC-003
- Status: active for issue #24 only.
- Authority: human decision (paraphrased: once M1 closes the server shall be findable in the MCPHub registry, i.e. the official MCP Registry; MCPM contribution and hosted mcphub.app form not wanted for now).
- Scope: #24 listing routes only (S2-MARKET-01 to 03).
- Decision: the goal is findability through the official MCP Registry after M1 closes. The MCPM / local-catalog contribution and the hosted mcphub.app submission are dropped for now; their drafts stay in `docs/listings/` unsubmitted and unmaintained. Tag, GitHub release, PyPI upload, `mcp-publisher login` and `mcp-publisher publish` each need an explicit instruction at that time.
- Conditions: bounded to #24 and "for now"; the owner may reinstate a route; not standing permission (DEC-023, DEC-030). Narrows ISSUE-24-DEC-001 item 3. Next: the 0.2.0 release chain in [PUBLISHING.md](../PUBLISHING.md#registry-listing-after-the-pypi-release).

## ISSUE-24-DEC-004 — Per-step publication instructions for the M1 release

- ID: ISSUE-24-DEC-004
- Status: executed (each instruction was used once; nothing remains authorized).
- Authority: human decision (separate owner chat instructions).
- Scope: #24 and the M1 minor release only, under ISSUE-24-DEC-003 and DEC-030 (S2-MARKET-01).
- Decision: authorized once each: tag and GitHub release of the M1 release, approval of the `pypi` environment for that publish run, the publisher login (run by the owner), and the registry publish of `server.json`.
- Conditions: consumed by execution; a later release, tag, upload or registry publish needs its own instruction (DEC-023, DEC-030). The fresh-install test (S2-MARKET-03) is separate. Completes the DEC-030 open question for M1 with ISSUE-24-DEC-003.

## ISSUE-24-DEC-005 — Waive the hub-side start of an adapted registry entry

- ID: ISSUE-24-DEC-005
- Status: active for issue #24 only.
- Authority: human decision (2026-11-10: "nein, es reicht so als installiert" (English: "no, it is enough as installed as it is")), answering whether the corrected entry should be started once in the owner's hub.
- Scope: item 6 of #24 (fresh install from generated configuration, S2-MARKET-03) only.
- Decision: the hub-side start of the manually adapted registry entry is waived. The registry listing, the observed install dialog with the documented manual adaptation ([validation/issue-24.md](../validation/issue-24.md#mcphub-registry-tab-observed-install-dialog-2026-11-10)) and the local launch check of the composed command are sufficient for item 6.
- Conditions: closed by waiver, not observation: the install-test row stays "not run" and says "waived by the owner". Claims nothing about other hosts; no publication permission. A later hub-side observation can be recorded without changing this. Closes the follow-up of ISSUE-24-DEC-004.
