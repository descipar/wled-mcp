# Issue #23 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-23-DEC-001 — Bring the M6 issues to current requirements

- ID: ISSUE-23-DEC-001
- Status: active for the open M6 issues (#23, #25, #151, #181) only; coordinator-proposal items are
  not owner decisions.
- Authority: human decision (owner chat, main coordinator session, 2026-11-12, no permalink) for the
  issue-body rewrite and workflow start; coordinator proposal (DEC-028) for deferrals. Owner
  statements: "Issue-Body anpassen" (English: "adapt the issue body"); "das issue soll einfach auf die
  aktuellen anforderungen angepasst werden. da interessiert mich der originaltext nicht" (English:
  "the issue should simply be adapted to the current requirements; I am not interested in the
  original text"); "Ja, Workflow für #23 starten" (English: "yes, start the workflow for #23"); the
  same treatment for all M6 issues, removing stage markers, and adding the stale H07 statement to #23.
- Decision: bodies of #23, #25, #181 rewritten against `main` (GitHub keeps history); #151 needed no
  change then (later rewritten under [ISSUE-151-DEC-001](issue-151.md)); `stage:5` removed from #23,
  #25. Acceptance of #23: troubleshooting page, replacement architecture guide, corrected stale
  statements (SOURCES.md, DEVELOPMENT.md, README, VALIDATION.md H07), ROADMAP Backlog row, existing
  doc checks. Runs as a docs-only change.
- Conditions: deferral of a release policy, support issue template, third-party license overview and
  metadata cross-check is a coordinator proposal; the owner may schedule or drop each. No
  publication, license change, repository setting or hardware contact; merge approval stays per PR.
- Affected: S2-PUBLIC-02/03, S2-LAUNCH-01/02; DEC-029. Supersedes: obsolete #23 body sections only.
