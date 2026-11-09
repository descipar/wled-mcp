# Issue #22 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-22-DEC-001 — Build the PyPI publish workflow

- ID: ISSUE-22-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #22 only.
- Authority: human decision (owner instruction relayed by the main session; chat is the
  normal channel for owner authority).
- Source: owner message in the main coordinator session on 2026-11-09 (no permalink): "ja,
  bau den workflow mit publish.yml und pypi aber lass das von opus machen" (English: "yes,
  build the workflow with publish.yml and pypi, but have Opus do it"). The question it
  answered was whether to build the workflow that builds the wheel, smoke-tests it with a
  real SDK client and then publishes behind the `pypi` environment, named
  `.github/workflows/publish.yml` with the GitHub environment `pypi`.
- Scope: the PyPI part of #22 (S2-DIST-01 and the PyPI side of S2-DIST-03): the workflow
  file, its tests and the owner-side setup and release procedure documentation.
- Decision: build `.github/workflows/publish.yml` with a build and smoke-test job and a
  separate publish job in the GitHub environment `pypi`, using PyPI Trusted Publishing
  (OIDC) without API tokens or secrets. Implementation and review run on Opus. The owner
  registers the pending Trusted Publisher at PyPI (project `wled-mcp`, owner `descipar`,
  repository `wled-mcp`, workflow `publish.yml`, environment `pypi`) and creates the
  GitHub environment `pypi` with required reviewers himself.
- Applicability / conditions / expiry: building and merging the workflow does not publish
  anything. No upload, name reservation, PyPI/TestPyPI registration, GitHub environment,
  repository setting or ruleset change, tag, release or workflow run is authorized by
  this decision; each needs the owner's explicit instruction at that time (DEC-023). The
  merge of the PR needs the owner's approval; the DEC-022 standing merge approval is not
  used (stage 5, DEC-027 item 7).
- Rationale supplied: none beyond the choice of model.
- Affected requirement IDs, files, issues and tests: S2-DIST-01, S2-DIST-03 (PyPI part);
  `.github/workflows/publish.yml`, its tests, `docs/PUBLISHING.md`; issue #22.
- Supersedes / superseded by: none. It answers, for #22, the workflow part of the open
  PyPI question of DEC-023 item 2 and DEC-027 item 4; whether and when a first package is
  actually published stays with the owner.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff (local packet under `.agent-runs/`).
- Revalidation needed / next action: owner merge decision on the PR; the owner-side setup
  steps before a first upload.
- Update 2026-11-09: the owner merge decision is made. PR #141 was merged as `bf2359e`
  (squash of `0021975`) on 2026-11-09 at the owner's instruction ("141 mergen, keine
  testpypi probe, trigger design wie vorgchlagen" (English: "merge 141, no TestPyPI
  rehearsal, trigger design as proposed"); typing error "vorgchlagen" kept), with `--admin`
  (DEC-024). Remaining next action: the owner-side setup steps before a first upload.

## ISSUE-22-DEC-002 — Technical defaults for the PyPI workflow packet

- ID: ISSUE-22-DEC-002
- Recorded date: 2026-11-09
- Status: active for issue #22 only; technical proposal by the coordinator under
  ISSUE-22-DEC-001, not an owner decision. The owner may overrule any item.
