# Validation and acceptance plan

Evidence added from stage 2 on lives in per-issue files under
`docs/validation/`, linked from the
[list at the end](#stage-2-and-later-files) of this document; see
[where new documentation goes](AGENT-WORKFLOW.md#where-new-documentation-goes).

Requirement-to-evidence mapping: [TRACEABILITY.md](TRACEABILITY.md) links every Must requirement and T01–T21 to the automated tests and scripts that exercise them and keeps hardware/deployment evidence visibly pending; `scripts/check_traceability.py` enforces it in ordinary CI. The per-issue evidence sections below are historical per-candidate records: they state the results recorded for that candidate at that time and are not re-executed. Where they mention the wall-clock flake of `test_one_total_deadline_and_bounded_read_retry`, it is superseded by the controlled-time test from #55; the failing `test_stdio_ignores_ambient_http_token_and_binds_nothing` noted for #48/#52 is superseded by the socket guard from #53. Current results for the issue #10 candidate are in [its section](#issue-10-acceptance-evidence); deployment-artifact evidence for #11 is in [its section](#issue-11-deployment-artifact-evidence). Hardware acceptance for #12 is partly recorded for one controller and one firmware in [its section](#issue-12-hardware-acceptance-2026-11-06), without a compatibility claim beyond them; a [second run](#issue-12-hardware-acceptance-run-2-2026-11-06) added both modes, the #66 hardware re-check, visual checks and the remaining drain/load items, and a [third run](#issue-12-hardware-acceptance-run-3-2026-11-06) added the owner-watched effect, speed and brightness-transition checks and records the resolution of the remaining #12 items. Live H07 moved to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)) per ISSUE-12-DEC-007 item 6; the simulated T02/T09 evidence remains. The other items in the runs' "Not run" lists remain pending.

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
| T12 | Snapshot format/version/source/device/preset/firmware/path validation, exact unknown-field retention, atomic durable backup and safe retention. Backup failure prevents overwrite/delete; changed prior object aborts before overwrite. Restore execution (Should) uses one verified single-entry write with a documented live effect (#18, [validation/issue-18.md](validation/issue-18.md)); no bulk shortcut or claimed restore acceptance from export | PRE-04 |
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

## Known limitations

State of the evidence and the limits of the source releases (see also the
[README](../README.md#limitations) and the [compatibility matrix](contract/compatibility.md)).

- Automated tests use mocked or synthetic loopback devices and run in CI without hardware.
  Hardware acceptance is partial: it was recorded for one RGB controller on WLED 16.0.1 in
  both transports, and one deployment of both modes on one MCPHub host was checked. The
  live offline-controller check (H07) is pending ([#25](https://github.com/descipar/wled-mcp/issues/25)),
  as are reboot persistence and the other "Not run" items below. No compatibility with
  other controllers or firmware versions is claimed. A short live check of the second
  release over HTTP and stdio on that controller is recorded in
  [validation/live-check-2026-11-08.md](validation/live-check-2026-11-08.md).
- A hardware run of the stage-2 features on the test controller (WLED 16.0.1, one RGB
  segment, HTTP service on the hub) covered a one-device group and scene (plan, apply, readback,
  delete), preset store, export, import and restore with snapshots on unused slots, and one
  single-entry playlist; every write was verified and the controller's state, segment and
  preset list were restored ([validation/issue-134.md](validation/issue-134.md)). Four snapshots
  of that run remain in the service data directory (no snapshot-delete tool). Not run on
  hardware: multi-device scenes, tool profiles, `discover`, restore onto an occupied slot
  (`overwrite=true`), playlist import and restoring a playlist preset. Advanced segment fields
  (CCT, RGBW, 2D) have mock and loopback evidence only.
- Of the newer features, a read-only run covered the effect metadata and one effect search.
  One read-only call of the explanation ran on the controller; the live colour snapshot
  reported the endpoint as unavailable (HTTP 501), so no positive snapshot was observed.
  Zones, name resolution in segment writes, the served guidance and the layout preview have
  mocked or local-client tests only.
- Storing, restoring or importing a preset without changing the live output is not possible
  on WLED 16, and saving a playlist starts it. Imports do not rescale LED ranges or convert
  matrix layouts, and import one playlist per call
  ([#18](https://github.com/descipar/wled-mcp/issues/18), closed).
- CCT, grouping, mirror and 2D coordinates are written only when the device reports the
  capability; segment `rpt` and `fxdef` and matrix or panel configuration are not exposed,
  and there is no raw state patch tool ([#19](https://github.com/descipar/wled-mcp/issues/19),
  closed).
- No inventory reload; changes need `wled-mcp config validate` and a restart
  ([#16](https://github.com/descipar/wled-mcp/issues/16), closed).
- No device authentication. The official WLED documentation states that anyone with a
  controller's IP and port can control the lights ([OTA lock](https://kno.wled.ge/advanced/ota-lock/)),
  describes the settings PIN as protecting the settings pages and the OTA lock as protecting
  firmware updates ([settings](https://kno.wled.ge/features/settings/)), and says nothing about
  the JSON API or presets under these locks. The server sends no device credentials and
  rejects credentials in a device URL, so a controller behind HTTP authentication or a
  credentialed proxy is not supported. Behavior with a settings PIN or OTA lock has not been
  tested; a test is planned ([#128](https://github.com/descipar/wled-mcp/issues/128)).
- One writer per controller: locks are per process, so a second process or service against
  the same devices is not coordinated.
- In stdio mode the MCP host may stop the subprocess without waiting for a running call; a
  write interrupted that way stays uncertain.
- `tools/list` was CPU-heavy on small hosts (about 270 ms of CPU per call on the single-board
  target with 27 tools); since release 0.1.2 the schemas are built once per server (about
  23 ms per call, [#67](https://github.com/descipar/wled-mcp/issues/67), closed).
- No container image on GHCR; releases are distributed on PyPI and listed in the official
  MCP Registry. Automated tests check that the current server reads the retained
  data of earlier releases and rejects newer data versions without changing files; an older
  server reading newer data is not tested and relies on unchanged formats
  ([versioning](contract/versioning.md#upgrade-downgrade-and-rollback)). A live update of a
  deployed HTTP service was checked once (earlier build to the second release, see the
  record above); a rollback has not been checked and stays part of the deferred launch
  work ([#25](https://github.com/descipar/wled-mcp/issues/25)).

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
| C2-08 | Storage-only current capture, persistent full-field verification, deferred supplied-state | T09/T11/T13; #9/#10/#18 |
| C2-09 | [Snapshot envelope](../examples/contracts/snapshot.json), durability/retention/failure and explicit deferred restore boundary | T12; #8/#9/#10 |
| C2-10 | Application/verification table, envelope/text/isError parity, [conflict](../examples/contracts/preset.json) and [uncertainty](../examples/contracts/errors.json) | T08–T14/T18; #3/#6/#7/#9/#10/#14 |
| C2-11 | Explicit transport, stateless SDK lifecycle, shared resources, disconnect/drain semantics | T18/T19/T21; #3/#14/#10/#11 |
| C2-12 | Direct endpoint auth, exact Host/Origin checks, 401/403, no proxy bypass | T20; #14 implementation, #10 software acceptance, #11 integration |

MCP-03/MCP-04/OPS-05 map to #14 implementation, #10 T18–T21 acceptance, and #11
integration/deployment evidence. H02/H03 remain separate authorized operational
checks. The SDK version is selected (MCP SDK 2.3.0) and mocked/loopback protocol
execution is automated (see [TRACEABILITY.md](TRACEABILITY.md)); hardware
compatibility and deployment remain pending. PRE-03 and restore execution are Should work
added by #18 (mock evidence in [validation/issue-18.md](validation/issue-18.md)); durable
backup before destructive operations remains Must.

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
recorded in the PR, not here. PRE-03 is not covered by #9; #18 adds it
([validation/issue-18.md](validation/issue-18.md)).

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
evidence for save-current, deferred supplied-state stays with #18 (ISSUE-13-DEC-001). Real flash-write
timing, post-delete file layout, whether saving moves the active-preset marker, and
real playlist behavior are not established by mocks.

## Read-only hardware checks

H01: Record selected device alias, firmware, LED count, RGB/RGBW/CCT and segment capabilities from real responses. Sanitize any committed fixture.

H02: Read state/catalogs/presets from the actual WLED-MCP execution context, then through MCPHub. In HTTP mode this is the independent service/container; in stdio mode it is the hub-managed process. Verify actual hub-to-service authentication/connectivity when HTTP is exercised. Compare observed IDs/names and capability interpretation with the WLED UI. No discovery scan or state write is needed.

H03: Start/restart the independent HTTP service or stdio entry as appropriate, record mode/startup/idle memory, confirm diagnostics/protocol separation and verify persistent paths. Record HTTP reconnect and liveness behavior when used. Hub/container recreation is a distinct operational check and must be recorded as pending if not performed. Evidence from one deployed mode does not claim the other was deployed; both need automated protocol coverage.

## Opt-in physical write checks

Choose an explicitly authorized device and test ranges/slots first. Record the pre-test state and relevant persistent preset snapshots. A visually animated state is not necessarily restorable frame-for-frame; preserve its configuration and note limits. Do not edit the operator's existing presets for convenience when an agreed unused slot works.

H04: Change power/brightness/color and one effect's speed/intensity; verify state and visible behavior. Restore original configuration where supported.

Visible brightness and transition checks must stay below the controller's current-limiter
(ABL) cap. When the controller's power estimate (`leds.pwr` in `/json/info`) is at the
configured limit, the limiter scales the output down, so a brightness change or transition
above the cap is barely visible even though state and readback are correct. Before a visual
brightness check, choose an effect, color and brightness whose power estimate stays below
the limit (for example a solid color at a low brightness), then dim from there.

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
(issue #7 only; decided by the main session under the owner's delegation, not personally
dictated by the owner). The narrow `brightness=0` reading (DEC-007) and the follow-up
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

## Issue #10 acceptance evidence

Mapping: [TRACEABILITY.md](TRACEABILITY.md). Mock/loopback software evidence only: the
new console tests start the installed `wled-mcp` console over stdio and Streamable HTTP
against a synthetic device bound to `127.0.0.1`; no LAN device, deployment, hub or
hardware check was involved, and no product code changed. 2026-11-05, Windows 11 /
CPython 3.13.2, uv 0.11.14, MCP SDK 2.3.0, commands from the repository root:

| Command | Result recorded for this candidate |
| --- | --- |
| `uv sync --locked` | ok |
| `uv run --frozen ruff check ...` / `ruff format --check ...` (CI file list incl. `scripts/check_traceability.py`) | clean, 47 files formatted |
| `uv run --frozen mypy` | no issues in 20 source files |
| `uv run --frozen python scripts/check_agent_setup.py`; `python scripts/sync_agents.py --check` | valid; adapters synchronized |
| `uv run --frozen python scripts/check_lock.py` | lock/export consistent |
| `uv run --frozen pytest` | 707 passed, 9 skipped (POSIX-only signal, permission, symlink and FIFO tests) |
| new test modules (`tests/test_acceptance_parity.py`, `tests/test_acceptance_verification.py`, `tests/test_traceability.py`), three consecutive runs | 131 passed each run |
| `uv run --frozen python scripts/check_distribution.py` | wheel, clean install, stdio, two HTTP start/stop cycles on one port and data directory, uvx; 30 exact runtime versions |
| `uv run --frozen python scripts/check_traceability.py` | 26 Must requirements and T01–T21 mapped |

| Packet ID | Evidence |
| --- | --- |
| AC-10-01 | `test_text_fallback_equals_structured_and_is_error_equals_not_ok`, `test_device_requests_match_the_outcome_and_writes_are_never_replayed`, `test_stdio_and_http_return_identical_results`, `test_outcome_axes_for_mismatch_and_uncertain_writes`, `test_unknown_tool_is_a_protocol_error_on_both_transports`: read, verified write, two schema rejections, two domain rejections, unknown device, mismatch, uncertain write and unknown tool; only the state read's `freshness.read_at` timestamp is masked in the stdio/HTTP comparison |
| AC-10-02 | `test_real_console_rejects_missing_credential_and_disallowed_host_before_device_work` (401, 401, 403; zero device requests) |
| AC-10-03 | `test_default_http_binding_is_loopback_8000_with_exact_default_hosts`, `test_console_without_bind_options_selects_the_default_binding_and_binds_nothing` |
| AC-10-04 | `tests/test_acceptance_verification.py` (two tolerance and two mismatch tests) |
| AC-10-05 | `scripts/check_distribution.py` `http_restart` |
| AC-10-06 | `test_stdio_hub_example_arguments_complete_a_handshake`, `test_documented_console_flags_exist_in_the_installed_console` and its extractor negative control |
| AC-10-07/08 | `docs/TRACEABILITY.md`; `tests/test_traceability.py` (real documents plus synthetic negative controls on tmp copies) |

Linux CI (3.13) is recorded from the pull request run, not here. Pending and not claimed:
H01–H07 (#12), H02/H03, deployment, hub integration, resource measurements and
update/rollback (#11), Windows signal delivery (the POSIX signal tests stay skipped on
Windows), T17/raw state (excluded, ISSUE-13-DEC-001) and restore execution (ISSUE-8-DEC-001; deferred to #18 by ISSUE-13-DEC-001).

## Issue #11 deployment-artifact evidence

Prepared artifacts only (ISSUE-11-DEC-001): Dockerfile with allowlist build context,
Compose example, both hub examples, `deploy/stage_release.py`, procedures in
[DEPLOYMENT.md](DEPLOYMENT.md) and an operations record template. Nothing was deployed,
registered in a hub, pushed or published; no LAN device was contacted. 2026-11-06,
macOS (arm64) / CPython 3.13.2, uv 0.11.7, MCP SDK 2.3.0, commands from the repository
root. Results were first recorded at `cd0795b` and re-run unchanged in outcome on the
review correction round 1 (strict image checksum step, inline-command scoping check;
parent `c75b468`); the exact candidate commit is stated in the pull request:

| Command | Result recorded for this candidate |
| --- | --- |
| `uv sync --locked` | ok (PyPI access for the new dev-only PyYAML 6.0.3) |
| `uv run --frozen ruff check ...` / `ruff format --check ...` (CI list plus `deploy`) | clean, 50 files formatted |
| `uv run --frozen mypy` | no issues in 21 source files (incl. `deploy/stage_release.py`) |
| `uv run --frozen python scripts/check_agent_setup.py`; `python scripts/sync_agents.py --check` | valid; adapters synchronized |
| `uv run --frozen python scripts/check_lock.py` | lock/export consistent; `requirements-runtime.txt` unchanged |
| `uv run --frozen pytest` | 745 passed, 1 skipped (opt-in Docker check), 8 subtests passed |
| `uv run --frozen python scripts/check_distribution.py` | PASS incl. the stdio hub example through uvx with only paths replaced; 29 exact runtime versions on this platform |
| `uv run --frozen python scripts/check_traceability.py` | 26 Must requirements and T01–T21 mapped |
| `WLED_MCP_DOCKER_CHECKS=1 uv run --frozen pytest tests/test_deployment_artifacts.py -k docker_compose` | passed (local Docker CLI) |

| Packet ID | Evidence |
| --- | --- |
| C11-01/02/05/14 | `test_hub_http_url_names_the_compose_service_and_its_allowed_host`, `test_compose_is_a_separate_single_process_project_without_host_ports` |
| C11-03/04 | `test_compose_command_accepts_the_hub_example_connection` (compose argv with paths, bind and port replaced; hub Host and header shape: SDK handshake in both modes, 403 for the loopback authority, 401 without credential, SIGTERM exit 0, empty stdout, credential not logged), `test_compose_substitution_keeps_every_other_argument`, `test_credential_only_from_a_git_ignored_runtime_secret_file`, `test_no_credential_literal_in_deployment_files` and its detector control |
| C11-06/07 | `test_stdio_hub_example_runs_the_staged_release_with_constraints`, `test_documented_uvx_invocation_matches_the_stdio_hub_example`, `scripts/check_distribution.py` `hub_example_uvx`; listener-free stdio stays covered by `test_stdio_ignores_ambient_http_token_and_binds_nothing` |
| C11-08 | `test_dockerfile_pins_base_image_wheel_and_constraints`, `test_image_checksum_step_requires_both_staged_inputs` (runs the image's checksum step: missing, duplicated or modified wheel/constraints entries fail), `test_build_context_is_an_allowlist_of_the_release_inputs` and its negative control, `test_no_unpinned_artifact_reference_in_deployment_files`, `test_stage_release_*` |
| C11-09/10 | `test_data_mount_matches_the_data_dir_and_holds_the_config`, `test_compose_is_a_separate_single_process_project_without_host_ports`, `test_healthcheck_is_a_credential_free_tcp_check_of_the_service_port` |
| C11-11/12 | DEPLOYMENT.md procedures; `test_documented_container_commands_touch_only_the_wled_mcp_project` (code blocks and inline code spans) with `test_container_command_check_rejects_unscoped_commands`, `test_documented_console_flags_exist_in_the_installed_console` |
| C11-13 | this section; TRACEABILITY deployment cells unchanged (`pending: ...`) |

Local developer machine, not target (Docker Desktop 29.9.2, linux/arm64 VM; no hub, no
LAN, nothing pushed): `docker build --pull` from a release directory staged at `cd0795b`
(clean tree) succeeded; build context 72.8 kB; both checksums OK; image user
`10001:10001`, entrypoint `["wled-mcp"]`, 183 MB. A context copy with planted
`devices.toml`, `secrets/` and `.env` files produced an image without them. The Compose
example (network placeholder replaced by a local `--internal` network, empty inventory)
passed `docker compose config`, reported `listening on 0.0.0.0:8000 path /mcp` 0.94 s
after `up -d` (including container creation), became `healthy`, answered the
authenticated in-container `ping` with Host `wled-mcp:8000` with 200 (also for
`WLED-MCP:8000`), 401 without credential and 403 for Host `127.0.0.1:8000`; idle memory
53 MiB (`docker stats`, one process) 20 s after the checks; `stop` took 0.52 s, exit
code 0; the credential did not appear in the logs; the data directory held only
`config/`. Correction round 1, same machine, release staged from the corrected tree:
`docker build --pull` succeeded (user `10001:10001`, `wled-mcp 0.1.0`); builds failed at
the checksum step for a `SHA256SUMS` without the wheel line (with and without a
modified wheel), without the constraints line, and for a modified wheel. Check images
were removed. These values are not target measurements.

Pending and not claimed: actual deployment of either mode, MCPHub registration and
connection, the hub's real network/service name/Host match, stdio launched by the real
hub, read-only hub checks H02, startup/idle measurements on the target H03, executed
update/rollback/recreation, Linux x86-64 image build, stdio start/idle measurements
(not taken locally), Linux CI (recorded from the pull request run) and H01–H07 (#12).

## Issue #11 live deployment check (2026-11-06)

One authorized live check of both modes on one target (ISSUE-11-DEC-003) with
follow-up checks on the same target (ISSUE-11-DEC-006, ISSUE-11-DEC-007), sanitized
from a local, git-ignored run record. Host names, addresses, paths, user names, device
names and image IDs of the installation are intentionally omitted.

Target class: aarch64 single-board computer, Docker, MCPHub 1.2.1 in its own Compose
project, `uvx` 0.13.7 and Python 3.13.18 inside the hub container. Release: wled-mcp
0.1.0 staged from commit `0da1249` (clean tree) on a build machine; wheel SHA-256
`db0b2edde4d20a07f789d7192314d1e606acb50f319a9c69900fa7d38e9eeb55`, constraints
SHA-256 `53fc7b43a799ac376b4210cbfbdb21a60bf8368c91142da715ec702f7217d8ee`;
`sha256sum -c SHA256SUMS` matched on the target; the release directory is read-only
there. The hub configuration was backed up before any change. Device operations were
limited to one authorized test controller: reads and master power on/off.

### Streamable HTTP service

| Check | Result |
| --- | --- |
| Image build on the target (`docker build --pull`) | arm64 image, user `10001`, 183 MB |
| Authenticated in-container `ping` with Host `wled-mcp:8000` | 200 |
| Wrong Host / missing credential | 403 / 401 |
| Session header | no `Mcp-Session-Id` |
| Tool listing in the container | 12 tools; `tools/list` p50 105 ms (including the Python `urllib` client) |
| Runtime recreation (`--force-recreate`) | stop 1.09 s, exit code 0; start to listening 6.67 s (including `up -d` 1.04 s) |
| Idle memory | RSS about 72 MiB, 1 thread (measured with `ps` on the container process; `docker stats` showed 0 B because the host has no memory cgroup) |
| Hub registration (`streamable-http`, service URL, bearer header) | first attempt refused by the hub's SSRF guard ("resolves to blocked address") because the entry owner was `system`; connected after setting the owner to an admin user and reloading the entry (see [DEPLOYMENT.md](DEPLOYMENT.md#mcphub-notes)) |
| Through the hub | `initialize` 175 ms; 12 tools; `wled_list_devices` and `wled_get_state` for the test controller |
| Authorized write through the hub | `wled_set_state` `on=true` and then `on=false`, each verified by the tool's readback; original state (off, original brightness) restored |
| Service restart | the next hub call succeeded without any hub action (stateless reconnect) |

### stdio via uvx

| Check | Result |
| --- | --- |
| Hub entry | arguments exactly as [mcphub.example.json](../examples/mcphub.example.json), `UV_*` paths under the persistent uv tree |
| Start | cold first launch 9.6 s including download of 29 dependency packages; warm reload 3.45 s to connected |
| Idle memory | Python process RSS 67 MiB (3 threads) plus `uv` wrapper RSS 27 MiB; uv tree 49 MB |
| Listeners | 0 listening sockets for the entry's processes |
| Reload | leaves a single server instance |
| Through the hub | `wled_list_devices` reached the test controller; `wled_set_state` `on=true` and `on=false` verified by readback; restored to off |
| Removal (ISSUE-11-DEC-004) | only the stdio hub entry was deleted; no stdio server process was left; the hub data/config directory, the uv cache and the staged release directory were retained |

### HTTP service removal and redeploy (ISSUE-11-DEC-006)

Run after the checks above, following [DEPLOYMENT.md](DEPLOYMENT.md#http-service-update-rollback-recreation-removal);
the hub configuration was backed up first.

| Check | Result |
| --- | --- |
| Hub entry removal | only the HTTP hub entry was deleted; all other hub entries unchanged |
| `docker compose -p wled-mcp-http -f compose.yaml rm --stop --force wled-mcp` | 1.27 s; no container of the `wled-mcp-http` project left |
| `docker image rm wled-mcp:0.1.0` | image removed |
| Hub and neighbors | hub container not restarted (start time unchanged), hub network present, other containers unchanged |
| Retained | data directory with the inventory, credential file and staged release directory |
| Redeploy from the retained release | `sha256sum -c SHA256SUMS` matched; `docker build --pull` produced an identical image ID (build cache); `up -d`; in-container `ping` 200, wrong Host 403, missing credential 401, no `Mcp-Session-Id` |
| Hub re-registration | create entry, set owner to an admin user, reload the entry; through the hub: `initialize`, 12 tools, `wled_list_devices` probe reachable, `wled_get_state` read for the test controller |

No device writes were part of this operation.

### Catalog/preset reads, stdio rebuild and hub container recreation (ISSUE-11-DEC-007)

Run after the removal test on the same target and the same single test controller;
the hub configuration was backed up first. A restorable baseline of the controller
(state, info, configuration, preset file, effect, palette and effect metadata data) was
recorded locally before any check. No device writes were needed or performed.

H02 reads through the hub, per mode:

| Check | Streamable HTTP | stdio via uvx |
| --- | --- | --- |
| `wled_list_devices` probe | reachable | reachable |
| `wled_get_state` | read | read, 203 ms |
| `wled_get_effects` (refresh) | 220 effects; see the fail-safe note below | succeeded with effect metadata available, 520 ms |
| `wled_get_palettes` | 72 palettes | succeeded, 286 ms |
| `wled_list_presets` | one state preset (ID 1) | succeeded, 139 ms |
| `wled_get_preset` 1 | the stored preset object | succeeded, 133 ms |

Comparison with the WLED UI data source: the controller's own catalog endpoints that the
WLED web UI reads (`/json/eff`, `/json/pal`) were read directly and their counts and
names match the HTTP-mode catalogs (220 effects, 72 palettes). This is a comparison
with the UI's data source, not a visual inspection of the UI; the stdio-mode catalog
counts were not recorded separately. Not performed in this run and still pending
([#12](https://github.com/descipar/wled-mcp/issues/12)): H02 reads from the server's own
execution context (the HTTP service container or the hub-managed stdio process)
separately from the hub, and a comparison of capability interpretation with the WLED UI.

Fail-safe observation: on the first HTTP-mode effect refresh the controller returned a
truncated effect metadata body (`/json/fxdata`, about 5.5 kB of invalid JSON). The
server returned the complete effect names, reported the metadata as unavailable
(`INVALID_RESPONSE`) with a warning and did not fail the call; the retry returned the
metadata. This matches the optional-metadata behavior covered by
`test_optional_fxdata_failure_keeps_names_and_succeeds`.

stdio re-registration, environment rebuild and removal:

| Check | Result |
| --- | --- |
| Re-registration (arguments as [mcphub.example.json](../examples/mcphub.example.json), warm uv cache) | connected 3.7 s |
| Environment rebuild following [DEPLOYMENT.md](DEPLOYMENT.md#stdio-via-uvx-register-update-rollback-rebuild-removal) | entry disabled (no stdio process left), only the uv cache directory (49 MB) deleted, entry enabled: connected 9.2 s including the dependency re-download, 12 tools, cache 49 MB again; inventory/data directory untouched |
| Removal again (ISSUE-11-DEC-004) | only the stdio entry deleted; all other hub entries present; no stdio process left |

Hub container recreation (stdio entry registered, HTTP service running):

| Check | Result |
| --- | --- |
| Command | the hub's own Compose project, hub service only, `--force-recreate --no-deps --pull never` |
| Hub image | same image before and after (no hub update) |
| Timings | Compose 14.7 s; hub HTTP ready 25.1 s; hub outage for all hub entries about 30 s |
| HTTP entry | reconnected 3.1 s after the client's `initialize`; the admin entry owner persisted |
| stdio entry | reconnected about 26 s after `initialize` (startup contention with all other hub servers); no dependency download: the uv tree (49 MB) survived; inventory survived |
| HTTP service | container not restarted (start time unchanged) |
| Hub entries | all present after recreation |

Observation, not wled-mcp behavior: other hub servers launched through `npx` downloaded
their packages again after the recreation because their caches live in the container
filesystem.

Final check: the controller state and preset file read after the run were identical to
the baseline.

Mode remaining active: Streamable HTTP (ISSUE-11-DEC-004), redeployed after the removal
test. Both entries were registered at the same time during the first run until the
stdio entry was removed, and again during the ISSUE-11-DEC-007 checks until its second
removal; no device writes were issued while both were registered in the second run.

Findings fed back into [DEPLOYMENT.md](DEPLOYMENT.md#mcphub-notes): the MCPHub entry
owner requirement and reload step, RSS measurement without a memory cgroup, and RFC 1123
host labels in `base_url` (an underscore name was rejected,
[#61](https://github.com/descipar/wled-mcp/issues/61); a hyphenated name resolved to two
addresses, so the run used an address).

Moved to stage 2 per ISSUE-11-DEC-005: live update and rollback between two releases
(only 0.1.0 exists), tracked by [#21](https://github.com/descipar/wled-mcp/issues/21)
(S2-COMPAT-03) and [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01);
the documented procedures remain #11 scope.

Moved to #12 per ISSUE-11-DEC-008: graceful drain of an in-flight call on the target
and load measurements (parallel calls, peak connections, largest body), tracked by
[#12](https://github.com/descipar/wled-mcp/issues/12); the automated drain coverage
(T21) remains the #11 evidence for the drain behavior.

Not exercised and still pending: any other device, preset or segment writes, and
H01/H04–H07 (#12).

## Issue #12 hardware acceptance (2026-11-06)

One authorized hardware acceptance run on one test controller (ISSUE-12-DEC-001) and on
the deployed Streamable HTTP service of #11 (stop/start and load per ISSUE-12-DEC-003, a
coordinator interpretation confirmed retroactively by the owner on 2026-11-06 for this run
only), with the technical
defaults of ISSUE-12-DEC-002, sanitized from a local, git-ignored run record. Host
names, addresses, paths, user names, device names, MAC addresses and image IDs of the
installation are intentionally omitted. The results describe this one controller and
this one firmware only; no compatibility with other firmware, controllers or LED types
is claimed.

```text
Date / operator / source commit: 2026-11-06 / project coordinator agent under the owner's
  authorization / wled-mcp 0.1.0 image built from commit 0da1249 (unchanged since #11);
  load and drain client scripts/hw_http_probe.py from commit 119229d
Package / Python / SDK / hub runtime: wled-mcp 0.1.0, Python 3.13.18, mcp 2.3.0,
  uvicorn 0.54.0, starlette 1.10.0, aarch64; MCPHub as in the #11 record
Transport mode / endpoint or uvx artifact / service lifecycle: Streamable HTTP only
  (ISSUE-12-DEC-002 TD-12-1), the #11 Compose service on the hub network, registered as
  the hub's HTTP entry; stop/start of that service for D1/D2; no rebuild, no image,
  inventory, secret, hub entry or hub container change
Sanitized device and firmware / relevant capabilities: see H01
Scenario IDs run: P0, I1-I3, H01, H02 (own context), L1-L6, D1, D2, H04, H05, H06, R1-R3
Before state and snapshot references (local, no secrets): P0 baseline of state, info,
  configuration, preset file, effect/palette names and effect metadata, each with a
  SHA-256, kept in the local run record
Expected and observed results: tables below
Restoration performed and verified: R1-R3 below
Not run / reason / remaining risk: "Not run" list below
```

### P0 baseline and interference (I1-I3)

The baseline was read directly from the controller before any write. Preset slots 2 and
250 were free; the preset file held only preset 1 (a state preset); no realtime input
was active. Three state reads 30 s apart before the first write were equal, and again
after the restoration (no external writer during the windows).

Interference sources, read only and left as found (nothing was disabled): timers
disabled; no countdown macro; boot preset 1; one push button without macros; no IR
receiver; UDP sync receive on (brightness, color, effect, palette; one group) and send
off; another WLED controller visible via the node list (node broadcast on); realtime
input (E1.31/DDP) enabled but not active; Alexa emulation enabled; MQTT and Hue sync
off; NTP on; nightlight off; the AudioReactive usermod disabled; one WebSocket client
connected. The quiet windows before and after were unchanged and all write readbacks
matched expectations; the sources were not monitored continuously.

### H01 device facts

| Fact | Result |
| --- | --- |
| Firmware | WLED 16.0.1 (outside the pinned v0.15.1 source review; the server has no version gate, so every result below is an observation for 16.0.1 only) |
| Platform | ESP32-C3 |
| LEDs | 133 RGB LEDs on one bus; RGB only (no white channel, no CCT); 1D (no matrix in info) |
| Segments | segment limit 32; one active segment in the baseline |
| Power limiter | automatic brightness limiter configured |
| Catalogs | 220 effects, 72 palettes |
| Locks | OTA lock and Wi-Fi settings lock off in the before and after configuration captures of runs 1-3; settings PIN state not captured (not part of the configuration export); no WLED API read or write refused by the controller in runs 1-3 (the #66 activation refusal came from this server, the run-3 `TIMEOUT` occurred before dispatch) |

### H02 reads

From the service's own execution context (an authenticated client inside the HTTP
service container on its loopback interface, credential from the mounted secret file):

| Tool | Result, compared with the controller's own endpoints |
| --- | --- |
| `wled_list_devices` (probe) | reachable |
| `wled_get_state` | on, brightness, segments, ranges, colors, effect, palette and transition equal to `/json/state`; capabilities (LED count, segment limit, effect/palette counts, RGB only, firmware) equal to `/json/info`; MAC, address and BSSID redacted |
| `wled_get_effects` (refresh) | 220 names equal to `/json/eff`; effect metadata available; no warnings |
| `wled_get_palettes` (refresh) | 72 names equal to `/json/pal` |
| `wled_list_presets` | one state preset (ID 1), the same IDs as `/presets.json` |
| `wled_get_preset` 1 / 250 | the stored preset object / `PRESET_NOT_FOUND` |

Through the hub: the H02 reads through the hub's entries for both modes are the
[#11 records of the same day](#issue-11-live-deployment-check-2026-11-06) (same release
and controller); in this run the H04-H06 tool calls went through the hub's HTTP entry.
The comparison is with the WLED UI's data sources (`/json/state`, `/json/info`,
`/json/eff`, `/json/pal`), not a visual inspection of the UI. In stdio mode the server's
own execution context is the hub-managed process, so the #11 stdio hub reads are cited
for it (ISSUE-12-DEC-002 TD-12-6).

### H03 load (L1-L6), Streamable HTTP

Client: `scripts/hw_http_probe.py` inside the service container against its loopback
interface; one TCP connection per request (included in the latency); latencies in ms.

| Check | Result |
| --- | --- |
| L1 idle | RSS 73,740 KiB, 1 thread (`ps` on the container process) |
| L2 `ping`, concurrency 1 / 4 / 16 (100 / 200 / 400 requests) | 167 / 195 / 201 requests/s; p50 5.3 / 19 / 76; p95 6.5 / 23 / 97; max 48 at c1, p99 107 at c16; all HTTP 200 |
| L2 `tools/list`, concurrency 1 / 4 / 16 (100 / 200 / 400 requests) | 9.1 / 9.2 / 9.2 requests/s; p50 106 / 425 / 1717; p95 117 / 470 / 1829; p99 1863 at c16; all HTTP 200; the service process used about 108-109 ms CPU per call (sampled), so the call is CPU-bound and concurrency only queues ([#67](https://github.com/descipar/wled-mcp/issues/67)) |
| L3 `wled_get_state`, concurrency 1 (20) / 4 (40) | 13 / 13.4 requests/s; p50 67 / 282; p95 104 / 347; the per-device lock serializes the controller reads; all HTTP 200 |
| L3 `wled_get_effects` (cached), concurrency 4 (40) | 19.4 requests/s; p50 201; p95 235; all HTTP 200 |
| Peak RSS during the bursts | 76,512 KiB |
| CPU per call (service process user + system time per burst) | `ping` about 5 ms; `tools/list` about 108-109 ms; `wled_get_state` about 21 ms; `wled_get_effects` (cached) about 22 ms |
| L4 peak concurrent connections | not sampled; the client concurrency was at most 16 |
| L5 sockets after the clients disconnected | 2 listening, 4 in TIME-WAIT, none established |
| L6 request-body bound | 262,143 bytes: HTTP 200; 262,145 bytes: HTTP 413 |

### Drain on SIGTERM (D1-D3), Streamable HTTP

Stop with `docker compose -p wled-mcp-http ... stop wled-mcp` (SIGTERM, grace period
130 s), start again in the same project. The drain client ran in a separate container on
the hub network (so it survived the stop) and sent read-only `wled_get_effects`
(refresh) calls at concurrency 4.

| Check | Result |
| --- | --- |
| Attempt 1 | invalid as a drain sample: the client started only after the stop. As an idle stop: stop 1.26 s, exit code 0; start to listening 7.36 s |
| D2 attempt 2, in-flight reads | three calls sent 0.53 / 0.35 / 0.15 s before the stop command's timestamp completed with HTTP 200 at +0.22 / +0.46 / +0.62 s (at least one, the last, certainly in flight at the signal; see the caveat); two calls sent +0.03 / +0.22 s after that timestamp were still admitted and completed with HTTP 200; calls sent from +0.46 s were refused (connection refused); the stop returned after 1.99 s with exit code 0; start to listening 6.30 s |
| D3 in-flight write | not run (the probe is read-only); automated coverage T21 |

Caveat: the reference time is the timestamp of the `compose stop` invocation on the CLI,
not the moment the process received SIGTERM. Two calls sent after that timestamp were
still admitted, so the signal arrived between +0.22 s and +0.46 s. Only the call
completing at +0.62 s is therefore certainly in flight at the signal; the run plan's
three in-flight samples are not strictly established.

### H04 master and one effect (writes)

| Step | Result |
| --- | --- |
| `wled_set_state` on with brightness 0 | `VALIDATION_ERROR`, no write |
| `wled_set_state` brightness only while off | master stays off (targeted compensation `on:false`, ISSUE-52-DEC-001), readback matched |
| `wled_set_state` on with `transition_ms` 1000 | on; wire transition 10; the persistent transition (7) untouched; readback matched |
| `wled_patch_segments` segment 0 color slot 1 | applied, readback matched; color slots 2 and 3 kept |
| `wled_patch_segments` segment 0 effect ID 9, speed 200, intensity 100 | applied, readback matched |
| Proxy for visible output | `/json/info` reported 850 mA (the limiter's cap) and 43 frames/s while on |

Observation (no issue opened): the dry-run plan's `resolved_segments` listed only the
supplied color slot, while the device keeps the other two slots; the plan display is
shorter than the device result, the actual write and readback were correct.

### H05 segments and layout (writes)

| Step | Result |
| --- | --- |
| `wled_replace_layout` dry run, two segments [0,66) and [66,133) | plan with two steps, no write |
| `wled_replace_layout` live | segment 0 shortened to [0,66) keeping its effect and colors; segment 1 created at [66,133) with the supplied color and resolved defaults; both steps matched on readback; master unchanged |
| `wled_patch_segments` segment 1 color and effect | applied, readback matched; segment 0 unchanged (`preserve_segment_ids` [0]) |
| Original one-segment layout | restored by activating the pre-existing state preset 1, not by a second `wled_replace_layout`; stale-ID removal by the tool was therefore not exercised on hardware |

### H06 presets, slot 250 (writes)

| Step | Result |
| --- | --- |
| `wled_save_preset` slot 250, dry run | plan, no write |
| `wled_save_preset` slot 250 | saved; present in `/presets.json` (persistence by readback); elapsed time and the active-preset marker not recorded |
| Classification of the saved entry | `unknown`: WLED 16 stores an additional top-level `bs` key that the reviewed state shape does not contain ([#66](https://github.com/descipar/wled-mcp/issues/66)) |
| `wled_activate_preset` 250 | refused with `UNSUPPORTED_CAPABILITY`, no write (consequence of #66) |
| `wled_save_preset` slot 250 again without `overwrite` | `PRESET_CONFLICT`, no write |
| `wled_save_preset` slot 250 with `overwrite=true` | saved after a snapshot; readback matched |
| `wled_save_preset` without an ID | allocated ID 2 (lowest free); readback matched |
| `wled_delete_preset` 250 | snapshot, then removed; absence matched on readback |
| `wled_delete_preset` 250 again | `PRESET_NOT_FOUND`, no write |
| `wled_delete_preset` 2 | snapshot, then removed; absence matched on readback |
| `wled_activate_preset` 1 (pre-existing state preset) | activated; readback matched (this also restored the one-segment layout) |
| `wled_set_state` off | readback matched |

Activation was therefore exercised only with the pre-existing state preset; activating
a preset saved by WLED 16 remains pending until #66 is resolved.

Note added after this run (not part of its results): the classification fix for #66
(ISSUE-66-DEC-001, `bs` accepted as state) is mock-tested only; the hardware re-check
of save then activate on WLED 16 is pending as a separately authorized #12 follow-up.

Snapshots: three snapshot files (overwrite of 250, delete of 250, delete of 2) in the
service data directory, directory mode 0700, files mode 0600, owned by the service user;
envelope keys `backup_id`, `created_at`, `device_id`, `firmware`, `format_version`,
`preset`, `preset_id`. They stay on the target and are not committed. Restoring saved
contents from a snapshot was not run (ISSUE-8-DEC-001).

### Restoration (R1-R3)

| Check | Result |
| --- | --- |
| R1 preset file | JSON-equal to the baseline (only preset 1, identical object); bytes differ, 713 to 3,770 bytes, because the firmware blanks deleted entries with spaces instead of compacting the file; the original bytes cannot be restored through the API (no whole-file upload, per the contract) |
| R2 state | byte-identical to the baseline |
| R3 configuration | byte-identical to the baseline (no configuration touched) |
| Quiet window after the restoration | three reads 30 s apart, equal |

### Not run

- Visual check of the LEDs and of the WLED UI (agents cannot see the LEDs; readback and
  the power/frame-rate proxy only).
- D3 drain of an in-flight write on the target.
- L4 peak concurrent connections (not sampled).
- stdio mode in this run: stdio drain, stdio load and stdio H04-H06 (HTTP only per
  ISSUE-12-DEC-002; stdio startup/idle and hub reads are the #11 records).
- H07 offline device on hardware (no unreachable device in the deployed inventory;
  simulated evidence T02/T09 remains).
- Controller reboot and power-cycle persistence (ISSUE-12-DEC-002 TD-12-3).
- Activation of a preset saved by WLED 16 (blocked by
  [#66](https://github.com/descipar/wled-mcp/issues/66)).
- Stale-ID removal by `wled_replace_layout` on hardware (see H05).
- Restoring preset contents from a snapshot (ISSUE-8-DEC-001).
- Other controllers and firmware, RGBW/CCT, 2D and multi-bus setups, playlists (none on
  the controller), live update/rollback (stage 2).

Several of these items were run later the same day in
[run 2](#issue-12-hardware-acceptance-run-2-2026-11-06).

## Issue #12 hardware acceptance, run 2 (2026-11-06)

A second authorized run on the same day, on the same test controller and target, under
ISSUE-12-DEC-005 (HTTP deployment update and stop/start, a temporary stdio hub entry
with the HTTP entry disabled, controller writes with capture and restore) and
ISSUE-12-DEC-001 (controller conditions). ISSUE-12-DEC-004 keeps stdio via uvx in #12
scope, so this run exercised both modes. The owner was within sight for visual checks
and replied with delay; no step depended on a quick reaction. Sanitized from a local,
git-ignored run record; host names, addresses, paths, user names, device and hub entry
names, MAC addresses and image IDs are intentionally omitted. The results describe this
one controller and this one firmware (WLED 16.0.1, unchanged since
[run 1](#issue-12-hardware-acceptance-2026-11-06)) only; no compatibility with other
firmware, controllers or LED types is claimed.

```text
Date / operator / source commit: 2026-11-06 / project coordinator agent under the owner's
  authorization / wled-mcp 0.1.0 built from main commit b36f410 (includes the #66 fix)
Package / Python / SDK / hub runtime: wled-mcp 0.1.0 (package version not bumped, see
  "Build identification"), Python 3.13, aarch64; MCPHub 1.2.1
Transport mode / endpoint or uvx artifact / service lifecycle: Streamable HTTP (the #11
  Compose service, updated to the b36f410 image, stop/start for D3) and stdio via uvx (a
  temporary hub entry running the staged b36f410 wheel with the documented argument
  list, HTTP entry disabled meanwhile, removed afterwards)
Sanitized device and firmware / relevant capabilities: as run 1 H01 (WLED 16.0.1,
  ESP32-C3, 133 RGB LEDs, one bus)
Scenario IDs run: P0, HTTP update, L4, D3, visual A-C (H04-H06 writes through the hub's
  HTTP entry), stdio H04-H06, stdio load, stdio drain, R1-R3
Before state and snapshot references (local, no secrets): run-2 baseline of state,
  info, configuration and preset file with SHA-256 values in the local run record; the
  state hash equals the run-1 baseline
Expected and observed results: tables below
Restoration performed and verified: R1-R3 below
Not run / reason / remaining risk: "Not run" list below
```

### Build identification and HTTP update

The package version on main was still 0.1.0, and the documented staging keys release
directories and image tags on the version alone (`<version>/`, `wled-mcp:<version>`),
whose existing 0.1.0 directory must not be overwritten. The b36f410 build was therefore
staged under an ad-hoc release directory `0.1.0+b36f410` and image tag
`wled-mcp:0.1.0-b36f410`. This is a deviation from the documented procedure; a defined
identification scheme for non-release builds is tracked by
[#70](https://github.com/descipar/wled-mcp/issues/70). The previous 0.1.0 release
directory and image were kept as the rollback source.

| Step | Result |
| --- | --- |
| HTTP update | `image:` in the Compose file changed to the b36f410 tag (the previous file kept as a backup), `up -d` for the service only: start to listening 7.53 s |
| Hub reconnection | the hub's HTTP entry reconnected without any hub action (a preset list call through it returned normally) |
| Remaining deployment | the b36f410 image stays the active HTTP deployment (authorized update) |

### L4 peak concurrent connections, Streamable HTTP

Client: `scripts/hw_http_probe.py` inside the service container against its loopback
interface, `ping`, one TCP connection per request; peak established connections on the
service port sampled during each burst; latencies in ms.

| Concurrency (requests) | Result |
| --- | --- |
| 16 (400) | 204 requests/s; p50 76; peak 16 established; all HTTP 200 |
| 32 (800) | 203 requests/s; p50 153; peak 32 established; all HTTP 200 |
| 64 (1,600) | 198 requests/s; p50 307; p95 412; peak 64 established; all HTTP 200 |
| Memory | RSS at most 75,656 KiB |
| Sockets after the clients disconnected | 2 listening, 2,731 in TIME-WAIT (one connection per request over all bursts), none established |

Peak connections followed the client concurrency up to 64; throughput stayed at about
200 requests/s, so additional concurrency only queued.

### D3 drain of an in-flight write, Streamable HTTP

A writer client in a separate container on the hub network sent brightness-only
`wled_set_state` calls back to back while the controller was off (the master stays off,
ISSUE-52-DEC-001); the service was then stopped as in run 1 (SIGTERM). Times relative to
the `compose stop` invocation (t0).

| Check | Result |
| --- | --- |
| Write i=6, sent -0.118 s | HTTP 200 at +0.049 s, applied and verified by readback |
| Write i=7, sent +0.050 s | HTTP 200 at +0.242 s, applied and verified |
| Write i=8, sent +0.242 s | HTTP 200 at +0.417 s, applied and verified |
| Write i=9 and later, from +0.417 s | connection refused (no request reached the service) |
| Uncertain writes | none; no write reported `uncertain` |
| Stop / start | stop returned after 1.42 s with exit code 0; start to listening 6.45 s |

Caveat on signal timing: as in run 1, t0 is the CLI invocation, not the moment the
process received SIGTERM. Writes sent after t0 were still admitted, so the signal arrived
between +0.242 s and +0.417 s. Write i=8 was admitted at +0.242 s and answered at
+0.417 s, so it was in flight at the signal unless the signal fell between its answer
and the next connection attempt, which the record's resolution cannot separate. No
admitted write was cut off or left uncertain.

### Visual checks (owner)

The owner observed the strip and confirmed each pattern with a delayed reply. The
checks and their setup writes ran through the hub's HTTP entry, before the stdio phase;
every write was verified by the tool's readback. The run record maps them to the
visible behavior of the H04-H06 writes.

| Check | Command | Owner's observation (translated) |
| --- | --- | --- |
| A | `wled_patch_segments`, `wled_replace_layout` and `wled_set_state` (brightness 120): segment 0 LEDs [0, 66) red, segment 1 LEDs [66, 133) blue; all verified | "left blue, right red": both halves as commanded; the strip starts (LED 0) on the right-hand side from the owner's view |
| B | `wled_replace_layout` to one segment LEDs [0, 133), green; the stale segment ID 1 is removed by the single-segment payload (verified) | "all green" |
| C | `wled_activate_preset` 250 (saved after A, see below): applied and verified by the tool's state readback, type `state` | "left blue, right red" (pattern A again) |

Directly after check A, `wled_save_preset` saved the pattern as preset 250 through the
same entry: verified, classified `state` on WLED 16 (the stored preset contains `bs`).

Results:

- [#66](https://github.com/descipar/wled-mcp/issues/66) hardware re-check: save then
  activate of a preset saved on WLED 16.0.1 passed (preset 250 and check C over HTTP:
  classification `state`, activation applied and verified by readback and confirmed
  visually; the stdio H06 below repeats it in stdio mode).
- H05 stale-ID removal on hardware passed: `wled_replace_layout` removed segment ID 1
  (check B; readback and visual).
- Visible behavior confirmed by the owner for colors, segment extents and preset
  recall (checks A-C). Effect animation, speed, brightness level and transition were
  not observed separately.

### stdio via uvx: H04-H06

The HTTP hub entry was disabled, and a temporary stdio entry was registered with the
staged b36f410 release and the documented argument list; it connected after 8 s and
listed 12 tools. All calls went through the hub.

| Scenario | Result |
| --- | --- |
| H04 `wled_set_state` on with brightness 0 | `VALIDATION_ERROR`, no write |
| H04 brightness only while off | master stays off (targeted compensation), readback matched |
| H05 `wled_replace_layout` two segments to one | stale segment ID 1 removed; readback matched |
| H05 `wled_replace_layout` one segment to three | segments 1 and 2 created; readback matched |
| H05 `wled_patch_segments` segment 1 | applied; segments 0 and 2 unchanged |
| H05 `wled_replace_layout` three segments to one | stale segment IDs 1 and 2 removed; readback matched |
| H06 `wled_save_preset` 250 without `overwrite` | `PRESET_CONFLICT`, no write |
| H06 `wled_save_preset` 250 with `overwrite=true` | snapshot, then saved; classification `state` on WLED 16; readback matched |
| H06 `wled_activate_preset` 250 | activated (type `state`); readback matched |
| H06 `wled_delete_preset` 250 | snapshot, then removed; absence matched; warning that the deleted preset carried the currently active preset marker |
| H06 `wled_delete_preset` 250 again | `PRESET_NOT_FOUND`, no write |

Snapshots: two snapshot files in the stdio data directory inside the hub's persistent
data (directory mode 0700, files mode 0600, owned by the hub's process user); the three
run-1 snapshot files of the HTTP service are unchanged. Not committed.

### stdio load (through the hub)

Client: a load script against the hub's MCP endpoint for the temporary stdio entry with
a temporary hub system key (removed afterwards). Temporary hub system keys, each created
and removed within its script, were the mechanism for all hub API operations in #11 and
#12 (register, toggle, reload, remove, probes); they fall under the owner's
authorization to register and remove the stdio entry and toggle the HTTP entry
(ISSUE-12-DEC-005). Figures include the hub hop; CPU is the
user + system time of the stdio Python process (not the uv wrapper) per run.

| Check | Result |
| --- | --- |
| `ping` and `tools/list` | answered by the hub itself; the stdio process used no CPU for them, so they do not measure the server |
| Hub rate limit | MCPHub 1.2.1 returned HTTP 429 "Too many requests" after about 200 requests in its window; no load beyond that limit was possible through the hub |
| `wled_get_state`, concurrency 1 (20) | all `ok`, no HTTP 429; 4 requests/s; p50 107; p95 319; max 2,537; about 20 ms CPU per call |
| `wled_get_state`, concurrency 4 (40) | all `ok`, no HTTP 429; 2.2 requests/s; p50 394; p95 7,884 |
| `wled_get_effects` (refresh), concurrency 4 (20) | all `ok`, no HTTP 429; p50 1,940; p95 3,247; about 38 ms CPU per call |
| Process | stdio Python process RSS 77.5 MiB, 3 threads, no listening socket; uv wrapper RSS 36 MiB |

Disclosure: the first load attempts were invalid and are not counted: a wrong tool-name
prefix in the load script, CPU sampled from the uv wrapper instead of the Python
process, and runs that hit the hub's rate limit. Only the runs above are valid; none of
them received an HTTP 429. They
are shaped by the hub (rate limit, hub-side handling) and are not comparable with the
in-container HTTP figures of run 1.

### stdio drain (entry disabled while calls were in flight)

The stdio entry was disabled through the hub API while `wled_get_effects` (refresh) calls
were in flight.

| Check | Result |
| --- | --- |
| Calls finished before the disable | 3, normal results |
| Calls in flight at the disable | 2, answered by the hub with "ProtocolError, Connection closed"; the client cannot tell the server-side outcome |
| Later calls | "Tool not available" |
| Process exit | the stdio Python process was gone 0.88 s after the disable; no stdio process left |

Finding: in stdio mode the host (here the hub) owns the subprocess lifecycle. On disable
it closed the connection without draining in-flight calls. Whether and when the server
process received a signal is not recorded; with the connection closed, a result could
not reach the client in any case, so the server's own SIGTERM drain (T21) does not help
at the host level. ISSUE-12-DEC-006 accepts this host behavior as a documented
limitation of stdio mode (Streamable HTTP is the preferred mode; no code change). The
calls in this check were reads; an
in-flight write cut off this way is possibly applied, so a client has to read the state
before retrying it (see [DEPLOYMENT.md](DEPLOYMENT.md#stdio-via-uvx-register-update-rollback-rebuild-removal)).

### Cleanup and restoration (R1-R3)

The temporary stdio entry was removed (only that entry), the HTTP entry was re-enabled
by its admin owner, and the temporary hub system key was removed. The controller was
restored by activating the pre-existing preset 1 and switching off.

| Check | Result |
| --- | --- |
| R1 preset file | JSON-equal to the run-2 baseline (only preset 1); bytes grew from 3,770 to 6,105 because the firmware blanks deleted entries with spaces instead of compacting the file |
| R2 state | byte-identical to the run-2 baseline |
| R3 configuration | byte-identical to the run-2 baseline |

### Not run

- H07 offline device on hardware (simulated evidence T02/T09 remains).
- Controller reboot and power-cycle persistence (ISSUE-12-DEC-002 TD-12-3).
- stdio load beyond the hub's rate limit, and per-request stdio latency without the
  hub (no direct client for the hub-managed subprocess).
- Visual comparison with the WLED UI (H02); the visual checks above covered the LEDs.
- Interference inventory and quiet windows were not repeated for this run (run 1 I1-I3);
  the run-2 state baseline equals the run-1 end state.
- Restoring preset contents from a snapshot (ISSUE-8-DEC-001); other controllers and
  firmware; live update/rollback between versions (stage 2).

The visible effect, speed and brightness-transition items and the scope of the remaining
items were settled afterwards in
[run 3](#issue-12-hardware-acceptance-run-3-2026-11-06) and ISSUE-12-DEC-007.

## Issue #12 hardware acceptance, run 3 (2026-11-06)

A short owner-watched run on the same day, on the same test controller, through the
deployed Streamable HTTP service and its hub entry, authorized for this run only by
ISSUE-12-DEC-007 item 2 (capture before, restore after; ISSUE-12-DEC-001 conditions). It
covers the visible H04 behavior that runs 1 and 2 did not observe: effect animation, a
speed change and a brightness transition. The owner watched the strip and replied to
each step. Authorization basis for E3: the owner's agreement covered the visible H04
behavior of this run, and the owner explicitly asked for the repeats of E3 (first fully
bright and then dimming, then with a single color). Sanitized from a local, git-ignored
run record; host names, addresses, paths,
user names, device and hub entry names are intentionally omitted. The results describe
this one controller and this one firmware (WLED 16.0.1, one RGB-only strip, current
limiter configured at 850 mA) only; no compatibility with other firmware, controllers or
LED types is claimed.

```text
Date / operator / source commit: 2026-11-06 / project coordinator agent under the owner's
  authorization / the HTTP deployment as left by run 2 (built from main commit b36f410);
  run 3 made no deployment, service, hub or inventory change
Package / Python / SDK / hub runtime: as run 2
Transport mode / endpoint or uvx artifact / service lifecycle: Streamable HTTP through the
  hub's HTTP entry; no service stop/start
Sanitized device and firmware / relevant capabilities: as run 1 H01 (WLED 16.0.1,
  ESP32-C3, 133 RGB LEDs, one bus, current limiter 850 mA)
Scenario IDs run: P0, E1-E3 (H04 visible behavior), R1-R3
Before state and snapshot references (local, no secrets): run-3 baseline of state,
  configuration and preset file in the local run record
Expected and observed results: tables below
Restoration performed and verified: R1-R3 below
Not run / reason / remaining risk: "Not run" list below
```

### Visible effect, speed and brightness transition (E1-E3)

Every write was a typed tool call through the hub's HTTP entry (segment fields as a
segment patch, master fields as a master state change) and was applied and verified by
the tool's readback unless stated otherwise: the E1 and E2 patches and master writes,
every E3 write including the setup writes of attempts 2 and 3 and the re-issued
dimming write, and the restoration writes. The only exception is the first dimming
call of attempt 2 (`TIMEOUT`, see below).

| Check | Command | Owner's observation (translated) |
| --- | --- | --- |
| E1 | segment 0 patch: effect ID 9 (Rainbow), speed 30; master on, brightness 120 | "yes": a slowly moving rainbow |
| E2 | segment 0 patch: speed 240 only | "faster, clearly" |
| E3 attempt 1 | master brightness 30 with `transition_ms` 3000 (rainbow) | no dimming visible |
| E3 attempt 2 | master brightness 200 without transition, then on the owner's signal brightness 30 with `transition_ms` 5000 (rainbow; see the TIMEOUT note below) | no dimming visible |
| E3 attempt 3 | segment 0 solid red (effect ID 0); master brightness 80 (power estimate at the cap), then 40 (below the cap), both without transition; then on the owner's signal brightness 2 with `transition_ms` 5000 | "yes, gently became darker" |

Results:

- E1 and E2: visible effect animation and a visible speed change of one effect
  confirmed by the owner.
- E3: a brightness transition confirmed by the owner (attempt 3, solid red dimming over
  5 s). A visual intensity change was not part of this run and is not needed for #12
  per ISSUE-12-DEC-008 (verified intensity readback in run 1 H04 plus the visible speed
  change E2); it is not claimed as visually observed.
- Why attempts 1 and 2 showed no dimming (analysis, not a measurement): the most
  likely cause is the controller's current limiter (ABL) capping the output, which
  compresses the visible range of the dim. Run 3 read the power estimate only twice:
  850 mA (the configured limit) for solid red at brightness 80, and 645 mA, below the
  cap, for solid red at brightness 40. No power reading was taken for the rainbow in
  run 3; run 1 read 850 mA for the rainbow at another brightness (see
  [run 1 H04](#h04-master-and-one-effect-writes)). Above the cap the limiter scales
  the output, so a requested brightness change can be barely visible although state
  and readback are correct; dimming solid red from below the cap was visible.
  Visual brightness and transition checks therefore have to start below the cap (see
  the H04 note under [Opt-in physical write checks](#opt-in-physical-write-checks)).

### TIMEOUT before dispatch (E3 attempt 2)

The first call of the dimming write in attempt 2 (brightness 30, `transition_ms` 5000)
returned `TIMEOUT` with application `not_attempted`: the operation deadline had expired
before the write was dispatched. A direct state read showed the brightness unchanged at
200 (the controller answered in 0.18 s), so the write had not been applied. After that
read, the same write was issued once more as a new, deliberate call (not a blind replay
of a possibly applied write) and was verified. The service and hub logs had no
corresponding lines; the cause of the expired deadline is unknown.

### Restoration (R1-R3)

The controller was restored by activating the pre-existing preset 1 and switching off.
Run 3 made no preset writes.

| Check | Result |
| --- | --- |
| R1 preset file | byte-identical to the run-3 baseline |
| R2 state | byte-identical to the run-3 baseline |
| R3 configuration | byte-identical to the run-3 baseline |

### Remaining #12 items after run 3 (ISSUE-12-DEC-007)

| Item left open after run 2 | Resolution |
| --- | --- |
| H02 comparison with the WLED UI | satisfied by the comparison with the controller endpoints the WLED UI renders ([run 1 H02](#h02-reads)), per ISSUE-12-DEC-007 item 1 |
| H04 visible effect animation, speed and brightness transition | E1-E3 above (HTTP), authorized by ISSUE-12-DEC-007 item 2 |
| H04 in stdio mode | sufficient as exercised in run 2 (power/brightness rules, and verified color and effect writes: layout replacements that set segment colors and one effect, and a segment patch that changed a color and the speed while preserving the other segments), same domain code, per ISSUE-12-DEC-007 item 3 |
| stdio drain on SIGTERM | the host-level record of run 2 is sufficient, per ISSUE-12-DEC-007 item 4 and ISSUE-12-DEC-006 |
| stdio load beyond the hub's rate limit and without the hub hop | not required for #12; the rate-limited figures through the hub of run 2 are sufficient, per ISSUE-12-DEC-007 item 5 |
| H07 offline device on hardware | moved to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)) per ISSUE-12-DEC-007 item 6; the simulated evidence T02/T09 remains |

### Not run

- A visual intensity change (not part of this run; not needed for #12 per
  ISSUE-12-DEC-008, which accepts the verified intensity readback of run 1 H04 plus the
  visible speed change E2).
- stdio mode in this run (HTTP only, per ISSUE-12-DEC-007 item 2).
- H07 offline device on hardware (stage 2,
  [#25](https://github.com/descipar/wled-mcp/issues/25)).
- Controller reboot and power-cycle persistence (ISSUE-12-DEC-002 TD-12-3); restoring
  preset contents from a snapshot (ISSUE-8-DEC-001); other controllers and firmware;
  live update/rollback between versions (stage 2).
- The cause of the `TIMEOUT` before dispatch was not investigated in this run.

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

## Stage 2 and later files

- [validation/issue-16.md](validation/issue-16.md): setup, `config validate` and
  read-only `doctor` commands (#16, mock evidence).
- [validation/issue-17.md](validation/issue-17.md): device groups, scenes, the plan and
  sharing (#17, mock evidence).
- [validation/issue-18.md](validation/issue-18.md): preset restore, supplied-state save,
  snapshot listing, playlist authoring and preset bundles (#18, mock evidence).
- [validation/issue-19.md](validation/issue-19.md): capability model, WLED 16 segment
  fields, CCT and 2D layouts (#19, mock and source evidence).
- [validation/issue-20.md](validation/issue-20.md): tool profiles, per-device maximum
  class, the guard layers, correlation IDs, call logs and the status tool (#20, mock and
  loopback evidence).
- [validation/issue-21.md](validation/issue-21.md): version source, non-release builds,
  the CI matrix and the compatibility policy (firmware tiers, contract snapshot,
  upgrade compatibility) (#21, #70).
- [validation/issue-22.md](validation/issue-22.md): PyPI publish workflow, release guard and
  local build, metadata and smoke checks of the built files (#22, local evidence; nothing
  published).
- [validation/issue-24.md](validation/issue-24.md): registry metadata, listing drafts, local
  schema validation and the 0.2.0 release preparation and publication (#24). The 0.3.0 preparation is recorded in
  [validation/release-m2.md](validation/release-m2.md) (preparation and the publication record of 2026-11-11).
- [validation/issue-29.md](validation/issue-29.md): static SVG layout preview, structural and
  golden renderer tests, planner reuse, bounds and stdio/HTTP parity (#29, mock and loopback
  evidence; no hardware).
- [validation/issue-30.md](validation/issue-30.md): evidence-separated lighting explanation,
  process-local control evidence, read-only guarantees and parity (#30, mock and loopback
  evidence plus one read-only live run on the test controller; no write path on hardware).
- [validation/issue-134.md](validation/issue-134.md): hardware check of groups, scenes, presets,
  bundles, restore and a playlist on the test controller (#134).
- [validation/issue-147.md](validation/issue-147.md): agent instructions, static prompt
  and nested schema guidance over stdio and HTTP (#147; MCPHub check pending).
- [validation/issue-148.md](validation/issue-148.md): parsed effect metadata, conservative
  filters and pinned-source fixtures (#148; read-only hardware probe pending).
- [validation/issue-149.md](validation/issue-149.md): effect and palette names in segment
  tools, whole-request no-write failures and resolved-ID readback (#149, mocks/loopback).

- [validation/issue-150.md](validation/issue-150.md): bounded live snapshot decoding,
  mapping, transport/profile parity and selected-controller unavailable response (#150).
- [validation/issue-25.md](validation/issue-25.md): live H07 check with an unreachable configured
  controller on the deployed HTTP service (#25; read-only, temporary inventory entry).
