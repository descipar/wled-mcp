# Changelog

All notable changes are listed here, newest first. Versions are `0.x` while the project is
early: a minor release may contain breaking changes and then carries migration notes in
this file. Fixes are made for the latest release only. See
[versioning](docs/contract/versioning.md) and the [support policy](README.md#support).

## Unreleased

### Changed

- The served output schema of every tool (the result envelope and its error object) now
  allows additional properties, so a later additive field no longer makes a client that
  cached the schema reject the response ([#130](https://github.com/descipar/wled-mcp/issues/130)).
  Required fields and the `data` object are unchanged.

### Migration

A client that cached the 0.1.0 or 0.1.1 schema (or an earlier non-release build) rejects the
`correlation_id` that every served envelope carries since #119, with "data must NOT have
additional properties", until it refreshes `tools/list`. Reload the hub entry once after the
upgrade; it also clears by itself after about a minute. Later additive fields are tolerated.

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
