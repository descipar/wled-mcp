# Issue #21 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-21-DEC-001 — Update and rollback evidence

- ID: ISSUE-21-DEC-001
- Recorded date: 2026-11-07
- Status: active for issues #21 and #25.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-21/packet.md` (Q1): "alles nach empfehlung"
  (English: "everything as recommended"); no permalink.
- Scope: closure evidence for S2-COMPAT-03 (version-to-version update and rollback of
  the deployed service, HTTP and uvx/stdio).
- Decision: #21 closes on automated upgrade/rollback tests plus the documented
  procedure. The live update/rollback run on the deployed target is evidence for #25
  (S2-LAUNCH-01), performed once with the published artifacts.
- Applicability / conditions / expiry: the live run needs its own operation
  authorization when #25 reaches it; this entry does not authorize it.
- Rationale supplied: none beyond accepting the recommendation; the packet rationale
  (one live operation with the final artifacts, no second authorization) is agent
  analysis.
- Affected requirement IDs, files, issues and tests: S2-COMPAT-03, S2-LAUNCH-01;
  issues #21, #25; ISSUE-11-DEC-005 expectation of a live run is satisfied in #25.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-21 packet; #25.
- Revalidation needed / next action: none before implementation.
