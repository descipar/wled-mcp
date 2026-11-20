# Issue #74 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-74-DEC-001 — Reject invalid IPv4-like hosts and map client URL errors

- ID: ISSUE-74-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #74 only.
- Authority/source: human decision, owner instruction 2026-11-06, "#74 nach Workflow, beide
  Optionen" (English: "#74 per workflow, both options"); no permalink.
- Scope: `base_url` host validation in `src/wled_mcp/config.py` and the client's handling of
  client-side URL errors.
- Decision: both options. (A) Inventory validation rejects all-numeric dotted hosts that are not
  valid IPv4, failing closed at startup and naming the device entry as in #61. (B) Client-side
  URL errors such as `InvalidURL` map to a safe domain error. Diagnostics never echo the URL or
  host; no discovery or name scanning.
- Conditions: exact host shapes and error code are technical proposals (DEC-002). Amends
  ISSUE-61-DEC-001's "IP-literal handling unchanged" for #74 only.

## ISSUE-74-DEC-002 — Numeric-host rule, error code and test scope

- ID: ISSUE-74-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #74 only; technical proposals TD-74-1 to TD-74-6 accepted by the
  coordinator, not a human decision; the owner may veto at review.
- Decision:
  - TD-74-1: if the last host label is all decimal digits or `0x` plus hex digits, the host must
    be a canonical dotted-quad IPv4 (four parts, 0–255, no leading zeros), else rejected with a
    fixed message (short, hex and integer forms like `1.2.3`, `0x7f.1`, `2130706433` would
    otherwise resolve to another address).
  - TD-74-2: client-side `InvalidURL` maps to `CONFIG_ERROR` with a fixed message, no retry.
  - TD-74-3: a write with such a URL ends as not attempted; nothing is sent.
  - TD-74-4: tests assert startup and client errors suppress the original exception (#61 note).
  - TD-74-5/6: documentation as in the packet; `--allowed-host`, the probe script, IPv6 and valid
    special addresses stay out of scope.
- Conditions: for #74 overrides TD-61-5's "IP-literal handling unchanged"; refines DEC-001.
  Tests must stub connections as well as name resolution.
