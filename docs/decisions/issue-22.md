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
- Applicability / conditions / expiry: this packet only.
- Rationale supplied: not applicable (proposal); reasons are given in `docs/PUBLISHING.md`.
- Affected requirement IDs, files, issues and tests: as ISSUE-22-DEC-001.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements, implementer and reviewer via the
  coordinator handoff.
- Revalidation needed / next action: owner may confirm or change items 2 and 4 at merge.
