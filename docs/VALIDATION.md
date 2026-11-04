# Validation and acceptance plan

Current runtime result: **issue #3 bootstrap checks pass locally on Windows/Python 3.13.2**. T14/T16 bootstrap evidence includes 24 tests, SDK subprocess current/legacy negotiation, fixture schema/result/error/uncertainty parity, stdout framing/EOF, configuration, wheel build, clean install and uvx with 30 exact runtime versions verified in each environment. Ruff, strict mypy, lock/export and static agent-setup checks pass. Linux CI is configured; verify its remote result separately. These tests do not implement device writes. Full HTTP T18–T21 and hardware H checks remain pending.

Bootstrap mapping: C3-01/02/08 -> distribution/lock scripts; C3-03/04/07 -> startup/CLI tests; C3-05/06 -> console/fixture subprocess and outcome tests; C3-09 -> CI; C3-10 -> [DEVELOPMENT.md](DEVELOPMENT.md). Remaining contract scenarios retain downstream ownership.

## Automated checks, without hardware

| ID | Scenario and expected evidence | Requirements |
| --- | --- | --- |
| T01 | Invalid/duplicate inventory, URL credentials, path traversal and arbitrary host inputs fail before HTTP; valid explicit ports work | DEV-01, OPS-03 |
| T02 | One offline probe does not hide other configured devices; list without probe performs no HTTP | DEV-02, MULTI-01 |
| T03 | Effect/palette IDs remain correct with gaps and unknown metadata; name ambiguity is explicit; optional metadata endpoint failure does not erase catalogs | READ-02–03 |
| T04 | Patch explicit ID 2 with speed=0/on=false/brightness=0; retain omitted colors/name/intensity and unrelated ID 0. Verify off/effective zero and remembered master/segment brightness separately; positive brightness while off preserves omitted power. Reject contradictory zero/on=true and test 149/150 ms conversion, transition-only/too-short inputs and unchanged persistent transition | CTRL-01, SEG-01 |
| T05 | Noncontiguous old active IDs 0/2/5 become exactly desired 2/6 under a known allocation profile; remove only 0/5, preserve existing omitted state/name, explicitly default new 6. No bulk purge, silent renumbering or dummy tail; sparse new 8 fails before POST. Test safe intermediate ordering, main-ID bookkeeping and partial-step outcomes | SEG-02 |
| T06 | Whole-request validation rejects invalid ranges/counts/IDs/colors/catalogs/overlap before all POSTs. RGB-only requires 3 channels, RGBW 4; unknown moved/new range capability fails. Scalar patches retain preexisting overlap while geometry patches check untouched IDs. Test rejected unrepresentable preservation and zero/power combinations | SEG-03 |
| T07 | Dry runs perform bounded reads only: no device POST, snapshot/temp-file/retention writes or slot reservation. Plans show exact update/create/remove IDs, resolved defaults, compensation and required backup; actual invocation replans under lock | SEG-04 |
| T08 | ACK alone is not success; mismatching/unavailable readback fails. Normalized off retains remembered brightness; expected transient frames do not fail equality. Verify all relevant fields/IDs and expose ignored unsupported changes | SEG-04, MCP-02 |
| T09 | Possible dispatched timeout/reset stays unknown unless bounded readback establishes postcondition; readable mismatch does not prove never applied. No mutation replay; partial sequences stop without further destructive steps, include completed/remaining state; reads/retries share one overall deadline | REL-01–02 |
| T10 | Per-device lock spans fresh reads, validation, backup, all mutation steps and verification; same-device calls cannot interleave, different devices progress. Actual writes revalidate dry-run plans; external client race is acknowledged | MULTI-01, REL-03 |
| T11 | List/read preserve types and unknown fields; key 0/temporary 255 excluded, null/empty absent, unknown nonempty occupied. Lowest-free allocation rechecks chosen ID; observed conflict does not reallocate. Explicit overwrite/name byte validation; storage-only capture controls; supported activation leaves storage unchanged | PRE-01–02, PLAY-01 |
| T12 | Snapshot format/version/source/device/preset/firmware/path validation, exact unknown-field retention, atomic durable backup and safe retention. Backup failure prevents overwrite/delete; changed prior object aborts before overwrite. Restore execution is Should pending safe single-entry storage path; no apply/bulk shortcut or claimed restore acceptance from export | PRE-04 |
| T13 | Delay persistent visibility within one deadline; compare saved name plus all captured included state, not only ID/name. Delete verifies target absence and reports unrelated interference. Asynchronous capture may mismatch; uncertain save/delete/allocation is never resent; unavailable readback and readable mismatch differ | PRE-05, REL-02 |
| T14 | Real subprocess SDK handshake/list/call, no stdout diagnostics; structured envelope equals JSON text fallback, isError=!ok across success/domain error/uncertainty. Test SDK argument-shape/protocol errors separately | MCP-01–02 |
| T15 | Mocked HTTP redirect, HTML response, malformed JSON, huge response, missing capabilities and connection reset return actionable bounded errors | READ-01, REL-01, OPS-03 |
| T16 | Build a wheel and start the installed console command in a clean environment using pinned dependencies; README command matches reality | OPS-02 |
| T17 | If optional raw tool is enabled, reject endpoints, hosts, persistence keys, layout deletion/replacement and unallowlisted fields that bypass typed rules | ADV-01 |
| T18 | Actual SDK clients initialize/list/call through stateless JSON /mcp with no session ID; tool/schema/outcome parity with stdio, including failure/uncertainty. Negotiation/notification 202/GET 405 and transport errors follow selected SDK | MCP-01–02, OPS-05 |
| T19 | Concurrent HTTP clients share process inventory/client/cache/snapshots and one per-device lock through write/verify, while different devices progress. No per-request resource duplication or multi-worker coordination claim | MCP-04, MULTI-01 |
| T20 | Fail closed before listen on missing/conflicting bearer config. Missing/wrong credential gives 401; disallowed/malformed Host or supplied Origin gives 403 before device access on every method. Absent Origin authenticated client works; no wildcard/proxy bypass or secret leakage. Loopback:8000 default, alternate binding explicit, stdio listener-free | MCP-03, OPS-03 |
| T21 | Disconnect is not cancellation; continue bounded verification, release lock, never requeue. Stateless reconnect/restart does not replay; client resubmission is a new invocation. Shutdown stops admission, drains within existing deadlines, closes resources; interrupted writes remain uncertain. Both installed modes select transport explicitly | MCP-04, REL-02, OPS-05 |

