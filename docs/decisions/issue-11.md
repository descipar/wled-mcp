# Issue #11 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06. Sources are coordinator-session instructions without permalink.

## ISSUE-11-DEC-001 — Scoped implementation authority for #11

- ID: ISSUE-11-DEC-001
- Status: active for issue #11 only.
- Authority: human decision (request to start #11 under the defined workflow, DEC-001).
- Scope: #11 implementation on its feature branch (deployment artifacts, docs, device-free tests, review, PR); OPS-01–05, MCP-01–04, TEST-01.
- Decision: implement under the defined workflow. Excluded: merge, deployment to any hub or home server, hub registration, LAN or device contact, physical writes, image/registry/package publication, license selection, router forwarding.
- Conditions: local developer-machine checks (image build, `docker compose config`, loopback run) are allowed and labeled "local developer machine, not target". Live checks H02/H03 and any deployment need a separate instruction naming mode(s) and target.

## ISSUE-11-DEC-002 — Technical deployment defaults TD-1 to TD-9

- ID: ISSUE-11-DEC-002
- Status: active for issue #11 only.
- Authority: technical proposal by the requirements agent, accepted by the coordinator within ISSUE-11-DEC-001; not a human decision, the owner may veto at review.
- Scope: #11 deployment artifacts and documentation (OPS-01–05, MCP-01/03/04).
- Decision:
  - TD-1 Both modes consume a pre-staged versioned directory `/app/binaries/wled-mcp/<version>/` (wheel, `requirements-runtime.txt`, `SHA256SUMS`).
  - TD-2 HTTP base image: official `python:3.13.<patch>-slim-<debian>`, exact tag.
  - TD-3 Image built locally on the target, tag `wled-mcp:<version>`, no push; wheel installed with `--constraint`; non-root UID 10001; exec-form `ENTRYPOINT ["wled-mcp"]`.
  - TD-4 Separate Compose project on the external hub network, no host port, `restart: unless-stopped`, `stop_grace_period` above the 122 s drain bound, read-only root fs, tmpfs `/tmp`, all capabilities dropped, `no-new-privileges`.
  - TD-5 Healthcheck is a TCP connect; an authenticated `ping` is the stronger manual check.
  - TD-6 Credential via Compose `secrets:` from a git-ignored file, read with `--http-token-file`.
  - TD-7 Stdio hub entry sets persistent `UV_CACHE_DIR`, `UV_TOOL_DIR`, `UV_PYTHON_INSTALL_DIR`; a runtime/ABI change needs an environment rebuild.
  - TD-8 Static YAML checks use a dev-only parser; `docker compose config` is opt-in, never required in CI.
  - TD-9 Placement: `deploy/http/Dockerfile` (+ allowlist `.dockerignore`), `examples/compose.http.example.yaml`, hub examples in `examples/`.
- Conditions: implementer refinements are in DEPLOYMENT.md. Network/service names, credential storage, hub field schema and architecture stay deployment-time facts. A human veto of a default needs a refreshed packet and tests.

## ISSUE-11-DEC-003 — Bounded live test installation on the hub host

- ID: ISSUE-11-DEC-003
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision.
- Scope: one operation: test installation of release 0.1.0 (source commit `0da1249`) in both modes on one hub host, with one authorized test controller for read tests and master power on/off only (OPS-01/02/05, MCP-01/03/04, H02/H03).
- Decision: installation, hub registration of each mode and the read and power on/off checks were authorized. Not authorized: other controllers, other writes, device configuration changes, publication, merge.
- Conditions: bounded to that run, no standing permission for deployments, updates, rollbacks, removal, other hosts or devices. Controller and host details stay in the local, git-ignored run record. Evidence: [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06).

## ISSUE-11-DEC-004 — Follow-up after the live check

- ID: ISSUE-11-DEC-004
- Status: active for issue #11 only.
- Authority: human decision accepting coordinator proposals ("setze deine Vorschläge um" (English: "implement your proposals")); the mode choice is an agent choice inside that approval.
- Scope: the live installation of ISSUE-11-DEC-003 and its documentation (OPS-05).
- Decision: keep exactly one mode active against the controllers (the coordinator selected Streamable HTTP); remove the stdio hub entry only; document the live results in a follow-up PR; track underscore hostnames in `base_url` as [issue #61](https://github.com/descipar/wled-mcp/issues/61); re-run the #11 completion check afterwards.
- Conditions: no further deployments, update/rollback, HTTP removal, devices or writes beyond ISSUE-11-DEC-003. A later human preference for stdio supersedes the mode choice.

## ISSUE-11-DEC-005 — Live version update/rollback moves to stage 2

- ID: ISSUE-11-DEC-005
- Status: active for issue #11 only.
- Authority: human decision ("rollback und update sehe ich erst in stage 2, das kann hier raus" (English: "I see rollback and update only in stage 2, that can be taken out here")).
- Scope: the live-evidence expectation of #11 (OPS-02/05, MCP-01/03/04, READ-01 deployment cells).
- Decision: live version-to-version update and rollback are not part of #11; they move to stage 2, tracked by [#21](https://github.com/descipar/wled-mcp/issues/21) (S2-COMPAT-03) and [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01). The documented update, rollback and recreation procedures in [DEPLOYMENT.md](../DEPLOYMENT.md) stay #11 scope.
- Conditions: narrows only the live-evidence expectation, authorizes no live operation. Superseded in part by ISSUE-11-DEC-008: drain on the target and load measurements are tracked by #12.

## ISSUE-11-DEC-006 — Live removal test of the HTTP service

- ID: ISSUE-11-DEC-006
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision ("entfernen des http dienstes teste doch einfach mal" (English: "just test removing the http service")).
- Scope: one operation on the target of ISSUE-11-DEC-003: remove the HTTP hub entry, service container and image per [DEPLOYMENT.md](../DEPLOYMENT.md), then redeploy from the retained release so HTTP stays active (OPS-05).
- Decision: removal test and redeploy authorized. Not authorized: deleting the data directory, credential file or release directory, changes to the hub container or network, other hosts, device writes.
- Conditions: bounded to that run.

## ISSUE-11-DEC-007 — Remaining box 5/6 live checks on the test controller

- ID: ISSUE-11-DEC-007
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision ("5 und 6 testen, dafür ist das bekannte [test controller] gerät freigegeben. wenn du dir merkst wie das aktuelle preset dort ist, ist auch das schreiben zum testen freigegeben" (English: "test 5 and 6; the known [test controller] device is released for that. If you remember what the current preset there is, writing for testing is released too"); device name replaced by its role).
- Scope: one operation on the target and single test controller of ISSUE-11-DEC-003: acceptance boxes 5 and 6 (H02 catalog and preset reads per mode, comparison with the device catalog, stdio re-registration and environment rebuild, hub container recreation, removal of the stdio entry); READ-01/02, PRE-01, OPS-01/02/05, MCP-01/04.
- Decision: the checks were authorized; device writes only after recording a restorable baseline. The run recorded a baseline, performed no device writes and found final state and presets equal to it. Hub container recreation interrupted all hub entries for about 30 s, announced to the owner beforehand. Not authorized: other controllers or hosts, hub image updates, device configuration changes, deleting the data directory, publication, merge.
- Conditions: bounded to that run. ISSUE-11-DEC-004 stays in force, so the stdio entry was removed again. Superseded in part by ISSUE-11-DEC-008: drain on the target and load measurements moved to #12.

## ISSUE-11-DEC-008 — Drain and load live checks move to #12

- ID: ISSUE-11-DEC-008
- Status: active for issue #11 only.
- Authority: human decision (answer "b" to the coordinator's options after the completion run for PR #64 returned NEEDS_DECISION).
- Scope: the #11 live-evidence expectation for two checks (MCP-04, OPS-01).
- Decision: two checks move to [#12](https://github.com/descipar/wled-mcp/issues/12): (1) drain of an in-flight call on SIGTERM on the target; (2) load measurements on the target ([DEPLOYMENT.md](../DEPLOYMENT.md)). Automated drain coverage (T21) remains the #11 evidence.
- Conditions: narrows only the #11 pending list; authorizes no live operation; running them needs its own instruction. Supersedes only the wording listing these two as remaining #11 items in ISSUE-11-DEC-005 and ISSUE-11-DEC-007.
