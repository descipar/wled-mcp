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

## ISSUE-74-DEC-002 — Numeric-host rule, error code and test scope

- ID: ISSUE-74-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #74 only.
- Authority: technical proposals TD-74-1 to TD-74-6 by the requirements agent, accepted
  by the coordinator. Not a human decision; the human may veto them at review.
- Source: requirements packet `.agent-runs/issue-74/packet.md` (2026-11-06), including
  an offline comparison of host shapes against httpx2, `ipaddress`, `inet_aton`,
  numeric-only `getaddrinfo` and the WHATWG host parser.
- Scope: issue #74; `base_url` host validation and client URL-error mapping.
- Decision:
  - TD-74-1: if the last host label is all decimal digits or `0x` followed by hex
    digits, the host must be a canonical dotted-quad IPv4 address (four parts, 0–255,
    no leading zeros); otherwise the entry is rejected with a fixed message. This is
    wider than "all-numeric dotted hosts" because short, hex and integer forms
    (`1.2.3`, `0x7f.1`, `2130706433`) are otherwise resolved by the system resolver to
    a different address without any error.
  - TD-74-2: client-side `InvalidURL` maps to the existing `CONFIG_ERROR` code with a
    fixed message, no retry and no catch-all handler.
  - TD-74-3: a write with such a URL ends as not attempted; nothing is sent.
  - TD-74-4: tests assert that both the startup configuration error and the new client
    error suppress the original exception (addresses the #61 review note).
  - TD-74-5/6: documentation list as in the packet; `--allowed-host`, the hardware probe
    script, IPv6 and valid special addresses stay out of scope.
- Applicability / conditions / expiry: issue #74 scope; for #74 this overrides
  TD-61-5's "IP-literal handling unchanged" per ISSUE-74-DEC-001.
- Rationale supplied: see the packet.
- Affected requirement IDs, files, issues and tests: DEV-01, tool contract error
  mapping; `src/wled_mcp/config.py`, `src/wled_mcp/client.py`, docs and tests.
- Supersedes / superseded by: none; refines ISSUE-74-DEC-001.
- Propagated to roles / packet references: implementation and review packets for #74.
- Revalidation needed / next action: implementation. Tests must stub connections as
  well as name resolution.
