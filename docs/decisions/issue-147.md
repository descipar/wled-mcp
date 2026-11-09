# Issue #147 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-147-DEC-001 — Replace the MCPHub forwarding observation with a local stdio client check

- ID: ISSUE-147-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #147 and the M1 exit criterion.
- Authority: human decision (owner chat authority).
- Source: owner chat message in the main coordinator session on 2026-11-09 (no permalink).
  The owner was offered two options for the remaining #147 observation (update the hub and
  observe forwarding through MCPHub, or accept a local stdio client check) and answered
  "Kriterium auf lokalen stdio-Check ändern" (English: "change the criterion to a local stdio
  check").
- Scope: the last acceptance item of #147 and the corresponding M1 exit-criterion wording
  only.
- Decision: the evidence for served instructions and prompts is one local check with a real
  MCP client over stdio against the current `main` build (instructions returned by
  `initialize`, `prompts/list`, `prompts/get`, served field descriptions). Whether MCPHub
  forwards instructions and prompts is no longer a #147 acceptance condition. It is recorded
  as not observed, not as a result, and is not claimed.
- Applicability / conditions / expiry: does not authorize a hub update or deployment, and it
  does not change the served behaviour. A later hub observation can be added without
  reopening #147 if the owner commissions one.
- Rationale supplied: none beyond the choice; the deployed hub service runs a release without
  #147, so the observation would need a deployment.
- Affected requirement IDs, files, issues and tests: AGENT-01/AGENT-02; #147;
  docs/ROADMAP.md (M1 row); docs/validation/issue-147.md.
- Supersedes / superseded by: narrows the "one actual MCPHub forwarding observation" wording
  in the issue; none otherwise.
- Propagated to roles / packet references: coordinator and `wled_completion` for #147.
- Revalidation needed / next action: none.
