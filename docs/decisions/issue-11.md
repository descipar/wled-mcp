# Issue #11 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-11-DEC-001 — Scoped implementation authority for #11

- ID: ISSUE-11-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: human decision.
- Source: human request in the coordinator session on 2026-11-06 to start #11
  following the defined workflow (DEC-001); no permalink available.
- Scope: issue #11 implementation work on its feature branch: deployment artifacts
  (Dockerfile, Compose and hub examples, staging helper), documentation, routine
  device-free tests, independent review and a reviewable pull request.
- Decision: implement #11 under the defined workflow. Explicitly excluded: merge,
  deployment to any hub or home server, starting a container on a hub, hub entry
  registration, LAN or device contact, physical writes, image/registry/package
  publication, license selection and router forwarding.
- Applicability / conditions / expiry: bounded to the #11 candidate and its review
  cycle. Local developer-machine checks (image build pulling a public base image,
  `docker compose config`, loopback container run) are allowed and must be labeled
  "local developer machine, not target". Live checks H02/H03 and any deployment need a
  separate human instruction naming the mode(s) and target.
- Rationale supplied: none beyond the request.
- Affected requirement IDs, files, issues and tests: OPS-01–05, MCP-01–04, TEST-01;
  #11; packet `.agent-runs/issue-11/packet.md`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements packet "Authorized scope";
  implementer and reviewer through the coordinator.
- Revalidation needed / next action: none for the candidate; the human merge decision
  remains separate.

## ISSUE-11-DEC-002 — Technical deployment defaults TD-1 to TD-9

- ID: ISSUE-11-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: technical proposal by the requirements agent, accepted by the coordinator
  within ISSUE-11-DEC-001. This is not a human decision; the owner did not choose these
  defaults and may veto them at review.
- Source: requirements packet `.agent-runs/issue-11/packet.md`, section "Technical
  defaults", 2026-11-06, no permalink.
- Scope: issue #11 deployment artifacts and documentation.
- Decision:
  - TD-1 Both modes consume a pre-staged versioned directory
    `/app/binaries/wled-mcp/<version>/` (wheel, `requirements-runtime.txt`,
    `SHA256SUMS`). Private Git pinned to a full commit is documented only as an
    alternative; an offline wheelhouse is optional.
  - TD-2 HTTP base image: official `python:3.13.<patch>-slim-<debian>` with an exact
    patch tag (and digest) in the Dockerfile.
  - TD-3 Image built locally on the target from the staged artifacts, local tag
    `wled-mcp:<version>`, no push; pip install of the wheel with `--constraint`;
    fixed non-root UID 10001 (adjustable); exec-form `ENTRYPOINT ["wled-mcp"]`.
  - TD-4 Separate Compose project joining the hub network as `external`; no host port;
    `restart: unless-stopped`; `stop_grace_period` above the 122 s drain bound;
    read-only root filesystem with writable data mount and tmpfs `/tmp`; all
    capabilities dropped; `no-new-privileges`.
  - TD-5 Liveness: Compose healthcheck is a TCP connect to the service port with the
    image's Python; an authenticated `ping` is the documented stronger manual check.
  - TD-6 Credential: Compose `secrets:` from a git-ignored file mounted at
    `/run/secrets/wled_mcp_http_token`, read with `--http-token-file`.
  - TD-7 Stdio: the hub entry sets persistent `UV_CACHE_DIR`, `UV_TOOL_DIR` and
    `UV_PYTHON_INSTALL_DIR`; a runtime/ABI change requires an environment rebuild.
  - TD-8 Static YAML checks use a dev-only YAML parser; an optional
    `docker compose config` check is opt-in and never required in CI.
  - TD-9 Placement: `deploy/http/Dockerfile` with an allowlist
    `deploy/http/Dockerfile.dockerignore`, `examples/compose.http.example.yaml`, hub
    examples in `examples/`.
