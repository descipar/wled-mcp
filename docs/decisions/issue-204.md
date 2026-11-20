# Issue #204 decisions

Read with DECISIONS.md. Recorded 2026-11-20.

## ISSUE-204-DEC-001 — Live discovery runs (stdio, container, mDNS-empty case)

- ID: ISSUE-204-DEC-001
- Recorded date: 2026-11-20
- Status: used and expired (the runs finished; never a standing approval)
- Authority: confirmed owner authorization (operation approval, not a design decision).
- Source: owner message in the main session on 2026-11-20: "ja, mach ich und gebe ich frei",
  the answer to a request that named the three runs and their reach. The coordinator role
  declined to treat a relayed approval as the owner's own, so the main session, which received
  the message directly, ran the runs. The controller name and address stay in the local-only
  inventory.
- Scope: issue #204 only. Run 1: stdio on the host, one `wled_discover_devices` call with `{}`
  over the configured /24 of the selected test controller. Runs 2 and 3: one call with `{}`
  from an own HTTP container (default bridge network). Reach: mDNS with a read-only
  `GET /json/info` to every announced private host (the second controller of the LAN may be
  contacted, as in the #200 record); unicast over the one configured /24 (up to 254 read-only
  requests); the hard caps of the contract; nothing written to any device; a temporary
  inventory outside git, resolved at run time; no retry. The mDNS-only and unicast-only
  follow-up calls of the procedure were not authorized and not run.
- Applicability / conditions / expiry: expired after the three runs of 2026-11-20.
- Affected requirement IDs, files, issues and tests: DISC-14, DISC-T08; `docs/validation/issue-204.md`.
- Revalidation needed / next action: a new run needs a new authorization.
