# Issue #200 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-19. The owner decision for
milestone M8 is [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment); this
file holds the technical defaults for the `wled_discover_devices` wrapper and one run approval.

## ISSUE-200-DEC-001 — Discovery tool wrapper defaults D1, D2, D4, D5

- ID: ISSUE-200-DEC-001
- Recorded date: 2026-11-19
- Status: proposed (active for the #200 implementation); coordinator acceptance of technical
  defaults from the requirements packet, not a human decision; the owner can change any item.
- Scope: #200 and its neighbours #202 and #203 (M8). Contract text:
  [contract/discovery.md](../contract/discovery.md#wled_discover_devices).
- Decision:
  - D1 Warnings: the envelope field `warnings` carries the engine warnings; result `data` has no
    `warnings` key. The contract line is amended accordingly.
  - D2 Conclusion first: the envelope is the JSON text block starting with `ok`, so `conclusion`
    is the first key of `data` (also kept in `coverage.conclusion`); the contract sentence is
    amended. No change to `server.py`.
  - D4 Ranges seam: the tool reads `Resources.discovery_ranges` once per call, never cached
    (placeholder `()` until #202, which replaced it; merged). `discovery.configured_ranges(config)`
    stays for the CLI. Only that seam feeds the engine; `proposed_ranges` never reaches it.
  - D5 Open-world tools: `openWorldHint` is true for `wled_discover_devices`; contract tests take
    the exception from `OPEN_WORLD_TOOLS` in `tests/tool_contract.py` (#203 adds
    `wled_add_device`).
  - Implementation choices: engine runner and clock are module attributes of
    `wled_mcp.discovery_tools`; `tests/conftest.py` replaces the runner with one that fails the
    test (no real multicast socket in tests); `DISCOVERY_BUSY` is `read_retryable` with
    `data.retry_after_seconds`; `coverage.unproposed_devices` is a list of `{reason, count}`.
- Conditions: M8 implementation; refinements need a recorded rationale. The live read-only run is
  ISSUE-200-DEC-002 ([validation/issue-200.md](../validation/issue-200.md)).

## ISSUE-200-DEC-002 — One read-only live discovery run

- ID: ISSUE-200-DEC-002
- Recorded date: 2026-11-19
- Status: used and expired (the run was executed once; never a standing approval)
- Authority/source: confirmed owner authorization (operation approval), session message
  2026-11-19: "read only lauf auf <selected test controller>" (English: "read-only run on
  <selected test controller>"; name omitted, stays in the local-only inventory).
- Scope: one run, one controller, read-only, stdio, for the `wled_discover_devices` evidence of
  #200. No writes, other device, unicast ranges or container run.
- Decision: authorized and executed as in
  [validation/issue-200.md](../validation/issue-200.md#live-run-executed-2026-11-19-partial-evidence).
- Conditions: expired when the run finished; a further run needs a new authorization.
- Note: the mDNS method verifies every announced private address with a read-only
  `GET /json/info` (DISC-02), so the run also sent single read-only requests to other LAN hosts,
  including a second WLED controller. Nothing was written. Future discovery authorizations
  should name this reach. #204 needs its own authorization.
