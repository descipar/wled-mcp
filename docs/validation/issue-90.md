# Issue #90 runbook: visibility change and `main` rules

Status: prepared, not executed. Every step in sections 1 to 4 is an owner-only action in the
repository settings; no agent changes visibility, rulesets or settings. Decisions:
[DEC-019](../DECISIONS.md#dec-019--make-the-repository-public-before-the-release),
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release) and
[DEC-024](../DECISIONS.md#dec-024--main-branch-rules-with-review-for-external-pull-requests).

Rulesets and the fork-approval setting are not available for this private repository
(observed on 2026-11-08: the rulesets API returned HTTP 403 and the fork-approval API HTTP
422), so sections 2 to 4 follow directly after section 1. The UI labels below follow the GitHub
documentation of that date and may differ slightly; the read-back in section 5 is the
authority, not the labels.

## 0. Before the visibility change

- The DEC-015 scan result is approved by the owner (recorded in #90).
- `main` is green and contains the commit the owner wants public.
- The owner has given the explicit instruction to change visibility.

## 1. Make the repository public

1. Open the repository, then Settings.
2. General, scroll to the "Danger Zone".
3. "Change repository visibility", then "Change visibility", choose public and confirm the
   prompts (the repository name has to be typed).

## 2. Require approval for workflow runs of outside pull requests

1. Settings, then Actions, then General.
2. Section "Approval for running fork pull request workflows from contributors": choose
   "Require approval for all external contributors".
3. Save.

## 3. Ruleset A: integrity of `main` (no bypass)

1. Settings, then Rules, then Rulesets, then New ruleset, then New branch ruleset.
2. Ruleset name: `main-integrity`. Enforcement status: Active.
3. Bypass list: leave empty.
4. Target branches: Add a target, then Include default branch.
5. Branch rules, tick:
   - Restrict deletions
   - Block force pushes
   - Require status checks to pass before merging: Add checks, then add
     `checks (ubuntu-latest, 3.13)` and `checks (ubuntu-24.04-arm, 3.13)`. The names only
     appear in the search once the checks have run recently; they have. Leave "Require
     branches to be up to date before merging" off.
6. Create.

## 4. Ruleset B: review of pull requests, owner bypass for merging (DEC-024)

1. Settings, then Rules, then Rulesets, then New ruleset, then New branch ruleset.
2. Ruleset name: `main-review`. Enforcement status: Active.
3. Bypass list: Add bypass, choose the "Repository admin" role, open its menu and set
   "For pull requests only" (not "Always allow", unless direct pushes to `main` by the owner
   are wanted).
4. Target branches: Add a target, then Include default branch.
5. Branch rules, tick "Require a pull request before merging" with "Required approvals" set to
   1. Leave "Require review from Code Owners", "Dismiss stale pull request approvals" and
   "Require approval of the most recent reviewable push" off.
6. Create.

Expected behavior: an external pull request cannot run workflows before the owner approves
them (section 2) and cannot merge without one approving review and green checks. A pull request
of the owner or of an agent working under the owner's account shows a bypass option for the
review requirement; the checks of ruleset A still apply.

## 5. Read-back by the agent (read-only)

After the owner reports sections 1 to 4 as done, the agent runs these GET requests with the
owner's authenticated `gh` and compares the output with the expected values. The agent never
sends a mutating request.

```bash
gh api repos/descipar/wled-mcp --jq '{visibility, private}'
# expect: visibility "public", private false

gh api repos/descipar/wled-mcp/actions/permissions/fork-pr-contributor-approval
# expect: the policy "all_external_contributors" (check the returned field name)

gh api repos/descipar/wled-mcp/rulesets --jq '.[] | {id, name, enforcement, target}'
# expect: main-integrity and main-review, both enforcement "active", target "branch"

gh api repos/descipar/wled-mcp/rulesets/<id> \
  --jq '{name, enforcement, bypass_actors, conditions, rules: [.rules[] | {type, parameters}]}'
# main-integrity: bypass_actors [], rules deletion, non_fast_forward and
#   required_status_checks with the two contexts above and
#   strict_required_status_checks_policy false
# main-review: one bypass actor (admin role) with bypass_mode "pull_request", rule pull_request
#   with required_approving_review_count 1
```

`bypass_actors` is only returned to a requester with write access to the ruleset, which the
owner's token has. The agent records the result in #90 without secrets.

## 6. After the first merge under the new rules

- The first merge of an agent-made pull request shows whether `gh pr merge --squash
  --match-head-commit <sha>` needs `--admin` for the review bypass. Only then are
  `agents/coordinator.md` (regenerated adapters) and DEC-022 item 4 updated.
- An outside pull request is not simulated by an agent; the owner may open a test pull request
  from a second account or a fork to observe the approval prompt and the missing merge option.
