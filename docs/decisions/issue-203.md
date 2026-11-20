# Issue #203 decisions

Read with DECISIONS.md. Recorded 2026-11-19. Owner decision: DEC-035 (items 1, 2 and 4). Technical proposals below by the requirements role.

## ISSUE-203-DEC-001 — `wled_add_device` implementation defaults TP-203-1 to TP-203-8

- Status: proposed (active for the #203 implementation); technical defaults, not a human decision; the owner can change any item at the merge decision or later.
- Scope: issue #203 only (M8); consumes the shared writer of #201/#202 and the probe transport of #199. Contract: docs/contract/discovery.md.
- Decision:
  - TP-203-1 Address: `http://<RFC 1918 IPv4 literal>[:port]` only, stored canonical (port 80 omitted, no trailing slash); host names, https and public addresses stay manual or CLI.
  - TP-203-2 Verification: `fetch_info` wraps `HttpTransport.get_info(address, port, HOST_TIMEOUT)` (one GET, body cap, no redirects, no proxy). `wled` proceeds; `other` (not WLED, redirect, non-200, oversize, malformed) is `NOT_WLED`; `refused` is `UNREACHABLE`; `timeout` is `TIMEOUT`; unexpected `error` is `INVALID_RESPONSE`. `NOT_WLED` is additive (ISSUE-130-DEC-001).
  - TP-203-3 Conflicts: ID and `base_url` against the snapshot before any request; MAC after the read; authoritative recheck inside the writer's edit callback under the lock. Order `id`, `base_url`, `mac`; `data.known_device_id` names the existing entry; never overwritten.
  - TP-203-4 Envelope: success has `application` `not_attempted`, `verification` `not_requested`, `device_id` the new ID (also on a successful dry run), null on failure; failures after the read are `not_applied` (writer `unknown` kept); validation and pre-read conflicts and dry-run failures are `not_attempted`.
  - TP-203-5 Defaults: ID is `suggest_id` over the reported name unless generic "WLED", else `wled-<last 6 of MAC>`, computed inside the locked edit against current IDs; name is `suggest_name` of the same label.
  - TP-203-6 Config: `devices[].mac` optional, normalized to lowercase 12 hex (colon form accepted on read), locator `devices[i].mac: invalid`, no startup uniqueness check, written by the tool only, passed to discovery matching.
  - TP-203-7 Write: the edit callback appends one `[[devices]]` block via `append_device` and self-checks that the parsed result equals the old document plus exactly that entry (else `INVENTORY_RELOAD_FAILED` stage `validation`, nothing written), through `Resources.inventory_writer()`; backup, atomic replace, rollback and baseline from the #201 writer. `max_class` never set.
  - TP-203-8 Seams: `enroll_tools.fetch_info` is a module attribute looked up per call, refused in `tests/conftest.py`; annotations false/false/false/true and `OPEN_WORLD_TOOLS` per ISSUE-200-DEC-001 D5; the tool-budget limit is measured and recorded.
- Conditions: M8 implementation; hard caps must not exceed DEC-035. The live enrollment needs its own authorization naming its reach.

## ISSUE-203-DEC-002 — Live enrollment run (two attempts)

- ID: ISSUE-203-DEC-002
- Recorded date: 2026-11-19
- Status: used and expired (both attempts finished; never a standing approval)
- Authority/source: confirmed owner authorization (operation approval), session messages
  2026-11-19: first authorization for one live enrollment of the selected test controller, then
  "ja" to rerunning with the address resolved at run time after attempt 1 failed. Controller name
  and address stay in the local-only inventory.
- Scope, attempt 1: one stdio run, one `GET /json/info` to one explicit address, one write to a
  temporary inventory outside git; no mDNS, scan, other host or device write.
- Scope, attempt 2: exactly one run: one `GET /json/info` to the one IPv4 address the controller's
  host name resolves to at run time; one write to a temporary inventory starting as
  `schema_version = 1` plus `devices = []`; no mDNS, scan, other host or device write; stdio; one
  `wled_add_device` call, not retried after a failure; a second identical call only after a
  success (refused before any read); no `dry_run`, no read-tool read of the new ID.
- Decision: both attempts authorized and executed as in
  [validation/issue-203.md](../validation/issue-203.md#live-enrollment-2026-11-19-two-attempts).
- Conditions: expired when attempt 2 finished; further runs need a new authorization naming calls,
  requests and reach. #204 needs its own.
- Notes: attempt 1 used a stale remembered address, the probe went to another host (`NOT_WLED`,
  nothing written); a second call made one further read-only `GET /json/info` to that same wrong
  host, one request beyond the authorized reach, no state change, none to the selected controller.
  Attempt 2 stayed within reach as far as observable (no packet capture).