- Applicability / conditions / expiry: implementation-level refinements made by the
  implementer are recorded in the implementation handoff and DEPLOYMENT.md (uv paths in
  a tree separate from the server data directory; `--isolated` in the stdio entry;
  a staging helper `deploy/stage_release.py`). Actual network name, service name,
  credential storage, hub field schema and target architecture remain deployment-time
  facts to be confirmed when a deployment is requested.
- Rationale supplied: none by the owner. Agent rationale: see the packet; pre-staged
  wheels avoid Git credentials on the target, slim Debian has glibc wheels for the
  compiled dependencies, and the separate Compose project keeps the hub untouched.
- Affected requirement IDs, files, issues and tests: OPS-01–05, MCP-01/03/04;
  `deploy/**`, `examples/*`, `docs/DEPLOYMENT.md`, `tests/test_deployment_artifacts.py`,
  `scripts/check_distribution.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet TD-1–TD-9; implementer handoff
  `.agent-runs/issue-11/implementation.md`; reviewer through the coordinator.
- Revalidation needed / next action: independent review; a human veto of any default
  (for example base image family or a separate Compose project) requires a refreshed
  packet and tests.

## ISSUE-11-DEC-003 — Bounded live test installation on the hub host

- ID: ISSUE-11-DEC-003
- Recorded date: 2026-11-06
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision.
- Source: human instruction in the coordinator session on 2026-11-06 to install the
  #11 artifacts on the project's hub host as a test and run the coordinator's tests
  there; no permalink available.
- Scope: one bounded operation: a test installation of release 0.1.0 (source commit
  `0da1249`) in both modes on that one hub host, and the coordinator's checks there.
  One authorized test controller, named in the instruction, for read tests and master
  power on/off only.
- Decision: the test installation, hub registration of each mode and the read-only and
  power on/off checks on that one controller were authorized. Not authorized: other
  controllers, other writes (brightness, color, effects, segments, layouts, presets),
  device configuration changes, publication, merge.
- Applicability / conditions / expiry: bounded to that run. It is not standing
  permission for future deployments, updates, rollbacks, removal of the HTTP service,
  other hosts or other devices; each needs its own instruction. The controller name and
  host details stay in the local, git-ignored run record and are not committed.
- Rationale supplied: none beyond the instruction.
- Affected requirement IDs, files, issues and tests: OPS-01/02/05, MCP-01/03/04, H02/H03;
  [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06),
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md).
- Supersedes / superseded by: narrows nothing in ISSUE-11-DEC-001 retroactively; that
  entry's deployment exclusion remains in force outside this bounded operation.
- Propagated to roles / packet references: packet
  `.agent-runs/issue-11/packet-live-evidence.md`; implementer through the coordinator.
- Revalidation needed / next action: any further live operation needs a new
  instruction naming mode, target and permitted device operations.

## ISSUE-11-DEC-004 — Follow-up after the live check

- ID: ISSUE-11-DEC-004
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: human decision accepting coordinator proposals ("setze deine Vorschläge
  um", 2026-11-06); the choice of mode is an agent choice inside that approval.
- Source: human instruction in the coordinator session on 2026-11-06; no permalink
  available.
- Scope: issue #11 live installation from ISSUE-11-DEC-003 and its documentation.
- Decision: keep exactly one mode active against the controllers (the coordinator
  selected Streamable HTTP; this is not a separate human mode decision); remove the
  stdio hub entry only; document the live results in a follow-up documentation pull
  request; track underscore hostnames in `base_url` as
  [issue #61](https://github.com/descipar/wled-mcp/issues/61); re-run the post-merge
  completion check for #11 afterwards.
- Applicability / conditions / expiry: does not authorize further deployments,
  update/rollback runs, removal of the HTTP service, other devices or writes beyond
  ISSUE-11-DEC-003. A later human preference for stdio supersedes the mode choice.
- Rationale supplied: none beyond accepting the proposals. Agent rationale: two active
  instances against the same controllers are not coordinated (DEPLOYMENT.md).
- Affected requirement IDs, files, issues and tests: OPS-05; #11, #61;
  [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06),
  [DEPLOYMENT.md](../DEPLOYMENT.md), `tests/test_deployment_artifacts.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet
  `.agent-runs/issue-11/packet-live-evidence.md`; implementer through the coordinator.
