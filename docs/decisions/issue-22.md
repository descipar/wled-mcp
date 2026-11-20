# Issue #22 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09. Human sources are owner chat messages in the main coordinator session, no permalinks.

## ISSUE-22-DEC-001 — Build the PyPI publish workflow

- ID: ISSUE-22-DEC-001
- Status: active for issue #22 only.
- Authority: human decision ("ja, bau den workflow mit publish.yml und pypi aber lass das von opus machen" (English: "yes, build the workflow with publish.yml and pypi, but have Opus do it")), answering whether to build the wheel, smoke-test and publish workflow behind the `pypi` environment.
- Scope: the PyPI part of #22 (S2-DIST-01 and the PyPI side of S2-DIST-03): workflow file, tests, owner-side setup and release documentation.
- Decision: build `.github/workflows/publish.yml` with a build and smoke-test job and a separate publish job in the GitHub environment `pypi`, using PyPI Trusted Publishing (OIDC), no API tokens. Implementation and review run on Opus. The owner registers the pending Trusted Publisher at PyPI (project `wled-mcp`, owner `descipar`, repository `wled-mcp`, workflow `publish.yml`, environment `pypi`) and creates the GitHub environment with required reviewers.
- Conditions: merging the workflow publishes nothing. No upload, name reservation, PyPI/TestPyPI registration, environment, setting or ruleset change, tag, release or workflow run is authorized; each needs an explicit instruction (DEC-023). Merge needs the owner's approval; the DEC-022 standing approval is not used (DEC-027 item 7). Answers, for #22, the workflow part of DEC-023 item 2 and DEC-027 item 4.
- Update 2026-11-09: PR #141 merged as `bf2359e` at the owner's instruction ("141 mergen, keine testpypi probe, trigger design wie vorgchlagen" (English: "merge 141, no TestPyPI rehearsal, trigger design as proposed"); typing error kept), with `--admin` (DEC-024).

## ISSUE-22-DEC-002 — Technical defaults for the PyPI workflow packet

- ID: ISSUE-22-DEC-002
- Status: active for issue #22 only; technical proposal by the coordinator under ISSUE-22-DEC-001, not an owner decision (items 2 and 4 later owner-confirmed, see Update).
- Authority: technical proposal (coordinator).
- Scope: the PyPI publish workflow packet of #22.
- Decision:
  1. Bounded packet: only the PyPI workflow; OCI image pipeline, SBOM, attestation and vulnerability review stay open.
  2. Triggers: a published GitHub release and manual `workflow_dispatch` on a tag; no `push` or `pull_request` trigger publishes. The publish job runs in environment `pypi`, whose required reviewers are the barrier.
  3. Version guard: the build job refuses unless the ref is tag `v<version>` matching `project.version` of `pyproject.toml` and the built artifacts.
  4. Actions in `publish.yml` pinned by full commit SHA (it holds `id-token: write`); `ci.yml` keeps its style.
  5. Documentation in new `docs/PUBLISHING.md` (DEC-021 placement); evidence in `docs/validation/issue-22.md`.
  6. The build job also refuses a tag whose commit is not reachable from `main` (DEC-023 item 1).
  7. Package metadata may be completed (classifiers without `License ::`, `Changelog` URL, sdist exclusion of a worktree `.git` file); exact runtime pins and README wording are reported to the owner.
- Observation (read-only, 2026-11-09, not a decision): PyPI and TestPyPI returned 404 for `wled-mcp`; a GitHub environment `pypi` existed with one required-reviewer rule; no tag for the current version existed.
- Update 2026-11-09: items 2 and 4 are owner-confirmed by the message quoted in ISSUE-22-DEC-001's update; items 1, 3 and 5 to 7 remain coordinator defaults. The owner declined a TestPyPI rehearsal. Item 7's report is answered by ISSUE-22-DEC-003 and ISSUE-22-DEC-005.

## ISSUE-22-DEC-003 — Loosen the exact runtime pins

- ID: ISSUE-22-DEC-003
- Status: active for issue #22 only.
- Authority: human decision ("laufzeit pins lockern" (English: "loosen the runtime pins")), answering whether to keep or loosen the exact pins `mcp==2.3.0`, `starlette==1.10.0`, `uvicorn==0.54.0`.
- Scope: #22 acceptance item 4 (S2-DIST-03).
- Decision: published metadata declares ranges instead of exact pins. The staged release, container image and stdio hub example keep installing the exact tested set through `requirements-runtime.txt`.
- Conditions: the ranges are technical defaults (ISSUE-22-DEC-004); no release or upload is authorized.

## ISSUE-22-DEC-004 — Technical defaults for the dependency ranges

- ID: ISSUE-22-DEC-004
- Status: active for issue #22 only; technical proposal accepted by the coordinator under ISSUE-22-DEC-003, not an owner decision.
- Authority: technical proposal (requirements role, accepted by the coordinator).
- Scope: #22 acceptance item 4.
- Decision:
  1. Ranges: `mcp>=2.3.0,<3`, `pydantic>=2.12.0,<3`, `httpx2>=2.16,<3`, `starlette>=1.0.0,<2`, `uvicorn>=0.31.1,<0.55` (capped at the next minor: `0.x`, internals subclassed), `anyio>=4.10,<5` (newly declared, imported directly).
  2. Floors confirmed by a lowest-direct install and test run; a failing floor is raised and recorded. The run confirmed all floors.
  3. Placement: `docs/contract/dependencies.md`; evidence `docs/validation/issue-22.md`; CHANGELOG entry in the 0.1.2 section.
- Conditions: widening an upper bound later needs a highest-resolution test run.
- Owner update 2026-11-09: "mach es doch sinnvoller und gehe nicht alle versionen so tief runter, da kann man doch mal abwägen" (English: "do it more sensibly and do not go down so deep for all versions, one can weigh things up"). The ranges rest on one lower-bound run and one newest/locked run; the review is light.

## ISSUE-22-DEC-005 — README fit for the PyPI project page

- ID: ISSUE-22-DEC-005
- Status: active for issue #22 only.
- Authority: human decision (paraphrased by the main session, no verbatim quote): fewer separate PRs on the release path, so the PR of ISSUE-22-DEC-003 also makes README.md correct for the PyPI page.
- Scope: README.md for the PyPI page of 0.1.2 (S2-DIST-01), same PR as ISSUE-22-DEC-003.
- Decision: no false "not published to PyPI" statement and no dated "published" claim; PyPI route first once published, Git route kept; every relative link made absolute (`https://github.com/descipar/wled-mcp/blob/main/...`); a test fails on a relative link. No other README edits.
- Conditions: no tag, release, upload, registration or setting change authorized; tagging afterwards is the main session's action under its own owner authorization.

## ISSUE-22-DEC-006 — Narrow #22 to the PyPI path

- ID: ISSUE-22-DEC-006
- Status: active for issue #22 only.
- Authority: human decision (instructions paraphrased, no verbatim quote): narrow #22 to the PyPI path and move container work to a new backlog issue.
- Scope: acceptance checklist and title of #22; new issue #156 (S2-DIST-01 to 03).
- Decision: #22 covers the PyPI wheel/sdist release path only (S2-DIST-01 and the PyPI parts of S2-DIST-03). Container selection and smoke tests, multi-architecture images, image SBOM/provenance, image name checks and OCI pin/rollback documentation (S2-DIST-02 and the OCI parts of S2-DIST-03) move to [#156](https://github.com/descipar/wled-mcp/issues/156) in the Backlog. DEC-023 still applies.
- Conditions: no build, upload, registration or setting change authorized. Next: close #22 once the inventory and vulnerability note exists.
