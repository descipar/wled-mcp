# Issue #12 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06. Human sources are owner replies in the coordinator session, also recorded as coordinator comments on [#12](https://github.com/descipar/wled-mcp/issues/12); no permalinks. Device and host names stay in the local, git-ignored run record.

## ISSUE-12-DEC-001 — One test controller released for #12 hardware testing

- ID: ISSUE-12-DEC-001
- Status: active for issue #12 only.
- Authority: human decision.
- Scope: one designated test controller for the #12 hardware acceptance run (H04-H06; CTRL-01, SEG-01-04, PRE-01-05, READ-01/02, TEST-01).
- Decision: the controller is released completely for #12 testing, including state, segment, layout and preset save/activate/delete writes. Condition: state, segment layout and presets file are captured before any write and restored afterwards; restoration is verified and recorded.
- Conditions: that controller only; no configuration, firmware, reboot or network change; not standing permission. A failed or unverifiable restoration is reported to the owner, not retried blindly.

## ISSUE-12-DEC-002 — Technical defaults for the #12 run

- ID: ISSUE-12-DEC-002
- Status: active for issue #12 only, superseded in part (TD-12-1) by ISSUE-12-DEC-004.
- Authority: technical proposal by the requirements agent, accepted by the coordinator; not a human decision, the owner may veto.
- Scope: #12 live run plan, harness and evidence recording (READ-01/02, SEG-04, PRE-05, OPS-01/02/05, MCP-03/04, TEST-01).
- Decision:
  - TD-12-1 Exercise Streamable HTTP only (ISSUE-11-DEC-004 keeps one active mode); stdio items are cited #11 observations or recorded as not exercised. Superseded in part by [ISSUE-12-DEC-004](#issue-12-dec-004--stdio-via-uvx-stays-in-12-scope).
  - TD-12-2 Preset tests use explicit slot 250, plus an optional lowest-free allocation check deleted immediately; preset 1 is never written.
  - TD-12-3 No controller reboot; persistence is the `/presets.json` readback of PRE-05; power-cycle survival is recorded as not run.
  - TD-12-4 Opt-in standard-library HTTP probe `scripts/hw_http_probe.py` (ping, `tools/list`, read-only tool allowlist, bursts with latency percentiles, body bound); never prints the credential, never run in CI.
  - TD-12-5 [TRACEABILITY.md](../TRACEABILITY.md) keeps its cell forms; ISSUE-10-DEC-001 unchanged.
  - TD-12-6 stdio "own execution context": the #11 stdio hub reads already ran from the hub-managed subprocess; cited, not repeated.
  - TD-12-7 Restoration: R1 presets file byte-equal preferred (parsed-equal with recognized empty test slots and identical preset 1 accepted, difference recorded); R2 state field by field (only `ps`/`pl` markers and empty-vs-absent segment name may differ); R3 configuration file hash equal.
- Conditions: bounded to the #12 run; a material deviation goes back to the coordinator.

## ISSUE-12-DEC-003 — Service stop/start and load on the deployed HTTP service

- ID: ISSUE-12-DEC-003
- Status: confirmed retroactively by the owner for the #12 run only (2026-11-06); issue #12 only.
- Authority: coordinator interpretation of the instruction to implement #12 and of acceptance box 7; confirmed retroactively by the owner ("ja, war in ordnung" (English: "yes, that was fine")) after the coordinator announced the plan and asked about two short outages of about 2 s. Not standing permission.
- Scope: the deployed Streamable HTTP service of #11 on the existing target (MCP-04, OPS-01/05; drain D1-D3, load L1-L6).
- Decision: stopping and starting the service (SIGTERM drain checks) and load measurements against it are within #12 scope. Not authorized: image rebuild, inventory or secret edits, hub entry or hub container changes, other hosts or services.
- Conditions: bounded to the #12 run; the service is left running as the one active mode (ISSUE-11-DEC-004). Source context: [ISSUE-11-DEC-008](issue-11.md#issue-11-dec-008--drain-and-load-live-checks-move-to-12) asked for an own instruction.

## ISSUE-12-DEC-004 — stdio via uvx stays in #12 scope

- ID: ISSUE-12-DEC-004
- Status: active for issue #12 only.
- Authority: human decision ("nein, auch stdio in #12" (English: "no, stdio in #12 too")).
- Scope: the remaining #12 acceptance work (MCP-04, OPS-01/02/05, CTRL-01, SEG-01-04, PRE-01-05, TEST-01).
- Decision: stdio via uvx stays in #12 scope; the stdio live checks (drain when the entry is stopped, load, H04-H06 as applicable) are required and not moved to stage 2. Supersedes TD-12-1 of ISSUE-12-DEC-002 for the remaining work; the first run's HTTP-only scope stays as recorded.
- Conditions: defines scope, not an operation approval (second run: ISSUE-12-DEC-005).

