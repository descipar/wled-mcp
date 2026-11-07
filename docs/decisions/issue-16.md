# Issue #16 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-16-DEC-001 — Inventory reload and discovery surface

- ID: ISSUE-16-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #16.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-16/packet.md` (Q1, Q2): "alles nach empfehlung"
  (English: "everything as recommended"); no permalink.
- Scope: issue #16 (S2-SETUP-02, DEV-03 remainder of ISSUE-13-DEC-001).
- Decision:
  - Q1 option A: inventory changes use `wled-mcp config validate` followed by the
    documented restart. In-process reload (for example on SIGHUP) is not part of
    stage 2; the deferral in ISSUE-13-DEC-001 is closed as "not needed".
  - Q2 option A: discovery is a CLI-only `wled-mcp discover` command implemented with
    the Python standard library (one-shot mDNS query, no new runtime dependency). It
    reports candidates and prints the enrollment command. It is not exposed as an MCP
    tool and never writes the inventory itself.
- Applicability / conditions / expiry: issue #16. Discovery runs only on explicit CLI
  invocation; the project rule against unrequested discovery scans stays in force.
  The WLED mDNS service type and TXT fields must be verified against the pinned WLED
  source and recorded in docs/SOURCES.md before implementation.
- Rationale supplied: none beyond accepting the packet recommendations; the packet
  rationale (validate removes the documented outage risk; no new dependency or license
  review; no model-triggered network scan) is agent analysis.
- Affected requirement IDs, files, issues and tests: S2-SETUP-02, DEV-03; issue #16
  CLI, docs/DEPLOYMENT.md, quickstart (#23).
- Supersedes / superseded by: closes the in-process reload deferral of
  ISSUE-13-DEC-001 (that entry stays as recorded).
- Propagated to roles / packet references: issue-16 packet; refresh against main before
  #16 starts (Track A, after #21).
- Revalidation needed / next action: none before implementation.
