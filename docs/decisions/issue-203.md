# Issue #203 decisions

Read with DECISIONS.md. Recorded 2026-11-19. Owner decision: DEC-035 (items 1, 2 and 4). Technical proposals below by the requirements role.

## ISSUE-203-DEC-001 — `wled_add_device` implementation defaults TP-203-1 to TP-203-8

- Status: proposed (active for the #203 implementation); technical defaults for the #203 implementation; not a human decision; the owner can change any item at the merge decision or later.
- Authority: technical proposal (requirements role, adopted by the coordinator for implementation).
- Source: requirements packet for issue #203 (local untracked file); contract text docs/contract/discovery.md.
- Scope: issue #203 only (milestone M8); consumes the shared writer of #201 and #202 and the probe transport of #199. Not a global rule.
- Decision:
  - TP-203-1 Address policy and storage: `http://<RFC 1918 IPv4 literal>[:port]` only; stored in the canonical form (port 80 omitted, no trailing slash); the returned entry equals the stored text; host names, https and public addresses stay a manual or CLI path.
  - TP-203-2 Verification mapping on the existing probe: `fetch_info` wraps `HttpTransport.get_info(address, port, HOST_TIMEOUT)` (one GET, body cap, no redirects, no proxy). `wled` proceeds; `other` (not WLED, redirect, non-200, oversize, malformed) is `NOT_WLED`; `refused` is `UNREACHABLE`; `timeout` is `TIMEOUT`; an unexpected `error` is `INVALID_RESPONSE`. The error code `NOT_WLED` is additive (ISSUE-130-DEC-001).
  - TP-203-3 Conflict checks: ID and `base_url` against the snapshot before any network request; MAC after the read; the authoritative recheck runs again inside the writer's edit callback under the lock. Order `id`, `base_url`, `mac`; `data.known_device_id` is the existing entry's ID; an existing entry is never overwritten or updated.
  - TP-203-4 Envelope: success has `application` `not_attempted`, `verification` `not_requested` and `device_id` the new ID (also on a successful dry run), null on failure; verification and writer failures after the read are `not_applied` (the writer's `unknown` is kept); request validation and pre-read conflicts are `not_attempted`; failures of a dry run are `not_attempted`.
  - TP-203-5 Defaults: the ID is `suggest_id` over the controller's reported name unless that is the generic "WLED", else `wled-<last 6 of MAC>` (the discovery suggestion rule), computed inside the locked edit against the current IDs; the name is `suggest_name` of the same label.
  - TP-203-6 Config model: `devices[].mac` is optional, normalized to lowercase 12 hex (colon form accepted on read), positional locator `devices[i].mac: invalid`, no uniqueness check at startup; written by the tool only; the stored MAC is passed to discovery matching (tool and CLI).
  - TP-203-7 Write: the edit callback appends one `[[devices]]` block with `append_device`, self-checks that the parsed result equals the old document plus exactly that entry (else `INVENTORY_RELOAD_FAILED` stage `validation`, nothing written), through the shared `Resources.inventory_writer()`; backup, atomic replace, rollback and baseline come from the #201 writer unchanged. `max_class` is never set.
  - TP-203-8 Seams and guards: `enroll_tools.fetch_info` is a module attribute looked up per call; `tests/conftest.py` replaces it with a refusing function so no test can reach the network; annotations false/false/false/true and `OPEN_WORLD_TOOLS` per ISSUE-200-DEC-001 D5; the tool-budget limit is measured and recorded.
- Applicability / conditions / expiry: M8 implementation; refinements need a recorded rationale; the hard caps must not exceed DEC-035.
- Rationale supplied: none from the owner; agent analysis in the packet.
- Affected requirement IDs, files, issues and tests: DISC-05, DISC-08, DISC-10, DISC-T06, DISC-T07, DISC-T08 (second half, live, pending); `src/wled_mcp/enroll_tools.py`, `tests/test_add_device.py`, docs/contract/discovery.md, docs/validation/issue-203.md.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet for #203; #204 adds the migration-notes rows.
- Revalidation needed / next action: none before review; the live enrollment needs its own owner authorization naming its reach.

## ISSUE-203-DEC-002 — Live enrollment run (two attempts)

- ID: ISSUE-203-DEC-002
- Recorded date: 2026-11-19
- Status: used and expired (both attempts finished; never a standing approval)
- Authority: confirmed owner authorization (operation approval, not a design decision).
- Source: owner messages in the session on 2026-11-19: the first authorization for one live
  enrollment of the selected test controller, and, after the first attempt failed, the answer
  "ja" to the proposal to rerun with the address resolved at run time. The controller name and
  address are omitted here and stay in the local-only inventory.
- Scope, attempt 1: one run over stdio, one `GET /json/info` to one explicit address of the
  selected test controller, one inventory write to a temporary inventory outside git, no
  mDNS, no scan, no other host, no device write.
- Scope, attempt 2: exactly one run with exactly this reach: one `GET /json/info` to the one
  IPv4 address that the host name of the selected test controller resolves to at run time
  (a DNS lookup, not a device request); one inventory write to a temporary inventory that
  started as `schema_version = 1` plus `devices = []`, never the real inventory; no mDNS, no
  scan, no other host, no device write, stdio only; one call to `wled_add_device`, not
  repeated or retried after a failure; a second call with the same arguments only after a
  success (refused before any read); no `dry_run` call and no read-only-tool read of the new
  ID.
- Decision: both attempts were authorized and executed as described in
  [validation/issue-203.md](../validation/issue-203.md#live-enrollment-2026-11-19-two-attempts).
- Applicability / conditions / expiry: expired when attempt 2 finished. Further live runs
  need a new authorization that names calls, requests and reach.
- Rationale supplied: none beyond the instruction.
- Notes:
  - Attempt 1 used a stale remembered address, so the probe went to another host and the
    tool answered `NOT_WLED` (nothing written). The agent then sent a second call, which made
    a second read-only `GET /json/info` to that same wrong host: one request beyond the
    authorized reach. It changed no state and no request reached the selected controller.
  - Attempt 2 stayed within its reach as far as the run could observe (no packet capture).
- Affected requirement IDs, files, issues and tests: DISC-08, DISC-T08 (second half);
  docs/validation/issue-203.md, docs/contract/discovery.md.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: #203 validation record.
- Revalidation needed / next action: none for these runs; #204 needs its own authorization.
