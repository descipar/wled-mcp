# Validation and acceptance plan

Issue #5 (read-only state/catalog tools) is validated with mocks only; see [its evidence](#issue-5-implementation-evidence). Current runtime result: **issue #3 bootstrap checks pass locally on Windows/Python 3.13.2**. T14/T16 bootstrap evidence includes 24 tests, SDK subprocess current/legacy negotiation, fixture schema/result/error/uncertainty parity, stdout framing/EOF, configuration, wheel build, clean install and uvx with 30 exact runtime versions verified in each environment. Ruff, strict mypy, lock/export and static agent-setup checks pass. Linux CI is configured; verify its remote result separately. These tests do not implement device writes. HTTP T18–T21 software evidence is recorded in [the issue #14 section](#issue-14-implementation-evidence); hardware H checks remain pending.

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

## Issue #8 implementation evidence

Mock/tmp_path only; no LAN, device or hardware access (H06 stays pending and
separately authorized). Tests in `tests/test_backups.py` (executed claims are
recorded in the PR, not here):

| Criteria | Test coverage |
| --- | --- |
| T12 format/validation | round trip with unknown-field preservation, contract example, invalid envelope table, malformed bytes, size/duplicate-key/NaN, path/device ID safety, symlinks, destination mismatch |
| T12 atomic durable write | single final file, fsync/publish ordering, injected fsync/link/mkdir/write/read-only faults, post-write validation, ID collision, leftover temp |
| T12 retention | newest-N, tie-break, per-device isolation, prune only after durable snapshot, never deleting invalid/temp/foreign/symlink files, warning-only prune failure, config wiring |
| T12/T11/T13 hook contract | synthetic destructive operation: backup failure gives zero POSTs, snapshot on disk before the POST, changed prior object gives zero POSTs, timeout keeps snapshot without resend |
| T07, T10, OPS-03 | dry-run plan without filesystem change, same-device serialization, log content, file modes, Git ignore guard |
| Restore deferral | read-only plan helper, exact device/firmware, occupied destination rules, no restore tool registered |

