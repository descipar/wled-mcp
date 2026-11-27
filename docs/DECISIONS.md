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
  in the group file of its milestone or topic under `docs/decisions/` (see its README), using the
  decision template. Link relevant
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
  conditions and expiry (currently DEC-022 item 4 for stage-2 merges and DEC-029 item 4 for milestones M1 and M2).
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
| DEC-002 | Workflow | Derive stage from issue labels, ancestor tracker and roadmap; stage is not a mandatory user input. Ask only for relevant conflict or genuinely unclear scope. Amended by DEC-010: every issue must carry a stage. Amended by DEC-029: open and new work uses milestones. | Confirmed human correction, project workflow discussion, 2026-11-04; [PR #32](https://github.com/descipar/wled-mcp/pull/32) |
| DEC-003 | Project / transport scope | Support both Streamable HTTP and client-managed stdio via uvx, sharing the WLED tool/domain contract. | Confirmed human scope instruction, transport discussion, 2026-11-04; [requirements](REQUIREMENTS.md), [issue #14](https://github.com/descipar/wled-mcp/issues/14) |
| DEC-004 | Stage 3 | Named zones, temporary signals, static previews, lighting explanations and effect-property search belong to stage 3 and do not block stage-2 publication. | Confirmed human stage assignment, roadmap discussion, 2026-11-04; [stage-3 roadmap](STAGE-3.md), [tracker #26](https://github.com/descipar/wled-mcp/issues/26) |
| DEC-005 | Project documentation / issues | Use neutral roles and synthetic examples. Exclude personal names, private hostnames and installation-specific personal context unless explicitly requested. | Existing governing [AGENTS.md](../AGENTS.md) rule, recorded 2026-11-04 |
| DEC-006 | Workflow | Add an agent responsible for completing issue checklists after merge. | Confirmed human instruction, post-merge workflow discussion, 2026-11-04; [issue #34](https://github.com/descipar/wled-mcp/issues/34) |
| DEC-007 | Workflow / role maintenance | Maintain shared agent definitions usable with Claude Code and Codex. | Confirmed human instruction, shared-agent discussion, 2026-11-04; [issue #37](https://github.com/descipar/wled-mcp/issues/37) |
| DEC-008 | Workflow / Claude Code only | In Claude Code, the coordinator launches the independent reviewer (`wled_reviewer`) explicitly with the Opus model. Codex is unaffected. | Confirmed human instruction, issue-48 workflow session, 2026-11-05; see [DEC-008](#dec-008--reviewer-on-opus-in-claude-code) |
| DEC-009 | Project / public readiness | Keep the repository public-ready: neutral, installation-independent content, a user-facing README and copyable synthetic example deployment files referenced from the README. This does not change visibility, choose a license, publish anything or rewrite history. | Confirmed owner direction, coordinator session, 2026-11-06; see [DEC-009](#dec-009--public-ready-repository-baseline) and [issue #62](https://github.com/descipar/wled-mcp/issues/62) |
| DEC-010 | Project / issue tracking | Every issue belongs to exactly one stage, visible as a `Stage N: ` title prefix plus one `stage:N` label. Issues #34 and #37 belong to stage 1. Further conventions are coordinator-derived (see section). Superseded by DEC-029 for open and new work; closed history unchanged. | Confirmed owner instruction, coordinator session, 2026-11-06; see [DEC-010](#dec-010--stage-in-every-issue-title) |
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
| DEC-024 | Project / main branch rules | Replaces the single branch rule of DEC-018 item 3 with two rulesets on `main` and one Actions setting: ruleset A (CI checks required, no force-push, no deletion, no bypass), ruleset B (pull request with one approval; the owner may bypass only when merging a pull request) and approval of workflow runs for all external contributors. Pull requests from others therefore need the owner's approval before their CI runs and before they merge. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-024](#dec-024--main-branch-rules-with-review-for-external-pull-requests) and [runbook](validation/releases.md) |
| DEC-026 | Project / deployment | Stage a release directory on the machine that will run it, from a clean checkout of the release tag or commit; never stage on one operating system and copy the result to another. Applies to every host. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-026](#dec-026--stage-releases-on-the-target-machine) |
| DEC-027 | Project / stages | Re-stage the open work by value per effort: stage 2 closes out with #130, #131, #67 and a hardware check of the stage-2 features; stage 3 is worked in the order #31, #30, #28, #27, #29; stage 4 (#128) stays after stage 3; a new stage 5 "public distribution and backlog" takes #22 to #25 and #117. The stage-2 Launch requirements those issues own are not met and not dropped. | Confirmed owner decision, coordinator session, 2026-11-08; see [DEC-027](#dec-027--re-stage-the-open-work-by-value-per-effort) |
| DEC-028 | Project / workflow | Pragmatic delivery: good enough instead of 100%. Scope, evidence and review depth are bounded up front, evidence is one or two runs instead of matrices, optional polish and nits go to the next PR, small follow-ups are folded into the open PR. Safety gates are unchanged. | Confirmed owner decision, main session, 2026-11-09; see [DEC-028](#dec-028--pragmatic-delivery) |
| DEC-029 | Project / roadmap | Replace numbered stages by GitHub milestones for open and new work: every open or new issue has exactly one milestone (Backlog counts), no `Stage N:` prefix and no `stage:N` label for new issues; closed history and requirement IDs keep their stages. Supersedes DEC-010 for open and new work, amends DEC-002. Records the new scope (#147 to #151), the order and a bounded standing merge approval for milestones M1 and M2. Amended by DEC-030 (#24 in M1, milestone closure). | Confirmed owner decision, main session, 2026-11-09; see [DEC-029](#dec-029--milestones-instead-of-stages) and [issue #152](https://github.com/descipar/wled-mcp/issues/152) |
| DEC-030 | Project / roadmap | Closing a milestone includes at least a minor release and a README update. Applies from M1, whose scope also includes #24; M1 stays open until that release is done. Tag, GitHub release, PyPI/registry publication and submissions still need the owner's explicit instruction. | Confirmed owner answers, main session, 2026-11-09; see [DEC-030](#dec-030--milestone-closure-includes-a-minor-release) |
| DEC-031 | Project / roadmap | Release scope for M2 is the same as for M1: tag, GitHub release, PyPI upload and official MCP Registry publication; preparing release 0.3.0 is allowed now, each publication step needs the owner's explicit instruction at that time, and M2 stays open until the release is done. Applies to M2 only. | Confirmed owner answer, coordinator session, 2026-11-11; see [DEC-031](#dec-031--release-scope-for-milestone-m2) |
| DEC-032 | Project / roadmap | Milestone M3 is closed without its own minor release: the owner waives DEC-030 item 1 for M3 because its scope is too small for a release. Its merged work (#27, #29) ships with the next minor release. Applies to M3 only. | Confirmed owner statement, coordinator session, 2026-11-11; see [DEC-032](#dec-032--m3-closes-without-its-own-release) |
| DEC-033 | Project / development platform | Windows is a supported development platform: the test suite and local tooling are expected to work on a Windows checkout, so Windows-only test failures are defects to fix or to skip with a stated reason. Narrow scope: the user-facing platform tier of DEC-020 item 4 (Windows experimental) and the CI matrix are unchanged. | Confirmed owner statement, coordinator session, 2026-11-11; see [DEC-033](#dec-033--windows-is-a-supported-development-platform) and [issue #191](https://github.com/descipar/wled-mcp/issues/191) |
| DEC-034 | Project / roadmap | Milestone M4 is closed without its own minor release: the owner waives DEC-030 item 1 for M4. Its merged work (#28) ships with the next minor release together with the unreleased work of M3. Applies to M4 only. | Confirmed owner statement, coordinator session, 2026-11-12; see [DEC-034](#dec-034--m4-closes-without-its-own-release) |
| DEC-035 | Project / discovery and enrollment (M8) | Agents discover WLED controllers through MCP and add them to the inventory after confirmation by the MCP client; inventory changes take effect by in-process reload; a bounded unicast `GET /json/info` probe of configured RFC 1918 ranges is approved in addition to mDNS under hard server-side caps; ranges are set by a separate configuration-write tool; an address change is reported, never rewritten; standard library only. Supersedes ISSUE-16-DEC-001 in part. | Confirmed owner answers, coordinator session, 2026-11-12 (paraphrased in English, no verbatim quote); see [DEC-035](#dec-035--agent-driven-discovery-and-enrollment) and [issue #198](https://github.com/descipar/wled-mcp/issues/198) |
| DEC-036 | Project / roadmap | Milestone M5 is closed without its own minor release: the owner waives DEC-030 item 1 for M5 (confirmed explicitly after the coordinator read the instruction to close M5 as a waiver). Its merged work (#128, validation evidence and one mock test) needs no release; the README already states the result. Applies to M5 only. | Confirmed owner statements, coordinator session, 2026-11-12; see [DEC-036](#dec-036--m5-closes-without-its-own-release) |
| DEC-037 | Project / operations | A reinstall of the MCPHub itself (a fresh install of the hub) is never authorized and never part of a project test, rollback or release step; the MCPHub fresh-install test stays waived (ISSUE-24-DEC-005). Changes to the wled-mcp service on a deployed target do not imply a hub reinstall. | Confirmed owner statement, coordinator session, 2026-11-13 (paraphrased in English, no verbatim quote); see [DEC-037](#dec-037--no-mcphub-reinstall-in-project-steps) |
| DEC-038 | Project / roadmap | Milestone M7 is closed without its own minor release: the owner waives DEC-030 item 1 for M7. Its work (#183, rooms), once merged, ships with the next minor release and stays under Unreleased in the changelog until then; the README marks it "not yet released". Applies to M7 only. | Confirmed owner statement, coordinator session, 2026-11-16; see [DEC-038](#dec-038--m7-closes-without-its-own-release) |
| DEC-039 | Workflow / branches | No long-lived milestone branch: short-lived feature branches merge into `main` one PR at a time; `main` is the integration line (green, not necessarily release-ready) and users receive a release tag on a reviewed `main` commit. Non-standalone changes are split or kept behind an off-by-default option. | Confirmed owner statement, main session, 2026-11-18; see [DEC-039](#dec-039--main-is-the-integration-line-releases-are-tags) |
| DEC-040 | Project / roadmap | The M8 release is published as 0.4.1; the owner counts it as satisfying DEC-030 item 1 for M8 (no waiver). Applies to this release only, not a rule for patch numbers. | Confirmed owner answer, main session, 2026-11-21; see [DEC-040](#dec-040--release-041-counts-as-the-dec-030-release-for-m8) |
| DEC-041 | Workflow / parallelism | When the owner commissions a milestone or several issues at once, the coordinator derives the parallel plan itself (dependency/hotspot analysis, at most two implementation tracks in isolated worktrees, serial where coupled) and starts it without asking back. Owner gates and per-PR safety rules are unchanged. | Owner request, main session, 2026-11-26; see [DEC-041](#dec-041--coordinator-plans-and-starts-parallel-issue-batches) |

These seed entries restate decisions already present in the current project
discussion/rules; they do not claim a separate human GitHub approval comment.
The source sessions have no permalink available in these files. PR/issue links
locate the durable project restatement, not an invented original-message URL.
The entries are active only within their described scope. A later human decision
can explicitly amend them.

Detail below is condensed: each entry keeps status, source, scope, the decision and
supersession. Coordinator notes, long rationale and affected-file lists live in the
contract files, CHANGELOG and git history. Quotes are verbatim with translation (DEC-017).

### DEC-006 — Post-merge issue completion

- Status: active workflow intent; implementation and merge follow the normal review and
  human merge process.
- Source: human request, coordinator session, 2026-11-04, after PR #33 merged while issue #2
  stayed open ([issue #34](https://github.com/descipar/wled-mcp/issues/34)).
- Decision: add an agent that completes issue checklists after merge. Not an authorization
  to implement the backlog, merge, deploy, change devices or publish.
- Conditions: based on actual merged work and acceptance evidence; a merge or agent verdict
  does not prove unrelated requirements. PM-01-06 details are technical choices.

### DEC-007 — Shared Claude Code and Codex roles

- Status: active workflow intent.
- Source: human request, coordinator session, 2026-11-04 ([issue #37](https://github.com/descipar/wled-mcp/issues/37)).
- Decision: maintain common role definitions for both clients, keeping the issue workflow,
  independent review and DEC-006 completion. Source files and generated adapters are
  technical choices (CA-01-06).
- Conditions: client configuration stays separate; no models, providers, credentials,
  permissions or MCP connections are forced.

### DEC-008 — Reviewer on Opus in Claude Code

- Status: active workflow decision for Claude Code sessions.
- Source: human instruction, issue-48 workflow session, 2026-11-05.
- Decision: in Claude Code the coordinator passes the Opus model on every `wled_reviewer`
  delegation; Codex keeps its inherited model. Role sources carry no model override. If
  Opus is unavailable, report it instead of reviewing with another model.

### DEC-009 — Public-ready repository baseline

- Status: active project decision.
- Source: owner direction, coordinator session, 2026-11-06 ([issue #62](https://github.com/descipar/wled-mcp/issues/62)).
- Decision: keep tracked content neutral and installation-independent, provide a user-facing
  README and synthetic example deployment files for both transports, guard against private
  identifiers in CI.
- Conditions: no visibility change, license choice, publication, listing submission or
  history rewrite is implied (tracked by #23). Rollback/update procedures stay in stage 2.

### DEC-010 — Stage in every issue title

- Status: active project decision (superseded by DEC-029 for open and new work; closed
  history unchanged).
- Source: owner instructions, coordinator session, 2026-11-06: "jedes Issue hat genau eine
  Stage, sichtbar als 'Stage N: …' im Titel plus Label stage:N" (English: "every issue has
  exactly one stage, visible as 'Stage N: …' in the title plus label stage:N").
- Decision: every issue has one stage, shown as a `Stage N: ` title prefix and one `stage:N`
  label; #34 and #37 belong to stage 1. Coordinator-derived conventions: trackers use
  `Stage N epic: `, issues are sub-issues of their tracker, workflow issues get a stage too.
- Supersedes: the "may be recorded as cross-stage" allowance from DEC-002.

### DEC-011 — Apache-2.0 license with NOTICE attribution

- Status: active project decision.
- Source: owner instructions, coordinator session, 2026-11-07: "apache mit notice" (English:
  "Apache with notice").
- Decision: license Apache-2.0; a `NOTICE` file carries copyright and author attribution that
  redistributions must retain (Section 4(d)). The author name in `NOTICE` and `pyproject.toml`
  is an explicit owner request and an exception to DEC-005 for those fields only.
- Conditions: no visibility change, publication, registry submission or history rewrite is
  decided here. Supersedes the "no license chosen" limit of DEC-009 for the license only.

### DEC-012 — Project and package identity

- Status: active project decision.
- Source: owner instructions, coordinator session, 2026-11-07 (option 1: keep the name with
  clear unofficial marking).
- Decision: repository `descipar/wled-mcp`, PyPI `wled-mcp`, image `ghcr.io/descipar/wled-mcp`,
  MCP Registry name `io.github.descipar/wled-mcp`. Conditions: (a) no WLED logo or imitation;
  (b) package summary and listing texts state the project is unofficial and not affiliated
  with WLED, besides the README; (c) comply if the WLED project asks for a rename.
- Conditions: reserves nothing and publishes nothing.

### DEC-013 — General contact and no security support

- Status: active project decision.
- Source: owner instructions, coordinator session, 2026-11-07 (private product, "use at own risk").
- Decision: public contact is GitHub issues only, no e-mail in metadata or listings. No
  security support: no private reporting channel (private vulnerability reporting stays off),
  no response commitment, no advisories. `SECURITY.md` states this, allows issue reports
  without exploit details and recommends a trusted network. S2-PUBLIC-03 requires this
  statement instead of a security contact. Built-in safeguards stay requirements.

### DEC-014 — Keep the existing Git history

- Status: active project decision.
- Source: owner instruction, coordinator session, 2026-11-07 (option A of keep versus fresh
  repository; the commit e-mail address may be public).
- Decision: the existing history and author identities stay when the repository becomes
  public; no history rewrite, no fresh public repository. Authorizes no visibility change.

### DEC-015 — Issue and PR review before visibility change

- Status: active project decision.
- Source: owner instruction, coordinator session, 2026-11-07: "ja, mach DEC-015 so" (English:
  "yes, do DEC-015 that way"), amended: the #11 revision may stay.
- Decision: (1) two layers: a repeatable read-only script (`scripts/check_issue_content.py`)
  scanning titles, bodies, comments and edit histories with the untracked private denylist,
  plus one agent read-through whose findings the owner approves; (2) the full review runs
  immediately before the visibility change (moved to #90 by DEC-019); (3) known edit-history
  findings stay; (4) AGENTS.md keeps issues impersonal. Deleting an edit-history revision is
  an owner action in the GitHub UI.

### DEC-016 — Ship the agent tooling and decision records

- Status: active project decision.
- Source: owner instruction, coordinator session, 2026-11-07 ("ja, mach DEC-016 so").
- Decision: the public repository ships AGENTS.md, CLAUDE.md, `agents/`, generated
  `.claude/agents/` and `.codex/` definitions, `docs/AGENT-*.md`, `docs/agent-workflow/`,
  `scripts/sync_agents.py` with tests, this log and `docs/decisions/`. A short orientation
  for outside readers is #23 work.

### DEC-017 — Verbatim owner quotes with English translation

- Status: active project decision.
- Source: owner instruction, coordinator session, 2026-11-07 ("ja, mach DEC-017 so").
- Decision: German owner quotes in decision records stay verbatim as source evidence and
  carry an English translation, `"original" (English: "translation")`; future records use the
  same form; quotes are never replaced by translations.

### DEC-018 — Private denylist and main branch rules

- Status: active project decision; item 3 (branch rules) is superseded by DEC-024.
- Source: owner instruction, coordinator session, 2026-11-07 ("ja, mach DEC-018 so").
- Decision: (1) the private denylist is a local untracked `runtime/private-denylist.txt` plus
  the same content as a GitHub Actions secret; CI writes it to a temporary file and sets
  `WLED_MCP_PRIVATE_DENYLIST` for `scripts/check_private_identifiers.py`; without the secret
  only the rule checks run; (2) an agent proposes candidate terms from `.agent-runs/`, history
  and issues/PRs, the owner edits the list, together with the DEC-015 review before the
  visibility change; concrete terms never appear in committed files; (3) branch rules at the
  visibility change (superseded by DEC-024).

### DEC-019 — Make the repository public before the release

- Status: active project decision.
- Source: owner instruction, coordinator session, 2026-11-07 ("ja, mach DEC-019 so").
- Decision: visibility is decoupled from the release. The repository becomes public once the
  readiness checklist of [#90](https://github.com/descipar/wled-mcp/issues/90) is complete and
  the owner explicitly instructs it (DEC-015 review, DEC-018 denylist and CI step, DEC-016
  orientation with pre-release/no-support status and a minimal CONTRIBUTING.md, owner review,
  visibility change by the owner, `main` ruleset right after). Package, image and
  marketplace publication stay in #25. Agents never change visibility, secrets or rulesets.

### DEC-020 — Support and version policy

- Status: active project decision.
- Source: owner instruction, coordinator session, 2026-11-07: "ja, aber eine ergänzung
  unterstützung erst ab wled 16.0.0" (English: "yes, but one addition: support only from WLED
  16.0.0").
- Decision: (1) `0.x` releases until a separate `1.0` decision, breaking changes in minors with
  changelog migration notes, fixes only for the latest release; (2) WLED support starts at
  16.0.0, tiers tested (hardware evidence, currently 16.0.1), expected (source-reviewed and
  mock-tested), unknown; below 16.0.0 is unsupported (warn, do not refuse); (3) Python means
  tested in CI (currently 3.13); (4) Linux supported, Windows and macOS experimental;
  (5) best-effort responses (DEC-013). A short README support table reflects this.

### DEC-021 — Adopt the stage-2 parallel plan

- Status: active stage-2 workflow decision.
- Source: owner instructions, coordinator session, 2026-11-07: "zustimmen zu allen offenen
  punkten im plan" (English: "agree to all open points in the plan").
- Decision: (1) docs/STAGE-2-PARALLEL-PLAN.md is the adopted plan; (2) at most two
  implementation tracks at once, a third only for docs/read-only work; (3) #90 first;
  (4) one coordinator per issue in an isolated worktree and branch, the main session is
  integration owner, branches sync by merging `main` (no force-push), stacked PRs are
  retargeted to `main` before the base is deleted, one merge at a time after the owner's
  approval; (5) "Depends on" lines reflect the plan; (6) "Starte Stage 2 parallel" starts or
  resumes the plan; the main session stops only for merge approval, owner-only actions
  (visibility, secrets, rulesets, publication), hardware authorization and genuine decisions.
- Conditions: stage 2 only; no authorization for visibility, publication, deployment or
  hardware writes.

### DEC-022 — Proportionate review and standing merge approval

- Status: active stage-2 workflow decision; the standing merge approval (item 4) is revalidated
  with the owner after three issues.
- Source: owner instructions, coordinator session, 2026-11-08: "ersten 3 punkte so übernehmen
  und auch so festschreiben das auf anderen rechner das so gemacht wird. pauschale freigabe
  erteilt, sollte aber nach 3-4 issues nochmal überprüpft werden" (English: "adopt the first 3
  points as proposed and record them so that it is done this way on other computers as well.
  Blanket approval granted, but it should be reviewed again after 3-4 issues").
- Decision:
  1. Nits do not start a review round. A PASS with no must-fix is mergeable; nits and optional
     should-fix items go to the next PR of the track (or a follow-up issue) and are listed in
     the PR body. A correction round is needed only for must-fix items and for should-fix
     items about behavior, safety, data loss or factually wrong documentation.
  2. A sync that merges `main` into a reviewed branch keeps the PASS when the coordinator
     verifies that the branch's own changes under `src/`, `tests/` and `scripts/` are
     unchanged (`git diff <base>..<reviewed>` equals `git diff <main>..<synced>` for those
     paths), the rest are conflict resolutions or documentation wording, no newly merged work
     overlaps semantically with the PR, and CI is green on the synced head; the coordinator
     records the check in the PR. Any own code/test/script change or semantic overlap needs a
     fresh review. Refines DEC-021 item 4.
  3. Review depth is proportionate: documentation-only and small non-behavioral PRs get a light
     review (acceptance criteria, links, consistency, privacy, CI; no mutation runs, fixture
     regeneration or source re-reads); full depth stays for code that writes to devices or
     files, changes safety, protocol or security behavior, or changes data formats. The
     reviewer still runs on Opus (DEC-008). The test suite is not reduced.
  4. Standing merge approval: the coordinator may merge a stage-2 PR without asking, and
     reports afterwards, when all hold: a current-head review PASS (nits allowed) without
     must-fix, or a sync that keeps the PASS under item 2; all CI checks green on that exact
     head (`gh pr merge --squash --match-head-commit <sha>`); no open NEEDS_DECISION, no scope
     change beyond the issue/packet, and no change to visibility, secrets, rulesets,
     publication, deployment or hardware/LAN access. The PR body or a coordinator comment
     states "Merged under DEC-022 standing approval".
- Conditions: stage 2 only. Item 4 covers at most three issues reaching completion (DONE),
  counted from 2026-11-08 (PR-by-PR merges of partial scopes count within their issue); after the third the coordinator stops and asks the owner to
  confirm, adjust or end it; the owner may end it at any time. Owner-only actions and hardware
  authorization stay separate.
- Revalidation, 2026-11-08 (owner): after #18, #21 and #19, the owner answered "Weiter für 3
  Issues (meine Empfehlung): Die Bedingungen bleiben gleich, also PASS von Opus für den
  aktuellen Stand und grüne CI. Danach frage ich wieder nach." (English: "Continue for 3 issues
  (my recommendation): the conditions stay the same, i.e. PASS from Opus for the current head
  and green CI. Afterwards I ask again."). Item 4 continues unchanged for the next three
  issues, the first being #16. The unanswered S-1 question stays with ISSUE-19-DEC-003.
- Coordinator note: since the DEC-024 rulesets the merge command is
  `gh pr merge --squash --match-head-commit <sha>` and, only when refused for lack of an
  approving review, the same with `--admin` (the owner's bypass). `--admin` is no extra
  permission and never covers failing checks (`agents/coordinator.md`).
- Supersedes: per-PR merge approval in stage 2 while item 4 is active (one merge at a time stays;
  DEC-021 item 4 "one merge at a time after the owner's merge approval" and item 6 "stops only for
  merge approval" apply again when item 4 ends); refines the DEC-021
  sync rule; an exception to the recording rule on standing permission.

### DEC-023 — Staged first public release

- Status: active stage-2 release decision; item 3 holds one coordinator reading awaiting owner
  confirmation.
- Source: owner instructions, coordinator session, 2026-11-08: "Stufe 0, dann PyPI danach
  entscheiden" (English: "Stage 0, then decide on PyPI afterwards").
- Decision: (1) the first public release is stage 0: after the DEC-015 scan and owner approval
  the owner makes the repository public (DEC-019) and a GitHub release is created from an exact
  `main` commit, tagged with the version of the single version source (S2-COMPAT-01),
  installable from Git (`uvx --from git+https://github.com/descipar/wled-mcp wled-mcp`);
  (2) whether a PyPI package follows (stage 1) is decided by the owner afterwards;
  (3) everything else marked Launch is deferred, not dropped: image pipeline and provenance
  work of #22 beyond a PyPI workflow, remaining #23 documentation, marketplace and registry
  listings (#24), the beta/launch report with simulator and H07 (#25). Coordinator reading,
  unconfirmed: the DEC-018 CI secret step and `main` ruleset are not prerequisites of stage 0
  (the ruleset stays recommended right after the visibility change); (4) the DEC-015 scan and
  owner approval of its findings are not reduced.
- Conditions: bounded to the first public release. Publication, visibility change, secrets and
  rulesets remain owner-only and need the owner's explicit instruction at that time.
- Supersedes: the Launch classification in docs/STAGE-2.md for the items in item 3 (first
  public release only).

### DEC-024 — Main branch rules with review for external pull requests

- Status: active project decision; items 1 and 3 hold coordinator readings awaiting owner
  confirmation.
- Source: owner instructions, coordinator session, 2026-11-08: "ja, mach DEC-024 so und schreib
  die klickschritte bzw. prüfe über du das per api nicht selber kannst" (English: "yes, do
  DEC-024 that way and write the click steps, or check via the API what you cannot do
  yourself"); the aim is to see pull requests from outsiders before they run or merge.
- Decision, applied by the owner at the visibility change (#90): (1) ruleset A, no bypass,
  default branch: required checks `checks (ubuntu-latest, 3.13)` and
  `checks (ubuntu-24.04-arm, 3.13)`, block force-push, restrict deletion, "up to date" not
  required; (2) ruleset B, default branch: pull request with one approving review, bypass
  only for the repository admin role (the owner), mode "for pull requests only"; (3) Actions
  setting "Require approval for all external contributors"; (4) the agent verifies the result
  read-only through the API as in the [runbook](validation/releases.md).
- Notes: the bypass applies to a whole ruleset, so CI, force-push and deletion rules stay in
  ruleset A. Observed 2026-11-08 on the first merge under the rulesets: plain squash merge was
  refused and `--admin` merged with green checks (confirms reading 3 and the DEC-022 command).
  Rulesets cannot be read while the repository is private.
- Conditions: creating rulesets and the setting is an owner-only action.
- Supersedes: DEC-018 item 3 (branch rules) only.

### DEC-026 — Stage releases on the target machine

- Status: active project decision. DEC-025 is reserved for the stage 4 plan (kept in issue #127).
- Source: owner instructions, coordinator session, 2026-11-08: "ich will kein staging auf
  windows und dann kopieren auf linux. stage immer auf dem rechner wo wir installieren wollen"
  (English: "I do not want staging on Windows and then copying to Linux. Always stage on the
  machine where we want to install"), and "das soll kein memory sein, sondern auch für andere
  rechner gelten" (English: "that should not be a memory, it should also apply to other
  computers").
- Decision: release directories (`deploy/stage_release.py`) are staged on the machine that will
  run them, from a clean checkout of the release tag or commit, never built elsewhere and
  copied. Applies on every host and for every agent.
- Conditions: covers release directories and the images and hub entries built from them, not
  the test suite or development checks. If the target cannot build, the owner decides the
  exception. Observed: Windows-built artifacts hashed differently from Linux ones (probably
  CRLF, [#131](https://github.com/descipar/wled-mcp/issues/131)).

### DEC-027 — Re-stage the open work by value per effort

- Status: active project decision. Items 5 to 8 are coordinator defaults the owner did not
  decide explicitly and stay open for confirmation.
- Source: owner instruction, coordinator session, 2026-11-08: "setze den plan vom review
  einfach so um" (English: "just implement the plan from the review as it is").
- Decision: (1) stage 2 closes out with #130, #131, #67 and a hardware check of the stage-2
  features on the test controller, limited to what one RGB controller can show (H07 and the
  live rollback stay with #25); (2) stage 3 order: #31, #30, #28, #27, #29; (3) stage 4
  (#127, #128) stays after stage 3; (4) a new stage 5 "public distribution and backlog"
  (tracker #133) takes #22 to #25 and #117, worked only on a trigger; the PyPI decision stays
  with the owner. The stage-2 Launch requirements owned by #22 to #25 are not met and not
  dropped; they now belong to stage 5. Refines DEC-023 item 3.
- Coordinator defaults, open: (5) merging PR #132 counted as part of the plan; (6) the nightlight
  auto-off idea is not added to stage 3; (7) DEC-021 and DEC-022 are not extended to stage 3 or
  5; (8) the pending confirmations (DEC-023 item 3, DEC-024 readings 1 and 3, ISSUE-19-DEC-003
  S-1, the PyPI decision) stay open.
- Conditions: no hardware run, setting change, deployment or publication is authorized.

### DEC-028 — Pragmatic delivery

- Status: active project workflow decision.
- Source: owner instructions, main session, 2026-11-09: "ich will eine pragmatische
  heransgehensweise und keine immer 100% lösung" (English: "I want a pragmatic approach and
  not always a 100% solution") and "das gehört allgemein in das projekt" (English: "this belongs
  in the project in general").
- Decision (item wording is the main session's): (1) aim for good enough; fix scope, evidence
  and review depth before starting, state them in the packet, weigh effort against risk in one
  or two lines; (2) evidence is one or two runs that show the point, not matrices; where thin,
  choose the conservative limit and say so; (3) review depth follows DEC-022 (light unless the
  change writes to devices or files, changes safety, protocol, security or data formats, or
  cannot be undone (the last is DEC-028's own addition to DEC-022)); no extra review rounds, no tests beyond what the change needs, no
  optional polish; nits go to the next PR; (4) a small follow-up on the same release path is
  folded into the open PR when it does not make review harder.
- Not changed: hardware authorization, owner approval for publication, tagging and releases, the
  human merge decision and the other rules of DEC-022, DEC-024 and DEC-023.
- Applicability: all issues and agents until the owner changes it.

### DEC-029 — Milestones instead of stages

- Status: active project decision.
- Source: owner answers, main session, 2026-11-09 (roadmap model, new scope, order, merge approval).
- Decision (item wording is the main session's): (1) open and new work is organised by GitHub
  milestones M1 to M6 plus Backlog ([ROADMAP.md](ROADMAP.md)); every open or new issue has
  exactly one milestone (Backlog counts), new issues get no `Stage N: ` title prefix and no
  `stage:N` label; closed issues, requirement IDs and stage documents keep their stage history;
  (2) new scope #147 to #151; timers (W-CFG-04) stay excluded; (3) order: M1 (#147, #148, #149),
  M2 (#150, #30), M3 (#29, #27), M4 (#28), M5 (#128), M6 distribution (#22 to #25, #151), then
  Backlog (#138, #117, #152); (4) standing merge approval under DEC-022 item 4 for milestones M1
  and M2 only: a PR with a current-head PASS and green CI may be merged without a per-PR
  question, revalidated with the owner after three issues; issues that write to devices (#149,
  #27, #28) keep per-PR approval; other milestones need the owner's merge decision; (5) stage
  trackers #26, #127 and #133 are closed as superseded (the acceptance line of #133 is carried by
  the M6 description).
- Not changed: DEC-021 and DEC-022 otherwise, hardware authorization, publication approvals
  (DEC-023), the human merge decision outside item 4.
- Supersedes: DEC-010 for open and new work; amends DEC-002.

### DEC-030 — Milestone closure includes a minor release

- Status: active project decision.
- Source: owner answers, main session, 2026-11-09 ("ja 1", English: "yes, 1", to "yes, from M1";
  release scope: "full path as M1 criterion").
- Decision: (1) a milestone is closed only after at least one minor (or higher) release that
  contains its merged work and after the README is adapted to its user-visible features;
  (2) applies from M1, which is re-opened until its release; #24 moved from M6 to M1;
  (3) documentation-only or maintenance milestones follow the rule unless the owner waives it
  for that milestone; (4) PR #168 (#24) merged with patch version 0.1.3 (ISSUE-24-DEC-001),
  which does not satisfy item 1, so M1 needs a minor release; (5) release scope for M1: minor
  release 0.2.0 tagged, published as GitHub release, uploaded to PyPI and published in the
  official MCP Registry, carried out under per-step owner instructions (ISSUE-24-DEC-003 to
  ISSUE-24-DEC-005; the hub-side install test was waived, not observed); M1 only.
- Not changed: DEC-023 and the publication gates. A version bump, changelog and README are
  repository changes; a tag, GitHub release, PyPI or registry upload, hub deployment and any
  external submission each need the owner's explicit instruction. A merge under the standing
  approval authorizes none of them. No hub deployment is part of the closing criterion.
- Amends: DEC-029 (assignment of #24 and the closing of milestones).

### DEC-031 — Release scope for milestone M2

- Status: active project decision, M2 only.
- Source: owner answer, coordinator session, 2026-11-11: "ja, 0.3.0 vorbereiten,
  Veröffentlichung später separat. Alle schritte" (English: "yes, prepare 0.3.0, publication
  separately later. All steps").
- Decision: (1) M2 release scope equals M1 (DEC-030 item 5): tag, GitHub release, PyPI upload,
  official MCP Registry; (2) preparing 0.3.0 (version, changelog, README, metadata, evidence) is
  allowed now in a repository change; (3) every publication step runs only on the owner's
  explicit instruction at that step (DEC-023), merging the preparation PR authorizes none;
  (4) M2 stays open until the release is done. No hub deployment is authorized.
- Carried out 2026-11-11, each step on the owner's instruction: tag v0.3.0 and GitHub release,
  PyPI upload (`pypi` environment approval by the owner, see
  [the record](validation/releases.md#release-and-registry-publication-2026-11-11)),
  registry publication. M2 closed after this record merged.

### DEC-032 — M3 closes without its own release

- Status: active project decision, M3 only.
- Source: owner statement, coordinator session, 2026-11-11: "wir machen für m3 kein neues
  release. das zu klein" (English: "we do not make a new release for M3. that is too small").
- Decision: the owner waives DEC-030 item 1 for M3 (under DEC-030 item 3). M3 closes once #27
  and #29 are closed and this record is merged; its work stays under `Unreleased` in
  `CHANGELOG.md` and ships with the next minor release; nothing is prepared for publication.
  The README's tool count and version statements are updated with that release.
- Scope: M3 only, not a general rule for small milestones.

### DEC-033 — Windows is a supported development platform

- Status: active project decision.
- Source: owner statement, coordinator session, 2026-11-11 (issue #191): "Windows wird
  unterstützt als entwicklungsplattform" (English: "Windows is supported as a development
  platform").
- Decision: the test suite, lint/type checks and local scripts are expected to work on a
  Windows checkout; a Windows-only failure is a defect to fix, or to skip on `win32` with a
  visible reason where behavior is POSIX-specific, without weakening the offline guarantee;
  #191 is implemented, not closed as unsupported.
- Scope: development platform only. DEC-020 item 4 stays (Windows experimental for users; the
  owner confirmed: "windows für nutzer experimental", English: "Windows stays experimental for
  users"), as do the CI matrix (Linux authoritative) and DEC-026.

### DEC-034 — M4 closes without its own release

- Status: active project decision, M4 only.
- Source: owner statement, coordinator session, 2026-11-12: "wir verzichten auf das release"
  (English: "we waive the release").
- Decision: the owner waives DEC-030 item 1 for M4. M4 closes once #28 is closed and this
  record is merged; its work stays under `Unreleased` with M3's and ships with the next minor
  release; nothing is prepared for publication. Scope: M4 only, extends no other waiver.

### DEC-041 — Coordinator plans and starts parallel issue batches

- Status: active workflow decision, global.
- Source: owner request, main session, 2026-11-26: "kann der koordinator so ergänz werden, das er
  wenn bei der beautragung der umsetzung eines milestone oder von mehreren issues schaut wie diese
  am besten parallel umgesetzt werden können und das dann ohne rückfrage anstößt?" (English: "can
  the coordinator be extended so that, when commissioned to implement a milestone or several
  issues, it works out how they can best be implemented in parallel and starts that without asking
  back?"); confirmed with "Ja, mach das so" for the proposed role change.
- Decision: a request to implement a milestone or several issues authorizes the coordinator to
  (1) read issue, dependency, PR and decision state, (2) derive the plan itself: coupled issues
  and shared hotspots (the files listed in docs/STAGE-2-PARALLEL-PLAN.md) run serially or stacked,
  independent issues in parallel, (3) run at most two implementation tracks at once, each issue
  with its own coordinator in an isolated worktree on its own branch (DEC-021 rule 1 as the
  general limit; read-only and docs work may run beside them), (4) record the plan in the work
  packet or issue state and start it without a confirmation question.
- Not changed: one PR merged at a time, human merge approval and DEC-022/DEC-029 standing
  approvals, hardware authorization, owner-only actions, genuine decisions, per-issue review depth.
  A third implementation track or a different limit needs the owner.
- Scope: workflow, all milestones. Does not authorize device writes, deployment or publication.

### DEC-040 — Release 0.4.1 counts as the DEC-030 release for M8

- Status: active project decision, M8 release 0.4.1 only.
- Source: owner answer, main session, 2026-11-21. Question: whether publishing the M8 work as
  0.4.1 waives DEC-030 item 1 (option 1) or counts as satisfying it (option 2), with the note that
  the number is then strictly not a minor release. Answer: "gilt als erfüllt" (English: "counts as
  fulfilled"). The owner also chose the number 0.4.1 instead of the provisional 0.5.0.
- Decision: release 0.4.1, which carries M8 (and M7's waived work, DEC-038), counts as the DEC-030
  release for M8. It is not a waiver. Tag, GitHub release, PyPI and registry publication still need
  the owner's explicit instruction (DEC-023, DEC-030).
- Scope: the M8 release 0.4.1 only. Not a general rule that a patch number may carry a minor
  release's content; later milestones follow DEC-030 as written.

### DEC-039 — `main` is the integration line, releases are tags

- Status: active workflow decision, global.
- Source: owner statements, main session, 2026-11-18: "man kann auch einfach das release nehmen
  dann" (English: "one can simply use the release instead"), after advice against a
  long-lived milestone branch.
- Decision: (1) no long-lived milestone branch; issues use short-lived feature branches merged
  into `main` one PR at a time; (2) `main` is the integration line, green (CI and a
  current-head review PASS before every merge, DEC-022 sync rule) but not necessarily
  release-ready; (3) users receive a release: a tag `v<version>` on a reviewed `main` commit
  (docs/PUBLISHING.md), staged per DEC-026, chosen deliberately and owner-gated (DEC-023,
  DEC-030); (4) a change not usable on its own is split or kept behind an off-by-default option.
- Scope: workflow, all milestones. A tightly coupled pair or triple of issues may use stacked PRs
  (retarget to `main` before deleting the base); a change that would break `main` incompatibly
  needs a short-lived integration branch and an owner decision first.
- Not changed: DEC-021 (sync by merging `main`), DEC-022, DEC-023, DEC-026, DEC-030, the human
  merge gate.

### DEC-038 — M7 closes without its own release

- Status: active project decision, M7 only.
- Source: owner statement, coordinator session, 2026-11-16: "keine release für m7" (English: "no
  release for M7").
- Decision: the owner waives DEC-030 item 1 for M7. Its work (#183, rooms), once merged, ships
  with the next minor release and stays under Unreleased; the README marks room behavior "not yet
  released". M7 closes once #183 is closed and this record is merged. Scope: M7 only.
- Update (after publication): M7's work shipped in release 0.4.1 together with M8's (the owner chose
  0.4.1 over the provisional 0.5.0; DEC-030 counted as satisfied by that release, [DEC-040](#dec-040--release-041-counts-as-the-dec-030-release-for-m8)).
  Published 2026-11-21.

### DEC-037 — No MCPHub reinstall in project steps

- Status: active project decision, global.
- Source: owner statement relayed by the coordinator, 2026-11-13 (coordinator's English
  paraphrase, no verbatim quote).
- Decision: a reinstall of the MCPHub itself is never authorized and never part of any project
  test, rollback or release step; the hub fresh-install test stays waived
  ([ISSUE-24-DEC-005](decisions/stage-2.md)); changes to the wled-mcp service on a deployed
  target (update, rollback, restore, restart) imply no hub reinstall.
- Scope: global, limited to reinstalling the hub; hub entries are governed by issue decisions
  (ISSUE-25-DEC-003).

### DEC-036 — M5 closes without its own release

- Status: active project decision, M5 only.
- Source: owner instruction, coordinator session, 2026-11-12: "M5 auf GitHub schließen und in der
  roadmap vermerken" (English: "close M5 on GitHub and note it in the roadmap"), then
  confirmed as a waiver: "kein minor release" (English: "no minor release").
- Decision: M5 is closed now; the owner waives DEC-030 item 1 for M5 (it only records hardware
  evidence and one mock test). Its work (#128) ships with the next minor release; nothing is
  prepared for publication; the README limitation already states the result; the roadmap
  notes M5 as done. Scope: M5 only.

### DEC-035 — Agent-driven discovery and enrollment

- Status: active project decision (milestone M8).
- Source: owner answers, coordinator session, 2026-11-12 (no permalink), relayed and paraphrased
  in English by the coordinator; no verbatim quote exists
  ([issue #198](https://github.com/descipar/wled-mcp/issues/198)).
- Decision (paraphrase): (1) agents find controllers through MCP and add them to the inventory
  after confirmation by the MCP client; no interactive approval inside the plugin;
  (2) inventory changes take effect by in-process reload, not restart; (3) a bounded unicast
  `GET /json/info` probe over configured private IPv4 ranges is approved in addition to mDNS,
  as thorough as possible, under hard server-side caps no tool parameter can override: RFC 1918 only (no loopback,
  link-local or public), at most a /24 per range, a small maximum number of ranges, bounded
  timeouts and concurrency; (4) ranges are set by the separate configuration-write tool
  `wled_set_discovery_ranges` (client confirmation shows the exact ranges, profiles can disable
  it, operators may set ranges by hand); `wled_discover_devices` without ranges runs mDNS only
  and proposes ranges from inventory addresses, never scanning them; (5) a known controller at a
  changed address is reported, never rewritten; (6) standard library only (OPS-01); (7) work is
  milestone M8 (issues #198 to #204). A coverage report must never claim nothing was found when
  the run could not look.
- Scope: M8 only. Not changed: DEC-023, DEC-029 item 4 (M8 has no standing merge approval, every
  PR needs its own), DEC-030 (M8 closes with a minor release and README update), the AGENTS rule
  against silent preset overwrite, delete, arbitrary endpoint forwarding and configuration
  migration; the new tools never write to a device.
- Supersedes: ISSUE-16-DEC-001 in part and ISSUE-16-DEC-002 TD-16-8 in part (restart instead of
  in-process reload; CLI only, no inventory writes, no unicast probes). Kept: standard library
  only, discovery only on explicit invocation, `wled-mcp discover`, validate-then-restart for
  hand edits. Amends the AGENTS.md rule on discovery scans and inventory writes.
- Technical details (caps, schemas, error codes, class `manage`, keys, MAC identity) are
  recorded as [ISSUE-198-DEC-001](decisions/m7-m8.md); the owner can override them
  ([contract/discovery.md](contract/discovery.md)).

## Issue-specific decisions (index)

- Workflow/tooling: [ISSUE-292-DEC-001](decisions/workflow.md) (human, competitor
  researcher role and owner-selected requirements/issue handoff).

Authority in parentheses: human = owner statement, coordinator/agent = technical proposal or
delegated decision (not a human decision). Details are in the linked files.

- Stage 1 and early issues: [ISSUE-1-DEC-001](decisions/stage-1.md) (human, OPS-04 delivered,
  rest to #16); [ISSUE-7-DEC-006](decisions/stage-1.md#issue-7-dec-006--align-7-with-6-limits-and-bri-handling)
  (human, `wled_replace_layout` aligns with #6 limits and `bri`; resolves ISSUE-7-OPEN-001);
  [ISSUE-7-DEC-003 to -005](decisions/stage-1.md) and ISSUE-7-DEC-007 to -009 (same file)
  (delegated, step order, range evidence, no-op behavior, follow-up #48);
  [ISSUE-8-DEC-001 and -002](decisions/stage-1.md) (human, restore deferred),
  [ISSUE-8-DEC-003](decisions/stage-1.md) (delegated defaults);
  [ISSUE-9-DEC-001](decisions/stage-1.md) (delegated, PRE-03 deferred, playlist overwrite
  rejected); [ISSUE-10-DEC-001](decisions/stage-1.md) (agent, traceability file and check);
  [ISSUE-13-DEC-001](decisions/stage-1.md) (human, stage-1 scope), [ISSUE-13-DEC-002](decisions/stage-1.md)
  (agent, "not applicable" boxes).
- Bug and hygiene issues: [ISSUE-48-DEC-001](decisions/hardening.md) (human, segment-tool input
  rejection; supersedes parts of ISSUE-7-DEC-006); [ISSUE-52-DEC-001](decisions/hardening.md)
  (delegated, `wled_set_state` brightness on an off master); [ISSUE-53-DEC-001](decisions/hardening.md)
  (delegated, stdio socket guard); [ISSUE-55-DEC-001](decisions/hardening.md) (coordinator,
  controlled time in a retry test); [ISSUE-61-DEC-001](decisions/hardening.md) (human) and
  [ISSUE-61-DEC-002](decisions/hardening.md) (agent) (underscore host labels, diagnostics);
  [ISSUE-62-DEC-001](decisions/hardening.md) (agent, private-identifier scanner);
  [ISSUE-66-DEC-001](decisions/hardening.md) (agent, `bs` in the state allowlist);
  [ISSUE-74-DEC-001](decisions/hardening.md) (human) and [ISSUE-74-DEC-002](decisions/hardening.md)
  (agent) (invalid IPv4-like hosts, `CONFIG_ERROR`); [ISSUE-94-DEC-001 and -002](decisions/hardening.md)
  (human; coordinator: `unplanned` coverage status); [ISSUE-98-DEC-001](decisions/hardening.md)
  (coordinator, tool contract entry per tool PR).
- Deployment and hardware (#11, #12): [ISSUE-11-DEC-001](decisions/stage-1.md) (human, scope),
  [ISSUE-11-DEC-002](decisions/stage-1.md) (agent, TD-1 to TD-9), [ISSUE-11-DEC-003](decisions/stage-1.md)
  to [ISSUE-11-DEC-008](decisions/stage-1.md) (human: bounded live operations, HTTP stays the
  active mode, update/rollback to stage 2, drain/load to #12; DEC-004 mode choice, DEC-005
  stage-2 move, DEC-006 service removal test, DEC-007 catalog reads and hub recreation);
  [ISSUE-12-DEC-001](decisions/stage-1.md) (human, one test controller with capture/restore),
  [ISSUE-12-DEC-002](decisions/stage-1.md) (agent, superseded in part by
  [ISSUE-12-DEC-004](decisions/stage-1.md)), [ISSUE-12-DEC-003](decisions/stage-1.md)
  (coordinator reading, retroactively confirmed), [ISSUE-12-DEC-005](decisions/stage-1.md)
  (human, run 2), [ISSUE-12-DEC-006](decisions/stage-1.md) (human, stdio drain limitation),
  [ISSUE-12-DEC-007](decisions/stage-1.md) (human, remaining #12 scope, run 3),
  [ISSUE-12-DEC-008](decisions/stage-1.md) (human, H04 needs no separate visual check of an
  intensity change).
- Stage 2 (2026-11-07): [ISSUE-16-DEC-001](decisions/stage-2.md) (human; superseded in part by
  DEC-035), [ISSUE-16-DEC-002](decisions/stage-2.md) (coordinator, CLI shape);
  [ISSUE-17-DEC-001](decisions/stage-2.md) (human, local groups/scenes, `strict` default),
  [ISSUE-17-DEC-002](decisions/stage-2.md) (coordinator, TD-17-1 to TD-17-18);
  [ISSUE-18-DEC-001](decisions/stage-2.md) (human, supplied objects), [ISSUE-18-DEC-002](decisions/stage-2.md),
  [ISSUE-18-DEC-003](decisions/stage-2.md) (coordinator); [ISSUE-19-DEC-001 and -002](decisions/stage-2.md)
  (human, overlap and unexposed fields), [ISSUE-19-DEC-003](decisions/stage-2.md) (coordinator,
  TD-19-1 to TD-19-14); [ISSUE-20-DEC-001](decisions/stage-2.md) (human, profiles and classes),
  [ISSUE-20-DEC-002](decisions/stage-2.md) (coordinator, TD-20-1 to TD-20-15);
  [ISSUE-21-DEC-001](decisions/stage-2.md) (human, update/rollback tests),
  [ISSUE-21-DEC-002](decisions/stage-2.md) (coordinator).
- Stage 2 close-out and M1/M2: [ISSUE-130-DEC-001](decisions/m3-m6.md) (human, envelope schema
  allows additional properties); [ISSUE-134-DEC-001](decisions/m3-m6.md) (human, one hardware run,
  [validation](validation/hardware-checks.md)); [ISSUE-147-DEC-001](decisions/m3-m6.md) (human, one
  local stdio client check); [ISSUE-150-DEC-001](decisions/m3-m6.md) (human, bounded read-only
  checks); [ISSUE-30-DEC-001](decisions/stage-3.md) (human, one read-only run);
  [ISSUE-31-DEC-001](decisions/stage-3.md) (coordinator, effect search TD-31-1 to TD-31-12);
  [ISSUE-24-DEC-001](decisions/stage-2.md), [ISSUE-24-DEC-002](decisions/stage-2.md),
  [ISSUE-24-DEC-003](decisions/stage-2.md) (registry route, MCPM and mcphub.app dropped),
  [ISSUE-24-DEC-004](decisions/stage-2.md) (per-step release instructions),
  [ISSUE-24-DEC-005](decisions/stage-2.md) (hub-side install test waived).
- M3 to M7: [ISSUE-27-DEC-001](decisions/stage-3.md) (coordinator, named zones);
  [ISSUE-28-DEC-001](decisions/stage-3.md) (human, bounded live signal runs),
  [ISSUE-28-DEC-002](decisions/stage-3.md) (coordinator, signal tools);
  [ISSUE-29-DEC-001](decisions/stage-3.md) (coordinator, `wled_preview_layout`);
  [ISSUE-128-DEC-001](decisions/m3-m6.md) and [ISSUE-128-DEC-002](decisions/m3-m6.md)
  (human, lock-state probes and minimal write set, [validation](validation/hardware-checks.md));
  [ISSUE-183-DEC-001](decisions/m7-m8.md) (human, bounded live room run),
  [ISSUE-183-DEC-002](decisions/m7-m8.md) (coordinator, rooms).
- M6 distribution and Stage 5: [ISSUE-22-DEC-001](decisions/stage-2.md) (human, PyPI workflow),
  [ISSUE-22-DEC-002](decisions/stage-2.md) (coordinator), [ISSUE-22-DEC-003 and -005](decisions/stage-2.md)
  (human, loosened pins, README for PyPI), [ISSUE-22-DEC-004](decisions/stage-2.md) (coordinator,
  ranges); [ISSUE-23-DEC-001](decisions/stage-2.md) (human, open M6 issue bodies);
  [ISSUE-25-DEC-001](decisions/stage-2.md) (human, simulator dropped), further ISSUE-25
  decisions in that file; [ISSUE-151-DEC-001](decisions/m3-m6.md) (human, MCPB bundle attached
  by a separate job, untested by the project), [ISSUE-151-DEC-002](decisions/m3-m6.md)
  (coordinator, manifest 0.3 and bundle job).
- M8 (discovery and enrollment, DEC-035): [ISSUE-198-DEC-001](decisions/m7-m8.md)
  (technical proposals TP-1 to TP-12, [contract/discovery.md](contract/discovery.md));
  [ISSUE-200-DEC-001](decisions/m7-m8.md); [ISSUE-201-DEC-001](decisions/m7-m8.md);
  [ISSUE-202-DEC-001](decisions/m7-m8.md); [ISSUE-203-DEC-001](decisions/m7-m8.md);
  all coordinator technical proposals, not human decisions.
- M9: [ISSUE-236-DEC-001](decisions/m7-m8.md) (tool groups, owner accepted);
  [ISSUE-258-DEC-001](decisions/m7-m8.md) (catalog resources; accepted, delegated decision of the
  main session under the owner's delegation, 2026-11-27).
- M9 (design): [ISSUE-237-DEC-001](decisions/m7-m8.md) (accepted, delegated decision of the main
  session under the owner's delegation, 2026-11-27: design C, per-endpoint tool sets over HTTP, is
  the target design; implementation not scheduled in M9, a spike comes first).

## Still unresolved

Handling an unmet issue prerequisite is not a confirmed workflow decision. Do not record
automatic prerequisite implementation or a mandatory stop policy as a human choice.
Requirements analysis reports actual dependency readiness under the existing issue scope.

## Lookup and propagation

1. Read this log and the issue-specific entries relevant to the selected issue, milestone and
   dependencies. Check current source and conditions, not keywords alone. Record applicable IDs
   and the log commit in the work packet.
2. Before asking the owner, check whether an active decision answers it; apply and cite it.
3. After a new answer, classify scope and source, save the decision and update the packet and
   relevant documentation. Do not edit global rules from a narrow or ambiguous answer.
4. Send changed decision IDs and consequences explicitly to active requirements, implementation
   and review agents; shared files alone do not prove receipt. Freeze dependent writes if the
   change invalidates the active contract.
5. Refresh requirements references, acceptance tests and commit-specific review when behavior
   changes; do not retain PASS for an outdated contract or candidate.
6. At handoff or resume, reload applicable entries and status. If saving is unavailable, report
   the exact unsaved decision; a future session cannot recall it automatically.
