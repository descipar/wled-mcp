# Issue #74 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-74-DEC-001 — Reject invalid IPv4-like hosts and map client URL errors

- ID: ISSUE-74-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #74 only.
- Authority: human decision (repository owner).
- Source: owner instruction in the coordinator session on 2026-11-06,
  "#74 nach Workflow, beide Optionen"; stage 1 assignment by owner on the same day
  (issue comment); no permalink for the session message.
- Scope: issue #74; `base_url` host validation in `src/wled_mcp/config.py` and the
  client's handling of client-side URL errors.
- Decision: both options. (A) Inventory validation rejects all-numeric dotted hosts
  that are not valid IPv4 addresses, failing closed at startup and naming the device
  entry as established for #61. (B) Client-side URL errors such as `InvalidURL` are
  mapped to a safe domain error instead of escaping a tool call. Diagnostics never
  echo the URL or host; no discovery or name scanning is added.
- Applicability / conditions / expiry: issue #74 scope only. The exact host shapes
  rejected under (A) and the domain error code under (B) are requirements-agent
  technical proposals, not part of this human decision.
- Rationale supplied: none beyond choosing both options.
- Affected requirement IDs, files, issues and tests: DEV-01 and client error mapping;
  `src/wled_mcp/config.py`, `src/wled_mcp/client.py`, inventory/client docs and tests;
  issue #74; review note from #61 (`from None` suppression not asserted by a test) may
  be addressed in the same scope.
- Supersedes / superseded by: none; amends ISSUE-61-DEC-001's "IP-literal handling
  unchanged" for issue #74 only.
- Propagated to roles / packet references: requirements, implementation and review
  packets for issue #74 (`.agent-runs/issue-74/`).
- Revalidation needed / next action: requirements packet.
