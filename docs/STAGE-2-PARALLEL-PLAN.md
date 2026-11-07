# Stage 2 parallel plan

Status: adopted by the owner as [DEC-021](DECISIONS.md#dec-021--adopt-the-stage-2-parallel-plan) on 2026-11-07.
Revised after an independent review (verdict: adopt with changes) and refreshed against repository state `3a489fc`.
"Starte Stage 2 parallel" starts or resumes this plan (see `agents/coordinator.md`, stage execution). Changes to the
plan's order, track count or rules need the owner.

## Diagnosis (confirmed by review)
Stage 1 was serial mainly because of shared hotspots, not product dependencies: the four feature PRs
(#43/#47/#49/#51) all touched `docs/VALIDATION.md`; three of four touched `operations.py`, `resources.py`,
`scripts/check_distribution.py`, several tests and `docs/TOOL-CONTRACT.md`. Real hotspots are the ~13 hard-coded
ordered tool lists/counts in tests and scripts, `resources.py` (shared write/verify/lock engine) and
`examples/contracts/errors.json`. Not a hotspot: `operations.py` (already composed from per-domain builders).
`docs/DECISIONS.md` and `docs/STAGE-2.md` are additional hotspots: every decision PR appends to the same table and
sections (observed with the stacked DEC-011 to DEC-020 PRs).
Branch rulesets become available when the repository is public (#90, DEC-018/DEC-019). A merge queue is not assumed.

## Hidden couplings
- #16 <-> #21: #16's "stage-1 config stays valid / migration" is #21's policy. #21's version/config policy is a design input to #16.
- #20 x every tool-adding issue (#17/#18/#19): profile classes must classify each new tool; #20 also overlaps #16 config/doctor and #67 (tools/list caching per profile).
- #18 x #19: shared capability model (range, RGBW/CCT, 2D); preset bundles carry #19 segment fields. One owner for the model.
- #17/#18 formats are versioned under #21. #70 shares the version-source decision with #21/#22.
- #21 implements DEC-020 (WLED 16.0.0 floor, below-floor warning together with #16 diagnostics, decision on 0.15.x-specific handling).
- #23, #22 and #90 add files under `.github/` and to the README; #90's minimal CONTRIBUTING.md is extended by #23.
- #44 touches `resources.py` and `tests/test_patches.py` (hotspots); small, but it should land before tracks start editing them.

Resolved since the first draft: #62 is merged; #1 is closed; the Phase 0 owner decisions (license, identity, contact,
history, review, agent tooling, quotes, denylist/branch rules, visibility timing, support policy) are recorded as
DEC-011 to DEC-020, so #22-#24 are no longer blocked on owner input.

## Plan
Phase 0, read-only, can start now: requirements packets in parallel for #16, #18, #19, #20, #21 (in ignored
`.agent-runs/`); they must state the couplings above and propose capability-model and profile-class owners.
Phase 1, serial small PRs (independent review each), in this order:
 (a) #90 visibility readiness (DEC-015 scan script and review, DEC-018 denylist CI step, DEC-016 orientation and minimal
     CONTRIBUTING.md), then the owner's visibility change and `main` ruleset; this makes required CI checks and
     force-push protection available before parallel tracks start;
 (a2) #94 WLED feature coverage list with completeness figures, after #90's README changes; documentation and a static
     test only, so it may also run alongside later steps as the docs/read-only track. Feature issues #17-#19 update its
     rows when they change support;
 (b) tool-contract helper: one hand-maintained, profile-aware expected-tool-contract helper replacing the hard-coded lists/counts;
 (c) #44 housekeeping nits (removes edits to `resources.py`/`tests/test_patches.py` before tracks begin);
 (d) docs convention: convention only: new contract/evidence go into new files (`docs/contract/<area>.md`,
     `docs/validation/<issue>.md`) and issue-specific decisions into `docs/decisions/issue-<n>.md`, linked from existing
     docs; nothing moves;
 (e) workflow rules: recorded as DEC-021 together with this plan (`agents/coordinator.md` stage execution, regenerated
     adapters); this step is done.
Phase 2, at most two implementation tracks:
 Track A: #21 (absorbs #70, implements DEC-020) -> #16 -> #20 (+#67).
 Track B: #18 then #19 (parallel only after capability-model owner is fixed); #17 after #16 and #20 profile classes.
 #22 after #21's version source merges; #23 remaining docs/governance after #90, quickstart after #16.
Phase 3: #24, then #25 (artifact publication and submissions only, per DEC-019).

## Sync/re-review rule
Keep a PR current by merging `main` into its branch, not by rebasing and force-pushing. A sync whose resulting diff
against `main` equals the PR's own commits and whose CI is green keeps the review PASS; any conflict resolution that
changes the PR's own content, or semantic overlap with newly merged work, triggers a fresh review. Merge one PR at a
time and sync the next before merging. Stacked PRs are retargeted to `main` before their base branch is deleted;
otherwise GitHub closes them.

## Hardware
Single shared device. Each hardware run needs its own human authorization; the integration owner only schedules.

## Owner decisions (DEC-021)
1. At most two implementation tracks; a third only for docs/read-only work.
2. #90 comes first in Phase 1.
3. Workflow rules adopted: per-issue coordinators, main session as integration owner, the sync/re-review rule above and
   DEC-010 conformance. They apply from the merge of DEC-021; parallel implementation tracks start in Phase 2.
4. "Depends on" in #16, #17, #20, #21 and #23 updated to the couplings above (2026-11-07).
5. #94 (WLED feature coverage list) added after #90 at the owner's request (2026-11-07).
