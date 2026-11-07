# Issue #20 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-20-DEC-001 — Default profile, device restrictions, status surface, classes

- ID: ISSUE-20-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #20.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-20/packet.md` (Q1-Q3 and the lower-priority confirmations):
  "alles nach empfehlung" (English: "everything as recommended"); no permalink.
- Scope: issue #20 (S2-ACCESS) and the tool classification used by every tool-adding
  issue.
- Decision:
  - Q1 option (a): when no profile is configured, the profile is `full` (all tools);
    stage-1 configurations and hub entries keep working. Restriction is opt-in, and
    README/quickstart show how to choose `read-only` or `control`.
  - Q2 option (a): device restrictions are a per-device maximum class in the inventory.
    The effective class is the lower of the process profile and the device cap; a call
    above it is refused before any device I/O with a domain error.
  - Q3 option (a): no unauthenticated health route (ISSUE-14-DEC-004 stays). Liveness
    is a TCP connect or authenticated `ping`; readiness/status is a new read-class MCP
    tool (working name `wled_get_service_status`) in both transports.
  - Confirmations: the class vocabulary is `read`, `control`, `manage`, with
    `wled_replace_layout` classified as `control` (D1); no per-credential scopes in #20
    (D3); a correlation ID as a result-envelope field (D8).
- Applicability / conditions / expiry: issue #20; issues #17, #18 and #19 classify each
  new tool with this vocabulary; the tool-contract helper (plan step b) uses it.
- Rationale supplied: none beyond accepting the recommendations; the packet rationale
  (no breaking change for existing deployments; the inventory already limits reachable
  devices; the access guard stays unchanged and works for stdio) is agent analysis.
- Affected requirement IDs, files, issues and tests: S2-ACCESS-01, S2-ACCESS-02,
  S2-T02; docs/TOOL-CONTRACT.md; #16 doctor; #17-#19 tool classification; #67.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-20 packet; plan step (b); #17-#19
  packets.
- Revalidation needed / next action: none before implementation.
