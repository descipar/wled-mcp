# Issue #198 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12. The owner decision for M8 is
[DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment); this file holds only the
technical proposals around it.

## ISSUE-198-DEC-001 — Discovery and enrollment contract defaults TP-1 to TP-12

- ID: ISSUE-198-DEC-001
- Status: active technical proposal for milestone M8; not a human decision (changeable by the owner
  at the #198 merge decision or later). Accepted by the coordinator 2026-11-12 from the #198 packet.
- Scope: #198 and the M8 issues #199 to #204 as design input. Not a global rule.
- Decision: the items TP-1 to TP-12 of [contract/discovery.md](../contract/discovery.md): tool
  annotations (TP-1); class `manage` for the two write tools, `read` for discovery, no new class or
  profile, discovery cannot be hidden below `read-only` (TP-2); error codes `DISCOVERY_BUSY`,
  `NOT_WLED`, `INVENTORY_CONFLICT`, `INVENTORY_RELOAD_FAILED` (TP-3); numeric hard caps: 4 ranges,
  /24, one `GET /json/info` on port 80 with 1.5 s and 64 KiB, 32 in flight, 20 s and 30 s deadlines,
  5 s gap, 3 mDNS rounds in 6 s, 64 candidates (TP-4); `wled_add_device` takes only an RFC 1918 IPv4
  literal with optional port (TP-5); enrollment envelope `device_id` (TP-6); range proposal derivation
  (TP-7); coverage report schema (TP-8); MAC identity, optional stored `mac`, `address_changed` rule
  (TP-9); reload scope (TP-10); `[discovery] ranges` key and `devices[].mac` (TP-11); request bounds
  and range string validation (TP-12).
- Conditions: M8 implementation. PRs may refine a value with a recorded rationale but must not widen a
  hard cap beyond DEC-035 (RFC 1918 only, at most a /24 per range, few ranges, bounded timeouts and
  concurrency).
- Affected: DISC-01 to DISC-14, DISC-T01 to DISC-T08, contract/discovery.md. Supersedes / superseded
  by: none (the owner decision is DEC-035).