- Revalidation needed / next action: independent review of the documentation pull
  request; human merge decision; then completion re-run.

## ISSUE-11-DEC-005 — Live version update/rollback moves to stage 2

- ID: ISSUE-11-DEC-005
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: human decision.
- Source: human scope decision in the coordinator session on 2026-11-06 ("rollback und
  update sehe ich erst in stage 2, das kann hier raus"); no permalink available.
- Scope: the live-evidence expectation of issue #11.
- Decision: live execution of a version-to-version update and rollback is not part of
  #11; it moves to stage 2, tracked by
  [#21](https://github.com/descipar/wled-mcp/issues/21) (S2-COMPAT-03) and
  [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01). The documented
  update, rollback and recreation procedures in [DEPLOYMENT.md](../DEPLOYMENT.md) remain
  #11 scope.
- Applicability / conditions / expiry: narrows only the #11 live-evidence expectation;
  it does not authorize any live operation and does not change other #11 criteria
  (for example hub container recreation, drain on the target, load measurements, H02
  catalog/preset reads).
  Superseded in part by ISSUE-11-DEC-008: drain on the target and load measurements are
  no longer #11 items; they are tracked by #12.
- Rationale supplied: none beyond the statement; only release 0.1.0 exists.
- Affected requirement IDs, files, issues and tests: OPS-02/05, MCP-01/03/04, READ-01
  (deployment cells); #11, #21, #25;
  [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06),
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md), README,
  `tests/test_deployment_artifacts.py`.
- Supersedes / superseded by: supersedes nothing; narrows the #11 live-evidence
  expectation only.
- Propagated to roles / packet references: implementer through the coordinator
  (correction round 2 of the live-evidence pull request).
- Revalidation needed / next action: stage-2 issues #21/#25 carry the live
  update/rollback evidence; independent review of this documentation change.

## ISSUE-11-DEC-006 — Live removal test of the HTTP service

- ID: ISSUE-11-DEC-006
- Recorded date: 2026-11-06
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision.
- Source: human instruction in the coordinator session on 2026-11-06 ("entfernen des
  http dienstes teste doch einfach mal"); no permalink available.
- Scope: one bounded operation on the same target as ISSUE-11-DEC-003: remove the HTTP
  hub entry, the HTTP service container and its image following
  [DEPLOYMENT.md](../DEPLOYMENT.md), then redeploy from the retained release so that
  Streamable HTTP stays the active mode (ISSUE-11-DEC-004).
- Decision: the removal test and the redeploy were authorized. Not authorized: deleting
  the data directory, credential file or release directory, changes to the hub
  container or its network, other hosts, device writes.
- Applicability / conditions / expiry: bounded to that run; not standing permission for
  further removals, deployments or updates.
- Rationale supplied: none beyond the instruction.
- Affected requirement IDs, files, issues and tests: OPS-05;
  [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06),
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md), README,
  `tests/test_deployment_artifacts.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: implementer through the coordinator
  (correction round 2 of the live-evidence pull request).
- Revalidation needed / next action: any further live operation needs a new
  instruction naming mode, target and permitted operations.

## ISSUE-11-DEC-007 — Remaining box 5/6 live checks on the test controller

- ID: ISSUE-11-DEC-007
- Recorded date: 2026-11-06
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision.
- Source: human instruction in the coordinator session on 2026-11-06 ("5 und 6
  testen, dafür ist das bekannte [test controller] gerät freigegeben. wenn du dir
  merkst wie das aktuelle preset dort ist, ist auch das schreiben zum testen
  freigegeben"; the device name is replaced by its role, the known test controller of
  ISSUE-11-DEC-003). No permalink available.
- Scope: one bounded operation on the same target and the same single test controller
  as ISSUE-11-DEC-003: the remaining #11 live checks of acceptance boxes 5 and 6 (H02
  catalog and preset reads per mode, comparison with the device's own catalog data,
  stdio re-registration and environment rebuild, hub container recreation, removal of
  the stdio entry again). Device reads were authorized; device writes for testing only
  after recording a restorable baseline of the current state and presets.
- Decision: the checks above were authorized. The run recorded a baseline first,
  performed no device writes and compared the final state and preset file equal to
  the baseline. The hub container recreation interrupted all hub entries for about
  30 s and was done under this instruction; before the run, the coordinator announced to
  the owner that the hub container would be recreated and that all hub services would
  be briefly unavailable. Not authorized: other controllers, other
  hosts, hub image updates, device configuration changes, deleting the data directory,
  publication, merge.
- Applicability / conditions / expiry: bounded to that run; not standing permission
  for further hub recreations, deployments, writes or devices. Device and host names
  stay in the local, git-ignored run record.
- Rationale supplied: none beyond the instruction.
- Affected requirement IDs, files, issues and tests: READ-01/02, PRE-01, OPS-01/02/05,
  MCP-01/04; H02/H03;
  [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06),
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md), README,
  `tests/test_deployment_artifacts.py`.
- Supersedes / superseded by: none; ISSUE-11-DEC-004 (HTTP stays the one active mode)
  remains in force, so the stdio entry was removed again after the checks.
- Propagated to roles / packet references: implementer through the coordinator.
- Revalidation needed / next action: independent review of the documentation change;
  human merge decision; then completion re-run. Drain of an in-flight call on the
  target and load measurements remain pending.
  Superseded in part by ISSUE-11-DEC-008: these two checks moved to #12 and are no
  longer pending in #11.

## ISSUE-11-DEC-008 — Drain and load live checks move to #12

- ID: ISSUE-11-DEC-008
- Recorded date: 2026-11-06
- Status: active for issue #11 only.
- Authority: human decision.
- Source: human answer "b" in the coordinator session on 2026-11-06 to the
  coordinator's options after the post-merge completion run for pull request #64
  returned NEEDS_DECISION (the open drain/load items were recorded as pending #11 items
  by ISSUE-11-DEC-005/007 and TRACEABILITY MCP-04/OPS-01); no permalink available.
- Scope: the live-evidence expectation of issue #11 for two checks.
- Decision: two remaining live checks move from #11 to
  [#12](https://github.com/descipar/wled-mcp/issues/12): (1) drain of an in-flight tool
  call on SIGTERM on the target; (2) load measurements on the target, as listed under
  resource measurements in [DEPLOYMENT.md](../DEPLOYMENT.md). The automated drain
  coverage (T21) remains the #11 evidence for the drain behavior.
- Applicability / conditions / expiry: narrows only the #11 pending list. It does not
  authorize any live operation, does not change the authority or bounded operations of
  ISSUE-11-DEC-005/007 and does not add to #12's acceptance criteria beyond carrying
  these two checks; running them needs its own instruction naming target and permitted
  operations.
- Rationale supplied: none beyond choosing option "b".
- Affected requirement IDs, files, issues and tests: MCP-04, OPS-01; #11, #12;
  [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06),
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md), README,
  `tests/test_deployment_artifacts.py`.
- Supersedes / superseded by: supersedes only the wording that lists drain on the
  target and load measurements as remaining #11 items in ISSUE-11-DEC-005
  ("Applicability") and ISSUE-11-DEC-007 ("Revalidation needed / next action"); both
  entries otherwise stay in force.
- Propagated to roles / packet references: implementer through the coordinator; the
  #11 completion run is to be repeated.
- Revalidation needed / next action: independent review of this documentation change;
  human merge decision; then completion re-run for #11.
