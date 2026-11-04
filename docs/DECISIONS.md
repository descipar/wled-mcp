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

These seed entries restate decisions already present in the current project
discussion/rules; they do not claim a separate human GitHub approval comment.
The conversation has no source permalink available in these files. PR/issue links
locate the durable project restatement, not an invented original-message URL.
The entries are active only within their described scope. A later human decision
can explicitly amend them.

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
