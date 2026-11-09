# Project decision log

This is versioned project knowledge, not model training or an authorization
service. All workflow roles read applicable active decisions before work and
before asking a question that may already have been answered.

## Recording rules

- Record a clear human answer as a concise, impersonal decision with ID, status,
  authority/source, scope, applicability, rationale if supplied, affected artifacts
  and any superseded decision. Do not invent a rationale or source permalink.
- Quote a short non-English owner statement verbatim and follow it with an English
  translation in the form `"original" (English: "translation")` (DEC-017). Typing
  errors may be corrected if the record says so; meaning must not change.
- Allocate the next unused sequential ID within the shared or issue-specific
  log, and never reuse an ID after supersession.
- Use the narrowest supported scope: operation, issue, stage, workflow or project.
  An answer about one issue is not a project default. Only explicit general intent
  or an existing governing project rule supports broader scope.
- Keep shared project/workflow/stage decisions here. Store issue-specific decisions
  in `docs/decisions/issue-<number>.md`, using the decision template. Link relevant
  issue/PR records when they contain the actual human decision. Avoid duplicating
  the full issue specification or chat transcript.
- Source authority matters: a real user instruction or verified human decision
  is different from an agent-written issue, model proposal or observation. Mark
  proposals/unverified sources accordingly; do not turn them into human approval.
- Search applicable entries and original sources before a repeated question.
  Reuse an answer while its conditions hold. Ask again only for a material change,
  genuine conflict or missing authority; explain what changed.
- A current explicit human correction supersedes the applicable older decision.
  Preserve history: mark the old entry superseded and link its replacement. Do
  not silently erase old reasoning or rewrite the agent instructions to broaden
  scope. Unclear answers remain unresolved, not approved by elapsed time.
- Merge/deployment/hardware/publication permissions are bounded to their actual
  scope/candidate/conditions. A log entry is evidence, not standing permission for
  future operations or a substitute for the current human merge decision, unless
  an active owner decision explicitly grants a bounded standing approval with its
  conditions and expiry (currently DEC-022 item 4 for stage-2 merges).
- Keep names, private hosts, credentials and raw transcripts out of committed
  entries. If a sensitive detail is necessary at runtime, store only a neutral
  reference to its local/protected source; do not copy it into the log.

Use [the entry template](agent-workflow/decision.template.md). The coordinator
owns recording and propagation, coordinating with the current checkout writer.
It must not claim durable learning until the decision has actually been saved
and handed off/committed through the current branch and PR workflow.

## Active shared decisions