- Authority: technical proposal (coordinator).
- Source: issue-22 coordinator session, 2026-11-09.
- Scope: the PyPI publish workflow packet of #22.
- Decision:
  1. Bounded packet: only the PyPI publish workflow part of #22 is implemented. The OCI
     image pipeline, SBOM, attestation/provenance and the vulnerability review stay open;
     #22 stays open after the merge.
  2. Triggers: a published GitHub release and a manual `workflow_dispatch` run on a tag.
     No `push` or `pull_request` trigger publishes. The publish job always runs in the
     environment `pypi`, whose required reviewers are the actual barrier.
  3. Version guard: the build job refuses to continue unless the checked-out ref is a tag
     `v<version>` where `<version>` is `project.version` of `pyproject.toml` and of the
     built artifacts.
  4. Actions in `publish.yml` are pinned by full commit SHA with the version tag as a
     comment, because this workflow holds `id-token: write`. `ci.yml` keeps its current
     style; aligning it is a separate change.
  5. Documentation goes into a new file `docs/PUBLISHING.md` (DEC-021 placement: new
     documentation in new files), linked from `docs/DEPLOYMENT.md` and `docs/STAGE-5.md`;
     evidence goes into `docs/validation/issue-22.md`.
  6. The build job also refuses a tag whose commit is not reachable from `main`
     (DEC-023 item 1: releases come from `main` commits).
  7. Package metadata other than the version may be completed for the package page:
     classifiers (no `License ::` classifier, PEP 639), a `Changelog` URL and an sdist
     exclusion of a worktree `.git` file. The exact runtime pins (#22 acceptance item 4)
     and the README links and wording are not changed here; they are reported to the owner.
- Observation (read-only, 2026-11-09, not a decision): PyPI and TestPyPI return 404 for
  `wled-mcp` (nothing is reserved). A GitHub environment `pypi` already exists with one
  required-reviewer rule and no deployment branch or tag policy; it was created outside
  this packet. No tag for the current version exists yet.
- Applicability / conditions / expiry: this packet only.
- Rationale supplied: not applicable (proposal); reasons are given in `docs/PUBLISHING.md`.
- Affected requirement IDs, files, issues and tests: as ISSUE-22-DEC-001.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff.
- Revalidation needed / next action: owner may confirm or change items 2 and 4 at merge.
- Update 2026-11-09: items 2 (triggers) and 4 (SHA pins only in `publish.yml`; `ci.yml`
  keeps tag pins) are owner-confirmed by the message quoted in ISSUE-22-DEC-001's update,
  which answered a question covering the trigger design and SHA pinning only in
  `publish.yml` together. Items 1, 3 and 5 to 7 remain coordinator technical defaults. The
  owner declined a TestPyPI rehearsal. Item 7's report to the owner is answered by
  ISSUE-22-DEC-003 and ISSUE-22-DEC-005.

## ISSUE-22-DEC-003 — Loosen the exact runtime pins

- ID: ISSUE-22-DEC-003
- Recorded date: 2026-11-09
- Status: active for issue #22 only.
- Authority: human decision (owner, main coordinator session).
- Source: owner message in the main coordinator session on 2026-11-09, chat, no permalink:
  "laufzeit pins lockern" (English: "loosen the runtime pins"). It answered whether to keep
  or loosen the exact pins `mcp==2.3.0`, `starlette==1.10.0` and `uvicorn==0.54.0`.
- Scope: #22 acceptance item 4 (S2-DIST-03, dependency declarations).
- Decision: the published metadata declares ranges instead of exact pins. The staged
  release, the container image and the stdio hub example keep installing the exact tested
  set through `requirements-runtime.txt`.
- Applicability / conditions / expiry: the concrete ranges are technical defaults
  (ISSUE-22-DEC-004); the owner may overrule them. No release or upload is authorized.
- Rationale supplied: none.
- Affected requirement IDs, files, issues and tests: S2-DIST-03; `pyproject.toml`,
  `docs/contract/dependencies.md`, `tests/test_dependency_ranges.py`,
  `scripts/check_distribution.py`; issue #22.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff.
- Revalidation needed / next action: none.

## ISSUE-22-DEC-004 — Technical defaults for the dependency ranges

- ID: ISSUE-22-DEC-004
- Recorded date: 2026-11-09
- Status: active for issue #22 only; technical proposal accepted by the coordinator under
  ISSUE-22-DEC-003, not an owner decision. The owner may overrule any item.
- Authority: technical proposal (requirements role, accepted by the coordinator).
- Source: issue-22 coordinator session, 2026-11-09.
- Scope: #22 acceptance item 4.
- Decision:
  1. Ranges: `mcp>=2.3.0,<3`, `pydantic>=2.12.0,<3` and `httpx2>=2.16,<3` (both unchanged),
     `starlette>=1.0.0,<2`, `uvicorn>=0.31.1,<0.55`, and `anyio>=4.10,<5`, newly declared
     because the package imports it directly. Upper bounds at the next breaking boundary of
     each upstream versioning policy; uvicorn is capped at the next minor because it is
     `0.x` and the server subclasses its internals (alternative not chosen: `<1`).
  2. Floors are confirmed by a lowest-direct install of the wheel and the test suite; a
     failing floor is raised to the lowest passing release and recorded here, without a new
     owner question. The run confirmed all floors (validation record).
  3. Placement: `docs/contract/dependencies.md`; evidence in `docs/validation/issue-22.md`;
     the CHANGELOG entry goes into the 0.1.2 section, because the change is
     install-compatible and ships with the `v0.1.2` tag.
- Applicability / conditions / expiry: this packet; widening an upper bound later needs a
  highest-resolution test run.
- Rationale supplied: not applicable (proposal); reasons are in
  `docs/contract/dependencies.md`.
- Affected requirement IDs, files, issues and tests: as ISSUE-22-DEC-003.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff.
- Revalidation needed / next action: owner may change the ranges or the uvicorn cap form.
- Owner update 2026-11-09 (main coordinator session, chat, no permalink): "mach es doch
  sinnvoller und gehe nicht alle versionen so tief runter, da kann man doch mal abwägen"
  (English: "do it more sensibly and do not go down so deep for all versions, one can
  weigh things up"). The ranges rest on one lower-bound run and one newest/locked run, with
  no intermediate versions; the review is light (owner).

## ISSUE-22-DEC-005 — README fit for the PyPI project page

- ID: ISSUE-22-DEC-005
- Recorded date: 2026-11-09
- Status: active for issue #22 only.
- Authority: human decision (owner instruction relayed by the main session).
- Source: owner instruction relayed by the main coordinator session on 2026-11-09, chat, no
  permalink. No verbatim quote was relayed; this is the main session's paraphrase: the owner
  wants fewer separate pull requests to finish the release path, so the pull request of
  ISSUE-22-DEC-003 also makes README.md correct for the PyPI project page.
- Scope: README.md for the PyPI project page of 0.1.2 (S2-DIST-01), in the same pull
  request as ISSUE-22-DEC-003.
- Decision: no false "not published to PyPI" statement and no dated "published" claim
  (wording true before and after an upload); the PyPI route first once published, the Git
  route kept; every relative link made absolute to
  `https://github.com/descipar/wled-mcp/blob/main/...`; a test fails on a relative link.
  No other README edits.
- Applicability / conditions / expiry: no tag, release, upload, registration or setting
  change is authorized by this decision; tagging after this pull request is the main
  session's action under its own owner authorization.
- Rationale supplied: fewer separate pull requests on the release path.
- Affected requirement IDs, files, issues and tests: S2-DIST-01; `README.md`,
  `scripts/check_coverage.py`, `tests/test_readme.py`, `tests/test_coverage.py`; issue #22.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff.
- Revalidation needed / next action: none.

- ID: ISSUE-22-DEC-006
- Recorded date: 2026-11-09
- Status: active for issue #22 only.
- Authority: human decision (owner instruction relayed by the main session).
- Source: owner instructions in the main coordinator session on 2026-11-09, chat, no permalink
  and no verbatim quote recorded. The owner agreed to narrow #22 to the PyPI path and to move
  the container work to a new backlog issue.
- Scope: acceptance checklist and title of #22; new issue #156.
- Decision: #22 covers the PyPI wheel/sdist release path only (S2-DIST-01 and the PyPI parts
  of S2-DIST-03). Container selection, container smoke tests, multi-architecture images,
  SBOM/provenance for images, image name checks and OCI pin/rollback documentation
  (S2-DIST-02 and the OCI parts of S2-DIST-03) move to [#156](https://github.com/descipar/wled-mcp/issues/156)
  in the Backlog. DEC-023 still applies: nothing is published without an owner instruction.
- Applicability / conditions / expiry: no build, upload, registration or setting change is
  authorized by this decision.
- Rationale supplied: the container pipeline is deferred by DEC-023 and should not keep the
  PyPI path open.
- Affected requirement IDs, files, issues and tests: S2-DIST-01 to 03; `docs/ROADMAP.md`;
  issues #22 and #156.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: coordinator and completion roles via the issue
  bodies.
- Revalidation needed / next action: reconcile #22 against the narrowed checklist; close it
  once the inventory and vulnerability note exists.
