# Post-merge completion

- Assigned repository / issue / PR / intended target branch:
- Packet / current issue scope reference / requirements / decision IDs:
- Actual human merge authority / reference and verified merge state:
- Reviewed full candidate SHA / passing review reference:
- Integrated commit(s) / merge-squash-rebase equivalence evidence:
- Current target history/content checked / reversion or invalidation checks:
- Acceptance criterion -> merged artifact and appropriate validation evidence:
- Unmet criteria / hardware, release or other evidence limits:
- Issue state/body before / concurrent changes or human reopening checked:
- Managed issue-body section (actual PR number replaces PR_NUMBER):

```markdown
<!-- wled-completion:PR_NUMBER:start -->
## Agent completion evidence

PR / reviewed and integrated references / merge authority:
Acceptance criterion -> artifact and validation:
Remaining criteria / limitations:
Completion assessment:
<!-- wled-completion:PR_NUMBER:end -->
```

- Actual checkbox/report changes or no-op / pre-write re-read:
- Body readback verified before closure / final body and state readback:
- Failed or uncertain writes / re-read and reconciliation / detected races:
- Result: COMPLETED, INCOMPLETE, NEEDS_DECISION or BLOCKED:
- Next action / resumable inputs when completion cannot run:

COMPLETED requires verified merge, satisfied current acceptance, and final
body/state readback. It does not authorize merge or prove unrelated acceptance.
Preserve issue prose and unrelated checklist items; update the managed section in
place. An identical repeat is a no-op, not a fresh timestamp or duplicate report.
