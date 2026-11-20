# Issue #20 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-20-DEC-001 — Default profile, device restrictions, status surface, classes

- ID: ISSUE-20-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #20.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  Q1-Q3 of DEC-021: "alles nach empfehlung" (English: "everything as recommended").
- Scope: issue #20 (S2-ACCESS) and the tool classification used by every tool-adding issue.
- Decision:
  - Q1 (a): with no profile configured the profile is `full`; restriction is opt-in, and
    README/quickstart show how to choose `read-only` or `control`.
  - Q2 (a): device restrictions are a per-device maximum class in the inventory; the
    effective class is the lower of the process profile and the device cap; a call above it
    is refused before any device I/O.
  - Q3 (a): no unauthenticated health route (ISSUE-14-DEC-004 stays); liveness is a TCP
    connect or authenticated `ping`; status is a read-class tool (`wled_get_service_status`)
    in both transports.
  - Confirmations: class vocabulary `read`, `control`, `manage`, with `wled_replace_layout`
    as `control` (D1); no per-credential scopes in #20 (D3); correlation ID as an envelope
    field (D8).
- Conditions: issues #17-#19 classify each new tool with this vocabulary.
- Supersedes / superseded by: none.

## ISSUE-20-DEC-002 — Technical defaults TD-20-1 to TD-20-15

- ID: ISSUE-20-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #20.
- Authority: technical proposal accepted by the coordinator (not a human decision; the owner
  can override any part).
- Source: TD-20-1 to TD-20-15 and C-20-1 of the issue-20 packet, accepted 2026-11-08; cites
  [ISSUE-20-DEC-001](#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes),
  which it does not change.
- Scope: issue #20. Contract text: docs/contract/profiles.md.
- Decision:
  - TD-20-1 Vocabulary and cumulative profiles: `read` (no live, storage or local file
    mutation), `control` (live output only), `manage` (device storage or local persistent
    artifacts); `read-only` = {read}, `control` = {read, control}, `full` = all. Production
    table `src/wled_mcp/access.py`; a test compares it with the test helper's copy.
  - TD-20-2 (D2) A tool's class is the maximum over all argument combinations; `dry_run`
    does not lower it.
  - TD-20-3 (D7) `Operation.tool_class` is a required keyword.
  - TD-20-4 `create_server(operations, access=None)`; `None` means `full`; a disabled tool is
    indistinguishable from an unknown one.
  - TD-20-5 (D4) Three guard layers: G1 registration filter; G2 dispatch-time device ceiling
    after schema validation; G3 entry guard of the write engines and preset-import path via
    an ambient `ContextVar`, before the device lock and any I/O. `Resources.require_access`
    is public for composite preflights.
  - TD-20-6 Additive error code `ACCESS_DENIED`, fixed message naming only device ID and
    class names, `not_attempted`/`not_requested`.
  - TD-20-7 Config (additive, `schema_version` 1): `[access] profile`, per-device
    `max_class`; `--profile` overrides the file; no environment variable.
  - TD-20-8 `config validate` and `doctor` unchanged without access settings; with them one
    extra line and additive JSON fields.
  - TD-20-9 to TD-20-12 (PR B) correlation ID, bounded structured stderr logging, read-class
    `wled_get_service_status` without device I/O, unchanged liveness/rotation with a "not
    tenancy" statement.
  - TD-20-13 Two PRs: A enforcement, B diagnostics and status. TD-20-14 Full review depth.
  - TD-20-15 #67 stays out; the filter is applied once in `create_server`.
  - C-20-1 The migration-note table of `docs/contract/versioning.md` gets two rows
    (`/access`, `/devices/max_class`) with provisional release `0.2.0`; #25 corrects the
    number if the release differs.
- Conditions: while #20 is open; deviations go back to the coordinator.
- Supersedes / superseded by: none. ISSUE-14-DEC-004 stays.
