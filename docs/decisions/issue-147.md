# Issue #147 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-147-DEC-001 — Replace the MCPHub forwarding observation with a local stdio client check

- ID: ISSUE-147-DEC-001
- Status: active for issue #147 and the M1 exit criterion.
- Authority: human decision (owner chat, main coordinator session, 2026-11-09, no permalink). Offered
  the choice between updating the hub to observe forwarding and a local stdio check, the owner
  answered "Kriterium auf lokalen stdio-Check ändern" (English: "change the criterion to a local stdio
  check").
- Scope: the last acceptance item of #147 and the M1 exit-criterion wording only.
- Decision: evidence for served instructions and prompts is one local check with a real MCP client over
  stdio against the current `main` build (`initialize` instructions, `prompts/list`, `prompts/get`,
  served field descriptions). Whether MCPHub forwards them is no longer an acceptance condition; it is
  recorded as not observed and not claimed.
- Conditions: no hub update or deployment authorized; served behaviour unchanged; a later hub
  observation needs no reopening if the owner commissions one.
- Affected: AGENT-01/02; #147; docs/ROADMAP.md (M1 row); docs/validation/issue-147.md. Supersedes:
  narrows the issue's "one actual MCPHub forwarding observation" wording only.
