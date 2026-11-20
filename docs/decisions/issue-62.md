# Issue #62 decisions

Read with [DECISIONS.md](../DECISIONS.md) (shared DEC-009). Recorded 2026-11-06.

## ISSUE-62-DEC-001 — Technical defaults for the public-ready baseline

- ID: ISSUE-62-DEC-001
- Status: active for issue #62 only.
- Authority: technical proposals TD-62-1 to TD-62-12 by the requirements agent, accepted by the
  coordinator; not a human decision (the owner may veto at merge review, notably the AGENTS.md
  language rule and `.lan`/`.local` as private suffixes). Source: packet, 2026-11-06.
- Decision:
  - A stdlib-only `scripts/check_private_identifiers.py` scans all tracked text files as its own
    CI step: private, link-local and shared IPv4, IPv6 link-local/unique-local, home/user paths,
    router-local DNS suffixes, MAC addresses outside the documentation range, personal-looking
    e-mail addresses. Loopback and documentation ranges are allowed.
  - A tracked allowlist (path, value, reason; stale entries fail) and an optional untracked
    denylist (`WLED_MCP_PRIVATE_DENYLIST` or `runtime/private-denylist.txt`); matches are never printed.
  - Neutral roles: "owner" in decision records, "maintainer" in workflow docs, "operator" in
    deployment/validation docs; "project conversation" becomes "coordinator session". German owner
    quotes stay verbatim. AGENTS.md language rule: discuss in the maintainer's language, commit English.
  - A wording check with negative controls guards against installation-specific framing.
  - Status/agent index moves from README.md to `docs/PROJECT.md`; README installs from a locally
    built wheel and the example files; nothing is published.
  - `pyproject.toml` gets neutral description, keywords and URLs; no authors, no license.
  - The remaining owner-decision checklist goes to `docs/STAGE-2.md`. One PR, three ordered commits.
- Affected: DEC-005, DEC-009, S2-PUBLIC-01/02 (preparatory); #62, #23. Supersedes: none.
