# Issue #23 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-23-DEC-001 — Bring the M6 issues to current requirements

- ID: ISSUE-23-DEC-001
- Recorded date: 2026-11-12
- Status: active for the open M6 issues (#23, #25, #151, #181) only; items marked as a
  coordinator proposal are not owner decisions.
- Authority: human decision (owner chat instructions in the main coordinator session;
  recorded by the coordinator) for the rewrite of the issue bodies and the start of the
  workflow; coordinator proposal (DEC-028) for which items are deferred.
- Source: owner messages in the main session on 2026-11-12 (no permalink): "Issue-Body
  anpassen" (English: "adapt the issue body"); "das issue soll einfach auf die aktuellen
  anforderungen angepasst werden. da interessiert mich der originaltext nicht" (English: "the
  issue should simply be adapted to the current requirements; I am not interested in the
  original text"); "und das kannst du auch gleich für allen anderen issues in m6 machen und
  auch sowas stage gleich entfernen. Bringt sie auf einen ordentlichen stand für m6"
  (English: "do that for all other issues in M6 as well and remove such stage things right
  away; bring them to a proper state for M6"); "ja, mach das" (English: "yes, do that"),
  answering the proposal to add the stale H07 statement of the README and VALIDATION.md to
  #23; "Ja, Workflow für #23 starten" (English: "yes, start the workflow for #23").
- Scope: the bodies and labels of the open issues of milestone M6, and the start of the
  defined workflow for #23.
- Decision: the bodies of #23, #25 and #181 were rewritten to the current requirements
  against `main` (original text not kept in the body; GitHub keeps the edit history); #151
  needed no change; the `stage:5` label was removed from #23 and #25. The current acceptance
  of #23 is: a troubleshooting page with recipes and failure recovery, a replacement
  architecture guide, corrected stale statements in SOURCES.md, DEVELOPMENT.md, the README and
  VALIDATION.md (H07), the ROADMAP Backlog row, and the existing documentation checks. The
  workflow runs for #23 as a docs-only change.
- Applicability / conditions / expiry: the deferral of a release policy, a question/support
  issue template with `config.yml`, a third-party license overview and a metadata
  cross-check is the coordinator's proposal under DEC-028, accepted only to the extent that
  the owner asked for the body to carry current requirements; the owner may schedule or drop
  each item. The decision authorizes no publication, license change, repository setting or
  hardware contact; merge approval stays per PR.
- Rationale supplied: the issue texts predated publication and were partly obsolete.
- Affected requirement IDs, files, issues and tests: S2-PUBLIC-02, S2-PUBLIC-03, S2-LAUNCH-01,
  S2-LAUNCH-02; issues #23, #25, #151, #181; DEC-029 (no stage labels on open issues).
- Supersedes / superseded by: the "Visibility split (DEC-019)" and carried-nit sections of the
  earlier #23 body (their content is delivered or obsolete); not superseded.
- Propagated to roles / packet references: requirements, implementer and reviewer through the
  #23 work packet.
- Revalidation needed / next action: the #23 work packet and PR.
