# Competitor research brief

The [researcher role](../agents/researcher.md) updates the project's comparison
with other WLED MCP servers. Read this brief on every run. Durable knowledge is
the repository evidence and decision records; no previous chat is assumed.

## Baseline and scope

The canonical known-project inventory, pinned observations and search limitations
are in [SOURCES.md, Reviewed alternatives](SOURCES.md#reviewed-alternatives).
The inherited baseline was checked on 2026-11-19; creating this brief on
2026-11-25 does not revalidate it. Start with all five listed projects and the
adjacent/excluded leads recorded there. Preserve their classification until new
evidence justifies changing it. Use [MARKETPLACE.md](MARKETPLACE.md) for catalog
context, not as proof that a current search has covered every catalog.

Default request: revisit known projects and search for new direct WLED MCP
alternatives in one bounded pass. Search GitHub and relevant package/registry
sources using WLED/MCP name variants; record the queries, sources and gaps.
Classify forks, repackages, firmware, skills and adjacent lighting systems
separately. Compare against current code, the [tool contract](TOOL-CONTRACT.md),
[coverage](WLED-COVERAGE.md), decisions and open issues/PRs. GitHub access failures
leave duplicate/milestone checks pending, not implicitly clear.

## Comparison criteria

These are working defaults accepted as part of creating this role, not a claim
to reconstruct undocumented preferences from earlier conversations.

| Area | Questions |
| --- | --- |
| Functions | Discovery, inventory, effects/palettes, segments/layouts, presets/playlists, groups/scenes/rooms, diagnostics and resources: what is exposed and what is missing? |
| Agent usability | Are names, descriptions, schemas, errors and tool-list size useful to an agent? Is setup understandable? |
| Safety and correctness | Validation, patch/replace semantics, readback, uncertain writes, snapshots, access protection and device reach: what does code establish? |
| Installation | Transports, packaging, registry presence, dependencies and platform claims: documented or demonstrated? |
| Maintenance and reuse | Recent commits/releases, tests, documentation, license and notices: what is evidenced, and what remains unknown? |

State benefits and disadvantages fairly; do not rank by tool count or infer
runtime quality from stars, README claims or code inspection. Features excluded
by this project's decisions remain excluded unless the owner changes that scope.
License observations do not authorize reuse. No candidate installation or hardware
test is part of a routine research pass.

## Evidence and report

Update the alternatives inventory in SOURCES.md without changing unrelated API
evidence. Keep dated reports as `docs/research/YYYY-MM-DD.md` (use a descriptive
suffix for another distinct run that day). Link each report below. Each report has:

1. Scope, baseline/project commit, checked sources/queries and access limitations.
2. Per-project changes with source URLs, checked date and commit/version; distinguish
   documented, code-observed and executed evidence. Unchecked facts stay historical.
3. A comparison focused on relevant differences and what changed since the last run.
4. Numbered proposals with benefit, evidence, local gap, exclusions, tradeoffs,
   duplicate issue/PR links, applicable requirement/decision IDs and proposed milestone.
5. Proposal status: pending, accepted, rejected or deferred, with the real human
   source/date and bounded rationale where supplied. Preserve superseded choices.

Keep facts and recommendations separate. A no-change result is valid. Search
limitations stay visible. Only save project-relevant knowledge, never raw chat
transcripts, personal installation data or invented owner preferences.

## Selection and requirements handoff

The owner requested this research role and an approval-before-handoff process in
the project session on 2026-11-25. This authorizes the role setup; it selects no
competitor feature for implementation. Research runs present proposals first.
After the owner selects proposals, the coordinator gives wled_requirements:

```text
Mode: research-to-requirements; no implementation
Report and proposal IDs:
Evidence URLs and pinned revisions:
Actual approval source/date and selected scope:
Explicit exclusions and rejected/deferred proposals:
Local baseline commit; applicable decisions and requirements:
Existing issues/PRs and dependency readiness:
Proposed milestone (Backlog if no planned milestone clearly fits):
Assigned writable docs paths and GitHub create/update scope:
Expected result: bounded requirements, acceptance criteria, issue URLs and readback
```

Approval covers authoring requirements and creating/updating issues for that
selection. Reuse an existing matching issue; preserve unrelated prose and human
edits. Each issue needs exactly one milestone, no stage prefix/label (DEC-029),
and acceptance criteria that distinguish mock evidence from required hardware
checks. Re-read before and after writes; re-read uncertain writes before retrying.
Return READY or NEEDS_DECISION with unresolved behavior and actual issue URLs.
Implementation requires its own owner instruction under the normal workflow.

## Reports

No new research run yet. The historical baseline remains in SOURCES.md.
