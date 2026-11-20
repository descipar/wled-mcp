# Issue #90 runbook: visibility change and `main` rules

Status: prepared, not executed. Sections 1 to 4 are owner-only actions in the repository settings;
no agent changes visibility, rulesets or settings. Decisions:
[DEC-019](../DECISIONS.md#dec-019--make-the-repository-public-before-the-release),
[DEC-023](../DECISIONS.md#dec-023--staged-first-public-release),
[DEC-024](../DECISIONS.md#dec-024--main-branch-rules-with-review-for-external-pull-requests).

Rulesets and the fork-approval setting are unavailable for the private repository (2026-11-08: rulesets
API HTTP 403, fork-approval API HTTP 422), so sections 2 to 4 follow section 1. UI labels follow the
GitHub documentation of that date; the read-back in section 5 is the authority.

## 0. Before the visibility change

The DEC-015 scan result is approved by the owner (recorded in #90); `main` is green and contains the
commit to publish; the owner has given the explicit instruction.

## 1. Make the repository public

Settings, General, "Danger Zone", "Change repository visibility", choose public and confirm (the
repository name has to be typed).

## 2. Require approval for workflow runs of outside pull requests

Settings, Actions, General, "Approval for running fork pull request workflows from contributors":
"Require approval for all external contributors", save.

## 3. Ruleset A: integrity of `main` (no bypass)

Settings, Rules, Rulesets, New branch ruleset: name `main-integrity`, enforcement Active, empty
bypass list, target the default branch. Rules: restrict deletions; block force pushes; require status
checks `checks (ubuntu-latest, 3.13)` and `checks (ubuntu-24.04-arm, 3.13)` (up-to-date branches
off).

## 4. Ruleset B: review of pull requests, owner bypass for merging (DEC-024)

New branch ruleset: name `main-review`, enforcement Active, bypass "Repository admin" role set to
"For pull requests only", target the default branch. Rule: require a pull request with 1 required
approval; Code Owners, stale-approval dismissal and most-recent-push approval off.

Expected: an external pull request cannot run workflows before the owner approves them and cannot
merge without one approving review and green checks. A pull request of the owner or of an agent under
the owner's account shows a bypass option for the review requirement; ruleset A still applies.

## 5. Read-back by the agent (read-only)

After the owner reports sections 1 to 4 as done, the agent runs these GET requests with the owner's
authenticated `gh`, never a mutating one, and records the result in #90 without secrets.

```bash
gh api repos/descipar/wled-mcp --jq '{visibility, private}'
# expect: visibility "public", private false
gh api repos/descipar/wled-mcp/actions/permissions/fork-pr-contributor-approval
# expect: policy "all_external_contributors" (check the returned field name)
gh api repos/descipar/wled-mcp/rulesets --jq '.[] | {id, name, enforcement, target}'
# expect: main-integrity and main-review, both "active", target "branch"
gh api repos/descipar/wled-mcp/rulesets/<id> \
  --jq '{name, enforcement, bypass_actors, conditions, rules: [.rules[] | {type, parameters}]}'
# main-integrity: bypass_actors [], deletion, non_fast_forward, required_status_checks with the
#   two contexts and strict_required_status_checks_policy false
# main-review: one admin bypass actor with bypass_mode "pull_request", rule pull_request with
#   required_approving_review_count 1
```

## 6. After the first merge under the new rules

The first agent-made merge shows whether `gh pr merge --squash --match-head-commit <sha>` needs
`--admin` for the review bypass; only then are `agents/coordinator.md` (regenerated adapters) and
DEC-022 item 4 updated. An outside pull request is not simulated by an agent; the owner may open a
test pull request from a second account or fork to observe the approval prompt.
