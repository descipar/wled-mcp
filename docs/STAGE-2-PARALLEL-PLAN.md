# Proposal: running stage 2 with limited parallelism

Status: proposal only, not a decision. Revised after an independent review (verdict: adopt with changes), 2026-11-07.
Based on repository state `c095ceb`. No workflow rule, issue or decision record is changed by this document.

## Diagnosis (confirmed by review)
Stage 1 was serial mainly because of shared hotspots, not product dependencies: the four feature PRs
(#43/#47/#49/#51) all touched `docs/VALIDATION.md`; three of four touched `operations.py`, `resources.py`,
`scripts/check_distribution.py`, several tests and `docs/TOOL-CONTRACT.md`. Real hotspots are the ~13 hard-coded
ordered tool lists/counts in tests and scripts, `resources.py` (shared write/verify/lock engine) and
`examples/contracts/errors.json`. Not a hotspot: `operations.py` (already composed from per-domain builders).
Merge queue and branch protection are NOT available (private repo, free plan).

## Hidden couplings
- #16 <-> #21: #16's "stage-1 config stays valid / migration" is #21's policy. #21's version/config policy is a design input to #16.
- #20 x every tool-adding issue (#17/#18/#19): profile classes must classify each new tool; #20 also overlaps #16 config/doctor and #67 (tools/list caching per profile).
- #18 x #19: shared capability model (range, RGBW/CCT, 2D); preset bundles carry #19 segment fields. One owner for the model.
- #17/#18 formats are versioned under #21. #70 shares the version-source decision with #21/#22.
- #23 and #22 both add files under `.github/`. #25 also waits for #1.
- #62 is a repo-wide wording rewrite (README, docs, agents, decision records) and conflicts with everything.

## Plan
Phase 0, no rule change: ask owner for license, publisher identity/namespace, support/version policy (gates #22-#24).
Start read-only requirements packets in parallel for #16, #18, #19, #20, #21 (in ignored `.agent-runs/`); they must state
couplings above and propose capability-model and profile-class owners.
Phase 1, serial small PRs (independent review each):
 (a) #62 wording pass (or explicitly defer until tracks finish);
 (b) tool-contract helper: one hand-maintained, profile-aware expected-tool-contract helper replacing the hard-coded lists/counts;
 (c) docs convention: convention only: new contract/evidence go into new files (`docs/contract/<area>.md`, `docs/validation/<issue>.md`) linked from existing docs; nothing moves;
 (d) Workflow rules as a human-approved shared decision: worktree per issue, main session as integration owner, rebase/re-review rule, dependency-file owner, one coordinator per issue; includes `agents/coordinator.md` edit and regeneration.
Phase 2, at most two implementation tracks:
 Track A: #21 (absorbs #70) -> #16 -> #20 (+#67).
 Track B: #18 then #19 (parallel only after capability-model owner is fixed); #17 after #16 and #20 profile classes.
 #22 after #21's version source merges; #23 governance parts after Phase 0 decisions, quickstart after #16.
Phase 3: #24, then #25 (also gated on #1).

## Rebase/re-review rule (needs human decision)
A clean rebase onto current main with green CI and scoped diff-equivalence keeps the PASS; any conflict resolution or semantic
overlap triggers a fresh review. Merge one PR at a time; rebase the next before merging.

## Hardware
Single shared device. Each hardware run needs its own human authorization; the integration owner only schedules.

## Decisions for the human
1. Accept 2 implementation tracks (3rd only if docs/read-only)?
2. Approve the workflow rule change (rule change: per-issue coordinators, integration owner, rebase rule) as a shared decision record?
3. Phase 0 owner decisions now or later (license, identity, support policy)?
4. Do #62 first, or defer?
5. Change "Depends on" in #16/#17/#20/#21/#23 issue bodies to match the real couplings?
