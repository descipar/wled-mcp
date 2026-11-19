# Issue #200 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-19. The owner decision for
milestone M8 is [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment); this
file holds only the technical defaults for the `wled_discover_devices` wrapper.

## ISSUE-200-DEC-001 — Discovery tool wrapper defaults D1, D2, D4, D5

- ID: ISSUE-200-DEC-001
- Recorded date: 2026-11-19
- Status: proposed (active for the #200 implementation); coordinator acceptance of technical
  defaults from the requirements packet, not a human decision. The owner can change any item at
  the merge decision of the #200 PR or later.
- Authority: technical proposal (not a human decision).
- Source: requirements packet for issue #200 (ignored local file), items D1, D2, D4 and D5;
  accepted by the coordinator for implementation. The contract text is
  [contract/discovery.md](../contract/discovery.md#wled_discover_devices).
- Scope: issue #200 and its neighbours #202 and #203 (milestone M8). Not a global rule.
- Decision:
  - D1 Warnings: the common envelope field `warnings` carries the engine warnings; the result
    `data` has no `warnings` key (no duplicated text in the token budget). The contract line
    `warnings[]` under the result `data` is amended accordingly.
  - D2 Conclusion first: every tool serializes the whole envelope as the JSON text block, which
    starts with `ok`. `conclusion` is therefore the first key of `data` (it also stays in
    `coverage.conclusion`); the contract sentence "the text content block repeats `conclusion`
    first" is amended to this. No change to `server.py`.
  - D4 Ranges seam: the tool reads the property `Resources.discovery_ranges` (a placeholder
    returning `()` until #202, which replaced its body; merged) once per call and never caches it, so
    #202 needs no edit of the tool. The original packet seam
    `discovery.configured_ranges(config)` stays for the CLI. The result of the seam is the only source of ranges handed to the
    engine; `proposed_ranges` is computed separately and never reaches the engine.
  - D5 Open-world tools: `openWorldHint` is true for `wled_discover_devices`; the contract tests
    take the exception from one set, `OPEN_WORLD_TOOLS` in `tests/tool_contract.py`, instead of
    asserting false for every tool. #203 adds `wled_add_device` to it.
  - Implementation choices within the packet: the engine runner and the clock are module
    attributes of `wled_mcp.discovery_tools` (looked up per call); `tests/conftest.py` replaces
    the runner with one that fails the test, so no test can open a real multicast socket
    (the connect-based offline guard does not see UDP `sendto`); `DISCOVERY_BUSY` is
    `read_retryable` with `data.retry_after_seconds`; `coverage.unproposed_devices` is a list
    of `{reason, count}`.
- Applicability / conditions / expiry: M8 implementation; refinements need a recorded rationale.
- Rationale supplied: none from the owner; the rationale is agent analysis in the packet
  (smallest change that keeps the envelope and server unchanged; a seam that needs no second
  edit when #202 lands).
- Affected requirement IDs, files, issues and tests: DISC-01, DISC-03 to DISC-06, DISC-11 to
  DISC-13, DISC-T02, DISC-T04, DISC-T05, DISC-T07; `src/wled_mcp/discovery_tools.py`,
  `tests/test_discovery_tools.py`, `tests/tool_contract.py`, `tests/conftest.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet for #200; #202 and #203 packets cite D4 and D5.
- Revalidation needed / next action: none. The live read-only run is recorded as
  ISSUE-200-DEC-002; see [validation/issue-200.md](../validation/issue-200.md).

## ISSUE-200-DEC-002 — One read-only live discovery run

- ID: ISSUE-200-DEC-002
- Recorded date: 2026-11-19
- Status: used and expired (the run was executed once; never a standing approval)
- Authority: confirmed owner authorization (operation approval, not a design decision).
- Source: owner message in the session on 2026-11-19 ("read only lauf auf <selected test
  controller>"; English: "read-only run on <selected test controller>"; the controller name is
  omitted here and stays in the local-only inventory).
- Scope: one run, one controller (the selected test controller), read-only, over stdio, for
  the `wled_discover_devices` evidence of #200. No writes, no other device, no unicast ranges,
  no container run.
- Decision: the run was authorized and executed as described in
  [validation/issue-200.md](../validation/issue-200.md#live-run-executed-2026-11-19-partial-evidence).
- Applicability / conditions / expiry: expired when the run finished. A further run needs a
  new authorization.
- Rationale supplied: none beyond the instruction.
- Note: the authorization named one controller, but the tool's mDNS method verifies every
  announced private address with a read-only `GET /json/info` (DISC-02). The run therefore
  also sent single read-only requests to other LAN hosts, including a second WLED controller
  outside the named one. The request did not state this; the procedure now does. Nothing was
  written. Future authorizations for discovery should name this reach.
- Affected requirement IDs, files, issues and tests: DISC-02, DISC-T08 (first half, partial);
  `docs/validation/issue-200.md`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: #200 validation record.
- Revalidation needed / next action: none for this run; #204 needs its own authorization.
