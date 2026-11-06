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
| DEC-002 | Workflow | Derive stage from issue labels, ancestor tracker and roadmap; stage is not a mandatory user input. Ask only for relevant conflict or genuinely unclear scope. | Confirmed human correction, project workflow discussion, 2026-11-04; [PR #32](https://github.com/descipar/wled-mcp/pull/32) |
| DEC-003 | Project / transport scope | Support both Streamable HTTP and client-managed stdio via uvx, sharing the WLED tool/domain contract. | Confirmed human scope instruction, transport discussion, 2026-11-04; [requirements](REQUIREMENTS.md), [issue #14](https://github.com/descipar/wled-mcp/issues/14) |
| DEC-004 | Stage 3 | Named zones, temporary signals, static previews, lighting explanations and effect-property search belong to stage 3 and do not block stage-2 publication. | Confirmed human stage assignment, roadmap discussion, 2026-11-04; [stage-3 roadmap](STAGE-3.md), [tracker #26](https://github.com/descipar/wled-mcp/issues/26) |
| DEC-005 | Project documentation / issues | Use neutral roles and synthetic examples. Exclude personal names, private hostnames and installation-specific personal context unless explicitly requested. | Existing governing [AGENTS.md](../AGENTS.md) rule, recorded 2026-11-04 |
| DEC-006 | Workflow | Add an agent responsible for completing issue checklists after merge. | Confirmed human instruction, post-merge workflow discussion, 2026-11-04; [issue #34](https://github.com/descipar/wled-mcp/issues/34) |
| DEC-007 | Workflow / role maintenance | Maintain shared agent definitions usable with Claude Code and Codex. | Confirmed human instruction, shared-agent discussion, 2026-11-04; [issue #37](https://github.com/descipar/wled-mcp/issues/37) |
| DEC-008 | Workflow / Claude Code only | In Claude Code, the coordinator launches the independent reviewer (`wled_reviewer`) explicitly with the Opus model. Codex is unaffected. | Confirmed human instruction, issue-48 workflow session, 2026-11-05; see [DEC-008](#dec-008--reviewer-on-opus-in-claude-code) |

These seed entries restate decisions already present in the current project
discussion/rules; they do not claim a separate human GitHub approval comment.
The conversation has no source permalink available in these files. PR/issue links
locate the durable project restatement, not an invented original-message URL.
The entries are active only within their described scope. A later human decision
can explicitly amend them.

### DEC-006 — Post-merge issue completion

- Status: active workflow intent; implementation and its merge remain subject to
  the normal branch, independent review and human merge process.
- Authority/source: human request in the current project conversation on
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
- Authority/source: human request in the current project conversation on
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
  behavior accepted. The human delegated the choice to the main session; the content was
  decided by the main session, not personally dictated by the human. Not generalized to
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
- [ISSUE-12-DEC-003](decisions/issue-12.md) (coordinator interpretation of the human
  #12 implementation instruction and #12 acceptance box 7, 2026-11-06, issue #12 only;
  not a human decision): stop/start of the deployed HTTP service and load against it
  are in scope; no rebuild, inventory/secret edit or hub change. ISSUE-11-DEC-008 asked
  for an instruction naming target and operations; the plan was announced to the owner
  without objection but without separate explicit approval. Confirmed retroactively by
  the owner on 2026-11-06 for that run only; not standing permission for future service
  operations.

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
2. Before asking the human, check whether an active decision answers the question.
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