CI should run on supported Python versions and a Linux environment, with lint/type checking proportional to the implementation. Protocol tests must run the actual console entry point, catching the missing-main class of issue observed in a candidate project. HTTP tests use ephemeral loopback ports and mocked WLED transport, not LAN devices. Build/dependency errors must not be hidden by mocks. T18–T21 are required alongside T01–T16; T17 remains conditional on the optional raw tool.

## Issue-2 contract traceability

C2 IDs are acceptance criteria for documentation delivery, not runtime tests.
All refer to [TOOL-CONTRACT.md](TOOL-CONTRACT.md) and the
[scoped decisions](decisions/issue-2.md). Synthetic JSON parse/consistency checks
cannot establish that an adapter implements these outcomes.

| Criterion | Concrete artifact / observable assertion | Future runtime evidence / owner |
| --- | --- | --- |
| C2-01 | Power/brightness section; [patch case](../examples/contracts/patch.json): zero/false, remembered versus effective values, preservation | T04/T06/T08; #6/#10 |
| C2-02 | Existing/new omission rules and default table; [replacement](../examples/contracts/replace.json) | T05/T08; #7/#10 |
| C2-03 | Complete range/ID/overlap validation, supported noncontiguous and rejected sparse IDs, bounded partial sequence | T05/T06/T09; #6/#7/#10 |
| C2-04 | Proven range RGB/RGBW widths and unknown capability rejection, omitted color slots | T06/T15; #5/#6/#7/#10 |
| C2-05 | One-call half-up transition conversion and bounds; [error assertions](../examples/contracts/errors.json) | T04/T06/T08; #6/#10 |
| C2-06 | Reads-only dry-run, resolved plan, no reservation or backup mutation | T07/T10/T19; #6/#7/#9/#14/#10 |
| C2-07 | Reviewed persistent ID range, reserved/empty/unknown occupancy, allocation and byte-limited names | T11; #5/#9/#10 |
| C2-08 | Storage-only current capture, persistent full-field verification, deferred supplied-state | T09/T11/T13; #9/#10/#13 |
| C2-09 | [Snapshot envelope](../examples/contracts/snapshot.json), durability/retention/failure and explicit deferred restore boundary | T12; #8/#9/#10 |
| C2-10 | Application/verification table, envelope/text/isError parity, [conflict](../examples/contracts/preset.json) and [uncertainty](../examples/contracts/errors.json) | T08–T14/T18; #3/#6/#7/#9/#10/#14 |
| C2-11 | Explicit transport, stateless SDK lifecycle, shared resources, disconnect/drain semantics | T18/T19/T21; #3/#14/#10/#11 |
| C2-12 | Direct endpoint auth, exact Host/Origin checks, 401/403, no proxy bypass | T20; #14 implementation, #10 software acceptance, #11 integration |

