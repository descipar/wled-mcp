# Issue #16 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-16-DEC-001 — Inventory reload and discovery surface

- ID: ISSUE-16-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #16; superseded in part by DEC-035 (2026-11-12): the "restart
  instead of reload" half of Q1 and the "CLI only, not an MCP tool, never writes the
  inventory" half of Q2 no longer hold from M8. The validate-then-restart procedure for hand
  edits and the `wled-mcp discover` command stay valid.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  Q1, Q2 of DEC-021: "alles nach empfehlung" (English: "everything as recommended").
- Scope: issue #16 (S2-SETUP-02, DEV-03 remainder of ISSUE-13-DEC-001).
- Decision:
  - Q1 A: inventory changes use `wled-mcp config validate` followed by the documented
    restart; in-process reload is not part of stage 2 (the ISSUE-13-DEC-001 deferral is
    closed as "not needed").
  - Q2 A: discovery is a CLI-only `wled-mcp discover` using the standard library (one-shot
    mDNS query, no new dependency); it reports candidates and prints the enrollment command,
    is not an MCP tool and never writes the inventory.
- Conditions: discovery runs only on explicit CLI invocation; WLED mDNS service type and TXT
  fields are verified against the pinned source in docs/SOURCES.md.
- Supersedes / superseded by: closes the reload deferral of ISSUE-13-DEC-001; superseded in
  part by DEC-035.

## ISSUE-16-DEC-002 — Technical defaults TD-16-1 to TD-16-10

- ID: ISSUE-16-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #16; TD-16-8 superseded in part by DEC-035 (2026-11-12): "no
  unicast probes" and the CLI-only engine no longer hold from M8 (the engine becomes the
  shared one of #199).
- Authority: technical proposal accepted by the coordinator (not a human decision; the owner
  can override any part).
- Source: TD-16-1 to TD-16-10 and two coordinator choices of the issue-16 packet, accepted
  2026-11-08.
- Scope: issue #16 (S2-SETUP-01 to -03, DEV-03, OPS-04 remainders). Contract text:
  docs/contract/cli.md.
- Decision:
  - TD-16-1 CLI shape: `cli.build_parser()`; no subcommand = serve; subcommands
    `config init|add-device|validate`, `doctor`, `discover` (second PR); `--format
    text|json`; exit codes 0 ok, 1 problem, 2 usage, 3 internal; JSON has `schema_version` 1
    and `command`.
  - TD-16-2 Absolute `--config`/`--data-dir` (or environment) only; no default lookup.
  - TD-16-3 `config init` writes only the selected file; `config add-device` appends one
    `[[devices]]` block textually, validates the result with the startup validator, rejects
    an equal normalized `base_url` and writes atomically, aborting if the file changed;
    0600 on POSIX; no token generation, no device contact.
  - TD-16-4 `config validate` shares `validate_document` with startup; never contacts devices.
  - TD-16-5 Read-only `doctor` (runtime, configuration, storage, device, optional endpoint
    checks); device checks via the in-process `wled_get_state` envelope and
    `compat.support_warning`.
  - TD-16-6 Sanitized `doctor --export` from an allowlist.
  - TD-16-7 OPS-04 remainder: doctor covers every listed condition; serve prints one advisory
    stderr line when the backups location is not writable and still starts.
  - TD-16-8 Discovery (second PR): standard-library one-shot IPv4 mDNS query, bounded
    window and candidate cap, never automatic.
  - TD-16-9 Docs in `docs/contract/cli.md` and `docs/validation/issue-16.md`.
  - TD-16-10 Two PRs; no new dependency.
  - Coordinator choices: no no-op `config migrate`; no `--create-data-dir`; #20 starts after
    the second #16 PR.
- Conditions: while #16 is open; deviations go back to the coordinator.
- Supersedes / superseded by: none (TD-16-8 in part by DEC-035, see Status).