| ID | Scope | Decision | Authority / record |
| --- | --- | --- | --- |
| DEC-001 | Workflow | A short issue implementation request starts the defined workflow by default. The user need not repeat roles, paths, testing or review steps. | Confirmed human instruction, project workflow discussion, 2026-11-04; implemented in [PR #32](https://github.com/descipar/wled-mcp/pull/32) |
| DEC-002 | Workflow | Derive stage from issue labels, ancestor tracker and roadmap; stage is not a mandatory user input. Ask only for relevant conflict or genuinely unclear scope. Amended by DEC-010: every issue must carry a stage. | Confirmed human correction, project workflow discussion, 2026-11-04; [PR #32](https://github.com/descipar/wled-mcp/pull/32) |
| DEC-003 | Project / transport scope | Support both Streamable HTTP and client-managed stdio via uvx, sharing the WLED tool/domain contract. | Confirmed human scope instruction, transport discussion, 2026-11-04; [requirements](REQUIREMENTS.md), [issue #14](https://github.com/descipar/wled-mcp/issues/14) |
| DEC-004 | Stage 3 | Named zones, temporary signals, static previews, lighting explanations and effect-property search belong to stage 3 and do not block stage-2 publication. | Confirmed human stage assignment, roadmap discussion, 2026-11-04; [stage-3 roadmap](STAGE-3.md), [tracker #26](https://github.com/descipar/wled-mcp/issues/26) |
| DEC-005 | Project documentation / issues | Use neutral roles and synthetic examples. Exclude personal names, private hostnames and installation-specific personal context unless explicitly requested. | Existing governing [AGENTS.md](../AGENTS.md) rule, recorded 2026-11-04 |
| DEC-006 | Workflow | Add an agent responsible for completing issue checklists after merge. | Confirmed human instruction, post-merge workflow discussion, 2026-11-04; [issue #34](https://github.com/descipar/wled-mcp/issues/34) |
| DEC-007 | Workflow / role maintenance | Maintain shared agent definitions usable with Claude Code and Codex. | Confirmed human instruction, shared-agent discussion, 2026-11-04; [issue #37](https://github.com/descipar/wled-mcp/issues/37) |
| DEC-008 | Workflow / Claude Code only | In Claude Code, the coordinator launches the independent reviewer (`wled_reviewer`) explicitly with the Opus model. Codex is unaffected. | Confirmed human instruction, issue-48 workflow session, 2026-11-05; see [DEC-008](#dec-008--reviewer-on-opus-in-claude-code) |
| DEC-009 | Project / public readiness | Keep the repository public-ready: neutral, installation-independent content, a user-facing README and copyable synthetic example deployment files referenced from the README. This does not change visibility, choose a license, publish anything or rewrite history. | Confirmed owner direction, coordinator session, 2026-11-06; see [DEC-009](#dec-009--public-ready-repository-baseline) and [issue #62](https://github.com/descipar/wled-mcp/issues/62) |
| DEC-010 | Project / issue tracking | Every issue belongs to exactly one stage, visible as a `Stage N: ` title prefix plus one `stage:N` label. Issues #34 and #37 belong to stage 1. Further conventions are coordinator-derived (see section). | Confirmed owner instruction, coordinator session, 2026-11-06; see [DEC-010](#dec-010--stage-in-every-issue-title) |
| DEC-011 | Project / outbound license | License the project under Apache-2.0 with a NOTICE file naming the author; redistributions must keep the attribution. Does not change visibility or publish anything. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-011](#dec-011--apache-20-license-with-notice-attribution) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-012 | Project / identity | Keep the name `wled-mcp`: repository `descipar/wled-mcp`, PyPI `wled-mcp`, image `ghcr.io/descipar/wled-mcp`, registry `io.github.descipar/wled-mcp`; always marked unofficial and unaffiliated, no WLED logo. Does not reserve names or publish anything. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-012](#dec-012--project-and-package-identity) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-013 | Project / contact and security | Public contact is GitHub issues only, with no published e-mail address. No security support: the project is provided as is, at the user's own risk, without a private reporting channel or response commitment; `SECURITY.md` states this. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-013](#dec-013--general-contact-and-no-security-support) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-014 | Project / repository history | Keep the existing Git history and author identities, including the owner's commit e-mail address, when the repository becomes public; no history rewrite and no fresh public repository. Does not change visibility. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-014](#dec-014--keep-the-existing-git-history) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-015 | Project / issue and PR review | Before the visibility change, review all issues, PRs, comments and their edit histories with a repeatable read-only scan plus one agent read-through; the owner approves the findings. Mandatory #23/#25 step; the script is #23 work. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-015](#dec-015--issue-and-pr-review-before-visibility-change) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-016 | Project / public repository content | The agent tooling (AGENTS.md, CLAUDE.md, agent roles and generated client definitions, agent workflow docs and templates, sync script) and all decision records ship in the public repository; a short orientation for outside readers is #23 work. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-016](#dec-016--ship-the-agent-tooling-and-decision-records) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-017 | Project / decision-record language | German owner quotes in decision records stay verbatim and carry an English translation; future records follow the same form. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-017](#dec-017--verbatim-owner-quotes-with-english-translation) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-018 | Project / private denylist and branch rules | The private denylist is a local untracked file plus a CI secret, built from an agent-proposed, owner-approved candidate list together with the DEC-015 review before the visibility change. At the visibility change `main` gets a ruleset: PRs only, required CI check, no force-push or deletion, no required reviews, owner bypass for the PR requirement only. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-018](#dec-018--private-denylist-and-main-branch-rules) and [issue #23](https://github.com/descipar/wled-mcp/issues/23) |
| DEC-019 | Project / visibility timing | Decouple repository visibility from release: the repository becomes public once the readiness checklist of #90 is complete and the owner instructs it; package, image and marketplace publication stay in #25. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-019](#dec-019--make-the-repository-public-before-the-release) and [issue #90](https://github.com/descipar/wled-mcp/issues/90) |
| DEC-020 | Project / support and version policy | Pre-1.0 `0.x` releases with migration notes; fixes only for the latest release. WLED support from 16.0.0 only, in tiers tested/expected/unknown; older firmware is unsupported and warned about, not refused. Python as tested in CI; Linux supported, Windows/macOS experimental; best-effort responses. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-020](#dec-020--support-and-version-policy) and [issue #21](https://github.com/descipar/wled-mcp/issues/21) |
| DEC-021 | Stage 2 / workflow | Adopt docs/STAGE-2-PARALLEL-PLAN.md: at most two implementation tracks, #90 first, per-issue coordinators in isolated worktrees with the main session as integration owner, branches synced by merging `main` (no force-push). "Starte Stage 2 parallel" starts or resumes the plan. | Confirmed owner decision, coordinator session, 2026-11-07; see [DEC-021](#dec-021--adopt-the-stage-2-parallel-plan) and [tracker #15](https://github.com/descipar/wled-mcp/issues/15) |
| DEC-022 | Stage 2 / workflow | Proportionate review: nits go to the next PR instead of a new review round; a main sync without own code changes keeps the PASS after a coordinator diff check; light review for docs-only/small PRs, full depth for writing code. Standing merge approval for PRs with a current-head PASS and green CI, to be revalidated after three issues. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-022](#dec-022--proportionate-review-and-standing-merge-approval) |
| DEC-023 | Stage 2 / release staging | Release in stages. Stage 0: the repository becomes public after the #90 scan and owner approval, with a GitHub release (tag from the single version source) that is installable from Git. Artifact publication (PyPI first) is decided afterwards; images, registry/marketplace listings, the extended docs set and the beta report are deferred past the first public release. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-023](#dec-023--staged-first-public-release) |
| DEC-024 | Project / main branch rules | Replaces the single branch rule of DEC-018 item 3 with two rulesets on `main` and one Actions setting: ruleset A (CI checks required, no force-push, no deletion, no bypass), ruleset B (pull request with one approval; the owner may bypass only when merging a pull request) and approval of workflow runs for all external contributors. Pull requests from others therefore need the owner's approval before their CI runs and before they merge. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-024](#dec-024--main-branch-rules-with-review-for-external-pull-requests) and [runbook](validation/issue-90.md) |
| DEC-026 | Project / deployment | Stage a release directory on the machine that will run it, from a clean checkout of the release tag or commit; never stage on one operating system and copy the result to another. Applies to every host. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-026](#dec-026--stage-releases-on-the-target-machine) |
| DEC-027 | Project / stages | Re-stage the open work by value per effort: stage 2 closes out with #130, #131, #67 and a hardware check of the stage-2 features; stage 3 is worked in the order #31, #30, #28, #27, #29; stage 4 (#128) stays after stage 3; a new stage 5 "public distribution and backlog" takes #22 to #25 and #117. The stage-2 Launch requirements those issues own are not met and not dropped. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-027](#dec-027--re-stage-the-open-work-by-value-per-effort) |
| DEC-028 | Project / workflow | Pragmatic delivery: good enough instead of 100%. Scope, evidence and review depth are bounded up front, evidence is one or two runs instead of matrices, optional polish and nits go to the next PR, small follow-ups are folded into the open PR. Safety gates are unchanged. | Confirmed owner decision, main session, 2026-11-09; see [DEC-028](#dec-028--pragmatic-delivery) |

These seed entries restate decisions already present in the current project
discussion/rules; they do not claim a separate human GitHub approval comment.
The source sessions have no permalink available in these files. PR/issue links
locate the durable project restatement, not an invented original-message URL.
The entries are active only within their described scope. A later human decision
can explicitly amend them.

### DEC-006 — Post-merge issue completion

- Status: active workflow intent; implementation and its merge remain subject to
  the normal branch, independent review and human merge process.
- Authority/source: human request in the current coordinator session on
  2026-11-04 following observation that PR #33 was merged while issue #2 remained
  open with unchecked criteria. No source-message permalink is available;
  [issue #34](https://github.com/descipar/wled-mcp/issues/34) records the work scope.
- Scope/decision: add an agent responsible for post-merge issue/checklist
  completion. This is a workflow change, not authorization to implement the WLED
  backlog, merge future PRs, deploy, change devices or publish.
- Conditions: use actual merged work and acceptance evidence under the governing
  project rules. A merge or agent verdict does not prove unrelated requirements.
  Detailed handoff, idempotency and issue-state policies in PM-01–06 are technical
  implementation choices, not separately supplied human decisions.
- Rationale supplied: issue completion should follow merge; no further rationale
  supplied. Supersedes no earlier recorded human decision; refines the existing
  workflow's missing post-merge handoff.
- Affected: PM-01–06; completion/coordinator roles, workflow, report template and
  setup checker. Coordinator propagates this ID with the requirements packet to
  implementer and reviewer; its recording is not evidence of a live completion run.
- Revalidation: changed scope, missing acceptance evidence or a different candidate
  requires reassessment; no bounded operation approval becomes standing authority.

### DEC-007 — Shared Claude Code and Codex roles

- Status: active workflow intent; the changed candidate requires refreshed
  independent review and the normal human merge decision.
- Authority/source: human request in the current coordinator session on
  2026-11-04 to rewrite the agents so Claude and Codex share definitions. No
  source-message permalink is available; [issue #37](https://github.com/descipar/wled-mcp/issues/37)
  records the implementation scope.
- Scope/decision: maintain common role definitions for both clients, preserving
  the existing issue workflow including independent review and DEC-006 completion.
  Provider-neutral source files, generated native adapters and their exact format
  are technical implementation choices, not individually human-confirmed details.
- Conditions: client configuration remains separate where native formats differ;
  do not force models, providers, credentials, permissions or MCP connections.
  This does not authorize product work, model launches, merge, deployment,
  device writes, publication or closing unrelated issues.
- Rationale supplied: shared agents for the two clients; no further rationale
  supplied. Supersedes no earlier human decision.
- Affected: CA-01–06, the five role definitions and client adapters, setup tooling,
  project instructions and workflow docs; PM-01–06 remain in force. The coordinator
  propagates DEC-007 with the packet to requirements, implementation and review.
- Revalidation: edits invalidate the prior PR #35 candidate review. Structural
  fidelity, native client discovery and actual model behavior require distinct
  evidence; generated files alone do not prove an end-to-end run.

### DEC-008 — Reviewer on Opus in Claude Code

- Status: active workflow decision for Claude Code sessions.
- Authority/source: human instruction in the issue-48 workflow session, 2026-11-05
  (no permalink): the review agent has to be started with Opus, restricted by the
  human to Claude only because Codex offers no Opus model.
- Scope/decision: when the coordinator runs in Claude Code, it passes the Opus model
  explicitly on every `wled_reviewer` delegation. Codex sessions keep their inherited
  model; no Codex configuration changes.
- Conditions: the choice is made at delegation time by the coordinator. Role sources and
  generated adapters keep carrying no model override (setup checker rule unchanged). If
  Opus is unavailable in a Claude Code session, report that instead of silently
  reviewing with another model.
- Rationale supplied: none beyond Codex lacking Opus. Supersedes no earlier decision;
  refines the "models inherited from the session" default for this one role/client.
- Affected: agents/coordinator.md (and its generated adapters), docs/AGENT-WORKFLOW.md.

### DEC-009 — Public-ready repository baseline

- Status: active project decision.
- Authority/source: owner direction in the coordinator session on 2026-11-06 (no
  permalink): the project should later become public rather than serve one
  installation only, so installation-specific content must go and a proper README is
  needed; the owner also asked for example deployment files in the repository,
  referenced from the README. Issue #62 restates this direction.
- Scope/decision: keep tracked content neutral and installation-independent, provide a
  user-facing README and synthetic example deployment files for both transports, and
  guard against private identifiers in CI.
- Conditions: no visibility change, license choice, package/image publication, listing
  submission or history rewrite is implied; those remain owner decisions tracked by #23.
  Rollback/update procedures stay in stage 2 per the owner.
- Rationale supplied: later public use instead of a single installation.
- Supersedes: amends earlier "private project" framing in REQUIREMENTS.md and
  ARCHITECTURE.md going forward; historical records keep their meaning.
- Affected: README.md, docs, examples, agent roles, pyproject.toml, CI; issue #62.

### DEC-010 — Stage in every issue title

- Status: active project decision.
- Authority/source: owner instructions in the coordinator session on 2026-11-06 (no
  permalink): "ein issue muss eine stage haben und das muss im namen sichtbar sein" (English: "an issue must have a stage and that must be visible in its name");
  the owner then confirmed recording the rule "jedes Issue hat genau eine Stage, sichtbar
  als 'Stage N: …' im Titel plus Label stage:N" (English: "every issue has exactly one stage, visible as 'Stage N: …' in the title plus label stage:N"), and chose stage 1 for the workflow-tooling
  issues #34 and #37 (previously described as cross-stage), including their link as
  sub-issues of #1.
- Owner decision: every issue has exactly one stage, shown as a `Stage N: ` title prefix
  and exactly one `stage:N` label. #34 and #37 belong to stage 1.
- Coordinator-derived conventions (not owner statements; the owner may amend them):
  stage trackers use `Stage N epic: `; each issue is linked as a sub-issue of its stage
  tracker (#1, #15 or #26); a new workflow/tooling issue is assigned a stage like any
  other issue instead of being left cross-stage, and the coordinator asks the owner when
  the stage is not clear from labels, tracker and roadmap.
- Conditions: DEC-002 still governs deriving stage context; it no longer permits leaving
  an issue without a stage. Moving an issue to a different stage than the one evident
  from its labels, tracker or an owner note needs the owner; adding a missing prefix,
  label or tracker link for an evident stage does not.
- Rationale supplied: none.
- Supersedes: the "may be recorded as cross-stage" allowance in agents/coordinator.md and
  docs/AGENT-WORKFLOW.md (introduced with DEC-002, PR #32).
- Affected: AGENTS.md, agents/coordinator.md, agents/requirements.md, generated adapters,
  docs/AGENT-WORKFLOW.md, docs/IMPLEMENTATION-PLAN.md, docs/PROJECT.md; all GitHub issues
  (retitled, labelled and linked 2026-11-06).

### DEC-011 — Apache-2.0 license with NOTICE attribution

- Status: active project decision.
- Authority/source: owner instructions in the coordinator session on 2026-11-07 (no
  permalink): the project should be freely available, but others must not be allowed to
  remove the owner as author ("ich würde es gerne frei verfügbar machen, aber sie sollen
  mich als author nicht entfernen dürfen" (English: "I would like to make it freely available, but they must not be allowed to remove me as author"), typing errors corrected); after the coordinator compared MIT, Apache-2.0
  and copyleft options, the owner chose "apache mit notice" (English: "Apache with notice") and the author name for the
  attribution.
- Owner decision: outbound license Apache-2.0; a `NOTICE` file carries the copyright and
  author attribution, which Section 4(d) of the license requires redistributions,
  including modified versions, to retain. The author name in `NOTICE` and in
  `pyproject.toml` authors is an explicit owner request and an exception to DEC-005 for
  those attribution fields only.
- Coordinator notes (not owner statements): no license can stop a fork from adding its
  own authors; it requires keeping the existing notices. No third-party NOTICE content is
  needed while no upstream code is reused (SOURCES.md).
- Conditions: no visibility change, package/image publication, registry submission,
  history rewrite or public contact address is decided here (STAGE-2 open items 2-9).
- Rationale supplied: free availability with preserved author attribution.
- Supersedes: the "does not choose a license" limitation of DEC-009 for the license only.
- Affected: LICENSE, NOTICE, pyproject.toml, README.md, docs/PROJECT.md, docs/STAGE-2.md,
  scripts/check_distribution.py, tests/test_readme.py.

### DEC-012 — Project and package identity

- Status: active project decision.
- Authority/source: owner instructions in the coordinator session on 2026-11-07 (no
  permalink). The owner asked whether `wled-mcp` sounds too official, as if part of the
  WLED project; the coordinator offered (1) keep `wled-mcp` with a clear unofficial
  marking, (2) an owner prefix, (3) an own project name. The owner chose option 1 after
  a check for a WLED trademark policy, then confirmed recording the identity and the
  three conditions below as DEC-012.
- Owner decision: repository `descipar/wled-mcp`, PyPI distribution `wled-mcp`, container
  image `ghcr.io/descipar/wled-mcp`, MCP Registry name `io.github.descipar/wled-mcp`.
  Conditions: (a) no WLED logo or logo imitation, including marketplace listings;
  (b) the package summary and registry/listing texts state that the project is
  unofficial and not affiliated with the WLED project, in addition to the README
  statement; (c) if the WLED project asks for a rename, comply; this is a known risk.
- Coordinator notes (not owner statements): research on 2026-11-07 found no trademark or
  name-usage policy in the WLED repository/README (code licensed EUPL-1.2) and no active
  US registration of the word mark (one 2011 application, abandoned 2012, relation to
  the project unknown); EU/German registers were not checked. Community forks and
  companion projects commonly use the WLED name. The PyPI name was unregistered on
  2026-11-07; nothing has been reserved.
- Conditions: no name reservation, package/image publication, registry submission or
  visibility change is authorized here.
- Rationale supplied: the owner was concerned the name could appear official; resolved by
  explicit unofficial marking rather than renaming.
- Supersedes: the `io.github.<publisher>` placeholder in STAGE-2.md and MARKETPLACE.md.
- Affected: pyproject.toml (description), docs/MARKETPLACE.md, docs/STAGE-2.md.

### DEC-013 — General contact and no security support

- Status: active project decision.
- Authority/source: owner instructions in the coordinator session on 2026-11-07 (no
  permalink). For general contact the owner chose option (a), GitHub issues only. For
  security the owner stated that this is a private product, that they do not want to do
  extra security work, and that it is "use at own risk"; the owner then confirmed the
  coordinator's proposal below.
- Owner decision: public contact is GitHub issues only; no e-mail address in package
  metadata or listings. No security support: no private reporting channel (GitHub
  private vulnerability reporting stays off), no response commitment, no guaranteed
  fixes, no advisories. A short `SECURITY.md` states this, allows reports as regular
  issues without exploit details and recommends running the HTTP service only on a
  trusted network. S2-PUBLIC-03 requires this statement instead of a security contact.
- Coordinator notes (not owner statements): the Apache-2.0 warranty and liability
  disclaimers (Sections 7 and 8) already apply; built-in safeguards (HTTP token,
  Host/Origin checks, validation before writes) remain project requirements and are not
  affected by this decision.
- Conditions: no repository setting is changed by this decision.
- Rationale supplied: private hobby product; the owner does not want security process work.
- Supersedes: the "security reporting/contact" part of S2-PUBLIC-03.
- Affected: SECURITY.md, docs/STAGE-2.md.

### DEC-014 — Keep the existing Git history

- Status: active project decision.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink): after the coordinator presented a history scan and the options (A) keep the
  history, (B) a fresh public repository, the owner chose A and stated that the commit
  e-mail address may be public.
- Owner decision: the existing history and author identities (owner and agent noreply
  identity) stay as they are when the repository becomes public. No history rewrite and
  no fresh public repository; existing issue/PR links and commit references remain valid.
- Coordinator notes (not owner statements): the 2026-11-07 scan of all 70 commits found
  the owner's commit e-mail address, the owner's first name in earlier wording and, in
  two commits of 2026-11-04 later neutralized by #62, an internal hub hostname and coarse
  hub hardware/mount details. Test IPv4 values are synthetic; no secrets and no deleted
  files were found. A rewrite in place was not recommended because GitHub keeps pull
  request refs, so old commits would remain reachable. Accepting these historic contents
  follows from this decision.
- Conditions: no visibility change is authorized here. Open owner decision 5 (review of
  issue/PR bodies and comments before a visibility change) is not resolved by this entry.
- Rationale supplied: none beyond the e-mail address being acceptable to publish.
- Supersedes: none.
- Affected: docs/STAGE-2.md.

### DEC-015 — Issue and PR review before visibility change

- Status: active project decision.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink): the owner confirmed the coordinator's four-part proposal ("ja, mach
  DEC-015 so" (English: "yes, do DEC-015 that way")), then amended item 3: the #11 revision may stay because the hub is not
  publicly reachable.
- Owner decision:
  1. Two review layers: (a) a repeatable, read-only script (working name
     `scripts/check_issue_content.py`) that scans issue/PR titles, bodies, comments,
     review comments and their edit histories; concrete private terms come from the
     existing untracked private denylist and are never committed; (b) one agent
     read-through of all items for context no pattern detects, producing a findings
     list that the owner approves.
  2. Timing: the full review runs immediately before the visibility change, as a
     mandatory step of #23/#25; the script is built as part of #23, not now.
     Amended by DEC-019: the review, the script and the visibility change moved to
     #90.
  3. Existing edit-history findings stay: the internal hub hostname in an earlier
     revision of #11 (the owner subsequently decided against the proposed deletion
     because the hub is not publicly reachable), the owner's first name (#15, #16, #24)
     and the hub hardware (#11, #62).
  4. The existing AGENTS.md rule keeps issues and PRs impersonal; no new rule.
- Coordinator notes (not owner statements): a pattern scan on 2026-11-07 of 85 issues/PRs,
  19 comments and 126 edit-history revisions found the current texts clean (remaining
  hits are synthetic examples or intended attribution) and the edit-history findings
  listed above. Pull request commits are covered by DEC-014.
- Conditions: no visibility change is authorized here. Any future deletion of an
  edit-history revision is an owner action in the GitHub UI; agents do not perform it.
- Rationale supplied: none.
- Supersedes: none.
- Affected: docs/STAGE-2.md; future #23/#25 scope.

### DEC-016 — Ship the agent tooling and decision records

- Status: active project decision.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink): the owner confirmed the coordinator's proposal below ("ja, mach DEC-016 so" (English: "yes, do DEC-016 that way")).
- Owner decision: the public repository ships `AGENTS.md`, `CLAUDE.md`, `agents/`, the
  generated `.claude/agents/` and `.codex/` definitions, `docs/AGENT-*.md`,
  `docs/agent-workflow/`, `scripts/sync_agents.py` with its tests, `docs/DECISIONS.md`
  and `docs/decisions/`. Nothing is removed or restructured now. A short orientation
  (README section and/or the CONTRIBUTING guidance of S2-PUBLIC-03) explains that the
  project is developed with a documented agent workflow, that human contributions do not
  require it, and where the design decisions are recorded; this is #23 work.
- Coordinator notes (not owner statements): removal would give no privacy benefit because
  the history stays public (DEC-014); product documentation and source comments link the
  decision records as design rationale, so removing them would break those references.
  The tracked client files contain agent roles and an agent concurrency limit only, no
  secrets or personal settings.
- Conditions: no visibility change is authorized here. Open owner decision 6 (German
  source quotes) is decided separately.
- Rationale supplied: none beyond accepting the proposal.
- Supersedes: none.
- Affected: docs/STAGE-2.md; future #23 scope.

### DEC-017 — Verbatim owner quotes with English translation

- Status: active project decision.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink): the owner confirmed the coordinator's proposal below ("ja, mach DEC-017 so"
  (English: "yes, do DEC-017 that way")).
- Owner decision: German owner quotes in decision records stay verbatim as source
  evidence and are followed by an English translation, `"original" (English:
  "translation")`. Existing quotes are translated now; the recording rules above require
  the same form for future records. Quotes are not removed or replaced by translations.
- Coordinator notes (not owner statements): 21 quote occurrences in DECISIONS.md and the
  issue-7, issue-11 and issue-12 records were translated; the translations are the
  coordinator's and do not change the recorded decisions. Earlier wording remains in the
  public history (DEC-014).
- Conditions: no visibility change is authorized here.
- Rationale supplied: none beyond accepting the proposal.
- Supersedes: none.
- Affected: docs/DECISIONS.md, docs/decisions/issue-7.md, docs/decisions/issue-11.md,
  docs/decisions/issue-12.md, docs/STAGE-2.md.

### DEC-018 — Private denylist and main branch rules

- Status: active project decision; item 3 (branch rules) is superseded by DEC-024.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink). The owner stated having no list of private terms in mind ("ich hab im
  moment keine liste überhaupt im kopf" (English: "at the moment I have no list in mind
  at all"), typing errors corrected) and then confirmed the adjusted proposal below
  ("ja, mach DEC-018 so" (English: "yes, do DEC-018 that way")).
- Owner decision:
  1. Private denylist mechanism: a local untracked `runtime/private-denylist.txt` and the
     same content as a GitHub Actions secret; a CI step writes the secret to a temporary
     file and sets `WLED_MCP_PRIVATE_DENYLIST` for `scripts/check_private_identifiers.py`.
     Without the secret (for example fork pull requests) only the rule checks run.
  2. Candidate list: an agent derives candidate terms (hostnames, addresses, device and
     network names) from the untracked `.agent-runs/` records, the Git history and the
     issues/PRs and presents them; the owner removes or adds entries. This runs together
     with the DEC-015 review immediately before the visibility change. Concrete terms
     never appear in committed files, issues or PRs.
  3. Branch rules at the visibility change: a ruleset on `main` with pull requests
     required, the CI status check required, force-push and deletion blocked, no
     required approving reviews; the owner may bypass only the pull-request requirement.
- Coordinator notes (not owner statements): branch protection/rulesets are not available
  for this private repository on its current plan, hence the timing. The script reports
  denylist hits as entry numbers only. Creating the secret and the ruleset are owner
  actions in the repository settings; the CI step is #23 work (moved to #90 by DEC-019).
- Conditions: no visibility change, secret or repository setting is created by this
  decision; no denylist content is decided here.
- Rationale supplied: none beyond accepting the proposal.
- Supersedes: none.
- Affected: docs/STAGE-2.md; future #23/#25 scope.

### DEC-019 — Make the repository public before the release

- Status: active project decision.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink): the owner confirmed the coordinator's proposal below ("ja, mach DEC-019 so"
  (English: "yes, do DEC-019 that way")), including creating the readiness issue and
  adjusting #23 and #25.
- Owner decision: repository visibility is decoupled from the release. The repository
  becomes public once the readiness checklist of
  [#90](https://github.com/descipar/wled-mcp/issues/90) is complete and the owner
  explicitly instructs the change: DEC-015 review, DEC-018 denylist and CI step, DEC-016
  orientation with pre-release/no-support status and a minimal CONTRIBUTING.md, owner
  review of the overall state, the visibility change by the owner, and the DEC-018
  `main` ruleset immediately afterwards. Package/image publication and registry or
  marketplace submissions remain in #25 and its final release instruction.
- Coordinator notes (not owner statements): rulesets and unlimited Actions minutes become
  available with public visibility, which supports parallel stage-2 work (PR #81). After
  the change, new issues, PRs and evidence are public immediately; the impersonal-issue
  rule and the DEC-018 denylist apply. #90 was created as a stage-2 sub-issue of #15; a
  "Visibility split (DEC-019)" section was appended to #23 and #25 with their previous
  bodies preserved.
- Conditions: this decision does not itself change visibility; the change requires the
  owner's explicit instruction under #90. Agents do not change visibility, secrets or
  rulesets.
- Rationale supplied: none beyond accepting the proposal.
- Supersedes: the part of #25 that bundled repository visibility into the final release
  instruction.
- Affected: docs/STAGE-2.md; issues #23, #25, #90.

### DEC-020 — Support and version policy

- Status: active project decision.
- Authority/source: owner instruction in the coordinator session on 2026-11-07 (no
  permalink): the owner accepted the coordinator's proposal below with one amendment
  ("ja, aber eine ergänzung unterstützung erst ab wled 16.0.0" (English: "yes, but one
  addition: support only from WLED 16.0.0"), typing errors corrected).
- Owner decision:
  1. Versions: `0.x` releases until a separate owner decision on `1.0`; breaking changes
     may occur in minor releases and carry migration notes in the changelog. Fixes only
     for the latest release.
  2. WLED firmware: support starts at WLED 16.0.0 (owner amendment). Within that range,
     tiers: tested (hardware evidence; currently 16.0.1), expected (source-reviewed and
     mock-tested), unknown (no claim). A version moves up a tier with recorded evidence
     from the owner or a reproducible user report. Firmware below 16.0.0, including
     0.15.x, is unsupported: the server warns but does not refuse.
  3. Python: supported means tested in CI (currently 3.13); newer versions are added when
     CI passes; older ones may be dropped when they cause effort.
  4. Platforms: Linux supported (container amd64/arm64 and stdio); Windows and macOS
     experimental.
  5. Responses to reports: best effort without commitment (DEC-013).
  A short support table in the README reflects this; #21 and #23 fill it with evidence.
- Coordinator notes (not owner statements): the existing source profile and several
  contract notes are based on WLED v0.15.1 source review plus WLED 16 evidence; this
  decision does not remove that code or documentation. Whether 0.15.x-specific handling is
  kept, and how the below-16.0.0 warning is implemented, is #21 (and #16 diagnostics) work.
  Windows is experimental partly because six tests currently fail on a local Windows
  setup while Linux CI passes.
- Conditions: no code change is made by this decision.
- Rationale supplied: none.
- Supersedes: none.
- Affected: docs/STAGE-2.md (S2-COMPAT-02); future #21/#23 scope.

### DEC-021 — Adopt the stage-2 parallel plan

- Status: active stage-2 workflow decision.
- Authority/source: owner instructions in the coordinator session on 2026-11-07 (no
  permalink). The owner asked whether stage 2 could be started with a single request
  so that the agent knows what to do ("kann man das nicht einfach machen, nach dem:
  starte stage 2 parallel und der agent weiss was zu tun ist dann?" (English: "can't
  this simply be done with: start stage 2 in parallel, and the agent then knows what to
  do?"), capitalization and typing errors corrected), and then agreed to all open points
  of the plan ("zustimmen zu allen offenen punkten im plan" (English: "agree to all open
  points in the plan"), typing errors corrected).
- Owner decision:
  1. docs/STAGE-2-PARALLEL-PLAN.md is the adopted stage-2 execution plan.
  2. At most two implementation tracks run at once; a third only for docs/read-only work.
  3. #90 comes first in Phase 1.
  4. Workflow rules: one coordinator per issue in an isolated worktree on its own branch;
     the main session is the integration owner; branches are kept current by merging
     `main` (no rebase with force-push); stacked PRs are retargeted to `main` before
     their base branch is deleted; a sync whose diff equals the PR's own commits with
     green CI keeps the review PASS, otherwise a fresh review; one merge at a time after
     the owner's merge approval; DEC-010 applies to new issues.
  5. "Depends on" in #16, #17, #20, #21 and #23 reflect the plan's couplings.
  6. "Starte Stage 2 parallel" (or an equivalent request) starts or resumes the plan;
     the main session derives progress from issue/PR state and decision records and
     stops only for merge approval, owner-only actions (visibility, secrets, rulesets,
     publication), hardware authorization and genuine decisions.
- Coordinator notes (not owner statements): the start phrase mirrors DEC-001 for single
  issues. Human merge approval per PR stays unchanged. The "Depends on" lines were edited
  on 2026-11-07 (#16: #21; #17: #16, #20, #21; #20: #16 plus classifying tools of
  #17-#19; #21: stage-1 foundations, absorbs #70; #23: #16, #90).
- Conditions: stage 2 only; changes to plan order, track count or rules need the owner.
  Does not authorize visibility changes, publication, deployment or hardware writes.
- Rationale supplied: start stage 2 with one request without repeating instructions.
- Supersedes: the "proposal only" status of docs/STAGE-2-PARALLEL-PLAN.md.
- Affected: docs/STAGE-2-PARALLEL-PLAN.md, agents/coordinator.md and generated adapters,
  AGENTS.md, docs/AGENT-WORKFLOW.md; issues #16, #17, #20, #21, #23.

### DEC-022 — Proportionate review and standing merge approval

- Status: active stage-2 workflow decision; the standing merge approval (item 4) is
  pending revalidation after three issues (see Conditions).
- Authority/source: owner instructions in the coordinator session on 2026-11-08 (no
  permalink). The owner observed that the work takes long ("ich hab das gefühl das
  alles dauert immer sehr lange weil vllt auch zuviele tests gemacht werden"
  (English: "I have the feeling that everything always takes very long, maybe also
  because too many tests are done")). The coordinator answered that the test suite is
  not the bottleneck and proposed items 1-3 and, optionally, item 4. The owner
  answered: "ersten 3 punkte so übernehmen und auch so festschreiben das auf anderen
  rechner das so gemacht wird. pauschale freigabe erteilt, sollte aber nach 3-4 issues
  nochmal überprüpft werden" (English: "adopt the first 3 points as proposed and record
  them so that it is done this way on other computers as well. Blanket approval
  granted, but it should be reviewed again after 3-4 issues"), typing errors kept.
- Owner decision:
  1. Nits do not start a review round. A PASS (which may list nits) with no must-fix is
     mergeable; nits and optional should-fix items are carried into the next PR of the
     same track (or a follow-up issue) and listed in the PR body. A correction round is
     needed only for must-fix items and for should-fix items that concern behavior,
     safety, data loss or factually wrong documentation.
  2. A sync that merges `main` into a reviewed branch keeps the review PASS when the
     coordinator verifies that the branch's own changes under `src/`, `tests/` and
     `scripts/` are unchanged against the reviewed SHA
     (`git diff <base>..<reviewed>` equals `git diff <main>..<synced>` for those paths),
     the remaining differences are conflict resolutions or wording in documentation,
     no newly merged work overlaps semantically with the PR (for example it changes
     code the PR calls or the same contract), and CI is green on the synced head. The
     coordinator records this check in the PR. Any change to own code, tests or
     scripts, or a semantic overlap, needs a fresh review. This refines the sync rule
     of DEC-021 item 4 and docs/STAGE-2-PARALLEL-PLAN.md.
  3. Review depth is proportionate. Documentation-only and small non-behavioral PRs get
     a light review: acceptance criteria, links, consistency, privacy and CI; no mutation
     runs, fixture regeneration or source re-reads. Full depth (reproducers, mutants,
     upstream source checks) stays for code that writes to devices or files, changes
     safety, protocol or security behavior, or changes data formats. The reviewer is
     still launched with Opus (DEC-008). The test suite itself is not reduced.
  4. Standing merge approval: the coordinator may merge a stage-2 PR without asking
     when all of the following hold, and reports the merge afterwards:
     - a current-head review verdict PASS (nits allowed) without must-fix, or a sync
       that keeps the PASS under item 2;
     - all CI checks green on that exact head; the merge uses
       `gh pr merge --squash --match-head-commit <sha>`;
     - no open NEEDS_DECISION, no scope change beyond the issue/packet, and no change
       to repository visibility, secrets, rulesets, publication, deployment or
       hardware/LAN access in the PR.
     The PR body or a coordinator comment states "Merged under DEC-022 standing
     approval". Post-merge completion follows as before.
- Conditions: stage 2 only. Item 4 covers the merges of at most three issues reaching
  completion (DONE) under it, counted from 2026-11-08 (first round: #18, #21, #19;
  renewed for a second round, see Revalidation), PR-by-PR merges of partial scopes
  included in their issue. After the third, the coordinator stops merging
  without asking and asks the owner to confirm, adjust or end the standing approval;
  the owner may end it at any time. Owner-only actions and hardware authorization
  stay separate.
- Revalidation, 2026-11-08 (owner, coordinator session): after #18, #21 and #19 had
  reached completion under item 4, the coordinator stopped merging and asked. The
  owner answered "Weiter für 3 Issues (meine Empfehlung): Die Bedingungen bleiben
  gleich, also PASS von Opus für den aktuellen Stand und grüne CI. Danach frage ich
  wieder nach." (English: "Continue for 3 issues (my recommendation): the conditions
  stay the same, i.e. PASS from Opus for the current head and green CI. Afterwards I
  ask again."), quoting the coordinator's option text. Effect: item 4 continues
  unchanged for the next three issues reaching completion (DONE), counted from this
  answer; the first of them is #16. After the third, the coordinator stops and asks
  again. The owner did not answer the second question of that exchange (see
  ISSUE-19-DEC-003, interpretation S-1, `blend_mode` without `allow_overlap`); it stays
  a coordinator reading awaiting owner confirmation.
- Coordinator note (not an owner statement), 2026-11-08: since the DEC-024 rulesets the
  merge command of item 4 is `gh pr merge --squash --match-head-commit <sha>` and, when
  that is refused only because no approving review exists, the same command with
  `--admin` (the owner's bypass for pull-request merges). The conditions of item 4 are
  unchanged; `--admin` is no additional permission and never covers failing checks. See
  `agents/coordinator.md`.
- Rationale supplied: shorten turnaround without reducing the test suite.
- Supersedes: per-PR merge approval in stage 2 while item 4 is active (DEC-021 item 4
  "one merge at a time after the owner's merge approval" and item 6 "stops only for
  merge approval" apply again when item 4 ends; one merge at a time stays); adds an
  exception to the recording rule on standing permission; refines the DEC-021 sync
  rule.
- Affected: agents/coordinator.md, agents/reviewer.md and generated adapters,
  AGENTS.md, docs/AGENT-WORKFLOW.md, docs/STAGE-2-PARALLEL-PLAN.md, the recording rules
  above.

### DEC-023 — Staged first public release

- Status: active stage-2 release decision; item 3 contains one coordinator reading
  awaiting owner confirmation.
- Authority/source: owner instructions in the coordinator session on 2026-11-08 (no
  permalink). The owner remarked that a lot of tokens and money had been spent without
  a public release ("wir haben nun schon massiv token und geld verbraucht und sind noch
  nicht bei einem öffentlichen release" (English: "we have already used a lot of tokens
  and money and are not yet at a public release"), typing errors corrected) and that the
  required scope itself can be shortened ("diesen plan was verlangt ist kann man auch
  kürzen" (English: "what this plan requires can also be shortened")). The coordinator
  proposed three stages (stage 0: public repository and GitHub release; stage 1: plus
  PyPI; stage 2: everything else, later). The owner answered "Stufe 0, dann PyPI danach
  entscheiden" (English: "Stage 0, then decide on PyPI afterwards").
- Owner decision:
  1. The first public release is stage 0: after the DEC-015 scan and the owner's approval
     of its findings, the owner makes the repository public (DEC-019) and a GitHub
     release is created from an exact `main` commit, tagged with the version of the single
     version source (S2-COMPAT-01). Installation is from Git
     (`uvx --from git+https://github.com/descipar/wled-mcp wled-mcp`).
  2. Whether a PyPI package follows (stage 1: wheel/sdist and one publish workflow) is
     decided by the owner after the repository is public.
  3. Everything else listed as Launch in this document is deferred past the first public
     release, not dropped: the container image pipeline and provenance work of #22
     beyond a possible PyPI workflow, the remaining documentation of #23 beyond what a
     reader of the public repository needs (quickstart, changelog), marketplace and
     registry listings (#24) and the beta/launch report with simulator and H07 (#25).
     Coordinator reading, awaiting owner confirmation: the DEC-018 CI secret step and the
     `main` ruleset are not prerequisites of stage 0; the ruleset stays recommended
     immediately after the visibility change because it needs no further work.
  4. The DEC-015 scan (issue and PR text with edit histories) and the owner's approval of
     its findings are not reduced: public content cannot be withdrawn afterwards.
- Conditions: bounded to the first public release. Publication of any artifact, a
  visibility change and every secret or ruleset remain owner-only actions that need the
  owner's explicit instruction at that time; this decision authorizes none of them.
  Deferred items can be scheduled again by the owner at any time.
- Rationale supplied: reach a public release with less spend and effort.
- Supersedes: the Launch classification in docs/STAGE-2.md for the items in item 3, for
  the first public release only; DEC-018 is not superseded (see item 3 reading).
- Affected: docs/STAGE-2.md (release staging note), issues #15, #22, #23, #24, #25 and
  #90 (comments with the deferral; bodies and acceptance lists unchanged).

### DEC-024 — Main branch rules with review for external pull requests

- Status: active project decision; items 1 and 3 contain coordinator readings awaiting
  owner confirmation (see Coordinator notes).
- Authority/source: owner instructions in the coordinator session on 2026-11-08 (no
  permalink). Asked how the `main` rules of DEC-018 could require a review of pull
  requests from others, the owner wrote "was ist wenn ich will, das ich das reviewn
  lassen will wenn andere außer dich und von mir gestartete agenten ein pr machen. von
  fremden will ich das vorher sehen" (English: "what if I want to have it reviewed when
  others, apart from you and agents started by me, open a PR. I want to see those from
  outsiders beforehand"), typing errors kept, and confirmed the coordinator's proposal:
  "ja, mach DEC-024 so und schreib die klickschritte bzw. prüfe über du das per api nicht
  selber kannst" (English: "yes, do DEC-024 that way and write the click steps, or check
  via the API what you cannot do yourself"), typing errors kept.
- Owner decision, applied at the visibility change (#90, DEC-019), created by the owner:
  1. Ruleset A, no bypass actors, target the default branch: required status checks
     `checks (ubuntu-latest, 3.13)` and `checks (ubuntu-24.04-arm, 3.13)`, block force
     pushes, restrict deletions. "Require branches to be up to date" is not enabled.
  2. Ruleset B, target the default branch: require a pull request with one approving
     review. Bypass list: the repository admin role (the owner), bypass mode "for pull
     requests only". Reviews of pull requests from external contributors are therefore
     required; pull requests of the owner and of agents working under the owner's account
     are merged by the owner's bypass.
  3. Repository setting Actions, General, "Approval for running fork pull request
     workflows from contributors": "Require approval for all external contributors", so
     that no workflow of an outside pull request runs before the owner has seen it.
  4. The agent verifies the result read-only through the API (GET requests only) after
     the owner created it, as described in the [runbook](validation/issue-90.md).
- Coordinator notes (not owner statements): GitHub applies a bypass to the whole ruleset,
  not to single rules, so the DEC-018 wording "bypass only the pull-request requirement"
  is realized by keeping the CI, force-push and deletion rules in ruleset A without
  bypass (documentation check, not yet observed live). Reading 1: bypass mode "for pull
  requests only" lets the owner merge but not push directly to `main`; an owner who wants
  direct pushes would choose "always allow" in ruleset B. Reading 3: the squash merge by
  the coordinator needs `gh pr merge --admin` once ruleset B is active; that command
  change, with `agents/coordinator.md` and DEC-022 item 4, is made after ruleset B exists
  and the first merge has been observed. Observed 2026-11-08 on the first merge under the
  rulesets: the plain squash merge was refused (review required) and `--admin` merged it
  with green checks, which confirms reading 3 and the documented bypass of ruleset B for a
  pull-request merge; the command change was then made. Rulesets and the fork-approval setting cannot be
  read or created while the repository is private (observed 2026-11-08: HTTP 403 and
  422), so verification is possible only after the visibility change.
- Conditions: creating the rulesets and the setting is an owner-only action; this decision
  changes no repository setting, visibility or secret. The CI-secret denylist step of
  DEC-018 and its deferral under DEC-023 are unaffected.
- Rationale supplied: pull requests from outsiders must be seen by the owner before they
  run or merge.
- Supersedes: DEC-018 item 3 (branch rules) only.
- Affected: docs/validation/issue-90.md (runbook), issue #90 acceptance item on the
  ruleset, agents/coordinator.md and DEC-022 item 4 (merge command, follow-up).

### DEC-026 — Stage releases on the target machine

- Status: active project decision. DEC-025 is reserved for the stage 4 plan, whose record is
  kept in issue #127 until stage 4 starts.
- Authority/source: owner instructions in the coordinator session on 2026-11-08 (no
  permalink), while a release was being installed on a Linux host after being staged on a
  Windows machine: "ich will kein staging auf windows und dann kopieren auf linux. stage
  immer auf dem rechner wo wir installieren wollen" (English: "I do not want staging on
  Windows and then copying to Linux. Always stage on the machine where we want to install"),
  typing errors corrected. When the coordinator had stored it as a private note, the owner
  corrected: "nein, das soll kein memory sein, sondern auch für andere rechner gelten"
  (English: "no, that should not be a memory, it should also apply to other computers").
- Owner decision: release directories (`deploy/stage_release.py`) are staged on the machine
  that will run them, from a clean checkout of the release tag or commit, and are not built
  on another machine or operating system and copied. The rule applies on every host and for
  every agent; it is part of the repository rules, not a personal preference.
- Observed the same day (not owner statements): a wheel and the staged `Dockerfile`,
  `.dockerignore` and `requirements-runtime.txt` built from a Windows checkout had other
  hashes than those staged on the Linux host, probably because of CRLF line endings
  ([#131](https://github.com/descipar/wled-mcp/issues/131)); the Linux constraints file had
  the SHA-256 recorded for the first release.
- Conditions: applies to release directories and the images and hub entries built from them.
  It does not cover running the test suite or the development checks on a development
  machine. Where the target cannot build (no `uv`, no network, no Docker), the owner decides
  the exception; it is not assumed.
- Rationale supplied: the directory that is installed must be the one that was built on that
  system.
- Supersedes: the "from a clean checkout ... on a build machine" and "copy the directory
  unchanged to the target" wording of docs/DEPLOYMENT.md and docs/QUICKSTARTS.md.
- Affected: docs/DEPLOYMENT.md, docs/QUICKSTARTS.md, AGENTS.md,
  docs/validation/live-check-2026-11-08.md.

### DEC-027 — Re-stage the open work by value per effort

- Status: active project decision. Items 5 to 8 are coordinator defaults the owner did not
  decide explicitly; they stay open for confirmation.
- Authority/source: owner instructions in the coordinator session on 2026-11-08 (no
  permalink). The owner asked the coordinator to go through all issues, find an order that
  brings the most with minimal effort, re-order the work and assign stages, have it reviewed
  by Opus and present the plan. After the plan and the review result were presented, the owner
  answered "setze den plan vom review einfach so um" (English: "just implement the plan from
  the review as it is").
- Owner decision (the plan as presented, with the review's changes):
  1. Stage 2 closes out with #130, #131, #67 and a new issue for a hardware check of the
     stage-2 features on the test controller, narrowed to what one RGB controller can show
     (preset store, import and restore, a playlist, one single-device scene, groups as local
     files). Multi-device scenes, CCT, 2D and profiles are not part of it; `discover` runs
     only on an explicit request; H07 and the live rollback stay with #25 (the rollback after
     the first release that changes code).
  2. Stage 3 is worked in value order: #31 (kept small), #30, #28, #27, #29.
  3. Stage 4 (#127, #128) stays after stage 3, as the owner set earlier.
  4. A new stage 5 "public distribution and backlog" (tracker #133) takes #22, #23, #24, #25
     and #117. They are worked only on a trigger: a wish to be listed, outside interest or
     hardware-verified features. The PyPI decision stays with the owner.
- Effect on earlier records: the stage-2 Launch requirements owned by #22 to #25 (S2-DIST-01 to
  03, the remaining S2-PUBLIC-02 and S2-PUBLIC-03, S2-MARKET-01 to 03, S2-LAUNCH-01 and 02 and
  the live part of S2-COMPAT-03) are not met and are not dropped; they now belong to stage 5.
  The acceptance line of #15 "every launch-required requirement has evidence" applies to
  stage 5 for these IDs, and DEC-023 item 3 is refined accordingly: still deferred, now
  tracked in stage 5. Records that say "moved to stage 2 (#25)" describe #25 as it was when
  they were written and are not rewritten.
- Coordinator defaults, not decided by the owner and open for confirmation:
  5. Merging PR #132 (DEC-026 and the live-check record) was treated as part of the plan.
  6. The nightlight auto-off idea is not added to stage 3 (it would be a sixth feature beyond
     DEC-004 and its end behavior is undocumented); no issue was created.
  7. DEC-021 and DEC-022 are not extended to stage 3 or 5: merges still need the owner's
     approval.
  8. The four pending confirmations (DEC-023 item 3, DEC-024 readings 1 and 3,
     ISSUE-19-DEC-003 S-1, the PyPI decision) stay open.
- Conditions: no hardware run, setting change, deployment or publication is authorized by
  this decision.
- Rationale supplied: the owner wants the next steps ordered by benefit for the least effort.
- Supersedes: nothing; refines DEC-023 item 3 and the stage assignment of #22 to #25 and #117.
- Affected: docs/STAGE-2.md, docs/STAGE-3.md, docs/STAGE-5.md, docs/PROJECT.md, issues #15,
  #22 to #25, #117, #26, #133 and the new hardware-check issue.

### DEC-028 — Pragmatic delivery

- Status: active project workflow decision.
- Authority/source: owner instructions in the main session on 2026-11-09 (no permalink). While
  a dependency-range change was being prepared the owner said "mach es doch sinnvoller und gehe
  nicht alle versionen so tief runter, da kann man doch mal abwägen" (English: "do it more
  sensibly and do not go that deep into all versions, you can weigh it up"), then "für mich
  haben sich die agenten da schon wieder verzettelt. ich will eine pragmatische heransgehensweise
  und keine immer 100% lösung" (English: "to me the agents got lost in details again. I want a
  pragmatic approach and not always a 100% solution") and "das gehört allgemein in das projekt"
  (English: "this belongs in the project in general").
- Owner decision (the wording of the items is the main session's, from that instruction):
  1. Aim for good enough, not for completeness. Fix scope, evidence and review depth before
     starting and say so in the packet; weigh effort against risk and state the weighing in one
     or two lines.
  2. Evidence is one or two runs that show the point (for example the lower bound and the
     current set of a dependency range), not matrices or exhaustive combinations. Where the
     evidence is thin, choose the conservative limit and say so.
  3. Review depth follows DEC-022 (light unless the change writes to devices or files, changes
     safety, protocol or security behavior or data formats; DEC-028 adds: or cannot be undone). No extra review
     rounds, no tests beyond what the change needs and no optional polishing; nits go to the
     next PR.
  4. A small follow-up that belongs to the same release path is folded into the open PR instead
     of a new PR, when it does not make the review harder.
- Not changed: hardware authorization, the owner's approval for publication, tagging and
  releases, the human merge decision and the other rules of DEC-022, DEC-024 and DEC-023.
- Applicability: all issues and all agents of this repository until the owner changes it.

## Issue-specific decisions (pointers)

Stage 5 (recorded 2026-11-09):
- [ISSUE-22-DEC-001](decisions/issue-22.md) (human, owner chat instruction, 2026-11-09,
  issue #22 only): build `.github/workflows/publish.yml` with Trusted Publishing behind the
  GitHub environment `pypi`, implemented and reviewed on Opus; no upload, registration,
  environment, tag or release is authorized. ISSUE-22-DEC-002 (coordinator, technical
  proposal): PyPI part only, release/dispatch triggers, tag-version and `main`-reachability
  guard, SHA-pinned actions, `docs/PUBLISHING.md`, package-page metadata. Owner update
  2026-11-09: #141 merged, items 2 and 4 confirmed, no TestPyPI rehearsal.
- [ISSUE-22-DEC-003 and -005](decisions/issue-22.md) (human, owner chat, 2026-11-09, issue
  #22 only): loosen the exact runtime pins; make README.md fit for the PyPI project page in
  the same pull request. ISSUE-22-DEC-004 (coordinator, technical proposal): the declared
  ranges, `anyio` declared, floors confirmed by a lowest-direct run,
  `docs/contract/dependencies.md`.

Stage 2 (recorded 2026-11-07):
- [ISSUE-16-DEC-001](decisions/issue-16.md) (human): `config validate` plus restart
  instead of in-process reload; CLI-only standard-library discovery.
  ISSUE-16-DEC-002 (coordinator, technical proposal): CLI shape and exit codes, atomic
  config writes, read-only `doctor` with sanitized export, no `config migrate`.
- [ISSUE-17-DEC-001](decisions/issue-17.md) (human): groups and scenes are local JSON
  documents under `<data-dir>/groups/` and `<data-dir>/scenes/`, written by `manage`
  tools; the default failure policy is `strict`, `best_effort` is an opt-in.
  ISSUE-17-DEC-002 (coordinator, technical proposal): technical defaults TD-17-1 to
  TD-17-18 for #17 (two pull requests, tools and classes, formats and limits, sharing,
  coverage) and C-17-1 (#17 starts with the class classification only); amendment 1
  (pull request B): per-device `UNKNOWN_DEVICE` reading, guard location of TD-17-16, leak
  scan of every exported string.
- [ISSUE-18-DEC-001](decisions/issue-18.md) (human): supplied objects are written as
  single JSON API entries with a documented live effect; ISSUE-18-DEC-002 (coordinator):
  #19 owns the capability model; ISSUE-18-DEC-003 (coordinator, technical proposal):
  no version gate, exact-firmware restore with its own snapshot, tool names/classes and
  coverage statuses, 192 KiB bundle and 50-entry import bounds; playlist restore
  accepts repeat/shuffle and refuses while a playlist runs.
- [ISSUE-19-DEC-001 and -002](decisions/issue-19.md) (human): overlap only with an
  explicit `allow_overlap`; `rpt`, `fxdef` and matrix/panel configuration not exposed.
- [ISSUE-19-DEC-003](decisions/issue-19.md) (coordinator): technical defaults TD-19-1 to
  TD-19-14 and acceptance scenarios AC-19-01 to AC-19-18 for #19 (capability module,
  evidence chain, field presence, matrix geometry, two pull requests).
- [ISSUE-20-DEC-001](decisions/issue-20.md) (human): default profile `full`, per-device
  maximum class, status tool, classes `read`/`control`/`manage`; applies to every
  tool-adding issue.
  ISSUE-20-DEC-002 (coordinator, technical proposal): TD-20-1 to TD-20-15 (profile and
  class vocabulary, required `Operation.tool_class`, guard layers G1 to G3, `ACCESS_DENIED`,
  additive configuration, two pull requests) and C-20-1 (provisional migration release).
- [ISSUE-21-DEC-001](decisions/issue-21.md) (human): automated update/rollback tests in
  #21, live run as #25 evidence.
- [ISSUE-21-DEC-002](decisions/issue-21.md) (coordinator): technical defaults TD-21-1 to
  TD-21-10 for #21 and #70 (version source, non-release ids, matrix, policy).
- [ISSUE-31-DEC-001](decisions/issue-31.md) (coordinator, technical proposal): technical
  defaults TD-31-1 to TD-31-12 for effect search, two properties `visibility` and
  `palette_saturation_need`, catalog not applied below the firmware floor.
- [ISSUE-94-DEC-001 and -002](decisions/issue-94.md) (human; coordinator): `unplanned`
  coverage status; coverage-list technical defaults.
- [ISSUE-98-DEC-001](decisions/issue-98.md) (coordinator): every tool-adding PR adds its
  tool with its class to `tests/tool_contract.py`.

- [ISSUE-52-DEC-001](decisions/issue-52.md) (delegated decision, 2026-11-05, issue #52
  only, content decided by the coordinator): `wled_set_state` sends `on=false` with a
  positive brightness on an off master, shows it as targeted compensation and verifies
  the resolved `on` on every master write.
- [ISSUE-48-DEC-001](decisions/issue-48.md) (human, 2026-11-05, issue #48 only): both
  segment tools reject unrepresentable names (>32 UTF-8 bytes, U+0000), grouping/spacing
  outside 1/0-255, `on=true` with `brightness=0` and `brightness=0` without `on=false` on
  an on segment before any write; positive brightness on an off segment is compensated
  with `on=false`. Supersedes the corresponding parts of ISSUE-7-DEC-006.

- [ISSUE-7-DEC-006](decisions/issue-7.md#issue-7-dec-006--align-7-with-6-limits-and-bri-handling)
  (human, 2026-11-05, issue #7 only): `wled_replace_layout` aligns with #6 for the
  name limit, grouping/spacing bounds and `bri` handling; resolves ISSUE-7-OPEN-001.
  It does not apply to other issues.
- [ISSUE-7-DEC-003 to -005](decisions/issue-7.md) (delegated decision, 2026-11-05, issue
  #7 only): step order/allocation bound, range-capability evidence and no-op/limit
  behavior accepted. The owner delegated the choice to the main session; the content was
  decided by the main session, not personally dictated by the owner. Not generalized to
  other issues or stages.
- [ISSUE-7-DEC-007 to -009](decisions/issue-7.md) (delegated decision, 2026-11-05, issue
  #7 only, content decided by the main session): narrow reading of DEC-006 confirmed,
  `scripts/check_distribution.py` edit accepted, follow-up issue
  [#48](https://github.com/descipar/wled-mcp/issues/48) for the shared #6/#7 limits.

- [ISSUE-8-DEC-001 and -002](decisions/issue-8.md) (human, 2026-11-05, issue #8 only):
  restore execution deferred (no `wled_restore_preset`); #8 delivers the snapshot store
  and `Resources` interface, #9 wires the real tools.
- [ISSUE-8-DEC-003](decisions/issue-8.md) (delegated decision, 2026-11-05, issue #8 only,
  content decided by the main session): layout/ID, envelope, compatibility, error codes,
  retention, repo guard, fsync and backup-source defaults accepted.

- [ISSUE-9-DEC-001](decisions/issue-9.md) (delegated decision relayed by the main session,
  2026-11-05, issue #9 only, content decided by the main session): PRE-03/restore stay
  deferred, playlist overwrite rejected, type/activation rules, delete route evidence rule.

- [ISSUE-53-DEC-001](decisions/issue-53.md) (delegated decision, 2026-11-05, issue #53
  only, content decided by the coordinator): the stdio no-listener test allows only the
  stdlib loopback socketpair of the asyncio self-pipe; no product change, no platform skip.

- [ISSUE-55-DEC-001](decisions/issue-55.md) (technical coordinator decision, 2026-11-05,
  issue #55 only): the deadline/retry test uses controlled time instead of wall-clock
  sleeps; no product change.

- [ISSUE-10-DEC-001](decisions/issue-10.md) (agent technical proposal accepted by the
  coordinator, 2026-11-05, issue #10 only; not a human decision): traceability lives in
  `docs/TRACEABILITY.md`, enforced by `scripts/check_traceability.py` through a pytest
  test; hardware/deployment cells may only say `pending: ...` or `not applicable: ...`.

- [ISSUE-11-DEC-001](decisions/issue-11.md) (human, 2026-11-06, issue #11 only):
  implementation, tests, docs, review and a reviewable PR; no merge, deployment, hub
  registration, LAN/device contact, publication or license selection.
- [ISSUE-11-DEC-002](decisions/issue-11.md) (agent technical proposal accepted by the
  coordinator, 2026-11-06, issue #11 only; not a human decision): deployment defaults
  TD-1 to TD-9 (pre-staged wheel, pinned slim base image, separate Compose project,
  file secret, persistent uv paths).
- [ISSUE-11-DEC-003](decisions/issue-11.md) (human, 2026-11-06, one bounded operation):
  test installation of both modes on the hub host with read checks and power on/off on
  one authorized test controller; not standing permission.
- [ISSUE-11-DEC-004](decisions/issue-11.md) (human approval of coordinator proposals,
  2026-11-06, issue #11 only; mode choice by the coordinator): keep one mode active
  (HTTP), remove the stdio hub entry, follow-up documentation PR, issue #61.
- [ISSUE-11-DEC-005](decisions/issue-11.md) (human, 2026-11-06, issue #11 only): live
  version-to-version update/rollback moves to stage 2 (#21, #25); the documented
  procedures remain #11 scope.
- [ISSUE-11-DEC-006](decisions/issue-11.md) (human, 2026-11-06, one bounded operation):
  live removal test of the HTTP service on the same target, followed by a redeploy so
  HTTP stays the active mode; not standing permission.
- [ISSUE-11-DEC-007](decisions/issue-11.md) (human, 2026-11-06, one bounded operation):
  remaining box 5/6 live checks on the same target and test controller (catalog and
  preset reads, stdio rebuild, hub container recreation); writes only after a
  restorable baseline, none performed; not standing permission.
- [ISSUE-11-DEC-008](decisions/issue-11.md) (human, 2026-11-06, issue #11 only): live
  drain of an in-flight call on the target and load measurements move from #11 to #12;
  automated T21 drain coverage stays the #11 evidence; no live operation authorized.

- [ISSUE-12-DEC-001](decisions/issue-12.md) (human, 2026-11-06, issue #12 only): one
  designated test controller released for #12 testing including writes, on condition
  that state, segment layout and presets file are captured before and restored after,
  with verified, recorded restoration; that controller only; not standing permission.
- [ISSUE-12-DEC-002](decisions/issue-12.md) (agent technical proposal accepted by the
  coordinator, 2026-11-06, issue #12 only; not a human decision): HTTP only, preset slot
  250, no controller reboot, opt-in read-only HTTP probe, restoration criteria R1-R3,
  stdio context interpretation; TRACEABILITY cell forms unchanged (ISSUE-10-DEC-001).
  Superseded in part: TD-12-1 (HTTP only) by ISSUE-12-DEC-004.
- [ISSUE-12-DEC-003](decisions/issue-12.md) (coordinator interpretation of the owner's
  #12 implementation instruction and #12 acceptance box 7, 2026-11-06, issue #12 only;
  not a human decision): stop/start of the deployed HTTP service and load against it
  are in scope; no rebuild, inventory/secret edit or hub change. ISSUE-11-DEC-008 asked
  for an instruction naming target and operations; the plan was announced to the owner
  without objection but without separate explicit approval. Confirmed retroactively by
  the owner on 2026-11-06 for that run only; not standing permission for future service
  operations.
- [ISSUE-12-DEC-004](decisions/issue-12.md) (human, 2026-11-06, issue #12 only): stdio
  via uvx stays in #12 scope; stdio-mode drain, load and H04-H06 live checks are
  required for #12; supersedes TD-12-1 (HTTP only) of ISSUE-12-DEC-002 for the remaining
  #12 work (ISSUE-12-DEC-002 is superseded in part).
- [ISSUE-12-DEC-005](decisions/issue-12.md) (human, 2026-11-06, one bounded run): second
  #12 live run: update the HTTP deployment to a build from current main and stop/start
  it; temporary stdio hub entry with the HTTP entry disabled, then restored; the same
  test controller with capture and restore; the owner observes with delayed replies, no
  test relies on a quick reaction; this run only, not standing permission.
- [ISSUE-12-DEC-006](decisions/issue-12.md) (human, 2026-11-06, issue #12 and stdio host
  lifecycle only): the host closing the stdio connection on entry disable/stop without
  draining in-flight calls is accepted as a documented stdio limitation; HTTP is the
  preferred mode; no code change; not a deprecation of stdio.
- [ISSUE-12-DEC-007](decisions/issue-12.md) (human, 2026-11-06, issue #12 only; item 2
  one bounded run): remaining #12 scope after run 2: H02 UI comparison satisfied by
  the controller endpoints the WLED UI renders; one owner-watched HTTP run for visible
  effect animation and speed with capture/restore (run 3, expired after it); stdio H04,
  host-level stdio drain and rate-limited stdio load through the hub are sufficient
  for #12; live H07 moves to stage 2 (#25), mocked coverage remains.
- [ISSUE-12-DEC-008](decisions/issue-12.md) (human, 2026-11-06, issue #12 only): H04
  needs no separate visual check of an intensity change; verified readback of intensity
  writes plus the owner-confirmed visible speed change are sufficient.
- [ISSUE-66-DEC-001](decisions/issue-66.md) (agent technical determination accepted by
  the coordinator, 2026-11-06, issue #66 only; not a human decision): WLED v16.0.1 `bs`
  (blending style) is light state; it joins the `state` allowlist and the save compare
  (only when live state has it); a saved entry that is not `state` gets a key-name-only
  warning. Amends the issue-9 allowlist without superseding ISSUE-9-DEC-001.
- [ISSUE-61-DEC-001](decisions/issue-61.md) (human, 2026-11-06, issue #61 only): option
  A — underscores are accepted in `base_url` host labels; all other URL checks stay
  fail-closed; a rejected inventory names the offending device entry without secrets.
- [ISSUE-61-DEC-002](decisions/issue-61.md) (agent technical proposals accepted by the
  coordinator, 2026-11-06, issue #61 only; not a human decision): host labels use
  `[A-Za-z0-9_-]` and must start/end alphanumeric; the startup diagnostic names
  `devices[i]` and the field, never values or the device id.
- [ISSUE-74-DEC-001](decisions/issue-74.md) (human, 2026-11-06, issue #74 only): both
  options — inventory rejects invalid IPv4-like hosts at startup, and client-side URL
  errors map to a safe domain error; no URL or host in diagnostics.
- [ISSUE-74-DEC-002](decisions/issue-74.md) (agent technical proposals accepted by the
  coordinator, 2026-11-06, issue #74 only; not a human decision): a host whose last
  label is numeric or `0x`-hex must be a canonical dotted-quad IPv4 address; client
  `InvalidURL` maps to `CONFIG_ERROR`; exception suppression is tested.
- [ISSUE-13-DEC-001](decisions/issue-13.md) (human, 2026-11-06, stage-1 scope): DEV-03
  is a documented restart procedure (reload/validate to #16); SEG-05 counts as
  delivered (CCT/2D to #19); PRE-03, restore and playlist authoring to #18; raw state
  patch, timers and pixel/realtime streaming are excluded.
- [ISSUE-13-DEC-002](decisions/issue-13.md) (agent proposal accepted by the coordinator,
  2026-11-06, #13 only; not a human decision): conditional acceptance boxes shown not to
  apply are checked as "not applicable" with evidence.
- [ISSUE-62-DEC-001](decisions/issue-62.md) (agent technical proposals accepted by the
  coordinator, 2026-11-06, issue #62 only; not a human decision): repository-wide
  private-identifier scanner with allowlist and optional untracked denylist, neutral
  role wording, README/PROJECT split, neutral package metadata.
- [ISSUE-1-DEC-001](decisions/issue-1.md) (human, 2026-11-06, stage-1 close-out): the
  OPS-04 diagnostics on main count as delivered for stage 1, the remainder is deferred to
  #16; housekeeping issue #44 belongs to stage 2.
- [ISSUE-134-DEC-001](decisions/issue-134.md) (human, delegated owner chat authority,
  2026-11-09, issue #134 only): one hardware run of the stage-2 features on the test
  controller through the hub HTTP service, state restored at the end, playlist covered; the
  run is complete and recorded in [validation/issue-134.md](validation/issue-134.md).
- [ISSUE-130-DEC-001](decisions/issue-130.md) (human, delegated owner chat authority,
  confirmed 2026-11-09, issue #130 only; technical content proposed by the coordinator):
  the served envelope and error output schema allow additional properties; the
  one-time stale-cache transition is documented.

## Still unresolved

Handling an unmet issue prerequisite is not yet a confirmed workflow decision.
Do not record either automatic prerequisite implementation or a mandatory stop
policy as a human choice: the prior discussion identified this gap but did not
choose its resolution. Requirements analysis must report actual dependency
readiness under the existing issue scope.

## Lookup and propagation

1. Read this log plus any issue-specific entries relevant to the selected issue,
   ancestor/stage and dependencies. Check current source/conditions, not keywords
   alone. Record the applicable IDs and log commit/reference in the work packet.
2. Before asking the owner, check whether an active decision answers the question.
   If it does, apply and cite it in the packet rather than ask again.
3. After a new answer, classify scope and source, save the decision and update the
   packet and relevant issue/contract documentation. Do not automatically edit
   global rules from a narrow or ambiguous answer.
4. Explicitly send changed decision IDs and consequences to active requirements,
   implementation and review agents. Shared files alone do not prove a child
   agent has received the update. Freeze dependent writes if the change invalidates
   the active implementation contract.
5. Refresh requirements references, acceptance tests and commit-specific review
   when behavior changes. Do not retain PASS for an outdated contract/candidate.
6. At handoff/resume, reload applicable entries and their status. If saving is
   unavailable, report the exact unsaved decision and hand it off; do not claim
   that a future session can recall it automatically.
