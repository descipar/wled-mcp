# Changelog

All notable changes are listed here, newest first. Versions are `0.x` while the project is
early: a minor release may contain breaking changes and then carries migration notes in
this file. Fixes are made for the latest release only. See
[versioning](docs/contract/versioning.md) and the [support policy](README.md#support).

## Unreleased

The served tool list grows from 33 to 37 tools; the change is additive.

### Added

- Temporary light signals ([#28](https://github.com/descipar/wled-mcp/issues/28),
  [contract](docs/contract/signals.md)): `wled_start_signal` shows an RGB colour on chosen
  existing segments of one controller for 1 to 300 seconds and `wled_cancel_signal` ends it
  early; `wled_get_signal_status` reads the state. The server restores only the fields it changed
  (slot-0 colour, the Solid effect, and segment or master power it turned on), and only if they
  still hold the signal value; otherwise the result is `skipped_conflict` and nothing is
  overwritten. One signal per device, no queue, no scheduler, no preset touched. Timing is best
  effort and nothing is persisted: a crash or kill can leave a signal applied, an orderly
  shutdown makes one bounded restore attempt, and a write whose outcome is unknown is never
  replayed.
- Static layout preview ([#29](https://github.com/descipar/wled-mcp/issues/29),
  [contract](docs/contract/layout-preview.md)): the read-only `wled_preview_layout` returns a
  bounded, script-free SVG string (`data.svg`) of one device's observed 1D segment layout or of a
  proposed complete layout validated by the existing layout planner, with ranges (exclusive
  stops), a scale, gaps, overlaps and approximate colours, optional zone bands and optional live
  colour samples. It sends no write, never simulates effects, and refuses matrix devices.

### Changed

- CI runs the complete test suite in parallel with pytest-xdist (`pytest -n auto`); a plain
  `pytest` run stays serial ([#154](https://github.com/descipar/wled-mcp/issues/154)).

## 0.3.0 - M2: observe and explain

The release that closes milestone M2 once it is published
([DEC-030](docs/DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release),
[DEC-031](docs/DECISIONS.md#dec-031--release-scope-for-milestone-m2)). A minor release under the
`0.x` policy ([versioning](docs/contract/versioning.md), DEC-020): the changes are additive and
no tool or field was removed or renamed, so it carries no migration notes. The served tool list
grows from 31 to 33 tools.

### Added

- Live LED colour snapshot ([#150](https://github.com/descipar/wled-mcp/issues/150),
  [contract](docs/contract/live-snapshot.md)): the read-only `wled_get_live_snapshot` returns
  bounded, sampled LED colours per segment with explicit missing data and mapping limits. The
  colours are sampled values from the controller's live endpoint, not a claim of colour
  accuracy, and matrix geometry that cannot be mapped is reported as such.
- Lighting explanation ([#30](https://github.com/descipar/wled-mcp/issues/30),
  [contract](docs/contract/explain.md)): the read-only `wled_explain_lighting` explains why a
  light change seems ineffective for one device. It reads the controller state and info once
  each, combines them with process-local evidence of the last control call and returns
  observations, causes with a confidence (inferred causes never above medium; only a directly
  observed blocker may be high), a conclusion, unknowns and next checks. It never writes and does not prove a cause or name an actor.

### Tested and not tested

- Both tools have mocked and loopback tests, including parity over stdio and protected HTTP.
  The live evidence is one read-only check each on the one test controller (WLED 16.0.1):
  the snapshot call reported the live endpoint as unavailable (HTTP 501), so no positive colour
  result was observed on hardware ([#150 record](docs/validation/issue-150.md)); one
  explanation call read state and info once each and returned an observed blocker (master
  power off) with a low-confidence sync possibility ([#30 record](docs/validation/issue-30.md)).
  No write, other device, stale-evidence or playback/realtime-override path ran on hardware.
- The registry metadata is updated for 0.3.0 and validated locally only; nothing is tagged,
  released, uploaded or published by this change.

## 0.2.0 - M1: agent guidance, effect metadata and search, names, zones and the registry marker

The release that closes milestone M1 ([DEC-030](docs/DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)).
A minor release under the `0.x` policy ([versioning](docs/contract/versioning.md), DEC-020): the
changes are additive and no tool or field was removed or renamed, so it carries no migration
notes. The served tool list grows from 27 to 31 tools. An earlier preparation of this content as a
patch release was never tagged or published.

### Added

- Named physical lighting zones ([#27](https://github.com/descipar/wled-mcp/issues/27),
  [contract](docs/contract/zones.md)): `wled_list_zones` and `wled_plan_zone` (read) and
  `wled_apply_zone` (control). A reviewed zone file maps a name to configured devices and
  explicit LED ranges; a zone applies only onto existing active segments that lie inside it and
  tile it exactly, otherwise the call is refused before any write. No geometry or master state
  is written; zone targets inside scenes and groups are not part of this release.
- Effect search ([#31](https://github.com/descipar/wled-mcp/issues/31),
  [contract](docs/contract/effect-search.md)): the read-only `wled_search_effects` finds the
  effects of one configured device by curated properties (motion, flashing, colour slots,
  palette use, strip length, visibility) and returns the device's own IDs and names. The
  catalog is deliberately small; an effect it does not list is not searchable.
- Agent guidance ([#147](https://github.com/descipar/wled-mcp/issues/147),
  [contract](docs/contract/agent-guidance.md)): the server serves the same safe-lighting
  `instructions` over stdio and HTTP, the prompt `change_lighting_safely`, and precise
  descriptions for segment, layout, scene and zone inputs and for destructive tools. Whether a
  client forwards them to its agent is up to the client. A local stdio client check is recorded
  ([ISSUE-147-DEC-001](docs/decisions/issue-147.md)); whether MCPHub forwards them was not
  observed.
- Effect metadata ([#148](https://github.com/descipar/wled-mcp/issues/148),
  [contract](docs/contract/effect-metadata.md)): `wled_get_effects` parses the firmware's
  effect metadata leniently and accepts the optional filters `query`, `two_d` and `audio_reactive`. Original effect IDs are kept.
- Effect and palette names in segment tools ([#149](https://github.com/descipar/wled-mcp/issues/149),
  [contract](docs/contract/segment-names.md)): `wled_patch_segments` and `wled_replace_layout`
  accept `effect_name` and `palette_name` as alternatives to `effect_id` and `palette_id`.
  Names resolve against the selected device's own catalog before any write (exact, then
  case-folded match); an ambiguous or unknown name is refused with bounded candidates, and
  supplying both a name and its ID is a validation error.
- The README carries the ownership marker the official MCP Registry checks on the PyPI
  description, the repository holds the registry metadata `server.json`, and
  `scripts/check_distribution.py` requires the marker in the built wheel
  ([#24](https://github.com/descipar/wled-mcp/issues/24)). Nothing is listed in the registry
  yet; that needs the owner's separate action after this release is on PyPI.

### Changed

- `wled_get_effects` no longer returns the reserved placeholder effects (`RSVD`), also without
  filters; effect IDs are not renumbered and `count` is the number of returned effects
  ([#148](https://github.com/descipar/wled-mcp/issues/148)).
- Documentation-only pull requests run a reduced CI check set; every other change still runs
  the complete suite ([#159](https://github.com/descipar/wled-mcp/issues/159)).
- Documentation: roadmap by milestones ([DEC-029](docs/DECISIONS.md#dec-029--milestones-instead-of-stages)),
  the first PyPI upload record, the dependency and licence inventory with a vulnerability review
  for the PyPI release, an architecture review after the zones merge, and the records of the
  read-only effect-metadata probe and the local stdio check of the guidance, and the rule
  that closing a milestone includes a minor release and a README update
  ([DEC-030](docs/DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)).

### Tested and not tested

- The new tools and the guidance have mocked and loopback tests. A single read-only run on the
  one test controller (WLED 16.0.1, over stdio, no write) covered `wled_get_effects` with the
  effect metadata and one `wled_search_effects` call ([#148 record](docs/validation/issue-148.md));
  two of the 216 effects were only partially parsed and are still returned. No hardware run
  covers zones, the segment-name resolution or any write path of the new features. The guidance
  was checked with a local stdio client; MCPHub forwarding of it was not observed. Hardware acceptance of the stage-2
  features is unchanged (see 0.1.2).
- The registry metadata was validated locally against the published schema only; the
  registry's own publisher checks were not run.

## 0.1.2 - stage-2 close-out

Closes stage 2. A patch release: it contains no breaking change (the owner chose 0.1.2
over 0.2.0; [versioning](docs/contract/versioning.md), DEC-020). The stage-2
features #16 to #21 (setup and `doctor` commands, groups and scenes, preset restore, bundles
and playlists, advanced segments, tool profiles and the status tool, firmware tiers and the
compatibility policy) and #70 (non-release build identity) are already part of 0.1.0 and 0.1.1;
this release adds the changes below and the first hardware evidence for several of them.

### Changed

- `tools/list` builds the tool schemas once per server instead of on every request. The served
  listing is unchanged. Measured on a single-board ARM host with the 27 tools: about 23 ms of
  CPU per call instead of about 270 ms ([#67](https://github.com/descipar/wled-mcp/issues/67)).
- The served output schema of every tool (the result envelope and its error object) now
  allows additional properties, so a later additive field no longer makes a client that
  cached the schema reject the response ([#130](https://github.com/descipar/wled-mcp/issues/130)).
  Required fields and the `data` object are unchanged.
- Packaged text files (`LICENSE`, `NOTICE`, the Dockerfile, its ignore file and `*.txt`) are
  checked out with LF line endings on every platform, so a wheel or staged release built from
  a Windows checkout no longer differs from the Linux build
  ([#131](https://github.com/descipar/wled-mcp/issues/131)).
- Documentation: README and limitations updated with the hardware evidence below and the
  device-authentication limit; releases are staged on the machine that runs them
  ([DEC-026](docs/DECISIONS.md#dec-026--stage-releases-on-the-target-machine)).
- The package metadata declares version ranges with a lower and an upper bound instead of
  the exact pins `mcp==2.3.0`, `starlette==1.10.0` and `uvicorn==0.54.0`, and declares
  `anyio`, which the server imports directly
  ([#22](https://github.com/descipar/wled-mcp/issues/22),
  [dependency policy](docs/contract/dependencies.md)). The change is install-compatible:
  every environment that satisfied the earlier exact pins satisfies the new ranges. The
  staged release directory, the container image and the stdio hub example still install
  the exact tested set through `requirements-runtime.txt`; a package user gets that set
  by adding the release's constraints. The lowest and the highest combination of the
  ranges passed the test suite.
- The README is usable as the PyPI project page: all links are absolute, and the
  installation path uses the PyPI package, with the Git tag as the alternative for a
  release that is not listed there.

### Tested and not tested

- Hardware ([#134](https://github.com/descipar/wled-mcp/issues/134),
  [record](docs/validation/issue-134.md)): one run through the deployed HTTP service on the same
  RGB controller (WLED 16.0.1, one segment) covered a one-device group and scene (plan, apply,
  readback, delete), preset store, export, import and restore with snapshots, and a one-entry
  playlist. Every write was verified and state, segment and preset list were restored; four
  snapshots remain in the service data directory.
- Still without a hardware run: multi-device scenes, tool profiles, `discover`, restore onto an
  occupied slot, playlist import, restoring a playlist preset, CCT, RGBW and 2D, and the live
  offline-controller check (H07). A live rollback has not been checked.
- Automated tests and CI as for 0.1.0, plus new tests for the schema cache and the line-ending
  rules. Platform and firmware support are unchanged.

### Known limitations

Unchanged from 0.1.0, except that `tools/list` is no longer CPU-heavy. Still: no image on
GHCR and no registry entry, and PyPI distribution starts with this release at the earliest
(the Git tag remains the installation route for a release not listed on PyPI); saving a
playlist starts it and a preset cannot
be stored without changing the live output; one writer per controller (locks are per process);
no inventory reload; no tool deletes a snapshot.

### Migration

None needed. No tool, input schema, error code, configuration key or file format changed.
The tagged releases 0.1.0 and 0.1.1 already serve `correlation_id` (#119), so upgrading from
them needs no refresh. A client that cached the schema of a build from before #119 (as the
hub did after an update from such a build) rejects every envelope with "data must NOT have
additional properties" until it refreshes `tools/list`: reload the hub entry once. About a
minute was observed once with the hub; other clients may cache longer. Clients that cached
the schema of 0.1.0 or 0.1.1 would reject a future additive field the same way once;
schemas served from 0.1.2 on tolerate additive fields.

## 0.1.1 - documentation release

No change to the server, its tools or its configuration: the package behaves exactly as in
0.1.0. This release carries the restructured documentation, so that the README at the
release tag is the short one.

### Changed

- The README is about 175 lines instead of 419: a short summary, the status, a three-step
  "Try it" path (installation check, `wled-mcp config init`, host registration), the safety
  model, the support matrix and the limits.
- The release-directory, stdio and HTTP quickstarts and the inventory format moved to
  [docs/QUICKSTARTS.md](docs/QUICKSTARTS.md); the tool table moved to
  [docs/TOOL-CONTRACT.md](docs/TOOL-CONTRACT.md#tools-at-a-glance); the full list of known
  limitations moved to [docs/VALIDATION.md](docs/VALIDATION.md#known-limitations).
- The Git installation route now creates its inventory with `wled-mcp config init` instead
  of pointing at a container-path step.

### Tested and not tested, limitations, migration

Unchanged from 0.1.0. Migration: none.

## 0.1.0 - first source release

The first release is a Git tag with a GitHub release. It is not published to PyPI or GHCR;
install it from Git as described in the [README](README.md#try-it).

### What it provides

- An MCP server for WLED controllers, as a client-managed stdio subprocess (`uvx`) or an
  independent Streamable HTTP service with its own bearer credential and Host/Origin
  allowlists. Both transports expose the same tools.
- Named inventory of controllers; normalized state, capabilities and per-firmware effect
  and palette catalogs.
- Typed changes: master power, brightness and transition; a patch of selected segments; a
  replacement of the complete layout. Omitted fields stay unchanged. Every write has
  `dry_run` and read-back verification, and uncertain outcomes are reported, not retried.
- Persistent presets: list, inspect, activate, save and delete with durable snapshots;
  snapshot restore, supplied-state saves, native playlist authoring, and portable preset
  bundles (export and import with a dry-run preview and explicit mapping).
- Named device groups and multi-device scenes with a dry-run plan and a strict or
  best-effort apply that reports one verified outcome per device (not atomic, no rollback).
- Advanced segment fields (grouping, spacing, offset, mirror, several colors, CCT, 2D
  coordinates) where the device reports them, and an explicit opt-in for overlapping
  segments.
- Server-enforced tool profiles (`read-only`, `control`, `full`), a service status tool,
  bounded logs with a correlation ID, and the commands `config init`,
  `config add-device`, `config validate`, `doctor` and `discover` (opt-in mDNS).
- A tool contract with schema versions, a contract snapshot test, firmware support tiers
  and a version and migration policy.

### Tested and not tested

- Automated tests use mocks and synthetic loopback devices and run in CI on Linux amd64
  and arm64 with Python 3.13, including real stdio and loopback HTTP clients and a
  container image build for both architectures.
- Hardware acceptance covers the first (single-controller) feature set on one RGB
  controller with WLED 16.0.1 in both transports, and one deployment of both modes on one
  MCPHub host. The live offline-controller check (H07) has not been run.
- Groups, scenes, preset bundles, playlist authoring, snapshot restore, advanced segment
  fields, tool profiles and `discover` have mock and loopback evidence only; no hardware
  run covers them yet.
- Windows and macOS are experimental. WLED below 16.0.0 is unsupported and only served
  with a warning; other 16.x versions are unknown.

### Known limitations

- No package on PyPI, no container image on GHCR and no registry or marketplace entry.
- Storing, restoring or importing a preset without changing the live output is not
  possible on WLED 16, and saving a playlist starts it.
- One writer per controller: locks are per process.
- `tools/list` is CPU-heavy on small hosts.
- No inventory reload; configuration changes need `wled-mcp config validate` and a restart.

### Migration

None; this is the first release.

### Notices

Not affiliated with, endorsed by or supported by the WLED project or MCPHub. There is no
support commitment and no security support; the software is provided as is, at your own
risk (see [SECURITY.md](SECURITY.md)). Licensed under Apache-2.0.
