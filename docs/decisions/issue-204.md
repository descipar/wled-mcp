# Issue #204 decisions

Read with DECISIONS.md. Recorded 2026-11-20.

## ISSUE-204-DEC-001 — Live discovery runs (stdio, container, mDNS-empty case)

- ID: ISSUE-204-DEC-001
- Status: used and expired (the runs finished; never a standing approval)
- Authority: confirmed owner authorization (operation approval, not a design decision). Source: owner
  message in the main session, 2026-11-20: "ja, mach ich und gebe ich frei" (English: "yes, I will do
  it and I approve it"), answering a request that named the three runs and their reach. The coordinator
  role declined to treat a relayed approval as the owner's own, so the main session ran the runs.
- Scope: issue #204 only. Run 1: stdio on the host, one `wled_discover_devices` call with `{}` over the
  configured /24 of the selected test controller. Runs 2 and 3: one call with `{}` from an own HTTP
  container (default bridge network). Reach: mDNS with a read-only `GET /json/info` to every announced
  private host; unicast over the one configured /24 (up to 254 read-only requests); the contract's hard
  caps; nothing written to any device; temporary inventory outside git; no retry. mDNS-only and
  unicast-only follow-up calls were not authorized and not run.
- Expiry: after the three runs of 2026-11-20; a new run needs a new authorization.
- Affected: DISC-14, DISC-T08; `docs/validation/issue-204.md`.
