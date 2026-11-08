# Issue #16 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-16-DEC-001 — Inventory reload and discovery surface

- ID: ISSUE-16-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #16.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-16/packet.md` (Q1, Q2): "alles nach empfehlung"
  (English: "everything as recommended"); no permalink.
- Scope: issue #16 (S2-SETUP-02, DEV-03 remainder of ISSUE-13-DEC-001).
- Decision:
  - Q1 option A: inventory changes use `wled-mcp config validate` followed by the
    documented restart. In-process reload (for example on SIGHUP) is not part of
    stage 2; the deferral in ISSUE-13-DEC-001 is closed as "not needed".
  - Q2 option A: discovery is a CLI-only `wled-mcp discover` command implemented with
    the Python standard library (one-shot mDNS query, no new runtime dependency). It
    reports candidates and prints the enrollment command. It is not exposed as an MCP
    tool and never writes the inventory itself.
- Applicability / conditions / expiry: issue #16. Discovery runs only on explicit CLI
  invocation; the project rule against unrequested discovery scans stays in force.
  The WLED mDNS service type and TXT fields must be verified against the pinned WLED
  source and recorded in docs/SOURCES.md before implementation.
- Rationale supplied: none beyond accepting the packet recommendations; the packet
  rationale (validate removes the documented outage risk; no new dependency or license
  review; no model-triggered network scan) is agent analysis.
- Affected requirement IDs, files, issues and tests: S2-SETUP-02, DEV-03; issue #16
  CLI, docs/DEPLOYMENT.md, quickstart (#23).
- Supersedes / superseded by: closes the in-process reload deferral of
  ISSUE-13-DEC-001 (that entry stays as recorded).
- Propagated to roles / packet references: issue-16 packet; refresh against main before
  #16 starts (Track A, after #21).
- Revalidation needed / next action: none before implementation.

## ISSUE-16-DEC-002 — Technical defaults TD-16-1 to TD-16-10

- ID: ISSUE-16-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #16.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: coordinator acceptance on 2026-11-08 of the technical defaults TD-16-1 to
  TD-16-10 in the issue-16 requirements packet (`.agent-runs/stage2/issue-16/packet.md`,
  refresh 1, pinned to main `f8a92ae`), together with the packet's two open coordinator
  choices; recorded in the first #16 implementation PR.
- Scope: issue #16 (S2-SETUP-01 to -03, DEV-03 and OPS-04 remainders). #20 and #23 may
  cite it as design input; it is not a global rule.
- Decision: the packet's TD-16-1 to TD-16-10, in summary:
  - TD-16-1 CLI shape: `cli.build_parser()`; no subcommand = the unchanged serve
    invocation; subcommands `config init|add-device|validate`, `doctor` and (second PR)
    `discover`; serve options with a subcommand are a usage error; `--format text|json`;
    no stdin; exit codes 0 ok, 1 problem found, 2 usage, 3 internal; JSON carries
    `schema_version` 1 and `command`.
  - TD-16-2 absolute `--config`/`--data-dir` (or environment) only; no default lookup.
  - TD-16-3 `config init` writes only the selected file; `config add-device` appends one
    `[[devices]]` block textually, validates the complete result with the startup
    validator, rejects an equal normalized `base_url` and writes atomically (temporary
    file, fsync, `os.replace`), aborting if the file changed; new files 0600 on POSIX;
    no token generation, no device contact, no TOML writer dependency.
  - TD-16-4 `config validate` shares `validate_document` with startup; optional
    `--data-dir` and `--check-backups`; never contacts devices.
  - TD-16-5 read-only `doctor` with runtime, configuration, storage, device and
    optional endpoint checks; device checks through the in-process `wled_get_state`
    envelope and `compat.support_warning` only (no `readmodels`/`capabilities` import);
    endpoint check with `initialize` + `ping` and the service's credential reader.
  - TD-16-6 sanitized `doctor --export` built from an allowlist.
  - TD-16-7 OPS-04 remainder: doctor covers every listed condition; serve prints one
    advisory stderr line when the backups location is not writable and still starts;
    tool-level `BACKUP_FAILED` unchanged; doctor codes are CLI contract, not MCP codes.
  - TD-16-8 discovery (second PR): standard-library one-shot IPv4 mDNS query, bounded
    window and candidate cap, no unicast probes, never automatic.
  - TD-16-9 documentation in `docs/contract/cli.md` and `docs/validation/issue-16.md`
    with sorted link lines.
  - TD-16-10 two PRs; no new runtime or development dependency.
  - Coordinator choices: no no-op `config migrate` (only schema 1 exists, so there is
    nothing to migrate; the "`config validate` family" sentence in
    docs/contract/versioning.md is reworded instead); no `--create-data-dir` for
    `config init` (AC2: only the selected configuration is written); #20 starts after
    the second #16 PR (plan order unchanged).
- Applicability / conditions / expiry: applies while #16 is open; a deviation found
  during implementation goes back to the coordinator with its rationale. Not an owner
  decision; the owner can override any part.
- Rationale supplied: packet analysis (agent), accepted by the coordinator.
- Affected requirement IDs, files, issues and tests: S2-SETUP-01 to -03, S2-T01, DEV-03,
  OPS-04; `src/wled_mcp/{cli,setup,doctor,config,compat,http_config}.py`;
  `tests/test_setup_cli.py`, `tests/test_doctor.py`; issues #20 and #23.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-16 packet (refresh 1); #20 packet
  (CLI framework, exit codes, `validate_document`, export schema); #23 (quickstart
  sequence and troubleshooting categories).
- Revalidation needed / next action: none before implementation.
