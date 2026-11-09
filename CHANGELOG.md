# Changelog

All notable changes are listed here, newest first. Versions are `0.x` while the project is
early: a minor release may contain breaking changes and then carries migration notes in
this file. Fixes are made for the latest release only. See
[versioning](docs/contract/versioning.md) and the [support policy](README.md#support).

## 0.2.0 - stage-2 close-out

Closes stage 2. The version number is a proposal from the pre-1.0 policy
([versioning](docs/contract/versioning.md), DEC-020); the owner may change it. The stage-2
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

Unchanged from 0.1.0, except that `tools/list` is no longer CPU-heavy. Still: no package on
PyPI, no image on GHCR and no registry entry; saving a playlist starts it and a preset cannot
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
schemas served from 0.2.0 on tolerate additive fields.

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
