# Issue #62 decisions

Read with [DECISIONS.md](../DECISIONS.md) (shared DEC-009). Recorded 2026-11-06.

## ISSUE-62-DEC-001 — Technical defaults for the public-ready baseline

- ID: ISSUE-62-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #62 only.
- Authority: technical proposals TD-62-1 to TD-62-12 by the requirements agent, accepted
  by the coordinator. Not a human decision; the owner may veto them at merge review
  (notably the reworded language rule in AGENTS.md and the treatment of `.lan` and
  `.local` as private suffixes).
- Source: requirements packet `.agent-runs/issue-62/packet.md` (2026-11-06).
- Scope: issue #62.
- Decision:
  - A stdlib-only `scripts/check_private_identifiers.py` scans all tracked text files
    as its own CI step. It covers private, link-local and shared IPv4 ranges, IPv6
    link-local and unique-local, home/user paths, router-local DNS suffixes (`.lan`,
    `.local`, `.home`, `.internal`, `.localdomain`, `.intranet`, `.corp`, `.private`,
    `.fritz.box`, `.home.arpa`), MAC addresses outside the documentation range and
    personal-looking email addresses. Loopback and documentation ranges are allowed.
  - A tracked allowlist with a path, value and reason per entry; stale entries fail.
    An optional untracked denylist is read from `WLED_MCP_PRIVATE_DENYLIST` or
    `runtime/private-denylist.txt`. Matched values are never printed.
  - Neutral roles: "owner" in decision records, "maintainer" in workflow and role docs,
    "operator" in deployment and validation docs; "project conversation" becomes
    "coordinator session". The German owner quotes in decision records stay verbatim as
    source evidence. The AGENTS.md language rule becomes "discuss in the maintainer's
    language; committed text in English".
  - A wording check with negative controls guards against installation-specific framing.
  - Status and agent index content moves from README.md to `docs/PROJECT.md`, together
    with the README-coupled checks. README install instructions use a locally built
    wheel and the example files; nothing is published.
  - `pyproject.toml` gets a neutral description, keywords and repository URLs; no
    authors and no license.
  - The publication checklist of remaining owner decisions goes to `docs/STAGE-2.md`
    and is linked from #23 after merge.
  - One PR with three ordered commits: (a) the CI check, decisions and metadata;
    (b) neutral wording and agent roles; (c) README, `docs/PROJECT.md` and the
    checklist.
- Applicability / conditions / expiry: #62 scope.
- Rationale supplied: see the packet.
- Affected requirement IDs, files, issues and tests: DEC-005, DEC-009,
  S2-PUBLIC-01/02 (preparatory subset); issues #62 and #23.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: implementation and review packets for #62.
- Revalidation needed / next action: implementation.
