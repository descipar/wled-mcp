# Issue #61 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-61-DEC-001 — Accept underscores in `base_url` host labels

- ID: ISSUE-61-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #61 only.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-06 choosing issue option A
  ("Unterstrich erlauben") over option B; no permalink.
- Scope: issue #61; inventory validation of the `base_url` host in
  `src/wled_mcp/config.py`, its tests and the inventory/configuration documentation.
- Decision: option A. An underscore is accepted in DNS host labels of a device
  `base_url`. Everything else stays fail-closed and unchanged: userinfo, query,
  fragment, path, whitespace and percent-encoding remain rejected; IP-literal handling
  is unchanged; no discovery or name scanning is added. Regardless of the option, a
  rejected inventory names the offending device entry without echoing secrets (issue
  acceptance item 2).
- Applicability / conditions / expiry: issue #61 scope only. Exact label rules beyond
  the underscore (for example leading/trailing underscore) are a requirements-agent
  technical proposal, not part of this human decision.
- Rationale supplied: none beyond choosing the recommended option; the issue records
  that some routers publish DHCP-derived names with underscores.
- Affected requirement IDs, files, issues and tests: `src/wled_mcp/config.py`,
  inventory/configuration docs, config validation tests; issue #61.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementation and review
  packets for issue #61 (`.agent-runs/issue-61/`).
- Revalidation needed / next action: requirements packet.

## ISSUE-61-DEC-002 — Host label rules and device-locating error message

- ID: ISSUE-61-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #61 only.
- Authority: technical proposals TD-61-1 to TD-61-9 by the requirements agent, accepted
  by the coordinator. Not a human decision; the owner may veto them at review.
- Source: requirements packet `.agent-runs/issue-61/packet.md` (2026-11-06), including
  an offline check that the installed HTTP stack sends ASCII underscore hosts without
  IDNA encoding.
- Scope: issue #61; `base_url` host validation and the inventory startup diagnostic.
- Decision:
  - TD-61-1 to TD-61-6: label characters `[A-Za-z0-9_-]`; ASCII only; at most 253
    characters; each label 1–63 characters, starting and ending with a letter or digit
    (no leading/trailing `_` or `-`, so underscore-only labels are rejected); no special
    rule for the last label or single-label names; IP-literal, IPv6, case and
    normalization handling unchanged.
  - TD-61-7: the diagnostic locates offending device entries only from the validation
    error location, as `devices[<zero-based index>]` plus the field name for `id`,
    `name` and `base_url` (an unknown key is reported as an unsupported field without
    its name); at most five locators; never the value, URL, host or exception text.
    Errors not tied to a device entry keep the generic message.
  - TD-61-8: the device id is not shown; the index identifies the entry.
  - TD-61-9: the read-only hardware probe script and the service `--allowed-host`
    rule are out of scope.
- Applicability / conditions / expiry: issue #61 scope; revisit if an HTTP library
  upgrade starts IDNA-encoding ASCII hosts (guarded by a client-level test).
- Rationale supplied: see the packet; mirrors the existing hyphen rule and keeps the
  existing secret-marker test meaningful.
- Affected requirement IDs, files, issues and tests: DEV-01, T01, OPS-05;
  `src/wled_mcp/config.py`, inventory/deployment docs, `tests/test_inventory_client.py`,
  `tests/test_bootstrap.py`.
- Supersedes / superseded by: none; refines ISSUE-61-DEC-001.
- Propagated to roles / packet references: implementation and review packets for #61.
- Revalidation needed / next action: implementation.
