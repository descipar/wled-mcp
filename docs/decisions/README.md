# Issue-specific decisions

Issue-specific decisions are grouped by milestone or topic, one `## Issue #<n> decisions`
section per issue with its `### ISSUE-<n>-DEC-xxx` (or `-OPEN-xxx`) entries. Record a decision
that applies only to one issue in the file of its group, appended after the existing sections;
a milestone or topic without a file gets a new `<group>.md` listed below. Do not recreate
per-issue files.

| File | Issues |
| --- | --- |
| [stage-1.md](stage-1.md) | #1 to #14 (stage 1 core) |
| [stage-2.md](stage-2.md) | #16 to #25 |
| [stage-3.md](stage-3.md) | #27 to #31 |
| [hardening.md](hardening.md) | #48, #52, #53, #55, #61, #62, #66, #74, #94, #98 |
| [m3-m6.md](m3-m6.md) | #128, #130, #134, #147, #150, #151 |
| [m7-m8.md](m7-m8.md) | #183, #198, #200 to #204, #236 |
| [workflow.md](workflow.md) | #292 |

Use [the decision template](../agent-workflow/decision.template.md) and stable
IDs such as `ISSUE-10-DEC-001`. Keep entries chronological within a section and mark
superseded entries instead of deleting them. IDs and heading text are stable anchors; do not
rename them. Do not create fictional examples that look like real human decisions.

The coordinator reads relevant files alongside [the shared log](../DECISIONS.md)
at startup/resume and before questions. Include applicable decision IDs and file
commit/references in each work packet and role handoff. The coordinator owns
updates while respecting the current checkout's single-writer assignment.

An issue's agent-generated acceptance criteria are not automatically a human
decision. Link actual human sources when available; otherwise record the neutral
source context/date and the limits of verification. Never copy personal details,
secrets or complete conversation transcripts into these files.
