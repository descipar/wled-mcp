# Issue-specific decisions

Create `issue-<number>.md` when an actual decision applies only to that issue.
Use [the decision template](../agent-workflow/decision.template.md) and stable
IDs such as `ISSUE-10-DEC-001`. Keep entries chronological and mark superseded
entries instead of deleting them. Do not create fictional examples that look
like real human decisions.

The coordinator reads relevant files alongside [the shared log](../DECISIONS.md)
at startup/resume and before questions. Include applicable decision IDs and file
commit/references in each work packet and role handoff. The coordinator owns
updates while respecting the current checkout's single-writer assignment.

An issue's agent-generated acceptance criteria are not automatically a human
decision. Link actual human sources when available; otherwise record the neutral
source context/date and the limits of verification. Never copy personal details,
secrets or complete conversation transcripts into these files.
