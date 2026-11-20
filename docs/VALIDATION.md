# Validation and acceptance plan

Evidence added from stage 2 on lives in per-issue files under `docs/validation/`, listed at the
[end of this document](#stage-2-and-later-files); see
[where new documentation goes](AGENT-WORKFLOW.md#where-new-documentation-goes).
[TRACEABILITY.md](TRACEABILITY.md) maps every Must requirement and T01-T21 to the automated tests and
scripts and keeps hardware/deployment evidence visibly pending; `scripts/check_traceability.py`
enforces it in CI. The sections below are historical per-candidate records: they state the result
recorded for that candidate and are not re-executed. The wall-clock flake
`test_one_total_deadline_and_bounded_read_retry` is superseded by the controlled-time test from #55;
the failing Windows `test_stdio_ignores_ambient_http_token_and_binds_nothing` noted for #48/#52 is
superseded by the socket guard from #53. Hardware acceptance for #12 is recorded for one controller
and one firmware (WLED 16.0.1) in three runs, without a compatibility claim beyond them; live H07
moved to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25), ISSUE-12-DEC-007 item 6);
the simulated T02/T09 evidence remains. The items in the runs' "Not run" lists remain pending.

Bootstrap mapping: C3-01/02/08 -> distribution/lock scripts; C3-03/04/07 -> startup/CLI tests;
C3-05/06 -> console/fixture subprocess and outcome tests; C3-09 -> CI; C3-10 ->
[DEVELOPMENT.md](DEVELOPMENT.md).

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
| T12 | Snapshot format/version/source/device/preset/firmware/path validation, exact unknown-field retention, atomic durable backup and safe retention. Backup failure prevents overwrite/delete; changed prior object aborts before overwrite. Restore execution (Should) uses one verified single-entry write with a documented live effect (#18, [validation/stage-2-core.md](validation/stage-2-core.md)); no bulk shortcut or claimed restore acceptance from export | PRE-04 |
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
  Hardware acceptance is partial: one RGB controller on WLED 16.0.1 in both transports and one
  deployment of both modes on one MCPHub host. The live offline-controller check (H07) ran once on
  the deployed HTTP service against a non-routed address ([validation/hardware-checks.md](validation/hardware-checks.md));
  reboot persistence and the other "Not run" items are pending. No compatibility with other
  controllers or firmware is claimed. A short live check of the second release over HTTP and stdio is in
  [validation/hardware-checks.md](validation/hardware-checks.md).
- A hardware run of the stage-2 features (WLED 16.0.1, one RGB segment, HTTP service on the hub)
  covered a one-device group and scene, preset store, export, import and restore with snapshots on
  unused slots, and one single-entry playlist; every write was verified and the controller state,
  segment and preset list were restored ([validation/hardware-checks.md](validation/hardware-checks.md)). Four
  snapshots remain in the service data directory (no snapshot-delete tool). Not run on hardware:
  multi-device scenes, tool profiles, `discover`, restore onto an occupied slot, playlist import and
  restoring a playlist preset. Advanced segment fields (CCT, RGBW, 2D) have mock and loopback evidence only.
- Of the newer features, a read-only run covered the effect metadata and one effect search; one
  read-only explanation call ran, and the live colour snapshot reported the endpoint unavailable
  (HTTP 501), so no positive snapshot was observed. Zones, name resolution in segment writes, the
  served guidance and the layout preview have mocked or local-client tests only.
- Storing, restoring or importing a preset without changing the live output is not possible on
  WLED 16, and saving a playlist starts it. Imports do not rescale LED ranges or convert matrix
  layouts and import one playlist per call ([#18](https://github.com/descipar/wled-mcp/issues/18), closed).
- CCT, grouping, mirror and 2D coordinates are written only when the device reports the capability;
  segment `rpt` and `fxdef` and matrix/panel configuration are not exposed, and there is no raw state
  patch tool ([#19](https://github.com/descipar/wled-mcp/issues/19), closed).
- No inventory reload; changes need `wled-mcp config validate` and a restart
  ([#16](https://github.com/descipar/wled-mcp/issues/16), closed).
- No device authentication. The official WLED documentation states that anyone with a controller's
  IP and port can control the lights ([OTA lock](https://kno.wled.ge/advanced/ota-lock/)), describes the
  settings PIN as protecting the settings pages and the OTA lock as protecting firmware updates
  ([settings](https://kno.wled.ge/features/settings/)), and says nothing about the JSON API or presets
  under these locks. The server sends no device credentials and rejects credentials in a device URL, so
  a controller behind HTTP authentication or a credentialed proxy is not supported. On one controller
  (WLED 16.0.1) with the settings PIN, the OTA lock or both enabled, five read probes and a minimal
  write set (master state, segment patch, preset store and delete) worked unchanged; other writes under
  a lock were not run ([#128](https://github.com/descipar/wled-mcp/issues/128),
  [validation/hardware-checks.md](validation/hardware-checks.md)).
- One writer per controller: locks are per process, so a second process or service against the same
  devices is not coordinated.
- In stdio mode the MCP host may stop the subprocess without waiting for a running call; a write
  interrupted that way stays uncertain.
- `tools/list` was CPU-heavy on small hosts (about 270 ms CPU per call on the single-board target with
  27 tools); since release 0.1.2 the schemas are built once per server (about 23 ms,
  [#67](https://github.com/descipar/wled-mcp/issues/67), closed).
- No container image on GHCR; releases are distributed on PyPI and listed in the official MCP Registry.
  Tests check that the current server reads retained data of earlier releases and rejects newer data
  versions without changing files; an older server reading newer data is not tested
  ([versioning](contract/versioning.md#upgrade-downgrade-and-rollback)). A live update of the deployed
  HTTP service was checked once (earlier build to the second release); one rollback to the previous
  release and back was checked once, without a data-format change
  ([launch report](validation/releases.md#3-upgrade-and-rollback-evidence),
  [#25](https://github.com/descipar/wled-mcp/issues/25)); a rollback after the next code-changing release
  is not checked.

## Issue-2 contract traceability

C2 IDs are acceptance criteria for documentation delivery, not runtime tests.
All refer to [TOOL-CONTRACT.md](TOOL-CONTRACT.md) and the
[scoped decisions](decisions/stage-1.md). Synthetic JSON parse/consistency checks
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
| C2-10 | Application/verification table, envelope/text/isError parity, conflict and [uncertainty](../examples/contracts/errors.json) | T08–T14/T18; #3/#6/#7/#9/#10/#14 |
| C2-11 | Explicit transport, stateless SDK lifecycle, shared resources, disconnect/drain semantics | T18/T19/T21; #3/#14/#10/#11 |
| C2-12 | Direct endpoint auth, exact Host/Origin checks, 401/403, no proxy bypass | T20; #14 implementation, #10 software acceptance, #11 integration |

MCP-03/MCP-04/OPS-05 map to #14 implementation, #10 T18–T21 acceptance, and #11
integration/deployment evidence. H02/H03 remain separate authorized operational
checks. The SDK version is selected (MCP SDK 2.3.0) and mocked/loopback protocol
execution is automated (see [TRACEABILITY.md](TRACEABILITY.md)); hardware
compatibility and deployment remain pending. PRE-03 and restore execution are Should work
added by #18 (mock evidence in [validation/stage-2-core.md](validation/stage-2-core.md)); durable
backup before destructive operations remains Must.


## Read-only hardware checks

- H01: record selected device alias, firmware, LED count, RGB/RGBW/CCT and segment capabilities from real responses; sanitize any committed fixture.
- H02: read state/catalogs/presets from the actual execution context (HTTP service/container, or the hub-managed stdio process), then through MCPHub; verify hub-to-service authentication when HTTP is used; compare IDs/names and capability interpretation with the WLED UI. No discovery scan or state write.
- H03: start/restart the HTTP service or stdio entry, record mode, startup and idle memory, diagnostics/protocol separation and persistent paths; HTTP reconnect and liveness. Hub/container recreation is a distinct check and stays pending if not performed. One deployed mode does not claim the other.

## Opt-in physical write checks

Use an explicitly authorized device and test ranges/slots; record the pre-test state and preset snapshots; an animated state is not restorable frame-for-frame (preserve configuration, note limits); do not edit existing presets when an agreed unused slot works.

- H04: change power/brightness/color and one effect's speed/intensity; verify state and visible behavior; restore. Visible brightness and transition checks must stay below the controller's current-limiter (ABL) cap: when the power estimate (`leds.pwr` in `/json/info`) is at the configured limit the limiter scales output down, so a change above the cap is barely visible although state and readback are correct. Choose an effect, color and brightness below the limit (for example a solid color at low brightness) and dim from there.
- H05: patch one segment, confirm unrelated segments unchanged; replace with an agreed small layout, verify stale IDs removed, restore. Account for timers, other API clients, playlists or realtime inputs; never disable them silently.
- H06: save to an agreed unused preset ID, activate, read back, test explicit overwrite with snapshot, delete the slot, test restoration if authorized; confirm persistent data.
- H07: observe an already unreachable target or approved test method; do not unplug production devices or change networking. Simulated transport tests can cover disruptive scenarios.

## Software evidence by issue (#4 to #53)

Historical per-candidate records (mock/loopback only; no LAN device; hardware pending unless stated). Executed claims per candidate are in the PR; the per-criterion test tables (C4/C5/C11/C14/AC-10/AC-48/AC-52 IDs) were condensed in #260 and survive only in history (`git show 7d2328d:docs/VALIDATION.md`); the tests themselves and [TRACEABILITY.md](TRACEABILITY.md) carry the current mapping.

| Issue | Candidate result recorded | Scenarios / criteria | Limits |
| --- | --- | --- | --- |
| #4 inventory and client | 2026-11-04, Windows/Python 3.13.2, MCP SDK 2.3.0: 80 tests passed; ruff, strict mypy, lock, agent setup, offline wheel/clean install/uvx (30 runtime versions) passed | C4-01 to C4-10; T01, T02, T09, T10, T14-T16 | Mocked writes do not establish firmware acceptance; HTTP T18-T21 not yet |
| #5 state and catalogs | 2026-11-04, same platform: 194 passed (3 runs); ruff, mypy 12 files, lock, distribution passed | C5-01 to C5-10; T02, T03, T14, T15 | Firmware facts from pinned source, not a controller; H01/H02 not run; OPS-04 partial |
| #6 segment patch | 2026-11-04: 219 passed (flaky deadline test deselected); mypy 13 files | C2-01, C2-03 to C2-06, C2-10; T04, T06-T10 | H04/H05 not run; mock POST handlers model profile 0 of the pinned source; the off-master brightness payload is superseded by #52 |
| #7 layout replace | 2026-11-05, macOS/Python 3.13: 316 passed (70 new); distribution PASS | C2-02 to C2-06, C2-10; T05-T10 | H05 not run; source-derived fake; the name, 255-bound and `bri` limits are superseded by #48 (ISSUE-7-DEC-003 to -007) |
| #8 snapshots, #9 presets | mock/tmp_path only | T12 (format, atomic durable write, retention, backup-failure gives zero POSTs); T11-T13 (list/read, activation, allocation/save, delete, verification, uncertainty); `examples/contracts/presets.json` and the `backup_failure` case in `errors.json` are actual #9 tool output reproduced by `tests/test_presets.py` (which contract examples are actual output and which are synthetic: see [their README](../examples/contracts/README.md)) | H06 not run; real flash-write timing, post-delete layout, active-preset marker and playlist behavior not established by mocks; restore tool added by #18 |
| #48 shared segment limits | 2026-11-05, Windows 11: 540 passed, 9 skipped, 1 failed (the Windows socket-guard test, identical on the base commit, fixed by #53) | AC-48-01 to AC-48-12 (32 UTF-8 byte names, grouping/spacing 255, `brightness=0` rule, power compensation, patch/replace parity); the new tests fail on the base commit | Per-build name buffer, `grp`/`spc` overflow and a visible blip on `{bri, on:false}` unverified (#12) |
| #52 master power | 2026-11-05: 563 passed, 9 skipped, 1 failed (same Windows test); 168 in patch/layout modules | AC-52-01 to AC-52-12 (off master + positive brightness sends `on:false`; every master write verifies resolved `on`); 12 new tests fail on the base `patches.py` | Visible blip, `tt` consumption, `ps` change unverified; external power change between read and POST is a residual risk |
| #14 HTTP service | 2026-11-05, macOS/Python 3.13: 246 passed (27 new HTTP tests); distribution PASS (29 runtime versions) | C14-01 to C14-11; T16, T18-T21 (SDK client list/call, stdio/HTTP parity, shared lock/cache, 60-case access matrix, 48 startup failures, disconnect/drain/forced shutdown, listener-free stdio) | No deployment, resource measurement or hardware; Windows signal delivery, TLS, rate limiting, per-user authorization, multi-worker coordination not covered |
| #53 stdio socket guard | Windows 11, CPython 3.13.2: the old stdio check failed on the Proactor loop self-pipe (`socket._fallback_socketpair` bind/listen/connect on loopback port 0), not on product code; ISSUE-53-DEC-001 changed the test, not the product, with no skip or xfail. The positive run records only the three allowed self-pipe operations; 9 negative controls are refused before the OS call | T20, T16 | Code calling `_socket`/`_overlapped` directly, Windows named pipes, macOS and other Python versions are not guarded/checked; Linux CI is the second platform |
| #10 acceptance | 2026-11-05, Windows 11: 707 passed, 9 skipped (POSIX-only); 131 passed in the new parity/verification/traceability modules in 3 runs; `check_traceability` 26 Must requirements and T01-T21 mapped; distribution PASS (30 versions, two HTTP start/stop cycles) | AC-10-01 to AC-10-08 (stdio/HTTP result parity, 401/401/403 before device work, loopback:8000 default, tolerance/mismatch tests, hub example handshake) | H01-H07, H02/H03, deployment, hub integration, T17/raw state (ISSUE-13-DEC-001) and restore execution (deferred to #18) pending |
| #11 deployment artifacts | 2026-11-06, macOS arm64/CPython 3.13.2: 745 passed, 1 skipped (opt-in Docker check), 8 subtests; distribution PASS incl. the stdio hub example; opt-in Docker compose check passed locally; local image checks (user `10001`, 183 MB, checksum step rejects missing/modified inputs, planted secrets absent from the image, compose healthy, 401/403/200 as designed, idle 53 MiB, stop 0.52 s exit 0) | C11-01 to C11-14 | Local developer machine, not target measurements; deployment, hub registration, H02/H03, update/rollback and Linux x86-64 build were pending then (see the live check below) |


## Issue #11 live deployment check (2026-11-06)

One authorized live check of both modes on one target (ISSUE-11-DEC-003) with follow-ups on the same target
(ISSUE-11-DEC-006, -007), sanitized from a local, ignored run record; host names, addresses, paths, user
and device names and image IDs are omitted. Target: aarch64 single-board computer, Docker, MCPHub 1.2.1 in
its own Compose project, `uvx` 0.13.7 and Python 3.13.18 in the hub container. Release wled-mcp 0.1.0 staged
from commit `0da1249` (clean tree) on a build machine; `sha256sum -c SHA256SUMS` matched on the target. Device
operations: reads and master power on/off on one authorized controller only.

### Streamable HTTP service

Image build on the target (arm64, user `10001`, 183 MB); authenticated in-container `ping` 200, wrong Host 403,
missing credential 401, no `Mcp-Session-Id`; 12 tools, `tools/list` p50 105 ms; recreation: stop 1.09 s exit 0,
start to listening 6.67 s; idle RSS about 72 MiB, 1 thread. Hub registration was first refused by the hub's SSRF
guard (entry owner `system`) and connected after setting an admin owner and reloading the entry
([DEPLOYMENT.md](DEPLOYMENT.md#mcphub-notes)). Through the hub: `initialize` 175 ms, 12 tools, `wled_list_devices`,
`wled_get_state`, and `wled_set_state` on then off, each verified by readback and the original state restored; a
service restart needed no hub action (stateless reconnect).

### stdio via uvx

Hub entry with the arguments of [mcphub.example.json](../examples/mcphub.example.json); cold first launch 9.6 s
including 29 packages, warm reload 3.45 s; idle RSS 67 MiB (3 threads) plus `uv` wrapper 27 MiB, uv tree 49 MB;
0 listening sockets; reload leaves one instance; through the hub `wled_list_devices` reached the controller and
`wled_set_state` on/off verified and restored. Removal (ISSUE-11-DEC-004) deleted only the stdio entry; hub data,
uv cache and staged release were retained.

### HTTP service removal and redeploy (ISSUE-11-DEC-006)

Following [DEPLOYMENT.md](DEPLOYMENT.md#http-service-update-rollback-recreation-removal), hub configuration backed
up first: only the HTTP hub entry deleted; `docker compose ... rm --stop --force wled-mcp` 1.27 s; `docker image rm
wled-mcp:0.1.0`; hub container not restarted, other containers unchanged. Retained: data directory with inventory
and credential file, and the staged release directory. Redeploy from the retained release (checksums matched, identical
image ID, `ping` 200, 403, 401) and hub re-registration (admin owner, reload) worked. No device writes.

### Catalog/preset reads, stdio rebuild and hub container recreation (ISSUE-11-DEC-007)

Same target and controller, hub configuration backed up and a restorable controller baseline recorded first. No
device writes were needed or performed. H02 reads through the hub in both modes succeeded: `wled_list_devices` probe
reachable, `wled_get_state`, `wled_get_effects` (HTTP: 220 effects), `wled_get_palettes` (HTTP: 72), `wled_list_presets`
(one state preset, ID 1), `wled_get_preset` 1; stdio calls took 133-520 ms. HTTP-mode counts match the controller's own
catalog endpoints (`/json/eff`, `/json/pal`) that the WLED UI reads (a data-source comparison, not a visual UI
inspection; stdio counts not recorded separately). Fail-safe observation: one HTTP-mode effect refresh got a truncated
`/json/fxdata` body; the server returned the complete names, reported metadata unavailable (`INVALID_RESPONSE`) with a
warning, and the retry returned the metadata (matches `test_optional_fxdata_failure_keeps_names_and_succeeds`).
stdio re-registration connected in 3.7 s; the environment rebuild (entry disabled, only the 49 MB uv cache deleted,
entry enabled) connected in 9.2 s with 12 tools. Hub container recreation (hub service only, same image before and
after): Compose 14.7 s, hub ready 25.1 s, hub outage about 30 s; HTTP entry reconnected 3.1 s after `initialize` with the
admin owner persisted; stdio entry reconnected about 26 s later without a download (the uv tree (49 MB) survived); HTTP
service container not restarted; all entries present. Final controller state and preset file were identical to the baseline.
Mode remaining active: Streamable HTTP (ISSUE-11-DEC-004). Findings fed back into
[DEPLOYMENT.md](DEPLOYMENT.md#mcphub-notes): the entry-owner requirement and reload step, RSS measurement without a memory
cgroup, and RFC 1123 host labels in `base_url` ([#61](https://github.com/descipar/wled-mcp/issues/61)).

Moved to stage 2 per ISSUE-11-DEC-005: live update and rollback between two releases (only 0.1.0 existed), tracked by
[#21](https://github.com/descipar/wled-mcp/issues/21) (S2-COMPAT-03) and [#25](https://github.com/descipar/wled-mcp/issues/25)
(S2-LAUNCH-01).

Moved to #12 per ISSUE-11-DEC-008: graceful drain of an in-flight call on the target and load measurements (parallel calls,
peak connections, largest body), tracked by [#12](https://github.com/descipar/wled-mcp/issues/12); the automated drain
coverage (T21) remains the #11 evidence for the drain behavior.

Not exercised and still pending in this run: H02 reads from the server's own execution context and a comparison of capability interpretation with the WLED UI (both covered later by #12 run 1), any other device, preset or segment writes, and H01/H04-H07 (#12).

## Issue #12 hardware acceptance (2026-11-06)

One authorized run on one test controller (ISSUE-12-DEC-001) and the deployed Streamable HTTP service of #11 (stop/start
and load per ISSUE-12-DEC-003, confirmed retroactively by the owner for this run only), with the technical defaults of
ISSUE-12-DEC-002; sanitized from a local, ignored run record (no host names, addresses, paths, MACs or image IDs). Results
describe this one controller and firmware only. Source: wled-mcp 0.1.0 image from commit `0da1249`; load/drain client
`scripts/hw_http_probe.py` from `119229d`; Python 3.13.18, mcp 2.3.0, aarch64. Mode: Streamable HTTP only (TD-12-1). Scenarios
run: P0, I1-I3, H01, H02 (own context), L1-L6, D1, D2, H04, H05, H06, R1-R3.

### P0 baseline and interference (I1-I3)

Baseline read directly from the controller; preset slots 2 and 250 free, only preset 1 (state) in the file, no realtime input. Three
state reads 30 s apart were equal before the first write and after restoration. Interference sources were read only and left as found
(timers off, boot preset 1, UDP sync receive on, another WLED node visible, E1.31/DDP enabled but idle, Alexa on, MQTT/Hue off, one
WebSocket client); they were not monitored continuously.

### H01 device facts

| Fact | Result |
| --- | --- |
| Firmware | WLED 16.0.1 (outside the pinned v0.15.1 source review; the server has no version gate, so every result is an observation for 16.0.1 only) |
| Platform | ESP32-C3 |
| LEDs | 133 RGB LEDs on one bus; RGB only (no white channel, no CCT); 1D (no matrix in info) |
| Segments | segment limit 32; one active segment in the baseline |
| Power limiter | automatic brightness limiter configured |
| Catalogs | 220 effects, 72 palettes |
| Locks | OTA lock and Wi-Fi settings lock off in the before and after configuration captures of runs 1-3; settings PIN state not captured; no WLED API read or write refused by the controller in runs 1-3 (the #66 activation refusal came from this server, the run-3 `TIMEOUT` occurred before dispatch) |

### H02 reads

From the service's own execution context (authenticated client inside the container): `wled_list_devices` reachable; `wled_get_state`,
`wled_get_effects` (220 names), `wled_get_palettes` (72), `wled_list_presets` (preset 1) and `wled_get_preset` 1 / 250 (stored object /
`PRESET_NOT_FOUND`) equal the controller's own `/json/state`, `/json/info`, `/json/eff`, `/json/pal` and `/presets.json` (MAC, address, BSSID
redacted). This compares with the WLED UI's data sources, not a visual UI inspection. Reads through the hub for both modes are the
[#11 records](#issue-11-live-deployment-check-2026-11-06); in stdio mode the hub-managed process is the execution context
(ISSUE-12-DEC-002 TD-12-6).

### H03 load (L1-L6) and drain (D1-D3), Streamable HTTP

Client in the service container, one TCP connection per request, latencies in ms.

| Check | Result |
| --- | --- |
| L1 idle | RSS 73,740 KiB, 1 thread; peak 76,512 KiB during bursts |
| L2 `ping`, concurrency 1 / 4 / 16 | 167 / 195 / 201 requests/s; p50 5.3 / 19 / 76; all HTTP 200 |
| L2 `tools/list`, concurrency 1 / 4 / 16 | about 9 requests/s; p50 106 / 425 / 1717; about 108 ms CPU per call, so CPU-bound and concurrency only queues ([#67](https://github.com/descipar/wled-mcp/issues/67)) |
| L3 `wled_get_state` c1 / c4 | 13 / 13.4 requests/s; p50 67 / 282 (per-device lock serializes reads); `wled_get_effects` (cached) c4 19.4 requests/s, p50 201 |
| L4 peak concurrent connections | not sampled in run 1 (see run 2) |
| L5 sockets after disconnect | 2 listening, 4 in TIME-WAIT, none established |
| L6 request-body bound | 262,143 bytes: HTTP 200; 262,145 bytes: HTTP 413 |
| D1/D2 SIGTERM drain (`compose stop`, grace 130 s) | attempt 1 invalid as a drain sample (client started after the stop; idle stop 1.26 s exit 0); attempt 2: in-flight and just-admitted reads completed with HTTP 200, later calls refused, stop 1.99 s exit 0, start to listening 6.30 s |
| D3 in-flight write | not run (read-only probe); automated coverage T21; see run 2 |

Caveat: the reference time is the `compose stop` CLI timestamp, not SIGTERM receipt, so only the last in-flight call is certainly in flight at the signal.

### H04 to H06 (writes)

- H04: `on` with brightness 0 rejected (`VALIDATION_ERROR`, no write); brightness only while off keeps the master off (compensation `on:false`, ISSUE-52-DEC-001); `on` with `transition_ms` 1000 sent wire transition 10 with the persistent transition untouched; segment 0 color slot 1 and effect 9 / speed 200 / intensity 100 applied and matched on readback; `/json/info` reported 850 mA (limiter cap) and 43 fps. Observation: the dry-run `resolved_segments` listed only the supplied color slot, shorter than the device result; the write was correct.
- H05: `wled_replace_layout` dry run and live to two segments [0,66) and [66,133) matched on readback, master unchanged; a segment 1 patch left segment 0 unchanged; the original layout was restored by activating state preset 1, so stale-ID removal was not exercised here (done in run 2).
- H06 (slot 250): save, conflict without `overwrite`, overwrite after snapshot, lowest-free allocation (ID 2), delete 250 and 2 after snapshots, repeated delete `PRESET_NOT_FOUND`, all verified by readback. WLED 16 stores an extra top-level `bs` key, so the saved entry was classified `unknown` and `wled_activate_preset` 250 was refused with `UNSUPPORTED_CAPABILITY` ([#66](https://github.com/descipar/wled-mcp/issues/66)); activation was exercised only with pre-existing preset 1. The #66 fix (ISSUE-66-DEC-001) was mock-tested here and re-checked in run 2. Three snapshot files (mode 0700/0600) remain on the target; restoring from a snapshot was not run (ISSUE-8-DEC-001).

### Restoration (R1-R3)

R1 preset file JSON-equal to the baseline (bytes differ, 713 to 3,770, because the firmware blanks deleted entries and the API has no whole-file upload); R2 state and R3 configuration byte-identical; quiet window of three equal reads.

### Not run

- Visual check of the LEDs and the WLED UI (agents cannot see the LEDs; readback and the power/frame-rate proxy only).
- D3 drain of an in-flight write on the target; L4 peak concurrent connections.
- stdio mode in this run: stdio drain, load and H04-H06 (HTTP only per ISSUE-12-DEC-002; stdio startup/idle and hub reads are #11 records).
- H07 offline device on hardware (no unreachable device in the inventory; simulated T02/T09 remains).
- Controller reboot and power-cycle persistence (ISSUE-12-DEC-002 TD-12-3).
- Activation of a preset saved by WLED 16 (blocked by [#66](https://github.com/descipar/wled-mcp/issues/66)); stale-ID removal on hardware; restoring preset contents from a snapshot (ISSUE-8-DEC-001).
- Other controllers and firmware, RGBW/CCT, 2D and multi-bus setups, playlists (none on the controller), live update/rollback (stage 2).

Several of these items were run later the same day in [run 2](#issue-12-hardware-acceptance-run-2-2026-11-06).

## Issue #12 hardware acceptance, run 2 (2026-11-06)

Second authorized run on the same day, controller and target, under ISSUE-12-DEC-005 (HTTP deployment update and stop/start, a temporary
stdio hub entry with the HTTP entry disabled, controller writes with capture and restore) and ISSUE-12-DEC-001; ISSUE-12-DEC-004 keeps stdio in
#12 scope, so both modes were exercised. The owner was within sight for visual checks. Sanitized; WLED 16.0.1 unchanged since
[run 1](#issue-12-hardware-acceptance-2026-11-06). Build: wled-mcp 0.1.0 from main commit `b36f410` (includes the #66 fix), MCPHub 1.2.1, staged under the ad-hoc
directory `0.1.0+b36f410` (a deviation from the documented procedure, identification scheme tracked by [#70](https://github.com/descipar/wled-mcp/issues/70));
the previous directory and image were kept as the rollback source. HTTP update: start to listening 7.53 s, the hub entry reconnected without hub action.
Scenarios run: P0, HTTP update, L4, D3, visual A-C, stdio H04-H06, stdio load, stdio drain, R1-R3.

### L4 and D3, Streamable HTTP

- L4 `ping` peak established connections followed client concurrency (16, 32, 64; about 200 req/s throughout, p50 76 to 307 ms, all HTTP 200), so more concurrency only
  queued; RSS at most 75,656 KiB; afterwards 2 listening, none established.
- D3 in-flight write: brightness-only `wled_set_state` calls on the off controller around the stop timestamp all returned HTTP 200 and were applied and verified;
  from +0.417 s connections were refused; no write reported `uncertain`; stop 1.42 s exit 0, start to listening 6.45 s. Caveat: the signal time is only bracketed
  (+0.242 s to +0.417 s); one write was probably in flight; no admitted write was cut off.

### Visual checks (owner)

The owner watched the strip and replied with delay; writes ran through the hub's HTTP entry and were verified by readback.

| Check | Command | Owner's observation (translated) |
| --- | --- | --- |
| A | segment 0 [0,66) red, segment 1 [66,133) blue via patch, replace and brightness 120 | "left blue, right red" (LED 0 is on the right from the owner's view) |
| B | `wled_replace_layout` to one green segment; stale segment ID 1 removed | "all green" |
| C | `wled_activate_preset` 250 (saved after A, classified `state`) | "left blue, right red" |

Results: the [#66](https://github.com/descipar/wled-mcp/issues/66) hardware re-check (save then activate on WLED 16.0.1, verified and confirmed visually) passed; H05
stale-ID removal on hardware passed (check B); colors, segment extents and preset recall were confirmed visually. Effect animation, speed, brightness level
and transition were not observed separately (run 3).

### stdio via uvx: H04-H06, load and drain

HTTP entry disabled; temporary stdio entry with the staged release connected after 8 s with 12 tools; all calls through the hub.

- H04/H05/H06 passed as in HTTP (brightness 0 rejected, master stays off, layouts two to one, one to three, three to one with stale IDs removed, segment patch leaving
  others unchanged, preset 250 conflict then overwrite after snapshot, activation, delete, repeated delete `PRESET_NOT_FOUND`); two snapshot files in the stdio data directory.
- stdio load through the hub (temporary hub key, removed afterwards): `ping` and `tools/list` are answered by the hub; MCPHub 1.2.1 returned HTTP 429 after about 200
  requests per window, so no load beyond that was possible; `wled_get_state` c1 4 req/s, p50 107; c4 2.2 req/s, p50 394; process RSS 77.5 MiB, 3 threads, no listening
  socket. The figures are shaped by the hub and not comparable with run 1.
- stdio drain: disabling the entry while `wled_get_effects` calls were in flight: 3 finished, 2 were answered by the hub with "ProtocolError, Connection closed"
  (server-side outcome unknown to the client), later calls "Tool not available", the process was gone 0.88 s after the disable. The host owns the subprocess lifecycle and does not
  drain; ISSUE-12-DEC-006 accepts this as a documented limitation of stdio mode (HTTP preferred). An in-flight write cut off this way is possibly applied, so read state before retrying
  ([DEPLOYMENT.md](DEPLOYMENT.md#stdio-via-uvx-register-update-rollback-rebuild-removal)).

### Cleanup and restoration (R1-R3)

Temporary stdio entry and hub key removed, HTTP entry re-enabled, controller restored via preset 1 and off. R1 preset file JSON-equal to the run-2 baseline (blanked entries
change the byte size); R2 state and R3 configuration byte-identical.

### Not run

- H07 offline device on hardware (simulated T02/T09 remains).
- Controller reboot and power-cycle persistence (ISSUE-12-DEC-002 TD-12-3).
- stdio load beyond the hub's rate limit and per-request stdio latency without the hub.
- Visual comparison with the WLED UI (H02); the visual checks above covered the LEDs.
- Interference inventory and quiet windows not repeated (run-2 baseline equals the run-1 end state).
- Restoring preset contents from a snapshot (ISSUE-8-DEC-001); other controllers and firmware; live update/rollback (stage 2).

The visible effect, speed and brightness-transition items were settled in [run 3](#issue-12-hardware-acceptance-run-3-2026-11-06) and ISSUE-12-DEC-007.

## Issue #12 hardware acceptance, run 3 (2026-11-06)

Short owner-watched run on the same day and controller through the deployed HTTP service and its hub entry, authorized for this run only by ISSUE-12-DEC-007 item 2
(capture before, restore after; ISSUE-12-DEC-001 conditions); the owner also asked for the repeats of E3. No deployment, service, hub or inventory change (build as left by run 2,
`b36f410`); WLED 16.0.1, one RGB-only strip, current limiter 850 mA. Sanitized. Scenarios: P0, E1-E3 (visible H04 behavior), R1-R3.

### Visible effect, speed and brightness transition (E1-E3)

All writes were typed tool calls applied and verified by readback except the first dimming call of E3 attempt 2 (`TIMEOUT`, below).

| Check | Command | Owner's observation (translated) |
| --- | --- | --- |
| E1 | segment 0 effect 9 (Rainbow), speed 30; master on, brightness 120 | "yes": slowly moving rainbow |
| E2 | segment 0 speed 240 | "faster, clearly" |
| E3 attempt 1 | brightness 30, `transition_ms` 3000 (rainbow) | no dimming visible |
| E3 attempt 2 | brightness 200, then 30 with `transition_ms` 5000 (rainbow) | no dimming visible |
| E3 attempt 3 | solid red; brightness 80 (power estimate at the cap), 40 (645 mA, below the cap), then 2 with `transition_ms` 5000 | "yes, gently became darker" |

Results: E1/E2 confirmed visible animation and speed change; E3 confirmed a brightness transition (attempt 3). A visual intensity change was not part of this run and is not needed for
#12 per ISSUE-12-DEC-008 (verified intensity readback in run 1 H04 plus the visible speed change E2); it is not claimed as visually observed. Attempts 1 and 2 showed no dimming; the likely
cause (analysis, not a measurement) is the current limiter capping output, which compresses the visible range of the dim (850 mA for solid red at brightness 80; no power reading for the rainbow
in run 3). Visual brightness checks must start below the cap (see [Opt-in physical write checks](#opt-in-physical-write-checks)).

TIMEOUT before dispatch (E3 attempt 2): the first dimming call returned `TIMEOUT` with application `not_attempted`; a direct state read showed brightness unchanged at 200, so the write had
not been applied; the same write was then issued once more as a new deliberate call and verified. Service and hub logs had no corresponding lines; the cause of the expired deadline is unknown.

### Restoration (R1-R3)

Restored via preset 1 and off; no preset writes. R1 preset file, R2 state and R3 configuration byte-identical to the run-3 baseline.

### Remaining #12 items after run 3 (ISSUE-12-DEC-007)

| Item left open after run 2 | Resolution |
| --- | --- |
| H02 comparison with the WLED UI | satisfied by the comparison with the controller endpoints the UI renders (run 1 H02), ISSUE-12-DEC-007 item 1 |
| H04 visible effect animation, speed and brightness transition | E1-E3 above (HTTP), item 2 |
| H04 in stdio mode | sufficient as exercised in run 2 (same domain code), item 3 |
| stdio drain on SIGTERM | host-level record of run 2 is sufficient, item 4 and ISSUE-12-DEC-006 |
| stdio load beyond the hub's rate limit / without the hub hop | not required; run-2 figures through the hub are sufficient, item 5 |
| H07 offline device on hardware | moved to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)), item 6; simulated T02/T09 remains |

### Not run

- A visual intensity change (not needed for #12 per ISSUE-12-DEC-008).
- stdio mode in this run (HTTP only, ISSUE-12-DEC-007 item 2).
- H07 offline device on hardware (stage 2, [#25](https://github.com/descipar/wled-mcp/issues/25)).
- Controller reboot and power-cycle persistence (ISSUE-12-DEC-002 TD-12-3); restoring preset contents from a snapshot (ISSUE-8-DEC-001); other controllers and firmware; live update/rollback (stage 2).
- The cause of the `TIMEOUT` before dispatch was not investigated.

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

All Must requirements need evidence. Mock implementation can be merged while hardware checks are pending if clearly labeled. "Production validated", "all firmware supported", "rollback tested" and "container-recreation persistent" require their own actual observations. Keep the integration issue open until its stated checks are met or explicitly revise the scope with a documented user decision.


## Stage 2 and later files

Evidence from stage 2 on lives in grouped files under `docs/validation/` with one section per
issue or record (rules in the [validation README](validation/README.md)).

| File | Contents |
| --- | --- |
| [validation/stage-2-core.md](validation/stage-2-core.md) | #16 setup, `config validate`, `doctor`; #17 groups, scenes, plan, sharing; #18 preset restore, supplied-state save, snapshots, playlists, bundles; #19 capability model and WLED 16 segment fields; #20 tool profiles, guard layers, call logs, status tool (mock and loopback evidence) |
| [validation/stage-2-release.md](validation/stage-2-release.md) | #21 version source, CI matrix, compatibility policy; #22 PyPI publish workflow (nothing published by it); #24 registry metadata and listing drafts; #151 MCPB bundle and cross-check |
| [validation/stage-3.md](validation/stage-3.md) | #27 zones; #28 temporary signals (two live runs recorded); #29 SVG layout preview; #30 lighting explanation (one read-only live run) |
| [validation/m3-m6.md](validation/m3-m6.md) | #147 agent guidance (local stdio check, ISSUE-147-DEC-001); #148 parsed effect metadata; #149 effect and palette names; #150 live snapshot; #181 source security review |
| [validation/m7-m8.md](validation/m7-m8.md) | #183 rooms; #200 `wled_discover_devices`; #203 `wled_add_device`; #204 M8 documentation, live runs and release preparation; #235 slim tool schemas and token budget |
| [validation/hardware-checks.md](validation/hardware-checks.md) | #128 PIN and OTA lock behavior; #134 stage-2 hardware check; #25 live H07 offline-controller check and rollback checklist; live check of the second release |
| [validation/releases.md](validation/releases.md) | Release records 0.3.0 (M2) and 0.4.0 (M3 to M6), the 0.3.0 launch report, the 0.4.0 deployment record and the visibility runbook (#90) |