## ISSUE-12-DEC-005 — Authorization of the second #12 live run

- ID: ISSUE-12-DEC-005
- Status: used by the second #12 live run on 2026-11-06; expired after that run.
- Authority: human decision ("ja zu den 3 fragen" (English: "yes to the 3 questions")).
- Scope: the deployed HTTP service and hub entry on the target, a temporary stdio hub entry on the same hub, and the test controller of ISSUE-12-DEC-001.
- Decision: (1) update the HTTP deployment to a build from current main and stop/start it; (2) temporarily register a stdio hub entry and disable the HTTP entry during the stdio tests, then remove the stdio entry and re-enable HTTP; (3) reuse the test controller with state, layout and presets captured and restored. No test may depend on a quick human reaction.
- Conditions: this run only. ISSUE-12-DEC-001 conditions apply to controller writes; ISSUE-11-DEC-004 held because HTTP was disabled while stdio was registered. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).

## ISSUE-12-DEC-006 — stdio host-level no-drain accepted as a documented limitation

- ID: ISSUE-12-DEC-006
- Status: active.
- Authority: human decision ("ja, ist in ordnung. stdio ist ja nur die zweite wahl für heute, ich bevorzuge http" (English: "yes, that is fine. stdio is only the second choice for today anyway, I prefer http")).
- Scope: #12, stdio via uvx and its host-owned subprocess lifecycle (MCP-04 drain evidence).
- Decision: the MCP host (MCPHub) closing the stdio connection on entry disable or stop without draining in-flight calls (second run) is accepted as a documented limitation for #12. Streamable HTTP is the preferred mode; no code change.
- Conditions: #12 and the stdio host lifecycle only; not a deprecation of stdio or change of the two-transport scope. Guidance stays: read state before retrying a cut-off write. ISSUE-12-DEC-004 unchanged. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).

## ISSUE-12-DEC-007 — Remaining #12 scope after the second run, and a third run

- ID: ISSUE-12-DEC-007
- Status: active for issue #12; item 2 (the run authorization) was used by the third #12 live run on 2026-11-06 and expired after that run.
- Authority: human decision ("stimme zu" (English: "I agree")) to the coordinator's six-point proposal; item 6 also recorded on [#25](https://github.com/descipar/wled-mcp/issues/25).
- Scope: items left open after the second run (boxes 1, 3 and 7 of #12, relevance of H07); H02, H04, H07, MCP-04.
- Decision:
  1. H02: comparison "with the WLED UI" is satisfied by comparing tool output with the controller endpoints the UI renders (state, info, effect, palette, preset data); no screenshot required.
  2. One short owner-watched run through the deployed HTTP service on the test controller of ISSUE-12-DEC-001 verifies visible effect animation, a speed change and (owner request) brightness transitions (E3); capture before, restore after. Authorizes the third run only.
  3. stdio H04 as exercised in the second run (power/brightness rules, verified color and effect writes via `wled_replace_layout` and `wled_patch_segments`) is sufficient; same domain code as HTTP.
  4. stdio drain evidence at host level is sufficient (ISSUE-12-DEC-006); no server-side SIGTERM observation in stdio mode.
  5. stdio load measured through the hub within its rate limit is sufficient; HTTP is fully measured; load beyond the rate limit or without the hub hop is not required.
  6. Live H07 (unreachable configured controller on the target) moves to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)); mocked coverage (T02, T09) remains the stage-1 evidence; a live run needs its own authorization.
- Conditions: #12 only; item 2 bounded to the third run, HTTP entry and one controller; items 1 and 3-5 are sufficiency rules for #12, not general rules. Narrows ISSUE-12-DEC-004 without removing stdio. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06).

## ISSUE-12-DEC-008 — No separate visual check of an intensity change for H04

- ID: ISSUE-12-DEC-008
- Status: active for issue #12 only.
- Authority: human decision ("rückmeldung und speedtest genügen" (English: "feedback and the speed test are sufficient")).
- Scope: the H04 item "speed/intensity visible behavior" for #12 (CTRL-01).
- Decision: no separate visual check of an intensity change is needed. Verified readback of intensity writes (run 1 H04) plus the owner-confirmed visible speed change of run 3 (E2) are sufficient. Complements ISSUE-12-DEC-007 item 2.
- Conditions: #12 only; not a general rule that readback replaces visual checks; no new hardware run authorized. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06).
