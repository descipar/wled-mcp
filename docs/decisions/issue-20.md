# Issue #20 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-20-DEC-001 — Default profile, device restrictions, status surface, classes

- ID: ISSUE-20-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #20.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-20/packet.md` (Q1-Q3 and the lower-priority confirmations):
  "alles nach empfehlung" (English: "everything as recommended"); no permalink.
- Scope: issue #20 (S2-ACCESS) and the tool classification used by every tool-adding
  issue.
- Decision:
  - Q1 option (a): when no profile is configured, the profile is `full` (all tools);
    stage-1 configurations and hub entries keep working. Restriction is opt-in, and
    README/quickstart show how to choose `read-only` or `control`.
  - Q2 option (a): device restrictions are a per-device maximum class in the inventory.
    The effective class is the lower of the process profile and the device cap; a call
    above it is refused before any device I/O with a domain error.
  - Q3 option (a): no unauthenticated health route (ISSUE-14-DEC-004 stays). Liveness
    is a TCP connect or authenticated `ping`; readiness/status is a new read-class MCP
    tool (working name `wled_get_service_status`) in both transports.
  - Confirmations: the class vocabulary is `read`, `control`, `manage`, with
    `wled_replace_layout` classified as `control` (D1); no per-credential scopes in #20
    (D3); a correlation ID as a result-envelope field (D8).
- Applicability / conditions / expiry: issue #20; issues #17, #18 and #19 classify each
  new tool with this vocabulary; the tool-contract helper (plan step b) uses it.
- Rationale supplied: none beyond accepting the recommendations; the packet rationale
  (no breaking change for existing deployments; the inventory already limits reachable
  devices; the access guard stays unchanged and works for stdio) is agent analysis.
- Affected requirement IDs, files, issues and tests: S2-ACCESS-01, S2-ACCESS-02,
  S2-T02; docs/TOOL-CONTRACT.md; #16 doctor; #17-#19 tool classification; #67.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-20 packet; plan step (b); #17-#19
  packets.
- Revalidation needed / next action: none before implementation.

## ISSUE-20-DEC-002 — Technical defaults TD-20-1 to TD-20-15

- ID: ISSUE-20-DEC-002
- Recorded date: 2026-11-08
- Status: active for issue #20.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: coordinator acceptance on 2026-11-08 of the technical defaults TD-20-1 to
  TD-20-15 and the choice C-20-1 in the issue-20 requirements packet
  (`.agent-runs/stage2/issue-20/packet.md`, refresh 1, pinned to main `87527dc`);
  recorded in the first #20 implementation PR (PR A, enforcement). Cites
  [ISSUE-20-DEC-001](#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
  (human), which this entry does not change.
- Scope: issue #20. Neither the owner nor any other issue is bound by it beyond the tool
  classification vocabulary of ISSUE-20-DEC-001.
- Decision: how the server enforces what ISSUE-20-DEC-001 decided, in summary:
  - TD-20-1 vocabulary and cumulative profiles: `read` (no live, storage or local file
    mutation), `control` (live device output only), `manage` (device storage or local
    persistent artifacts); `read-only` = {read}, `control` = {read, control}, `full` =
    all. The production table is `src/wled_mcp/access.py`; the test helper keeps its
    independent copy and a test compares both.
  - TD-20-2 (D2) a tool's class is the maximum over all argument combinations;
    `dry_run` does not lower it. A read-only deployment previews through read-class
    plan tools (for example `wled_plan_scene` of #17).
  - TD-20-3 (D7) `Operation.tool_class` is a required keyword; the class cannot come
    from `tests/tool_contract.py` (not shipped), so production carries it.
  - TD-20-4 `create_server(operations, access=None)`; `None` means `full` without caps;
    `build_operations` stays complete and unfiltered. A disabled tool is
    indistinguishable from an unknown one.
  - TD-20-5 (D4) three guard layers: G1 registration filter in `create_server`; G2
    dispatch-time device ceiling after schema validation and before `execute`; G3 entry
    guard of the three write engines and the preset-import path using an ambient
    `ContextVar` holding the calling tool's class, run before the device lock and any
    I/O. `Resources.require_access` is public for composite preflights. A test pins
    `client.post_state` to `resources.py` and `bundle_tools.py`.
  - TD-20-6 additive error code `ACCESS_DENIED`, fixed message naming only the device
    ID and class names, `not_attempted`/`not_requested`.
  - TD-20-7 configuration, additive with `schema_version` 1: `[access] profile` and a
    per-device `max_class`; the serve option `--profile` overrides the file; no
    environment variable; invalid values give a positional, value-free message.
  - TD-20-8 `config validate` and `doctor` output is unchanged without access settings;
    with them, one extra line and additive JSON fields; the doctor export allowlist
    gains the profile and `max_class` names.
  - TD-20-9 to TD-20-12 (PR B) correlation ID with an omit-while-unset serializer,
    bounded structured stderr logging, the read-class `wled_get_service_status` tool
    without device I/O, and unchanged liveness/rotation with a "not tenancy" statement.
  - TD-20-13 two pull requests: A = enforcement, B = diagnostics and status.
  - TD-20-14 full review depth for both.
  - TD-20-15 #67 stays out; the filter is applied once in `create_server`.
  - C-20-1 the migration-note table of `docs/contract/versioning.md` gets two rows
    (tool `-`, pointers `/access` and `/devices/max_class`) with the provisional release
    `0.2.0`, stated in the Change cell; #25 corrects the number if the release differs.
- Applicability / conditions / expiry: applies while #20 is open; a deviation found
  during implementation goes back to the coordinator with its rationale. Not an owner
  decision; the owner can override any part.
- Rationale supplied: packet analysis (agent), accepted by the coordinator; the guard
  hook analysis (three engines plus a direct import path, a sink-level guard would turn a
  refusal into an uncertain write) is in the packet.
- Affected requirement IDs, files, issues and tests: S2-ACCESS-01 to -03, S2-T02,
  S2-COMPAT-01, S2-T06; issues #17 (scene operations add `tool_class`; apply uses the
  engines and calls `Resources.require_access` in its preflight), #18, #67;
  `docs/contract/profiles.md`, `docs/validation/issue-20.md`,
  `tests/test_access_profiles.py`.
- Supersedes / superseded by: none. ISSUE-14-DEC-004 (no health route) stays.
- Propagated to roles / packet references: issue-20 packet (refresh 1); #17 coordinator
  notes (new required field, guard location, `ErrorCode` append).
- Revalidation needed / next action: none before implementation.