MCP-03/MCP-04/OPS-05 map to #14 implementation, #10 T18–T21 acceptance, and #11
integration/deployment evidence. H02/H03 remain separate authorized operational
checks. SDK version selection, mocked/runtime protocol execution and hardware
compatibility remain pending. PRE-03 and restore execution are explicitly deferred
Should work; durable backup before destructive operations remains Must.

## Read-only hardware checks

H01: Record selected device alias, firmware, LED count, RGB/RGBW/CCT and segment capabilities from real responses. Sanitize any committed fixture.

H02: Read state/catalogs/presets from the actual WLED-MCP execution context, then through MCPHub. In HTTP mode this is the independent service/container; in stdio mode it is the hub-managed process. Verify actual hub-to-service authentication/connectivity when HTTP is exercised. Compare observed IDs/names and capability interpretation with the WLED UI. No discovery scan or state write is needed.

H03: Start/restart the independent HTTP service or stdio entry as appropriate, record mode/startup/idle memory, confirm diagnostics/protocol separation and verify persistent paths. Record HTTP reconnect and liveness behavior when used. Hub/container recreation is a distinct operational check and must be recorded as pending if not performed. Evidence from one deployed mode does not claim the other was deployed; both need automated protocol coverage.

## Opt-in physical write checks

Choose an explicitly authorized device and test ranges/slots first. Record the pre-test state and relevant persistent preset snapshots. A visually animated state is not necessarily restorable frame-for-frame; preserve its configuration and note limits. Do not edit existing household presets for convenience when an agreed unused slot works.

H04: Change power/brightness/color and one effect's speed/intensity; verify state and visible behavior. Restore original configuration where supported.

H05: Patch one selected segment, confirm unrelated segments remain unchanged; replace with an agreed small layout, verify stale IDs removed, restore original layout. Account for timers, other API clients, playlists or realtime inputs if verification is affected; never disable them silently.

H06: Save to an agreed unused persistent preset ID, activate, read back, test explicit overwrite with snapshot, then delete the test slot. Test explicit restoration of its saved contents if authorized. Confirm persistent data, not just the current live effect.

H07: Observe an offline/unreachable device using an already unavailable target or approved test method; do not unplug production devices or change networking merely to create a failure. Simulated transport tests can remain the evidence for otherwise disruptive scenarios.

## Evidence template

```text
Date / operator / source commit:
Package / Python / SDK / hub runtime:
Transport mode / endpoint or uvx artifact / service lifecycle:
Sanitized device and firmware / relevant capabilities:
Scenario IDs run:
Before state and snapshot references (local, no secrets):
Expected and observed results:
Restoration performed and verified:
Not run / reason / remaining risk:
```

## Release decision

All Must requirements need evidence. Mock implementation can be merged while hardware checks are pending if clearly labeled. “Production validated”, “all firmware supported”, “rollback tested” and “container-recreation persistent” require their own actual observations. Keep the integration issue open until its stated checks are met or explicitly revise the scope with a documented user decision.
