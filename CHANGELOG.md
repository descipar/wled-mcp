# Changelog

All notable changes are listed here, newest first. Versions are `0.x` while the project is
early: a minor release may contain breaking changes and then carries migration notes in
this file. Fixes are made for the latest release only. See
[versioning](docs/contract/versioning.md) and the [support policy](README.md#support).

## Unreleased

### Added

- **`wled_discover_devices` (#200).** Read tool, served in every profile: runs the shared discovery
  engine on request (mDNS, known-device reads, stored ranges since #202) and returns candidates
  (`new`, `known`, `address_changed`), a coverage report that never claims nothing was found when it
  could not look, and proposed ranges that are never probed. Writes nothing. A concurrent call, or a
  probe run within 5 s of the previous one, returns the new error code `DISCOVERY_BUSY` with
  `retry_after_seconds`.
- **`wled_add_device` (#203).** `manage` tool (profile `full` only): adds one controller from an
  explicit `http://<RFC 1918 IPv4>[:port]` (optional `device_id`, `name`, `expected_mac`,
  `dry_run`). One read-only `GET /json/info` (discovery hard caps apply); refuses a non-WLED answer
  (`NOT_WLED`) and a duplicate ID, address or MAC (`INVENTORY_CONFLICT`); appends one
  `[[devices]]` entry through the shared writer and applies it without a restart. Never writes to a
  device. Additive: devices gain the optional `mac` key (12 lowercase hex; an older server rejects
  the unknown key at startup, see [versioning](docs/contract/versioning.md)); a stored `mac` lets
  discovery recognize a moved controller. The live enrollment ran twice on 2026-11-19 (first
  attempt `NOT_WLED`, second succeeded; [record](docs/validation/issue-203.md)).
- **`wled_set_discovery_ranges` (#202).** `manage` tool (profile `full` only): replaces the stored
  discovery ranges (RFC 1918, /24 to /30, at most 4, no overlap; `[]` clears; `dry_run`). Rejections
  list each bad entry as `data.rejected[]` (`index`, fixed `reason`, never the value). Stored as
  `[discovery] ranges` through the shared writer (lock, backup, atomic replace, rollback), applied
  without a restart; no device is contacted. `wled-mcp discover --config` probes the stored ranges;
  an out-of-policy hand-edited range stops startup. Additive; an older server rejects the
  `[discovery]` table. Writer fixes: the storage failure reason names the real cause, the write lock
  is per file, a Windows lock-byte failure is a storage failure. Contract:
  [discovery](docs/contract/discovery.md); live discovery runs of #204 on 2026-11-20
  ([record](docs/validation/issue-204.md)).
- **Rooms (#183).** A stored group can be a room (`kind` `room` on `wled_save_group`; format stays
  version 1). A controller is in at most one room; conflicts are refused on save, reported by
  `wled_list_groups` and `wled_list_devices`, and refused by room actions before any write. New
  control tool `wled_apply_room` applies a master state or stored scene to a room's members through
  the scene write path (dry run, strict by default, per-device outcomes, uncertain writes never
  retried). `wled_plan_zone` and `wled_apply_zone` take an optional `room` (`outside_room`). The
  tool list grows from 37 to 38 and the `full` profile from 60572 to 63676 characters
  ([measurements](docs/validation/issue-235.md)). All additive; an older server counts a room file as
  invalid and leaves it untouched ([migration note](docs/contract/versioning.md#migration-notes)).
  Contract: [rooms](docs/contract/rooms.md); one live run in
  [validation/issue-183.md](docs/validation/issue-183.md), not yet released.

### Changed

- **`wled-mcp discover` uses the shared discovery engine (#199).** Up to 3 mDNS rounds in a 6 s
  window (also `_http._tcp`), each answer verified with one `GET /json/info` (RFC 1918, port 80),
  merged by MAC, marked `new`, `known` or `address_changed`, with a coverage report. Behavior
  change: the command now makes HTTP reads, a controller on another port or outside RFC 1918 space is
  not listed, and `--timeout` only lowers the deadline. The JSON keeps its version-1 fields and adds
  `conclusion`, `coverage`, `warnings` and per-candidate fields.
- **Inventory writes keep a backup and take a lock (#201).** `config add-device` and
  `config init --force` keep the previous file as `<config>.bak` and take `.<config>.lock`
  (new refusal `CONFIG_LOCKED`). A reusable inventory writer with in-process reload and the error
  codes `INVENTORY_CONFLICT` and `INVENTORY_RELOAD_FAILED` are added. The configuration directory
  must be writable.
- **Smaller served tool list (#235).** Schemas drop generated `title` keys and `"default": null`;
  the longest descriptions are tighter. On the 37-tool `full` profile name, description and input
  schemas shrink from 70926 to 60572 characters (14.6 %), output schemas from 67118 to 53095.
  No tool, name, annotation, field, validation rule or result changed; a test guards a size budget
  per tool and profile ([measurements](docs/validation/issue-235.md)).
- Documentation: M8 closing documentation (#204: README, deployment guide, quickstart, tool
  contract, coverage table, migration rows, [validation plan](docs/validation/issue-204.md)); the
  version is unchanged and no release is made. Decision, roadmap and workflow documents do not
  affect the package.

## 0.4.0 - M3 to M6: layout preview, signals, security review and the MCPB bundle

The minor release that carries all work merged since 0.3.0: M3 (layout preview), M4 (temporary
signals), M5 (locked controllers) and M6 (public distribution, bounded security review) plus
backlog and tooling changes; M3, M4 and M5 close without a release of their own
([DEC-032](docs/DECISIONS.md#dec-032--m3-closes-without-its-own-release),
[DEC-034](docs/DECISIONS.md#dec-034--m4-closes-without-its-own-release),
[DEC-036](docs/DECISIONS.md#dec-036--m5-closes-without-its-own-release)). Tool list grows from 33 to
37; changes are additive. Four behaviors changed and carry migration notes
([versioning](docs/contract/versioning.md), DEC-020).

### Migration

- **Snapshot directory (#181).** A symlinked `<data_dir>/backups` is no longer followed. The
  snapshot listing shows no snapshots (with a warning), load or restore reports `PRESET_NOT_FOUND`
  and creating a snapshot fails with `BACKUP_FAILED`, so overwrites and deletes needing one are
  refused. Snapshots are not lost; point `data_dir` at the real directory or replace the link
  with a real directory containing them.
- **HTTP error bodies (#181).** Transport-level errors (status 400 and above) carry a fixed message
  and no SDK text that could quote the request; a client that parsed that text sees "HTTP request
  rejected." Status, JSON-RPC code, request ID and the server's own messages are unchanged.
- **HTTP startup line (#181).** The stderr notice is `listening on configured address path /mcp`
  and no longer names host and port; a bind failure prints a fixed message with the OS error
  number. A script that parsed `listening on <host>:<port>` must match the new line.
- **Definition directories (#181).** A group, scene or zone directory with more files than the scan
  cap refuses to store a new definition instead of using an incomplete count.

### Added

- Temporary light signals ([#28](https://github.com/descipar/wled-mcp/issues/28),
  [contract](docs/contract/signals.md)): `wled_start_signal` shows an RGB colour on existing
  segments of one controller for 1 to 300 seconds, `wled_cancel_signal` ends it early and
  `wled_get_signal_status` reads the state. Only the fields the server changed are restored, and
  only if they still hold the signal value; otherwise `skipped_conflict` and nothing is
  overwritten. One signal per device, no queue, scheduler or preset. Timing is best effort and
  nothing is persisted: a crash can leave a signal applied, an orderly shutdown makes one bounded
  restore attempt, an unknown write outcome is never replayed.
- Static layout preview ([#29](https://github.com/descipar/wled-mcp/issues/29),
  [contract](docs/contract/layout-preview.md)): read-only `wled_preview_layout` returns a bounded,
  script-free SVG of a device's observed 1D layout or a proposed layout validated by the layout
  planner (ranges with exclusive stops, scale, gaps, overlaps, approximate colours, optional zone
  bands and live samples). No writes, no effect simulation, matrix devices refused.
- Claude Desktop MCPB bundle ([#151](https://github.com/descipar/wled-mcp/issues/151),
  [contract](docs/contract/mcpb-bundle.md)): the release workflow builds `wled-mcp-<version>.mcpb`
  and, after the PyPI upload succeeded, attaches it with a SHA-256 file to the GitHub release;
  a failure of either job does not affect PyPI. It only makes Claude Desktop start the released
  package through `uvx` (uv required), is untested by the project and comes without warranty.
- Usage feedback issue template ([#193](https://github.com/descipar/wled-mcp/issues/193)); no
  telemetry is collected. Troubleshooting guide and current architecture description
  ([#23](https://github.com/descipar/wled-mcp/issues/23)).
- Security and supply-chain checks in CI ([#181](https://github.com/descipar/wled-mcp/issues/181),
  [record](docs/validation/issue-181.md)): Ruff security rules, CodeQL `security-extended`, weekly
  Dependabot, SHA-pinned actions. One open medium CodeQL finding: the explicit CLI mDNS discovery
  binds its reply socket to all IPv4 interfaces ([#222](https://github.com/descipar/wled-mcp/issues/222),
  [SECURITY.md](SECURITY.md#practical-limits)).

### Changed

- Bounded security review fixes ([#181](https://github.com/descipar/wled-mcp/issues/181)): unknown
  keys are no longer echoed in error text and HTTP diagnostics no longer name the listener. One
  pass over five areas, not an audit; remaining directory-replacement risk is
  [#220](https://github.com/descipar/wled-mcp/issues/220).
- Layout preview `colour_basis` is `mixed` when only some lanes use live samples and
  `state_slot_0` when none does (additive value).
- README is shorter; the test suite passes on Windows
  ([DEC-033](docs/DECISIONS.md#dec-033--windows-is-a-supported-development-platform), user-facing
  Windows tier stays experimental); CI runs the suite in parallel (`pytest -n auto`, #154).

### Tested and not tested

- New tools have mocked and loopback tests with stdio/HTTP parity. Temporary signals ran twice on
  the one test controller (WLED 16.0.1, stdio only; [record](docs/validation/issue-28.md)). The
  layout preview has no hardware run. The MCPB bundle was never started in Claude Desktop. The
  security review gives no security support ([DEC-013](docs/DECISIONS.md)).
- Validation records without code change: PIN and OTA locks
  ([#128](https://github.com/descipar/wled-mcp/issues/128), [record](docs/validation/issue-128.md))
  and the launch report with the live rollback from 0.3.0 to 0.2.0
  ([#25](https://github.com/descipar/wled-mcp/issues/25), [report](docs/validation/launch-report.md)).

## 0.3.0 - M2: observe and explain

Closes M2 ([DEC-030](docs/DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release),
[DEC-031](docs/DECISIONS.md#dec-031--release-scope-for-milestone-m2)). Additive, no migration
notes; tool list 31 to 33.

- Live LED colour snapshot ([#150](https://github.com/descipar/wled-mcp/issues/150),
  [contract](docs/contract/live-snapshot.md)): read-only `wled_get_live_snapshot` returns bounded
  sampled colours per segment with explicit missing data and mapping limits; sampled values, no
  claim of colour accuracy.
- Lighting explanation ([#30](https://github.com/descipar/wled-mcp/issues/30),
  [contract](docs/contract/explain.md)): read-only `wled_explain_lighting` explains why a change
  seems ineffective: one state and one info read plus process-local evidence of the last control
  call, returning observations, causes with a confidence (inferred never above medium), a
  conclusion, unknowns and next checks. Never writes, proves a cause or names an actor.
- Tested: mocked and loopback tests with parity. One read-only live check each on the test
  controller (WLED 16.0.1): the snapshot call reported the live endpoint unavailable (HTTP 501), so
  no positive colour result was observed ([#150 record](docs/validation/issue-150.md)); one
  explanation returned an observed blocker (master power off) ([#30 record](docs/validation/issue-30.md)).
  No write path ran on hardware.

## 0.2.0 - M1: agent guidance, effect metadata and search, names, zones and the registry marker

Closes M1 ([DEC-030](docs/DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)).
Additive, no migration notes; tool list 27 to 31. An earlier preparation as a patch release was
never tagged or published.

- Named physical lighting zones ([#27](https://github.com/descipar/wled-mcp/issues/27),
  [contract](docs/contract/zones.md)): `wled_list_zones`, `wled_plan_zone` (read) and
  `wled_apply_zone` (control). A zone applies only onto existing active segments inside it that
  tile it exactly, otherwise it is refused before any write; no geometry or master state is
  written.
- Effect search ([#31](https://github.com/descipar/wled-mcp/issues/31),
  [contract](docs/contract/effect-search.md)): read-only `wled_search_effects` finds a device's
  effects by curated properties and returns the device's own IDs and names; an effect the small
  catalog does not list is not searchable.
- Agent guidance ([#147](https://github.com/descipar/wled-mcp/issues/147),
  [contract](docs/contract/agent-guidance.md)): the same safe-lighting `instructions` over stdio and
  HTTP, the prompt `change_lighting_safely` and precise input descriptions; forwarding is up to the
  client (local stdio check recorded, ISSUE-147-DEC-001; MCPHub forwarding not observed).
- Effect metadata ([#148](https://github.com/descipar/wled-mcp/issues/148),
  [contract](docs/contract/effect-metadata.md)): `wled_get_effects` parses firmware metadata
  leniently with optional filters `query`, `two_d`, `audio_reactive`; original IDs are kept and the
  reserved `RSVD` placeholders are no longer returned (`count` is the number returned).
- Effect and palette names in segment tools ([#149](https://github.com/descipar/wled-mcp/issues/149),
  [contract](docs/contract/segment-names.md)): `effect_name` and `palette_name` as alternatives to
  the IDs, resolved against the device's catalog before any write; ambiguous or unknown names are
  refused with bounded candidates; name plus ID is a validation error.
- README carries the registry ownership marker, the repository holds the registry `server.json`,
  and `scripts/check_distribution.py` requires the marker in the wheel
  ([#24](https://github.com/descipar/wled-mcp/issues/24)); nothing is listed yet.
- Documentation-only PRs run a reduced CI set (#159); documentation: milestone roadmap (DEC-029),
  PyPI upload record, dependency/licence inventory and vulnerability review.
- Tested: mocked and loopback tests. One read-only stdio run on the test controller (WLED 16.0.1)
  covered `wled_get_effects` with metadata and one `wled_search_effects` call
  ([#148 record](docs/validation/issue-148.md)); two of 216 effects were only partly parsed and are
  still returned. No hardware run covers zones, name resolution or any new write path. Registry
  metadata was validated locally against the schema only.

## 0.1.2 - stage-2 close-out

A patch release without breaking change ([versioning](docs/contract/versioning.md), DEC-020). The
stage-2 features #16 to #21 and #70 are already part of 0.1.0 and 0.1.1; this release adds the
changes below and first hardware evidence for several of them.

### Changed

- `tools/list` builds the tool schemas once per server: about 23 ms CPU per call instead of 270 ms
  on a single-board ARM host with 27 tools ([#67](https://github.com/descipar/wled-mcp/issues/67)).
- The served output schema of every tool allows additional properties, so a later additive field no
  longer makes a client with a cached schema reject the response
  ([#130](https://github.com/descipar/wled-mcp/issues/130)).
- Packaged text files are checked out with LF on every platform, so builds from a Windows checkout
  match Linux ([#131](https://github.com/descipar/wled-mcp/issues/131)).
- Package metadata declares lower and upper version ranges instead of the exact pins `mcp==2.3.0`,
  `starlette==1.10.0` and `uvicorn==0.54.0`, and declares
  `anyio` ([#22](https://github.com/descipar/wled-mcp/issues/22),
  [dependency policy](docs/contract/dependencies.md)); install-compatible. The staged release, the
  image and the stdio hub example still install the exact tested set through
  `requirements-runtime.txt`.
- README usable as the PyPI project page (absolute links, PyPI installation path); releases are
  staged on the machine that runs them ([DEC-026](docs/DECISIONS.md#dec-026--stage-releases-on-the-target-machine)).

### Tested and not tested

- Hardware ([#134](https://github.com/descipar/wled-mcp/issues/134),
  [record](docs/validation/issue-134.md)): one run through the deployed HTTP service on one RGB
  controller (WLED 16.0.1) covered a one-device group and scene, preset store, export, import and
  restore with snapshots, and a one-entry playlist; every write was verified and state restored.
- Still without hardware run: multi-device scenes, tool profiles, `discover`, restore onto an
  occupied slot, playlist import, CCT, RGBW, 2D and the live offline check (H07). No live rollback
  yet.

### Known limitations and migration

As in 0.1.0 except that `tools/list` is no longer CPU-heavy: no GHCR image or registry entry
(the Git tag stays the route for releases not on PyPI), saving a playlist starts it, one writer
per controller (locks are per process), no inventory reload, no snapshot deletion tool.
Migration: none. A client that cached the schema of a build from before #119 rejects every
envelope ("data must NOT have additional properties") until it refreshes `tools/list`; reload the
hub entry once. Schemas served from 0.1.2 on tolerate additive fields.

## 0.1.1 - documentation release

No change to the server, tools or configuration. The README at the tag is the short one (about 175
lines): summary, status, a three-step "Try it" path, safety model, support matrix and limits.
Quickstarts and the inventory format moved to [docs/QUICKSTARTS.md](docs/QUICKSTARTS.md), the tool
table to [docs/TOOL-CONTRACT.md](docs/TOOL-CONTRACT.md#tools-at-a-glance), the known limitations to
[docs/VALIDATION.md](docs/VALIDATION.md#known-limitations). The Git route creates its inventory with
`wled-mcp config init`. Testing, limitations and migration as in 0.1.0 (none).

## 0.1.0 - first source release

A Git tag with a GitHub release; not published to PyPI or GHCR, install it from Git as described in
the [README](README.md#try-it).

- An MCP server for WLED controllers as a client-managed stdio subprocess (`uvx`) or an independent
  Streamable HTTP service with its own bearer credential and Host/Origin allowlists; both expose
  the same tools.
- Named inventory; normalized state, capabilities and per-firmware effect and palette catalogs.
- Typed changes: master power, brightness, transition; a patch of selected segments; a replacement of
  the complete layout. Omitted fields stay unchanged; every write has `dry_run` and read-back
  verification, and uncertain outcomes are reported, not retried.
- Persistent presets (list, inspect, activate, save, delete with durable snapshots), snapshot
  restore, supplied-state saves, native playlist authoring and portable bundles (export/import with
  dry-run preview and explicit mapping).
- Named groups and multi-device scenes with a dry-run plan and strict or best-effort apply (not
  atomic, no rollback).
- Advanced segment fields (grouping, spacing, offset, mirror, several colors, CCT, 2D) where the
  device reports them, with an opt-in for overlapping segments.
- Server-enforced tool profiles (`read-only`, `control`, `full`), a status tool, bounded logs with a
  correlation ID, and `config init`, `config add-device`, `config validate`, `doctor` and
  opt-in mDNS `discover`.
- A tool contract with schema versions, a contract snapshot test, firmware tiers and a version and
  migration policy.

Tested: mocks and loopback devices in CI on Linux amd64 and arm64 with Python 3.13, including real
stdio and loopback HTTP clients and image builds for both architectures. Hardware acceptance
covers the single-controller feature set on one RGB controller (WLED 16.0.1) in both transports and
one deployment of both modes on one MCPHub host; H07 was not run. Groups, scenes, bundles,
playlists, restore, advanced segment fields, profiles and `discover` have mock and loopback
evidence only. Windows and macOS are experimental; WLED below 16.0.0 is unsupported (served with a
warning), other 16.x versions are unknown.

Known limitations: no PyPI package, GHCR image or registry entry; storing a preset without changing
the live output is impossible on WLED 16 and saving a playlist starts it; one writer per controller;
`tools/list` is CPU-heavy on small hosts; configuration changes need `config validate` and a
restart. Migration: none.

Not affiliated with, endorsed by or supported by the WLED project or MCPHub. No support commitment
and no security support; provided as is, at your own risk (see [SECURITY.md](SECURITY.md)).
Licensed under Apache-2.0.
