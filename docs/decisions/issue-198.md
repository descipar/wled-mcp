# Issue #198 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12. The owner decision for
milestone M8 is [DEC-034](../DECISIONS.md#dec-034--agent-driven-discovery-and-enrollment);
this file holds only the technical proposals around it.

## ISSUE-198-DEC-001 — Discovery and enrollment contract defaults TP-1 to TP-12

- ID: ISSUE-198-DEC-001
- Recorded date: 2026-11-12
- Status: active technical proposal for milestone M8; not a human decision. The owner can
  change any item at the merge decision of the #198 PR or later.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: requirements packet for issue #198, with the coordinator's acceptance on
  2026-11-12 of its open items (optional `devices[].mac`, RFC 1918 literal only for
  `wled_add_device`, numeric caps, new error codes, MAC in candidates). The packet is an
  ignored local file; the contract carries the substance.
- Scope: issue #198 and the M8 implementation issues #199 to #204 as design input. Not a
  global rule.
- Decision: the items marked TP-1 to TP-12 in [contract/discovery.md](../contract/discovery.md):
  TP-1 tool annotations; TP-2 class `manage` for the two write tools and `read` for discovery,
  no new class or profile, accepted limitation that discovery cannot be hidden below
  `read-only`; TP-3 new error codes `DISCOVERY_BUSY`, `NOT_WLED`, `INVENTORY_CONFLICT` and
  `INVENTORY_RELOAD_FAILED`; TP-4 numeric hard caps (4 ranges, /24, one `GET /json/info` on
  port 80 with 1.5 s and 64 KiB, 32 in flight, 20 s and 30 s deadlines, 5 s gap, 3 mDNS
  rounds in a 6 s window, 64 candidates); TP-5 `wled_add_device` accepts only an RFC 1918
  IPv4 literal with an optional port; TP-6 envelope `device_id` of the enrollment; TP-7 range
  proposal derivation; TP-8 coverage report schema; TP-9 MAC identity in candidates, the
  optional stored `mac` and the `address_changed` rule; TP-10 reload scope; TP-11 the
  `[discovery] ranges` key and `devices[].mac`; TP-12 request bounds and range string
  validation.
- Applicability / conditions / expiry: M8 implementation. The implementing PRs may refine a
  value with a recorded rationale; they must not widen a hard cap beyond the owner's answers in
  DEC-034 (RFC 1918 only, at most a /24 per range, a small number of ranges, bounded timeouts
  and concurrency).
- Rationale supplied: none from the owner beyond DEC-034; the rationale in the contract is
  agent analysis.
- Affected requirement IDs, files, issues and tests: DISC-01 to DISC-14, DISC-T01 to DISC-T08,
  contract/discovery.md and the tests that later issues add or change (listed in the #198 PR).
- Supersedes / superseded by: none. Supersession by the owner decision is in DEC-034.
- Propagated to roles / packet references: the #199 to #204 requirement packets cite it after
  the #198 merge, with the refreshed main commit.
- Revalidation needed / next action: none before #199.
