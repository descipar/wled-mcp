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
- Status: active for issue #12 only, superseded in part (TD-12-1) by ISSUE-12-DEC-004.
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
- Supersedes / superseded by: superseded in part: TD-12-1 (HTTP only) is superseded by
  [ISSUE-12-DEC-004](#issue-12-dec-004--stdio-via-uvx-stays-in-12-scope) for the
  remaining #12 work; TD-12-2 to TD-12-7 stay active. ISSUE-10-DEC-001 remains in force
  unchanged.
- Propagated to roles / packet references: implementer and reviewer through the
  coordinator.
- Revalidation needed / next action: independent review of the candidate.

## ISSUE-12-DEC-003 — Service stop/start and load on the deployed HTTP service

- ID: ISSUE-12-DEC-003
- Recorded date: 2026-11-06
- Status: confirmed retroactively by the owner for the #12 run only (2026-11-06);
  issue #12 only.
- Authority: coordinator interpretation of the human instruction to implement #12
  under the defined workflow and of #12 acceptance box 7 (drain and load per mode);
  not a human decision and not an explicit human answer.
  [ISSUE-11-DEC-008](issue-11.md#issue-11-dec-008--drain-and-load-live-checks-move-to-12)
  asked for an own instruction naming target and permitted operations. The
  coordinator announced the stop/start and load plan (including stopping the service
  while a call is in flight) to the owner before the run; the owner did not object but
  gave no separate explicit approval. This interpretation was then presented to the
  owner for confirmation.
- Owner confirmation: confirmed retroactively on 2026-11-06 for that run only; not
  standing permission for future service operations. Source: owner reply "ja, war in
  ordnung" in the project conversation on 2026-11-06, answering the coordinator's
  question whether stopping/starting the deployed HTTP service during the #12 tests
  (two short outages of about 2 s) was acceptable; also recorded as a coordinator
  comment on #12. No permalink.
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
- Revalidation needed / next action: none for the #12 run (owner confirmation
  recorded above). Any further service stop/start, load run or operation outside this
  list needs a new human instruction.

## ISSUE-12-DEC-004 — stdio via uvx stays in #12 scope

- ID: ISSUE-12-DEC-004
- Recorded date: 2026-11-06
- Status: active for issue #12 only.
- Authority: human decision.
- Source: owner reply in the project conversation on 2026-11-06 ("nein, auch stdio in
  #12", answering the coordinator's question on the stdio scope of #12), recorded as a
  coordinator comment on [#12](https://github.com/descipar/wled-mcp/issues/12); no
  permalink to the original message available.
- Scope: the remaining #12 acceptance work.
- Decision: stdio via uvx stays in #12 scope. The stdio-mode live checks (drain of an
  in-flight call when the entry is stopped, load measurements, and the H04-H06
  scenarios as applicable) are required for #12 and are not moved to stage 2.
- Applicability / conditions / expiry: issue #12 only. It defines scope, not an
  operation approval: each live run still needs its own authorization (for the second
  run, ISSUE-12-DEC-005).
- Rationale supplied: none beyond the reply.
- Affected requirement IDs, files, issues and tests: MCP-04, OPS-01/02/05, CTRL-01,
  SEG-01-04, PRE-01-05, TEST-01; [VALIDATION.md](../VALIDATION.md),
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md).
- Supersedes / superseded by: supersedes TD-12-1 (HTTP only) of ISSUE-12-DEC-002 for
  the remaining #12 work; the first run's HTTP-only scope stays as recorded.
- Propagated to roles / packet references: coordinator comment on #12; implementer and
  reviewer through the coordinator.
- Revalidation needed / next action: none.

## ISSUE-12-DEC-005 — Authorization of the second #12 live run

- ID: ISSUE-12-DEC-005
- Recorded date: 2026-11-06
- Status: used by the second #12 live run on 2026-11-06; expired after that run.
- Authority: human decision.
- Source: owner reply in the project conversation on 2026-11-06 ("ja zu den 3 fragen",
  answering the coordinator's three questions), recorded as a coordinator comment on
  [#12](https://github.com/descipar/wled-mcp/issues/12); no permalink to the original
  message available.
- Scope: the deployed Streamable HTTP service of #11 and its hub entry on the existing
  target, a temporary stdio hub entry on the same hub, and the test controller of
  ISSUE-12-DEC-001.
- Decision:
  1. Update the HTTP deployment on the target to a build from current main, and stop
     and start the HTTP service.
  2. Temporarily register a stdio hub entry and temporarily disable the HTTP hub entry
     during the stdio tests, then remove the stdio entry and re-enable the HTTP entry.
  3. Use the same designated test controller again, with state, segment layout and
     presets file captured beforehand and restored afterwards.
  The owner is within sight for visual checks but may reply with delay; no test may
  depend on a quick human reaction.
- Applicability / conditions / expiry: this run only; not standing permission for later
  deployments, hub changes, service operations or controller writes. Device and host
  names stay in the local run record.
- Rationale supplied: none beyond the reply.
- Affected requirement IDs, files, issues and tests: as ISSUE-12-DEC-004, plus OPS-02;
  [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).
- Supersedes / superseded by: none. ISSUE-12-DEC-001 conditions apply to the controller
  writes; ISSUE-11-DEC-004 (one active mode) holds because the HTTP entry was disabled
  while the stdio entry was registered.
- Propagated to roles / packet references: coordinator comment on #12; implementer and
  reviewer through the coordinator.
- Revalidation needed / next action: any further deployment, hub change or controller
  write needs a new human instruction.

## ISSUE-12-DEC-006 — stdio host-level no-drain accepted as a documented limitation

- ID: ISSUE-12-DEC-006
- Recorded date: 2026-11-06
- Status: active.
- Authority: human decision.
- Source: owner reply in the project conversation on 2026-11-06 to the coordinator's
  question whether the stdio host-level no-drain is acceptable ("ja, ist in ordnung.
  stdio ist ja nur die zweite wahl für heute, ich bevorzuge http"), relayed by the
  coordinator; no permalink to the original message available.
- Scope: issue #12, the stdio-via-uvx mode and its host-owned subprocess lifecycle
  (MCP-04 drain evidence).
- Decision: the behavior observed in the second #12 run, that the MCP host (MCPHub)
  closes the stdio connection on entry disable or stop without draining in-flight
  calls, is accepted as a documented limitation of stdio mode for #12. Streamable HTTP
  is the owner's preferred mode. No code change is requested.
- Applicability / conditions / expiry: #12 and the stdio host lifecycle only. Not a
  deprecation of stdio, not a change to the confirmed two-transport scope, and no
  acceptance of other host behavior. The documented guidance stays: read the state
  before retrying a write cut off this way.
- Rationale supplied: stdio is the second choice for the current use; HTTP is preferred.
- Affected requirement IDs, files, issues and tests: MCP-04;
  [TRACEABILITY.md](../TRACEABILITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md),
  [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).
- Supersedes / superseded by: none; resolves the open question of the MCP-04 cell
  raised after the second run. ISSUE-12-DEC-004 (stdio stays in #12 scope) is unchanged.
- Propagated to roles / packet references: coordinator to implementer; reviewer through
  the coordinator.
- Revalidation needed / next action: none.
