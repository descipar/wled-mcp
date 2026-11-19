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
