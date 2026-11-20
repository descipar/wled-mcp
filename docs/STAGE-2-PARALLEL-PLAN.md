# Stage 2 parallel plan

Status: adopted by the owner as [DEC-021](DECISIONS.md#dec-021--adopt-the-stage-2-parallel-plan) on 2026-11-07. "Starte Stage 2 parallel" starts or resumes this plan (see `agents/coordinator.md`). Changes to the order, track count or rules need the owner. Phase 0 and Phase 1 are done; the stage-2 issues are closed out ([STAGE-2.md](STAGE-2.md)), so this page remains the reference for the execution rules.

## Why serial work was the problem

Stage 1 was serial because of shared hotspots, not product dependencies: `docs/VALIDATION.md`, `docs/DECISIONS.md`, `docs/TOOL-CONTRACT.md`, `resources.py` (shared write/verify/lock engine), `scripts/check_distribution.py`, the hard-coded tool lists in tests and `examples/contracts/errors.json`. New contract text and evidence therefore go into new files (`docs/contract/<area>.md`, `docs/validation/<issue>.md`, `docs/decisions/issue-<n>.md`) linked from the existing documents.

## Couplings between issues

- #16 and #21: the version/config policy of #21 is a design input to #16's migration rule; #21 implements DEC-020 (WLED 16.0.0 floor).
- #20 and every tool-adding issue (#17/#18/#19): each new tool needs a profile class.
- #18 and #19 share one capability model; preset bundles carry #19 segment fields.
- #17/#18 formats are versioned under #21; #70 shares the version-source decision with #21/#22.
- #22, #23 and #90 add files under `.github/` and to the README.

## Execution rules (DEC-021)

1. At most two implementation tracks in isolated worktrees; a third only for docs/read-only work.
2. Track A: #21, #16, #20 (+#67). Track B: #18, #19 (once the capability-model owner is fixed); #17 after #16 and #20. #22 after #21's version source; #23 after #90; then #24 and #25 (publication and submissions only, per DEC-019).
3. Per-issue coordinators, the main session as integration owner, DEC-010 conformance.
4. Keep a PR current by merging `main` into its branch, never by rebase and force-push. A sync whose diff against `main` equals the PR's own commits with green CI keeps the review PASS; conflict resolutions that change the PR's own content, or semantic overlap with newly merged work, need a fresh review. DEC-022 item 2: the coordinator compares the PR's own diff under `src/`, `tests/` and `scripts/` with the reviewed one and records the check; documentation conflict resolutions alone keep the PASS. Merge one PR at a time and sync the next before merging; retarget stacked PRs to `main` before their base branch is deleted.
5. Hardware is a single shared device; each run needs its own human authorization and the integration owner only schedules.
