# WLED MCP

An unofficial [MCP](https://modelcontextprotocol.io/) server that lets an AI agent read
and control [WLED](https://kno.wled.ge/) LED controllers by name: power, brightness,
segments, effects, palettes, presets, groups, scenes and zones. It talks to each controller's
JSON API on your network, validates every change before sending it and reads it back
afterwards. It runs as a subprocess of your MCP host (stdio) or as a separate HTTP
service. It is not affiliated with, endorsed by or supported by the WLED project or
MCPHub.

<!-- mcp-name: io.github.descipar/wled-mcp -->

**Status:** early software with `0.x` versions that may break between releases
([CHANGELOG.md](https://github.com/descipar/wled-mcp/blob/main/CHANGELOG.md)). Releases are distributed on PyPI as
[`wled-mcp`](https://pypi.org/project/wled-mcp/); a release that is not listed there
installs from its Git tag. The server is listed in the official
[MCP Registry](https://registry.modelcontextprotocol.io/) as `io.github.descipar/wled-mcp`.
The container image is not published to GHCR. Hardware acceptance is partial: one controller
on WLED 16.0.1. No support is promised
([Support](https://github.com/descipar/wled-mcp/blob/main/README.md#support)).

## What it does

- Self-hosted: no cloud service, account, MQTT broker or public endpoint. Controllers are a
  named inventory in a TOML file; nothing is discovered unless you run the opt-in
  `wled-mcp discover`.
- State and catalogs: normalized state, capabilities and each device's own effect and
  palette catalogs; effects can be filtered by firmware metadata and searched by curated
  properties (motion, flashing, colour slots; the catalog is small).
- Typed changes: power and brightness, a patch of selected segments or a replacement of the
  complete layout. Effects and palettes by name or ID, checked against the device's catalog
  before any write.
- Zones: a reviewed zone file maps a physical region to devices and LED ranges; changes apply
  only inside the zone, otherwise they are refused before any write.
- Presets, groups and scenes: persistent presets with snapshots, restore, portable bundles
  and playlists; named device groups and multi-device scenes with a dry-run plan.
- Observe and explain (read-only): sampled live LED colours per segment, and an explanation
  of why a change may not show. Neither proves a cause or colour accuracy.
- Layout preview (read-only, not yet released): a static SVG of a device's segment layout,
  1D only.
- Agent guidance: safe-lighting instructions, a prompt and precise field descriptions, served
  identically over stdio and HTTP; the client has to pass them on to its agent.
- Server-enforced profiles (`read-only`, `control`, `full`); for the HTTP service a bearer
  credential with Host and Origin allowlists.

All tools, each with its read-only, write or destructive hint, are listed in the
[tool contract](https://github.com/descipar/wled-mcp/blob/main/docs/TOOL-CONTRACT.md#tools-at-a-glance).

<!-- wled-coverage:start -->
WLED feature coverage: 60 % of the planned scope, 48 % of WLED overall ([method and list](https://github.com/descipar/wled-mcp/blob/main/docs/WLED-COVERAGE.md)).
<!-- wled-coverage:end -->

## Safety model

- **Validate first.** A complete request is checked against the current device state before
  the first write; unknown fields and out-of-range values are rejected. Omitted fields mean
  "unchanged", never "reset".
- **Patch versus replace.** `wled_patch_segments` changes only the named segments; only
  `wled_replace_layout` removes segments that are not listed.
- **Dry run and verification.** `dry_run=true` returns the plan without writing. Writes are
  read back; a write that timed out is reported as
  possibly applied and is never retried blindly.
- **Snapshots.** Overwriting or deleting a preset first stores a durable snapshot in the
  data directory. Restores, imports, supplied-state stores (`wled_store_preset`) and
  playlist saves change the live output before they store, and the previous lighting is not
  restored.
- **No hidden reach.** No discovery by the server or its tools, no arbitrary endpoints or
  caller-supplied hosts, no silent preset overwrite (`overwrite=true` is required).
- **Authorization.** Whether a person may run a tool is the MCP host's job; tool
  annotations are hints only. The HTTP service also requires its own bearer credential and
  Host allowlist and must not be exposed to the internet.

## Try it

You need [uv](https://docs.astral.sh/uv/), an MCP host that can start a stdio server and a
WLED controller reachable over HTTP. Replace `<version>` with the version of the
[latest release](https://github.com/descipar/wled-mcp/releases/latest). The commands install
that release from [PyPI](https://pypi.org/project/wled-mcp/) and are for a POSIX shell;
Windows is experimental
([compatibility](https://github.com/descipar/wled-mcp/blob/main/docs/contract/compatibility.md)).

1. Check the installation (no device, no configuration):

   ```text
   uvx --isolated --python 3.13 --from wled-mcp==<version> wled-mcp --version
   ```

2. Create a data directory and an inventory with one controller (contacts nothing):

   ```text
   mkdir -p "$HOME/wled-mcp"
   uvx --isolated --python 3.13 --from wled-mcp==<version> wled-mcp config init --config "$HOME/wled-mcp/devices.toml" --device-id desk --device-name "Desk strip" --base-url http://<controller-address>
   ```

3. Register the server in your MCP host with the command `uvx` and these arguments, each
   one separate, using absolute paths:

   ```text
   --isolated --python 3.13 --from wled-mcp==<version> wled-mcp --transport stdio --config <absolute path>/wled-mcp/devices.toml --data-dir <absolute path>/wled-mcp
   ```

   Ask the agent to list your WLED devices (`wled_list_devices`). Every write tool accepts
   `dry_run=true` to preview a change without touching the lights.

More devices, the [inventory format](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md#inventory), the Git-tag route, a
checksum-verified wheel, the MCPHub Registry install note and the HTTP service are in the
[quickstarts](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md); updates, rollback and removal are in
[docs/DEPLOYMENT.md](https://github.com/descipar/wled-mcp/blob/main/docs/DEPLOYMENT.md). Dependencies resolve within the declared
ranges ([dependency policy](https://github.com/descipar/wled-mcp/blob/main/docs/contract/dependencies.md)).

## Compatibility

What the checks cover; the evidence and the firmware tiers are in
[docs/contract/compatibility.md](https://github.com/descipar/wled-mcp/blob/main/docs/contract/compatibility.md). This is not a
support commitment (see [Support](https://github.com/descipar/wled-mcp/blob/main/README.md#support)).

| Area | Status |
| --- | --- |
| Python 3.13 | supported |
| Linux amd64 | supported |
| Linux arm64 | supported |
| HTTP container image, amd64 and arm64 | supported |
| stdio via uvx on Linux | supported |
| Windows | experimental |
| macOS | experimental |
| WLED 16.0.1 | tested |
| WLED 16.x other than 16.0.1 | unknown |
| WLED below 16.0.0, including 0.15.x | unsupported |

Unsupported or unrecognized firmware is served with a warning and never refused;
`wled_get_state` reports the tier in `diagnostics.firmware_support`.

## Limitations

Automated tests use mocks and synthetic loopback devices. Hardware acceptance is partial:
core features ran on one RGB controller with WLED 16.0.1, and a live check with an offline
controller is still pending. Multi-device scenes, profiles, zones, the layout preview and
CCT, RGBW or 2D controllers have no hardware run; details are in
[docs/VALIDATION.md](https://github.com/descipar/wled-mcp/blob/main/docs/VALIDATION.md#known-limitations).

- No tool deletes a snapshot on request; retention pruning keeps 20 per controller.
- On WLED 16, storing, restoring or importing a preset changes the live output, and saving a
  playlist may start it.
- One writer per controller: locks are per process.
- No inventory reload; changes need `wled-mcp config validate` and a restart.
- No device authentication: WLED has none for its light API ("Anyone with your IP and port
  can control the lights", [WLED docs](https://kno.wled.ge/advanced/ota-lock/)). The server
  sends no device credentials and does not support a controller behind HTTP authentication.
  Behavior with a settings PIN or OTA lock is untested
  ([#128](https://github.com/descipar/wled-mcp/issues/128)).

## Documentation

| Document | Contents |
| --- | --- |
| [Quickstarts](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md) | Release directory, stdio and HTTP setup, inventory format |
| [Deployment](https://github.com/descipar/wled-mcp/blob/main/docs/DEPLOYMENT.md) | Both transports in detail: staging, verification, update, rollback, removal |
| [Tool contract](https://github.com/descipar/wled-mcp/blob/main/docs/TOOL-CONTRACT.md) | Tools, parameters, results, errors and mutation semantics |
| [WLED feature coverage](https://github.com/descipar/wled-mcp/blob/main/docs/WLED-COVERAGE.md) | WLED features with support status, owning issue or decision, and coverage figures |
| [Development](https://github.com/descipar/wled-mcp/blob/main/docs/DEVELOPMENT.md) | Local checks, build and launch, including PowerShell |
| [Validation](https://github.com/descipar/wled-mcp/blob/main/docs/VALIDATION.md) | Automated checks, opt-in hardware checks, recorded evidence, known limitations |
| [Contract examples](https://github.com/descipar/wled-mcp/blob/main/examples/contracts/README.md) | Synthetic request, result and snapshot examples |

## Support

There is no support commitment. Questions and problems go to
[GitHub issues](https://github.com/descipar/wled-mcp/issues), which are answered best
effort, without any commitment to respond or fix. There is no security support; see
[SECURITY.md](https://github.com/descipar/wled-mcp/blob/main/SECURITY.md).

The server collects no telemetry, so the project does not know whether it is used. If you
run it, a short note on how you use it and what is missing is welcome as a
[usage feedback issue](https://github.com/descipar/wled-mcp/issues/new?template=usage-feedback.yml).
Please leave out secrets, hostnames and addresses.

## Project and contributing

Roadmap and maintainer documents are in
[docs/PROJECT.md](https://github.com/descipar/wled-mcp/blob/main/docs/PROJECT.md). How to report problems and propose changes is in
[CONTRIBUTING.md](https://github.com/descipar/wled-mcp/blob/main/CONTRIBUTING.md).

### How this project is developed

The maintainer develops this project with coding agents that follow a documented workflow
([AGENTS.md](https://github.com/descipar/wled-mcp/blob/main/AGENTS.md), [docs/AGENT-WORKFLOW.md](https://github.com/descipar/wled-mcp/blob/main/docs/AGENT-WORKFLOW.md),
[docs/DECISIONS.md](https://github.com/descipar/wled-mcp/blob/main/docs/DECISIONS.md)). Human contributions do not need this workflow.

## License

Licensed under the [Apache License 2.0](https://github.com/descipar/wled-mcp/blob/main/LICENSE). Redistributions, including modified
versions, must retain the copyright and attribution notice in [NOTICE](https://github.com/descipar/wled-mcp/blob/main/NOTICE).
The project is provided as is, without security support; see [SECURITY.md](https://github.com/descipar/wled-mcp/blob/main/SECURITY.md).
