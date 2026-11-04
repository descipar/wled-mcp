# Requirements specification

Version: 0.2, 2026-11-04. State: proposed implementation baseline with confirmed dual-transport scope, prepared for agent handoff.

This document defines **stage 1**. Future public-release and product requirements use `S2-` IDs in [STAGE-2.md](STAGE-2.md) and separate tracker [#15](https://github.com/descipar/wled-mcp/issues/15). Stage-2 direction does not change current private visibility or silently add release-publication requirements to stage 1.

## 1. Authority and meaning of priorities

**Confirmed:** Kai wants a self-developed WLED MCP option assessed and a detailed, private GitHub project prepared so a later agent can check it out and implement it. Documentation and actionable GitHub issues are required. The existing home MCPHub is the intended integration context. No implementation, installation, or hardware mutation was requested in this assignment.

**Confirmed scope update:** v1 supports both Streamable HTTP for independent service operation and stdio for client-managed launch via uvx. Both expose identical WLED tools and domain behavior. The original stdio-only transport proposal is superseded. Updating this scope/backlog does not commission runtime implementation or deployment.

**Proposed baseline:** the feature scope and technical defaults below synthesize the preceding discussion. They are design proposals, not individually approved product requirements. A later implementation request can accept or adjust this baseline. Unknown device facts must not be invented.

Priorities: **Must** = required for the proposed first usable release; **Should** = useful v1 enhancement, may be deferred with an explicit decision; **Later** = outside first release. Requirement IDs remain stable when priorities or wording evolve. A Must blocked by unavailable hardware can be implemented and mock-tested, but the release remains hardware-unverified.

## 2. Context and intended users

MCPHub runs on `serviceplasma`, previously inspected as a Raspberry Pi 4 with approximately 4 GB RAM, using Docker Compose. The known installation uses persistent `/app/data` and `/app/binaries` mounts; actual deployment configuration must be rechecked before integration. This is historical environment context, not a live deployment guarantee.

Several agent clients can use the hub. This server connects directly to WLED controllers and exposes their capabilities through a consistent MCP interface: device inspection, lighting controls, segment layout editing and preset management. It operates independently of other home-automation systems. Feature scope is determined by WLED capabilities and this project's requirements.

Primary user: a household owner asking an agent for lighting changes. Secondary user: the implementing/maintaining agent, who needs stable contracts, helpful errors, reproducible installation, and a narrow operational footprint.

## 3. User scenarios

| Scenario | Expected behavior | Requirements |
| --- | --- | --- |
| “Which WLED controllers are configured and reachable?” | List configured names immediately; reachability is explicit and bounded | DEV-01, DEV-02 |
| “Show the desk strip's effects and current layout.” | Read device-specific names, IDs, active segments and capabilities | READ-01, READ-02 |
| “Make the first section warm white and the remainder blue.” | Agent reads LED count/capabilities, proposes or applies an explicit layout; unrelated controllers stay untouched | SEG-01–04, CTRL-01 |
| “Change only segment 2's effect speed.” | Patch only that segment and speed; preserve other fields and segments | SEG-01, SEG-03 |
| “Save this as Evening.” | Allocate an unused persistent preset ID; report name/ID and verify persistence | PRE-01–03 |
| “Replace preset 5 with this layout.” | Explicit overwrite of that ID with restorable prior preset data; no accidental second save on timeout | PRE-02–04, REL-02 |
| “Turn both configured strips off.” | Execute per device with individual outcomes; no claim of an atomic transaction | MULTI-01 |
| Controller disconnects during a request | Return a bounded, informative failure or uncertain write outcome | REL-01–03 |

## 4. Functional requirements

### Device selection and reads

- **DEV-01 Must — Named inventory.** Load a TOML file containing unique stable device IDs, human names and explicit base URLs. Every device-targeted tool requires `device_id`; no implicit default-device writes. Reject duplicate IDs, invalid entries, URL credentials, query strings/fragments and unsupported URL schemes at startup. Only HTTP(S) controller roots are allowed.
- **DEV-02 Must — Explicit availability.** List configured devices without network access by default. Optional bounded reachability probes return independent per-device outcomes. One offline device must not prevent listing or accessing others.
- **DEV-03 Should — Explicit reload.** Reload a changed inventory through a documented restart or controlled reload procedure. Invalid replacement configuration must not silently replace a working inventory. No automatic network discovery in v1.
- **READ-01 Must — State and information.** Read state plus device identity, firmware version, LED count, segment limit and reported color capabilities. Keep raw observed API fields available where useful, with unverified/absent capability fields reported as unknown rather than false.
- **READ-02 Must — Device-specific catalogs.** Read effect names/IDs and palette names/IDs from the target controller. Preserve original IDs; do not reindex filtered entries or hardcode a universal effect count. Combine metadata when available and handle unsupported metadata endpoints without losing the basic catalog.
- **READ-03 Should — Bounded metadata cache.** Cache catalogs for a proposed 300 seconds, support explicit refresh, invalidate on observed firmware change, and label cached/stale data. Never silently substitute cached state for a requested current state read.

### Lighting and segment behavior

- **CTRL-01 Must — Typed state controls.** Support master power, brightness 0–255, transition duration in clearly documented milliseconds, RGB/RGBW colors when supported, effect and palette selection, speed and intensity. Zero, false, empty and omitted values must remain distinguishable. Resolve effect/palette names only when unambiguous; otherwise return candidates and require an ID or precise name.
- **SEG-01 Must — Patch semantics.** Update explicit existing segment IDs without resending or altering unrelated fields/segments. Omitted fields retain their values. No automatic deletion or “cleanup” of segments in patch mode.
- **SEG-02 Must — Replace semantics.** A separate tool replaces the active segment layout with explicit IDs and ranges, identifies old segment IDs that must be removed, and deletes only those IDs. Never append a fixed number of dummy segments. Read the current layout first, calculate a plan, then verify the result. Document that cross-client changes can race with the plan.
- **SEG-03 Must — Validation.** Validate all segments before writing: unique/nonnegative IDs, `start < stop`, exclusive stop within LED count, segment-count/ID limits when known, valid colors and channel counts, brightness/speed/intensity bounds, effect/palette existence, positive grouping, nonnegative spacing, documented offset handling. Reject ambiguous overlapping ranges in replacement mode by default; if overlap support is later needed, make it explicit. Unknown capabilities must not be silently guessed.
- **SEG-04 Must — Plan and verify.** Mutating state/layout tools support `dry_run`. A dry run performs reads/validation but no writes and shows the semantic change plan. After an actual write, read back relevant state and compare normalized values; animation progression and normal unrelated transient fields are not equality requirements. Report applied, not applied, mismatch, or unknown rather than treating HTTP 200 alone as proof.
- **SEG-05 Should — Segment options.** Support segment power, brightness, up to three colors, grouping, spacing, offset, reverse, mirror, selection and name where supported. Add RGBW and CCT through capability-aware fields. RGBW is part of core color handling; CCT and 2D matrix geometry need real device requirements before becoming Must.
- **SEG-06 Later — Matrix and streaming.** Pixel art, image uploads, text scrolling, audio capture, custom realtime animation streaming and DDP are separate scope. Built-in WLED effects remain usable in v1.

### Presets and playlists

- **PRE-01 Must — Inspect and activate.** List persistent presets, read an individual preset's contents and activate a specified existing ID. Exclude reserved/empty entries correctly. Do not alter saved contents when activating.
- **PRE-02 Must — Save current state.** Create a named preset from current state, allocating a free supported persistent ID. Updating an occupied ID requires explicit `overwrite=true`. Do not allocate a free ID and later overwrite a newly occupied one without noticing the conflict. External clients prevent a true atomic guarantee; document the remaining race.
- **PRE-03 Should — Save supplied state.** Save a named, validated supplied layout/state without changing live output where the target firmware supports it. If live activation is technically necessary, expose that behavior before execution; do not introduce it as an invisible side effect.
- **PRE-04 Must — Delete and backup.** Delete one explicitly identified existing preset. Before overwrite/delete, store a validated snapshot of its prior contents atomically in the configured project data directory; if backup fails, abort the destructive write. Backups record device ID, preset ID, firmware, timestamp and format version. Prevent path traversal; keep per-device retention configurable. Restoration is documented, explicit and separately verified, not automatic blind rollback.
- **PRE-05 Must — Persistent outcome.** After save/delete, read persistent preset data until the expected condition is observed or a bounded deadline expires. Distinguish flash persistence delay, failure and uncertain outcome. Never automatically replay an uncertain save, delete or allocation.
- **PLAY-01 Should — Playlists.** Inspect and activate existing playlist presets. Creating/editing playlists, duration/repeat rules and interaction with active playback are a later enhancement unless requested; do not interpret playlist objects as ordinary color presets when editing.

### Multi-device behavior and advanced operations

- **MULTI-01 Must — Independent outcomes.** Different devices can be used by separate tool calls without global serialization. Multi-device orchestration belongs initially to the agent: results are per controller, and no synchronized or all-or-nothing behavior is promised. Within one server process serialize a device's write/verify sequence; document limits across multiple server processes and other WLED API clients.
- **ADV-01 Should — Restricted raw state patch.** Provide an advanced state patch only if typed tools leave a demonstrated gap. Accept a JSON object, not a JSON-encoded string. Restrict target to the configured controller's state API, reject unknown fields by default and recursive excessive payloads, and block hardware/network/security/firmware settings. A raw patch cannot bypass preset overwrite, backup, delete or layout replacement rules. Default disabled. A documented allowlist is required before enabling it.
- **ADV-02 Later — Configuration management.** Timer editing, firmware updates, Wi-Fi changes, reboot, hardware pin/bus configuration, factory reset, filesystem uploads and arbitrary URL forwarding are outside v1.

## 5. Nonfunctional and protocol requirements

- **MCP-01 Must — Standard transports.** Expose both stdio and Streamable HTTP using the official Python SDK or a justified maintained alternative. Select with `--transport stdio|streamable-http`; default stdio starts no listener. HTTP is an independent service with `/mcp`, configurable bind/port and lifecycle. Both modes support initialization, tools/list and tools/call through SDK negotiation, with identical tools, schemas and domain behavior. HTTP must not be implemented as only legacy SSE or ordinary REST. Tools have accurate annotations; annotations are not authorization enforcement.
- **MCP-02 Must — Machine-readable results.** Return structured, stable result/error objects plus a compact text fallback. Tool execution failures set MCP `isError` appropriately; do not bury failures in an apparently successful string. Protocol errors and expected device/tool errors remain distinct. Preserve valid structured results for partial or uncertain outcomes.
- **MCP-03 Must — HTTP endpoint access.** Default CLI HTTP binding is loopback; private container-network binding is explicit. Validate configured Host/Origin allowlists and reject invalid supplied Origins before device operations. Protect an independently reachable service with a runtime bearer credential or documented equivalent authenticated proxy; do not assume hub authentication protects it. Keep credentials outside CLI values, committed examples and logs. Document the private shared-credential deployment's limits; a full OAuth service is outside v1.
- **MCP-04 Must — Multi-client HTTP lifecycle.** Multiple HTTP sessions share inventory, WLED client, metadata caches, snapshots and per-device write/verify locks in one process. Define the SDK's session/stateless mode and shutdown behavior. Disconnect/reconnect must not imply write cancellation or trigger mutation replay. Use one worker for v1 unless cross-process coordination is implemented; ordinary process-local locks do not coordinate separate workers.
- **REL-01 Must — Bounded I/O.** Proposed defaults: 3-second connection timeout, 10-second overall device-operation deadline, at most one bounded retry for safe reads, and maximum response/payload sizes. Final defaults are configurable and documented. A tool deadline must include verification and retries rather than multiplying unbounded per-stage timeouts.
- **REL-02 Must — Uncertain writes.** After a response timeout/reset, report that a write may have applied. Attempt bounded readback when possible, but never label a mismatch as proof the command was not previously applied. No automatic write replay, including preset allocation. Distinguish successful, failed, and indeterminate application/persistence.
- **REL-03 Must — Coexistence.** Preserve unknown fields in backups and untouched state. Never read-modify-write the whole config to change a single light value. Document that the WLED UI, other API clients, playlists, timers, realtime senders and other agents may change state concurrently. Verification can report interference; do not continually fight another controller.
- **OPS-01 Must — Lightweight runtime.** Support a Python Streamable HTTP service independently of MCPHub and a stdio process launched by the client via uvx. One shared implementation supplies both transports. HTTP may use a dedicated Docker Compose service or equivalent managed process; stdio does not require that service. No database, browser UI, cloud service or mDNS dependency. Measure startup/idle memory for each mode exercised on the target; no unmeasured resource claim is an acceptance result.
- **OPS-02 Must — Reproducible delivery.** Version the package, pin/lock resolved dependencies, document console start, persist application/data paths across hub recreation, and provide update/rollback instructions. Runtime bootstrap must not depend on a developer's editable checkout or unpinned `latest` resolution.
- **OPS-03 Must — Logs and privacy.** In stdio mode stdout carries MCP only; diagnostics go to stderr in both modes. Avoid logging credentials, full configuration dumps or unsanitized HTTP bodies. Real devices, secret-bearing backups and runtime files are excluded from Git. Only explicitly selected HTTP mode opens the configured listener.
- **OPS-04 Should — Diagnostics.** Include application version and capability diagnostics in read results, with actionable messages for bad configuration, unsupported firmware, unavailable backup storage, offline devices and invalid responses.
- **OPS-05 Must — Both deployment modes.** Supply reproducible HTTP-service/Docker and uvx/stdio instructions plus MCPHub examples, persistent inventory/backups, explicit version pinning, secret injection and update/rollback procedures. The service runs independently of the hub and can be restarted/updated separately. Document host/container address differences, single-worker operation, bounded shutdown and a liveness check that does not change devices. Actual deployment evidence must identify which mode was exercised.
- **TEST-01 Must — Meaningful verification.** Automated tests cover the contract's hard cases and run without devices or LAN access. An opt-in hardware checklist records firmware, capabilities, observations and restoration. Unrun hardware tests remain visibly pending.

## 6. Explicit non-goals

No independent automation scheduler, cloud remote access, OAuth server, graphics editor, public package publishing, or guarantee of simultaneous multi-controller frames. No blanket “supports all WLED versions/features” claim. No automatic reconfiguration of the existing hub or device firmware as a prerequisite.

## 7. Open inputs and defaults

| Input | Current state | Effect / progress without answer |
| --- | --- | --- |
| Device names/URLs, count, firmware | Unknown | Implement against fixtures; do not invent household inventory |
| LED count/type, RGBW/CCT, 1D/2D | Unknown | Core RGB/RGBW contracts; gate extra capabilities; real acceptance pending |
| Existing presets/playlists worth preserving | Unknown | Mock preset behavior; require selected test slots before destructive hardware tests |
| Device reachability from actual WLED-MCP runtime | Not checked for WLED | Check the stdio execution context or independent HTTP-service context as appropriate; no network topology change assumed |
| HTTP service topology and credential storage | To choose during integration | Prepare private network/bind/Host/Origin configuration and runtime credential injection; no public exposure assumed |
| Authentication/OTA lock/API restrictions | Unknown | Surface firmware/API refusal; no password bypass or lock changes |
| Final Python/SDK versions | To select at bootstrap | Check upstream support and hub runtime; record locked versions |
| License and public release intent | Not selected / private requested | Original private work only; do not choose a license or publish |
| Backup location/retention | Proposed project data path, default 20 snapshots per device | Validate persistent writable path before enabling destructive preset tools |
| Resource acceptance target | No measured budget agreed | Record idle/startup measurements and discuss material impact if high |

These questions need not block architecture, packaging, mocks, schemas or most implementation. They block relevant hardware validation or deployment claims only.

## 8. Completion definition

The first usable release implements every Must, documents any deferred Should, passes the automated acceptance suite, is installable reproducibly, and has read-only integration evidence through the actual hub. Physical write acceptance additionally requires explicitly authorized checks on selected devices. Until those run, label the build “implemented, hardware write validation pending”; do not silently downgrade Must requirements to claim completion.
