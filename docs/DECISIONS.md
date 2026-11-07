# Project decision log

This is versioned project knowledge, not model training or an authorization
service. All workflow roles read applicable active decisions before work and
before asking a question that may already have been answered.

## Recording rules

- Record a clear human answer as a concise, impersonal decision with ID, status,
  authority/source, scope, applicability, rationale if supplied, affected artifacts
  and any superseded decision. Do not invent a rationale or source permalink.
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
  future operations or a substitute for the current human merge decision.
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
  permalink): "ein issue muss eine stage haben und das muss im namen sichtbar sein";
  the owner then confirmed recording the rule "jedes Issue hat genau eine Stage, sichtbar
  als 'Stage N: …' im Titel plus Label stage:N", and chose stage 1 for the workflow-tooling
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
  mich als author nicht entfernen dürfen", typing errors corrected); after the coordinator compared MIT, Apache-2.0
  and copyleft options, the owner chose "apache mit notice" and the author name for the
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

## Issue-specific decisions (pointers)

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
