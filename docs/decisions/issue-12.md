# Issue #12 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-12-DEC-001 — One test controller released for #12 hardware testing

- ID: ISSUE-12-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #12 only.
- Authority: human decision.
- Source: owner instruction in the project conversation on 2026-11-06, recorded as a
  coordinator comment on [#12](https://github.com/descipar/wled-mcp/issues/12); no
  permalink to the original message available.
- Scope: one designated test controller (named only in the local, git-ignored run
  record) for the #12 hardware acceptance run.
- Decision: the designated test controller is released completely for #12 testing,
  including state, segment, layout and preset save/activate/delete writes (H04-H06).
  Condition: the current state, segment layout and presets file are captured before
  any write, and restored afterwards; the restoration is verified and recorded.
- Applicability / conditions / expiry: that controller only; no other controller,
  no controller configuration, firmware, reboot or network change. Bounded to the #12
  test run; not standing permission for later writes, devices or issues. Device and
  host names stay in the local run record.
- Rationale supplied: none beyond the instruction.
- Affected requirement IDs, files, issues and tests: H04-H06; CTRL-01, SEG-01-04,
  PRE-01-05, READ-01/02, TEST-01; [VALIDATION.md](../VALIDATION.md),
  [TRACEABILITY.md](../TRACEABILITY.md); packet `.agent-runs/issue-12/packet.md`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: requirements packet "Authorized scope";
  implementer and reviewer through the coordinator.
- Revalidation needed / next action: the coordinator captures the baseline before
  the first write; a failed or unverifiable restoration is recorded and reported to
  the owner instead of being retried blindly.

## ISSUE-12-DEC-002 — Technical defaults for the #12 run

- ID: ISSUE-12-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #12 only.
- Authority: technical proposal by the requirements agent, accepted by the coordinator.
  This is not a human decision; the human did not choose these defaults and may veto
  them at review.
- Source: requirements packet `.agent-runs/issue-12/packet.md`, sections 1, 2 and 4
  (TD-12-1 to TD-12-7), 2026-11-06, no permalink.
- Scope: issue #12 live run plan, harness and evidence recording.
- Decision:
  - TD-12-1 Exercise Streamable HTTP only. ISSUE-11-DEC-004 keeps one active mode;
    registering stdio as a second writer would be uncoordinated. stdio items are
    recorded explicitly as cited #11 observations (dated) or as not exercised.
  - TD-12-2 Preset tests use explicit slot 250 (highest reviewed ID, free in the
    baseline, least collision risk with household saves), plus an optional
    lowest-free allocation check that is deleted immediately. Preset 1 is never
    written.
  - TD-12-3 No controller reboot. Persistence is the `/presets.json` readback defined
    by PRE-05 and the tool contract; power-cycle survival is recorded as not run.
  - TD-12-4 An opt-in, standard-library-only HTTP probe (`scripts/hw_http_probe.py`)
    for ping, `tools/list`, an allowlist of read-only tools, bursts with latency
    percentiles and the request-body bound. It refuses any other tool, never prints
    the credential and is never run against devices or targets in CI; its tests use a
    loopback stub and the in-process service.
  - TD-12-5 [TRACEABILITY.md](../TRACEABILITY.md) keeps its existing cell forms; no new
    `recorded:` form is added, so ISSUE-10-DEC-001 stays unchanged.
  - TD-12-6 stdio "own execution context": in stdio mode the server runs as the
    hub-managed subprocess inside the hub container, so the #11 stdio hub reads
    already ran from that context; they are cited, not repeated.
  - TD-12-7 Restoration criteria: R1 presets file byte-equal to the baseline
    preferred; parsed-equal with recognized empty entries for the test slots and a
    byte-identical preset 1 is accepted with the exact byte difference recorded.
    R2 state compared field by field with the baseline (only `ps`/`pl` markers and an
    empty versus absent segment name may differ, each recorded). R3 configuration
    file hash equal to the baseline.
- Applicability / conditions / expiry: bounded to the #12 run and its evidence. A
  material deviation during the run is recorded and returned to the coordinator.
- Rationale supplied: none by the human. Agent rationale: see the packet.
- Affected requirement IDs, files, issues and tests: READ-01/02, SEG-04, PRE-05,
  OPS-01/02/05, MCP-03/04, TEST-01; `scripts/hw_http_probe.py`,
  `tests/test_hw_http_probe.py`, [VALIDATION.md](../VALIDATION.md),
  [TRACEABILITY.md](../TRACEABILITY.md).
- Supersedes / superseded by: none; ISSUE-10-DEC-001 remains in force unchanged.
- Propagated to roles / packet references: implementer and reviewer through the
  coordinator.
- Revalidation needed / next action: independent review of the candidate.

## ISSUE-12-DEC-003 — Service stop/start and load on the deployed HTTP service

- ID: ISSUE-12-DEC-003
- Recorded date: 2026-11-06
- Status: active for issue #12 only.
- Authority: coordinator interpretation of the human instruction to implement #12
  under the defined workflow and of #12 acceptance box 7 (drain and load per mode);
  not a human decision and not an explicit human answer.
  [ISSUE-11-DEC-008](issue-11.md#issue-11-dec-008--drain-and-load-live-checks-move-to-12)
  asked for an own instruction naming target and permitted operations. The
  coordinator announced the stop/start and load plan (including stopping the service
  while a call is in flight) to the owner before the run; the owner did not object but
  gave no separate explicit approval. This interpretation is presented to the owner at
  merge review for confirmation.
- Source: ISSUE-11-DEC-008, the #12 acceptance criteria and the coordinator's plan
  announcement in the project conversation, 2026-11-06; no permalink.
- Scope: the deployed Streamable HTTP service of #11 (its own Compose project) on the
  existing target.
- Decision: stopping and starting the deployed HTTP service (SIGTERM drain checks)
  and load measurements against it are within #12 scope. Not authorized: image
  rebuild or change, inventory or secret edits, hub entry or hub container changes,
  other hosts or services.
- Applicability / conditions / expiry: bounded to the #12 run; the service is left
  running as the one active mode (ISSUE-11-DEC-004). Not standing permission.
- Rationale supplied: none by the human. Coordinator rationale: box 7 cannot be met
  without stopping the deployed service and loading it.
- Affected requirement IDs, files, issues and tests: MCP-04, OPS-01/05; drain D1-D3,
  load L1-L6; [VALIDATION.md](../VALIDATION.md), [DEPLOYMENT.md](../DEPLOYMENT.md),
  [TRACEABILITY.md](../TRACEABILITY.md).
- Supersedes / superseded by: none.
- Propagated to roles / packet references: implementer and reviewer through the
  coordinator.
- Revalidation needed / next action: owner confirmation of this interpretation at
  merge review; if the owner rejects it, the D1/D2 and L1-L6 evidence is reported as
  gathered without explicit authorization. Any operation outside this list needs a new
  human instruction.