Restoration execution and real preset tools remain pending (#9, #13/#18).

## Issue #9 implementation evidence

Mock/tmp_path only; no LAN, device or hardware access. H06 is not run and stays
separately authorized and pending; nothing here is hardware acceptance. Tests in
`tests/test_presets.py` with the stateful fake `tests/preset_support.py` (which models
only the facts in SOURCES.md "Issue-9 preset evidence"); executed results are
recorded in the PR, not here. PRE-03 stays deferred to #13 and is not covered.

| Criteria | Test coverage |
| --- | --- |
| T11 list/read | types and unknown-field/order preservation, reserved/temporary/null/`{}` handling, malformed keys and non-object entries, fresh uncached GET per call, failure mapping without leaks |
| T11 activation | state and playlist activation send only `{"ps": id}` and leave storage identical; api-command/unknown/control-key/unsafe-playlist entries refused with zero POSTs; deferred application polled; unobservable acceptance is a mismatch; already-active warning |
| T11 allocation/save | lowest free ID with gaps, explicit free ID, occupied needs `overwrite=true`, exhausted ID space, malformed store fails closed, name validation (blank, control, 32 vs 33 bytes, multi-byte), no `state` input, storage-controls-only wire payload, collision recheck without reallocation, playlist replacement rejected, dry run read-only |
| T12 | snapshot of the exact object on disk before the POST (overwrite and delete, every object entry type), backup failure gives zero POSTs, changed prior object conflicts and keeps the snapshot, free explicit ID takes no snapshot, non-object entry rejected, dry run creates no files |
| T13/REL-02 | delayed persistence within the deadline, acknowledged-but-never-persisted save/delete is a mismatch, field-level capture differences, inactive-slot markers, interference warning, timed-out POST reconciled with warning, failed POST plus unchanged store or unreadable readback is unknown, exactly one POST in every case, a later call is a new invocation, same-device serialization with distinct IDs, other device progresses |
| Evidence examples | `examples/contracts/presets.json` and the `backup_failure` case are actual tool output, reproduced by tests |

C2-07 (ID range, occupancy, allocation, names) and C2-09 (backup before destructive
writes) have mock evidence; C2-08 (persistent full-field verification) has mock
evidence for save-current, deferred supplied-state stays with #13. Real flash-write
timing, post-delete file layout, whether saving moves the active-preset marker, and
real playlist behavior are not established by mocks.

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

## Issue #4 implementation evidence

2026-11-04, Windows/Python 3.13.2, MCP SDK 2.3.0, HTTPX2 2.16.0: 80 tests passed,
including the 24 inherited bootstrap checks. Ruff, strict mypy (10 source/script
files), lock/export consistency and static agent setup passed. Offline wheel,
noneditable clean installation and uvx checks passed with 30 exact active runtime
versions verified; installed stdio lists/calls the inventory tool. No LAN/device
requests were made. Independent review and remote CI are recorded per candidate.

| Criteria | Executed evidence |
| --- | --- |
| C4-01/02, T01/T02 | strict config/URL/settings and duplicate rejection, immutable inventory, zero-HTTP default list, real stdio schemas/result parity |
| C4-03/04/05, T02/T15 | independent probes, bounded eight-worker fan-out, fixed endpoints, redirect/proxy policy, actual stream limit/closure, malformed/HTML/UTF-8/compressed/NaN responses |
| C4-06/07, T09 | one read deadline/retry, write timeout/reset/slow dispatch with reserved readback, match/mismatch/unavailable, one POST, invalid/oversize/expired preparation sends nothing |
| C4-08/09, T10/logical T19 | event-synchronized same-device lock through readback, independent device progress, cancellation release, lock wait deadline, shared client/cache/backup/lock identity and one close |
| C4-10, T14/T16 regressions | safe secret-marker errors, stdout framing, schema/error parity, locked wheel/clean-install/uvx version checks |

Internal mocked writes do not establish firmware/domain-control acceptance.
Logical session closures do not establish running HTTP T18–T21 acceptance. Full
state/catalog tools, protected HTTP, snapshots, deployment and hardware remain
pending. Hardware results are not inferred from mocks or package checks.

## Issue #5 implementation evidence

Candidate under review (mock transport only; no LAN/device access; H01/H02 remain
pending). 2026-11-04, Windows/Python 3.13.2, MCP SDK 2.3.0, HTTPX2 2.16.0. Commands
run from the repository root with `UV_CACHE_DIR=.uv-cache`, `UV_PYTHON_DOWNLOADS=never`:

| Command | Result |
| --- | --- |
| `uv sync --locked` | up to date (43 packages) |
| `uv run --frozen ruff check src tests scripts/check_lock.py scripts/check_distribution.py` | All checks passed |
| `uv run --frozen ruff format --check src tests scripts/check_lock.py scripts/check_distribution.py` | 23 files already formatted |
| `uv run --frozen mypy` | Success: no issues found in 12 source files (strict) |
| `uv run --frozen python scripts/check_agent_setup.py` | valid; `python scripts/sync_agents.py --check`: synchronized |
| `uv run --frozen python scripts/check_lock.py` | Lock/export consistency: PASS |
| `uv run --frozen pytest` | 194 passed (three consecutive full runs; 100 of them new in `tests/test_state_catalogs.py`, including the stdio subprocess test) |
| `uv run --frozen python scripts/check_distribution.py` | Wheel/clean install/uvx: PASS; 30 exact runtime versions verified, four tools listed |

Known flake: the pre-existing #4 test `test_one_total_deadline_and_bounded_read_retry`
(`tests/test_inventory_client.py`) is wall-clock sensitive (40 ms sleep inside a 50 ms
deadline). It failed intermittently on this Windows host, also on the unmodified base
(three of three stashed runs), and passed in the final runs above. It was not changed.

| Criterion | Executed evidence (all in `tests/test_state_catalogs.py` unless noted) |
| --- | --- |
| C5-01, T02/T03 | full-fixture state: normalized fields, raw state/info retained, firmware facts, capabilities null (not false) with `unknown_capabilities`; examples `state.json`/`catalogs.json` validate as envelopes |
| C5-02 | noncontiguous segment IDs 0/2/5 addressed by `id`; off master with nonzero `bri` gives effective 0; segment `on=false` keeps `bri`; zero white trimmed only with per-segment RGB-only proof, nonzero/white-capable/unknown/mismatched evidence not trimmed, raw kept |
| C5-03 | IDs equal array indexes with gaps, `RSVD` placeholders, numeric/Unicode/duplicate/case-variant names and an empty list; count mismatch warns |
| C5-04 | resolver: exact, trimmed case-folded, ambiguity with bounded candidates (10 of 40), blank/unknown/placeholder never matched |
| C5-05 | fxdata 404/HTML/reset/timeout/non-string/object/oversize/length mismatch give `ok=true`, intact names, `metadata=unavailable`, one warning; success attaches by index; fxdata never creates names; hanging fxdata respects the deadline |
| C5-06 | miss/hit (one info read, no catalog request), age/source, expiry at exactly TTL, `refresh`, failed refresh keeps the entry, no stale fallback, `ver`/`vid` change, TTL 0, per device and kind isolation, concurrent misses, shared cache identity (`tests/test_resource_boundaries.py`) |
| C5-07 | two consecutive state reads see changed mock data; request counts assert no state/info caching |
| C5-08/T15 | redirect, HTML, malformed JSON, oversize, gzip, NaN, wrong shape, reset, timeout, HTTP 500 on every read endpoint: stable codes, no body/URL/`synthetic-secret`, message carries resource label and numeric status |
| C5-09/T02 | reset/timeout/503 device fails while another succeeds (concurrently); no request to unselected devices; unknown ID makes no HTTP |
| C5-10/T14 | real stdio subprocess (`tests/state_fixture.py`): four tools, `additionalProperties=false`, annotations, envelope equals JSON text, `isError == !ok` for success/domain failure, integer `refresh` and unknown field rejected |

Remaining limits: the firmware facts used (placeholder serialization, `leds.lc`/`seglc`,
fxdata layout) come from reading the pinned source ([SOURCES.md](SOURCES.md#issue-5-statecatalog-evidence)),
not from a controller; H01/H02 (real device facts, comparison with the WLED UI and
MCPHub) are not performed. OPS-04 is only partially covered (server version, unknown
capabilities, safe errors). No issue acceptance box that needs hardware evidence is claimed from mocks.

## Issue #6 implementation evidence

Candidate under review (mock transport only; no LAN/device access; H04/H05 remain
pending). 2026-11-04, Windows/Python 3.13.2, MCP SDK 2.3.0, HTTPX2 2.16.0. Commands
run from the repository root with `UV_CACHE_DIR=.uv-cache`, `UV_PYTHON_DOWNLOADS=never`:

| Command | Result |
| --- | --- |
| `uv sync --locked` | up to date (44 packages) |
| `uv run --frozen ruff check src tests scripts/check_lock.py scripts/check_distribution.py` | All checks passed |
| `uv run --frozen ruff format --check src tests scripts/check_lock.py scripts/check_distribution.py` | 26 files already formatted |
| `uv run --frozen mypy` | Success: no issues found in 13 source files (strict) |
| `uv run --frozen python scripts/check_agent_setup.py` | valid; `python scripts/sync_agents.py --check`: synchronized |
| `uv run --frozen python scripts/check_lock.py` | Lock/export consistency: PASS |
| `uv run --frozen pytest` | 219 passed with the pre-existing wall-clock-sensitive `test_one_total_deadline_and_bounded_read_retry` deselected; 26 new tests in `tests/test_patches.py` |

Known flake (unchanged by #6): `test_one_total_deadline_and_bounded_read_retry`
in `tests/test_inventory_client.py` remains wall-clock sensitive on this Windows
host, as documented under issue #5's evidence.

| Criterion | Executed evidence (all in `tests/test_patches.py` unless noted) |
| --- | --- |
| C2-01, T04 | master patch rules: off-master + positive brightness payload excludes `on` (superseded by #52: the payload now carries the compensating `on=false`, see [Issue #52 implementation evidence](#issue-52-implementation-evidence)); explicit `on=False` sends only `{on:false}`; reject `on=true, brightness=0` and `brightness=0` with resolved `on=true`; turning on requires an explicit positive brightness when remembered is zero; persistent `transition` is never in the payload |
| C2-05, T04 | `transition_ms` -> `tt` conversion verified for `0`, `50`, `149`, `150`, `65500` (0/1/1/2/655); 1-49 rejected; transition-only request rejected before POST; `transition_ms` out of range caught by request schema |
| C2-03/04, T06 | RGB-only with 4 channels or RGBW with 3 channels -> `VALIDATION_ERROR`; unknown per-segment capability for a color change -> `UNSUPPORTED_CAPABILITY`; unknown patch target -> `VALIDATION_ERROR`; patch without a mutable field -> `VALIDATION_ERROR`; range change requires both `start`/`stop`; range change introducing overlap with an untouched active segment -> `VALIDATION_ERROR`; `effect_id` beyond catalog range -> `VALIDATION_ERROR`; unknown device -> `UNKNOWN_DEVICE` with zero HTTP |
| C2-06, T07 | dry-run plan lists exact update IDs, empty create/remove IDs and all preserved IDs; payload shows only the sent fields; zero POSTs; actual invocation under the per-device lock revalidates and rejects a plan invalidated by a live state change |
| C2-10, T08/T09 | ACK alone with mismatching readback -> `application=unknown, verification=mismatch, ok=false, VERIFICATION_MISMATCH`; normalized off with remembered brightness unchanged is accepted; dispatched POST timeout + unavailable readback -> `WRITE_OUTCOME_UNKNOWN`, exactly one POST, never replayed |
| MULTI-01, T10 | two concurrent patches on the same device serialize through the per-device lock while a patch on a different device progresses in parallel; both complete with one POST each |

Remaining limits: hardware acceptance (H04/H05) is not authorized in this round
and not run; mock-only POST handlers model profile 0 behavior per the pinned
source (`docs/SOURCES.md#issue-2-contract-evidence`) and `ISSUE-6-DEC-002`. No
issue acceptance box that requires hardware evidence is claimed from mocks.

## Issue #7 implementation evidence

Candidate under review (mock transport and a stateful fake WLED only; no LAN/device
access; **H05 not run**). 2026-11-05, macOS/Python 3.13, MCP SDK 2.3.0. Commands run from
the repository root with `UV_CACHE_DIR=.uv-cache`, `UV_PYTHON_DOWNLOADS=never`:

| Command | Result |
| --- | --- |
| `uv sync --locked` | up to date |
| `uv run --frozen ruff check src tests scripts/check_lock.py scripts/check_distribution.py` | All checks passed |
| `uv run --frozen ruff format --check src tests scripts/check_lock.py scripts/check_distribution.py` | 34 files already formatted |
| `uv run --frozen mypy` | Success: no issues found in 16 source files (strict) |
| `uv run --frozen python scripts/check_agent_setup.py`; `python3 scripts/sync_agents.py --check` | valid; adapters synchronized |
| `uv run --frozen python scripts/check_lock.py` | Lock/export consistency: PASS |
| `uv run --frozen pytest` | 316 passed (70 in the new `tests/test_layouts.py`) |
| `uv run --frozen python scripts/check_distribution.py` | wheel/clean install/stdio/HTTP/uvx: PASS (tool list and count updated to seven, a necessary one-line edit outside the work packet's path list) |

| Criterion | Executed evidence (`tests/test_layouts.py`, fake in `tests/layout_support.py`) |
| --- | --- |
| C2-02, T05 (SEG-02) | fixture case sends exactly `mainseg:2`, remove 0, remove 5, update 2 (name resent), create 6 with all defaults and `frz:false`; final active IDs exactly {2,6}, preserved fields of ID 2; removal POST count equals `|old - desired|` for 1, 3, 9 and 20 noncontiguous stale IDs (no array payload, no filler, no purge); gap reuse and chained ascending creates; sparse chain and ID 8 rejected before any POST with the fixture message; blocked move waits for the segment in its way, no intermediate overlap after any POST; range swap cycle rejected; main handled for kept, stale (redirect first), all-new (redirect last, warning) and inactive main; no master keys in any payload |
| C2-03/04, T06 (SEG-03, SEG-05) | 18 parametrized invalid requests plus RGBW, capability-evidence, missing `led_count`/`maxseg`, offset clamp, unrepresentable name and schema cases, each with zero POSTs and the expected code; late invalid entry leaves the device untouched; name at 32 characters accepted (also multibyte; dry run sends nothing and does not warn), 33 rejected by the schema, 32 two-byte characters -> `VERIFICATION_MISMATCH` (fake with a configurable 32-byte name buffer), new ID with grouping 256 -> `applied/mismatch` with the earlier removals completed, grouping/spacing without a 255 cap (aligned with #6); unknown device zero HTTP |
| C2-06, T07 (SEG-04) | dry run: zero POSTs, no file created, plan keys/values; live POSTs equal the dry-run `step_payloads`; live call re-plans after a state change; unchanged request is an `ok` no-op with zero POSTs |
| C2-10, T08 (MCP-02) | ACK with unchanged state -> `unknown/mismatch`; ignored `rev` -> mismatch with `observed`; normalized off accepted; `brightness` alone on an off segment -> firmware power flip reported as mismatch, explicit `on=false` stays off; envelope JSON round-trip; annotations `destructive_hint=true` and `additionalProperties:false`; `examples/contracts/replace.json` and the `errors.json` partial case equal the actual output |
| T09 (REL-01/02) | POST failure plus unreadable state at each step 0-4 -> `unknown/unknown` + `WRITE_OUTCOME_UNKNOWN`, exactly k+1 POSTs, later steps `not_dispatched`; failed POST with differing/matching readback; matching last step succeeds; external interference after a step and extra segment at the end -> mismatch with no corrective POST; deterministic budget exhaustion (shifted `anyio.current_time`, no sleep) stops after two verified steps with exactly two POSTs, `applied/mismatch` + `TIMEOUT`; a final-check mismatch with all five steps verified; a repeated call is a new invocation |
| T10 (MULTI-01, REL-03) | two concurrent replacements on one device are fully serialized (second read after the first's last POST and readback); a second device progresses while the first is blocked in a POST |

Remaining limits: all firmware behavior is source-derived from pinned v0.15.1
([SOURCES.md](SOURCES.md#issue-7-layout-evidence)) and modeled by the fake; hardware check
H05 is opt-in, later and not authorized in this round, so no hardware acceptance box is
claimed. Before H05 capture `wled_get_state` output; restoring uses another
`wled_replace_layout` (recreated IDs need explicit colors; unexposed state of reused slots
cannot be restored). No stdio/HTTP result-parity case was added beyond the
shared tool-list tests. ISSUE-7-OPEN-001 is resolved by the human decision
[ISSUE-7-DEC-006](decisions/issue-7.md) (alignment with #6): the 32-character name,
no 255 bounds and `bri` without an extra `on` are known limits shared with #6 (silent
firmware name truncation, `uint8_t` wrap, an off segment switched on by `bri > 0`,
reported as `VERIFICATION_MISMATCH`). The agent technical baselines
[ISSUE-7-DEC-003 to -005](decisions/issue-7.md) are accepted by delegated decision
(issue #7 only; decided by the main session under the human's delegation, not personally
dictated by the human). The narrow `brightness=0` reading (DEC-007) and the follow-up
issue #48 for the shared #6/#7 limits are recorded the same way. The name, 255-bound and
`bri` points above (and the tests that pinned them) are superseded by issue #48; see the
next section.

## Issue #48 implementation evidence

Shared #6/#7 segment limits per the human decision
[ISSUE-48-DEC-001](decisions/issue-48.md) (option B, 32 UTF-8 bytes, `brightness=0`
without `on=false` on an on segment rejected). Candidate under review; mock transport and
the stateful fake WLED only (`tests/layout_support.py`, 32-byte name buffer, `uint8_t`
grp/spc, bri/on coupling); no LAN/device access; **H04/H05 not run** (#12). 2026-11-05,
Windows 11/Python 3.13.2, MCP SDK 2.3.0, commands from the repository root:

| Command | Result |
| --- | --- |
| `uv run --frozen ruff check src tests scripts/check_lock.py scripts/check_distribution.py` | All checks passed |
| `uv run --frozen ruff format --check src tests scripts/check_lock.py scripts/check_distribution.py` | 41 files already formatted |
| `uv run --frozen mypy` | Success: no issues found in 19 source files |
| `uv run --frozen python scripts/check_agent_setup.py` | valid (static) |
| `uv run --frozen python scripts/check_lock.py` | Lock/export consistency: PASS |
| `uv run --frozen pytest` | 540 passed, 9 skipped, 1 failed: `test_http_cli.py::test_stdio_ignores_ambient_http_token_and_binds_nothing` (audit hook sees `socket.bind`/`socket.connect` on Windows); it fails identically on the unchanged base commit and is unrelated to #48 |
| `uv run --frozen python scripts/check_distribution.py` | Wheel/clean install/stdio/HTTP/uvx: PASS; 30 exact runtime versions verified |

| Criterion | Executed evidence (#6 in `tests/test_patches.py`, #7 in `tests/test_layouts.py`) |
| --- | --- |
| AC-48-01 | `test_48_name_of_exactly_32_utf8_bytes_is_accepted_and_verified`, `test_T06_name_of_exactly_32_utf8_bytes_is_accepted_and_verified` (32 ASCII, 16 two-byte characters; `applied/verified`, stored name equal) |
| AC-48-02/03/05/06, AC-48-11 | `test_48_rejections_before_any_post`, `test_T06_issue48_rejections_before_any_post` (33 bytes, 17 two-byte characters, U+0000, `on=true`+`brightness=0`, `brightness=0` on an on segment; dry run and live: `VALIDATION_ERROR`, `not_attempted/not_requested`, message names segment and byte limit, zero POSTs); `..._brightness_zero_with_on_false_or_on_off_segment_is_accepted` in both files |
| AC-48-04 | `test_48_grouping_and_spacing_255_are_accepted_and_verified` (#6; 256 schema-rejected), `test_T06_grouping_and_spacing_255_are_accepted_and_verified`, 256 cases in `test_T06_schema_rejections`, `test_T06_limits_are_shared_with_patch_segments` (both JSON input schemas advertise `maximum: 255`) |
| AC-48-07, AC-48-11 | `test_48_positive_brightness_on_off_segment_is_compensated` (payload `{"id":0,"on":false,"bri":50}` in dry run and live, `targeted_compensation` entry, segment stays off with bri 50, `applied/verified`), `test_T05_positive_brightness_on_off_segment_is_compensated_with_on_false` (dry-run `step_payloads` equal live POSTs) |
| AC-48-08 | `..._positive_brightness_on_on_segment_is_sent_alone_and_stays_on` in both files (`bri` sent alone, segment stays on, verified) |
| AC-48-09 | `test_48_power_flip_after_brightness_is_a_mismatch_not_silent_success` (device drops `on`, segment flips on -> `VERIFICATION_MISMATCH`), `test_48_power_flip_on_on_segment_is_also_verified`, `test_T05_power_flip_by_external_change_is_still_a_mismatch` |
| AC-48-10 | `test_T06_invalid_later_segment_keeps_every_stale_segment` (stale IDs 0 and 5 plus each invalid case in a desired segment: zero POSTs, layout unchanged); grouping/spacing 256 never reaches a plan because the schema rejects it |
| Parity | `test_48_patch_and_replace_apply_the_same_rules` (11 edge cases through both tools: same code, same power compensation, same resolved `on`); both planners call `src/wled_mcp/segment_rules.py` |
| AC-48-12 | [TOOL-CONTRACT.md](TOOL-CONTRACT.md#shared-segment-limits-wled_patch_segments-and-wled_replace_layout) shared rule set, #7 exceptions removed; [SOURCES.md](SOURCES.md#issue-7-layout-evidence) grp/spc and name wording; existing suites pass |

The new tests were also run against the unchanged base commit, where they fail (old
behavior: names and 256 accepted, no compensation, no `on` verification in #6, removals
before a mismatch in #7). Remaining limits: firmware behavior is source-derived (pinned
v0.15.1) and modeled by the fake; the real per-build name buffer, the exact overflow
behavior of `grp`/`spc` above 255 and a possible visible transition when `{bri, on:false}`
is sent to an off segment are unverified and stay with #12. Master `wled_set_state`
behavior is unchanged (a positive `bri` can still switch an off master on); that is
outside #48.

## Issue #52 implementation evidence

Master power preservation in `wled_set_state` per the delegated decision
[ISSUE-52-DEC-001](decisions/issue-52.md): a positive `brightness` with omitted `on` on an
off master is sent with the resolved `on=false` and every master write verifies the
resolved `on`. Candidate under review; mock transport and the stateful fake WLED only
(`tests/layout_support.py` now also models the master `on = root["on"] | (bri > 0)`,
`toggleOnOff` and the `on = bri > 0` / `bri = briLast` readback); no LAN/device access;
**H04/H05 not run** (#12). 2026-11-05, Windows 11/Python 3.13.2, commands from the
repository root:

| Command | Result |
| --- | --- |
| `uv run --frozen ruff check src tests scripts/check_lock.py scripts/check_distribution.py` | All checks passed |
| `uv run --frozen ruff format --check src tests scripts/check_lock.py scripts/check_distribution.py` | 41 files already formatted |
| `uv run --frozen mypy` | Success: no issues found in 19 source files |
| `python scripts/check_agent_setup.py` / `python scripts/sync_agents.py --check` | valid (static) / adapters synchronized |
| `uv run --frozen python scripts/check_lock.py` | Lock/export consistency: PASS |
| `uv run --frozen pytest` | Final run: 563 passed, 9 skipped, 1 failed: `test_http_cli.py::test_stdio_ignores_ambient_http_token_and_binds_nothing` (fails identically on an export of the unchanged base commit; tracked by #53). An earlier run also hit the known wall-clock flake `test_one_total_deadline_and_bounded_read_retry` (passed in 2 of 3 isolated reruns). `tests/test_patches.py` and `tests/test_layouts.py`: 168 passed |

| Criterion | Executed evidence (all in `tests/test_patches.py`) |
| --- | --- |
| AC-52-01 | `test_52_off_master_positive_brightness_dry_run_is_compensated` (payload `{"on": false, "bri": 120}`, `targeted_compensation == [{"on": false}]`, `plan.on` null, `plan.resolved` `{on: false, brightness: 120}`, postcondition, zero POSTs); the former #6 assertion in `test_T04_master_set_state_power_and_brightness_rules` now expects the same payload |
| AC-52-02 | `test_52_off_master_positive_brightness_live_stays_off_and_verifies` (one POST, readback `on=false`/`bri=120`, `applied/verified`, live plan equals dry-run plan, segment power unchanged) |
| AC-52-03 | `test_52_on_master_positive_brightness_is_sent_alone_and_stays_on` |
| AC-52-04 | `test_52_dropped_compensation_power_flip_is_a_mismatch` (device drops `on`, master flips on: `VERIFICATION_MISMATCH`, `unknown/mismatch`, exactly one POST) |
| AC-52-05 | `test_52_on_master_that_ends_off_after_bri_is_a_mismatch` |
| AC-52-06 | `test_52_compensation_keeps_one_call_transition` (`{"on": false, "bri": 120, "tt": 2}`, 150/200/2, persistent `transition` untouched) |
| AC-52-07 | `test_52_existing_master_rejections_before_any_post` (3 cases x dry/live: `VALIDATION_ERROR`, `not_attempted/not_requested`, zero POSTs) |
| AC-52-08 | `test_52_off_master_brightness_zero_is_accepted_without_compensation` |
| AC-52-09 | `test_52_explicit_on_with_brightness_is_not_compensation` (4 power combinations; a dropped explicit `on=false` is a mismatch) |
| AC-52-10 | `test_52_master_without_boolean_on_is_invalid_response` (missing/string/int `on` x dry/live: `INVALID_RESPONSE`, zero POSTs) |
| AC-52-11 | [TOOL-CONTRACT.md](TOOL-CONTRACT.md#master-power-rules-wled_set_state) master rule table; [SOURCES.md](SOURCES.md) power row; #6 row above marked superseded; decision recorded in [issue-52.md](decisions/issue-52.md) |
| AC-52-12 | command table above; #48 segment tests and `tests/test_layouts.py` pass unchanged |

The new tests were also run against the unchanged base `src/wled_mcp/patches.py` (new tests
and fake kept): 12 failed (AC-52-01/02/04/05/06 on behavior; AC-52-03/08/09 on the missing
`targeted_compensation` field; the updated #6 assertion), while the AC-52-07/10 regression
guards passed as expected. Remaining limits: the firmware behavior is source-derived
(pinned v0.15.1) and modeled by the fake; a visible blip or transition effect when
`{on: false, bri: X}` reaches an off master, `tt` consumption and a `ps` change on real
devices are unverified and stay with #12. An external power change between the fresh read
and the POST remains a documented residual risk.

## Issue #14 implementation evidence

2026-11-05, macOS/Python 3.13, MCP SDK 2.3.0, starlette 1.10.0, uvicorn 0.54.0: 246 tests passed
(27 new HTTP tests, one superseded refusal test removed); the new HTTP tests passed in three
consecutive runs. Ruff, strict mypy, lock/export consistency, agent setup/sync checks, offline
wheel build and the distribution check (clean install, stdio and installed-console HTTP
smoke, uvx; 29 exact runtime versions on this platform) passed. All tests use mocks,
a synthetic loopback fake device and `127.0.0.1` ephemeral ports; no LAN device was
contacted. This is software evidence only: no deployment, hub integration, resource
measurement or hardware check was performed, and Linux CI plus independent review are
recorded per candidate.

| Packet ID / scenario | Executed evidence |
| --- | --- |
| C14-01, T18 | `test_sdk_client_initialize_list_call_over_http` (legacy, auto, 2026-07-28 SDK clients: list, mocked reads, one verified write); `test_stateless_json_transport_behavior` (no session ID, 202 notification, GET/DELETE 405, stale ID served, 400/413 transport errors execute no tool); `test_console_serves_http_and_shuts_down_cleanly` (real console, env and file credential) |
| C14-02, T18/T14 | `test_http_results_match_in_process_server` (identical envelopes, text, isError, MCP errors and device traffic for success, schema/range/domain validation, unknown device, read failure, mismatch, uncertain write, crash, unknown tool; both protocol eras); `test_http_and_stdio_expose_identical_tool_descriptors` (real consoles) |
| C14-03, T19 | `test_two_http_clients_share_device_lock_while_other_device_progresses` (second writer and a read wait for the same lock, other device progresses, strict per-device request order, one resource graph, one close); `test_clients_share_one_catalog_cache` |
| C14-04/05, T20 | `test_access_matrix_rejects_before_any_tool_or_device_work` (60 header/method/path cases, zero tool executions and device requests, no secret or header-value leakage in responses or logs); `test_duplicate_and_missing_host_are_rejected_on_the_wire`; `test_http_startup_fails_closed_in_process` (48 startup failures: credential, bind, allowlist, flags) and `test_real_console_refuses_to_start_and_never_listens` |
| C14-06/07, T21 | `test_disconnect_after_dispatch_does_not_cancel_or_replay` (both protocol eras); `test_reconnect_is_a_new_invocation`; `test_graceful_shutdown_drains_in_flight_write`; `test_forced_shutdown_leaves_write_uncertain_without_replay` (restart contacts no device); `test_signal_drains_in_flight_write_and_exits_zero` (SIGTERM, SIGINT; skipped on Windows) |
| C14-08/09, T20/T16 | `test_stdio_ignores_ambient_http_token_and_binds_nothing` (real default-stdio `cli.main` subprocess with an ambient HTTP token and the `tests/stdio_socket_probe.py` guard: audit hook on bind/connect/sendto/sendmsg/getaddrinfo plus a `socket.socket.listen` wrapper and, where `asyncio.windows_events.IocpProactor` exists, wrappers on its `connect`/`sendto`; only `socket._fallback_socketpair` may bind loopback port 0, listen and connect to loopback; zero violations, exit 0, empty stdout, HTTP module unloaded); `test_stdio_socket_guard_detects_violation` (9 negative controls: loopback listener, unbound `listen()`, wildcard bind, asyncio `create_server`, foreign loopback connect, UDP sendto, and on the event loop `asyncio.open_connection`, a UDP `create_datagram_endpoint(remote_addr=...)` and a datagram-transport `sendto`, all to 127.0.0.1:9; each asserts that the injected code received the guard's own `PermissionError` and, for plain sockets, that no local port was assigned, so the refusal happens before the OS call); existing stdio tests unchanged; `scripts/check_distribution.py` installed-console HTTP smoke |
| C14-10/11 | [DEPLOYMENT.md](DEPLOYMENT.md), [TOOL-CONTRACT.md](TOOL-CONTRACT.md#transport-access-and-lifecycle), [decisions](decisions/issue-14.md) |

Pending and not claimed: H02/H03 and hub integration (#11), the resource measurements
listed in DEPLOYMENT.md, Windows signal delivery (covered only by the in-process
shutdown tests), TLS, rate limiting, per-user authorization and multi-worker
coordination. Session expiry is vacuous under stateless JSON and is evidenced by the
stale-ID and no-session tests.

## Issue #53 stdio socket-guard note

Cause (Windows 11, CPython 3.13.2): the previous listener-free stdio check failed with
`socket.bind`/`socket.connect` audit events. Both come from
`cli.main -> anyio.run -> asyncio.Runner -> ProactorEventLoop.__init__ ->
_make_self_pipe -> socket.socketpair` (= `socket._fallback_socketpair`): a bind to
`('127.0.0.1', 0)`, a `listen()` and a connect to that ephemeral loopback port, all
closed inside the function. Nothing came from `wled_mcp` or the MCP SDK. Linux uses the
native AF_UNIX `socketpair` and emits none of these events. CPython emits no
`socket.listen` audit event, so the old filter could not see any `listen()`, including
an unbound one. Per [ISSUE-53-DEC-001](decisions/issue-53.md) the test, not the product,
was changed; no platform skip or `xfail` is used.

Windows result: the positive run records exactly the three allowed self-pipe operations
and no violation (the Proactor wrappers see no call from the self-pipe); every negative
control records a violation of its expected kind and is refused before the OS call.
Without the socketpair allowlist the same start reports a violation and exits 1. Without
the Proactor wrappers the three event-loop outbound controls are not detected on
Windows. Linux CI is the second platform result (no allowed events expected there; the
event-loop controls run on the selector loop, which calls `socket.connect`/`sendto`
directly and is covered by the audit events).

Visibility on Windows: on the Proactor loop, outbound TCP connects (`ConnectEx`), UDP
connects (`WSAConnect`) and datagram sends (`WSASendTo`) bypass the socket audit events;
the guard sees them through the wrapped `IocpProactor.connect`/`sendto`. Binds, `listen()`
and name resolution still go through `socket.socket`/`getaddrinfo` and are seen as on
Linux. Proactor `accept`, `send`/`recv`, `recvfrom` and `sendfile` are not wrapped: they
need a socket that is already listening, connected or bound, which the guard refuses
earlier (an unbound UDP `recvfrom` assigns no port).

Residual limits: code that calls `_socket.socket` methods or `_overlapped` directly
bypasses the wrappers (asyncio, anyio and uvicorn use `socket.socket` and
`IocpProactor`); a product call to `socket.socketpair()` on Windows would be allowed, and
it only creates the same transient loopback pair; Windows named pipes
(`loop.start_serving_pipe`, `IocpProactor.connect_pipe`) are not sockets and are not
guarded on either platform; macOS and Python versions other than 3.13 are not checked.

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
