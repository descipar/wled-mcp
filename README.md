# WLED MCP

An unofficial [MCP](https://modelcontextprotocol.io/) server that lets an AI agent read
and control [WLED](https://kno.wled.ge/) LED controllers by name: power, brightness,
segments, effects, palettes, presets, groups and scenes. It talks to each controller's
JSON API on your network, validates every change before sending it and reads it back
afterwards. It runs as a subprocess of your MCP host (stdio) or as a separate HTTP
service. It is not affiliated with, endorsed by or supported by the WLED project or
MCPHub.

**Status:** early software with `0.x` versions that may break between releases
([CHANGELOG.md](https://github.com/descipar/wled-mcp/blob/main/CHANGELOG.md)). Releases are distributed on PyPI as
[`wled-mcp`](https://pypi.org/project/wled-mcp/) (the first two releases are Git tags only);
a release that is not listed there installs from its Git tag instead. The container image is not published to GHCR.
Hardware acceptance is partial: one controller on WLED 16.0.1. No support is promised
([Support](https://github.com/descipar/wled-mcp/blob/main/README.md#support)).

## What it does

- Self-hosted: no cloud service, account, MQTT broker or public endpoint is needed.
- Named inventory of controllers in a TOML file. The server and its tools discover
  nothing; `wled-mcp discover` is an opt-in command.
- Normalized state, capabilities and each device's own effect and palette catalogs.
- Typed changes: master power and brightness, a patch of selected segments, or a
  replacement of the complete layout. Advanced segment fields (CCT, 2D) are written only
  where the device reports them.
- Persistent presets with snapshots, restore, portable bundles and playlists; named
  device groups and multi-device scenes with a dry-run plan.
- Server-enforced profiles (`read-only`, `control`, `full`) and, for the HTTP service, a
  bearer credential with Host and Origin allowlists.

Every tool, with its read-only, write or destructive hint, is listed in the
[tool contract](https://github.com/descipar/wled-mcp/blob/main/docs/TOOL-CONTRACT.md#tools-at-a-glance).

<!-- wled-coverage:start -->
WLED feature coverage: 59 % of the planned scope, 47 % of WLED overall ([method and list](https://github.com/descipar/wled-mcp/blob/main/docs/WLED-COVERAGE.md)).
<!-- wled-coverage:end -->

## Try it

You need [uv](https://docs.astral.sh/uv/), an MCP host that can start a stdio server and
a WLED controller reachable over HTTP; the optional HTTP service also needs Docker with
Docker Compose. Replace `<version>` with the version of the
[latest release](https://github.com/descipar/wled-mcp/releases/latest) (its tag is
`v<version>`). The commands install that release from
[PyPI](https://pypi.org/project/wled-mcp/). If the version is not listed there yet, use the
Git route instead: replace `wled-mcp==<version>` with
`git+https://github.com/descipar/wled-mcp@v<version>`, which builds the package from the tag
on your machine; without a tag, `uvx` takes the current `main`, which can change at any
time. The commands are for a POSIX shell; Windows is experimental
([docs/DEVELOPMENT.md](https://github.com/descipar/wled-mcp/blob/main/docs/DEVELOPMENT.md)).

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

Both routes need network access (the Git route to GitHub as well as PyPI). The dependencies
are resolved within the ranges the package declares when `uvx` first creates the tool
environment, so they can be newer than the set the release was tested with; for that tested
set add the release constraints ([dependency policy](https://github.com/descipar/wled-mcp/blob/main/docs/contract/dependencies.md)). For a
checksum-verified wheel, more devices, the
[inventory format](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md#inventory) and the HTTP service, follow the
[quickstarts](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md); updates, rollback and removal are in
[docs/DEPLOYMENT.md](https://github.com/descipar/wled-mcp/blob/main/docs/DEPLOYMENT.md).

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

## Compatibility

What the checks cover; the evidence for each row and the firmware tiers are in
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

Automated tests use mocks and synthetic loopback devices. Hardware acceptance covers the
first feature set on one RGB controller, and a live check with an offline controller is
still pending. A short live check of release 0.1.1 over HTTP and stdio covered state
reads, power, brightness and effect changes on that controller
([record](https://github.com/descipar/wled-mcp/blob/main/docs/validation/live-check-2026-11-08.md)). A later run on the same controller
exercised a one-device group and scene, preset store, export, import and restore, and a
playlist, with the controller restored afterwards
([record](https://github.com/descipar/wled-mcp/blob/main/docs/validation/issue-134.md)). Multi-device scenes, profiles, `discover`, restore
onto an occupied slot, playlist import, restoring a playlist preset and CCT, RGBW and 2D controllers have no hardware run.
Other limits:

- No tool deletes a snapshot on request; snapshots are only removed by retention pruning
  (20 per controller by default).
- Storing, restoring or importing a preset without changing the live output is not
  possible on WLED 16, and saving a playlist starts it.
- One writer per controller: locks are per process, so a second process or service against
  the same devices is not coordinated.
- No inventory reload; changes need `wled-mcp config validate` and a restart.
- No device authentication: WLED has none for its light API ("Anyone with your IP and port
  can control the lights", [WLED docs](https://kno.wled.ge/advanced/ota-lock/)). The server
  sends no device credentials and rejects credentials in a device URL, so a controller
  behind HTTP authentication or a credentialed proxy is not supported. Behavior with a
  settings PIN or OTA lock is untested; a test is planned
  ([#128](https://github.com/descipar/wled-mcp/issues/128)).
- No image on GHCR, no registry entry. A live update of a deployed HTTP
  service was checked once, from an earlier build to release 0.1.1; a rollback has not
  been checked.

The complete list and the evidence are in
[docs/VALIDATION.md](https://github.com/descipar/wled-mcp/blob/main/docs/VALIDATION.md#known-limitations).

## Documentation

| Document | Contents |
| --- | --- |
| [Quickstarts](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md) | Release directory, stdio and HTTP setup, inventory format |
| [Deployment](https://github.com/descipar/wled-mcp/blob/main/docs/DEPLOYMENT.md) | Both transports in detail: staging, verification, update, rollback, removal |
| [Tool contract](https://github.com/descipar/wled-mcp/blob/main/docs/TOOL-CONTRACT.md) | Tools, parameters, results, errors and mutation semantics |
| [WLED feature coverage](https://github.com/descipar/wled-mcp/blob/main/docs/WLED-COVERAGE.md) | WLED features with support status, owning issue or decision, and coverage figures |
| [Inventory and client](https://github.com/descipar/wled-mcp/blob/main/docs/INVENTORY-CLIENT.md) | Inventory schema, limits and HTTP client behavior |
| [Development](https://github.com/descipar/wled-mcp/blob/main/docs/DEVELOPMENT.md) | Local checks, build and launch, including PowerShell |
| [Validation](https://github.com/descipar/wled-mcp/blob/main/docs/VALIDATION.md) | Automated checks, opt-in hardware checks, recorded evidence, known limitations |
| [Architecture](https://github.com/descipar/wled-mcp/blob/main/docs/ARCHITECTURE.md) | Components, runtime and design decisions |
| [Contract examples](https://github.com/descipar/wled-mcp/blob/main/examples/contracts/README.md) | Synthetic request, result and snapshot examples |

## Support

There is no support commitment. Questions and problems go to
[GitHub issues](https://github.com/descipar/wled-mcp/issues), which are answered best
effort, without any commitment to respond or fix. There is no security support; see
[SECURITY.md](https://github.com/descipar/wled-mcp/blob/main/SECURITY.md).

## Project and contributing

Project status, roadmap and the maintainer document index are in
[docs/PROJECT.md](https://github.com/descipar/wled-mcp/blob/main/docs/PROJECT.md). How to report problems and propose changes is in
[CONTRIBUTING.md](https://github.com/descipar/wled-mcp/blob/main/CONTRIBUTING.md).

### How this project is developed

The maintainer develops this project with coding agents that follow a documented
workflow: [AGENTS.md](https://github.com/descipar/wled-mcp/blob/main/AGENTS.md) holds the project rules,
[docs/AGENT-WORKFLOW.md](https://github.com/descipar/wled-mcp/blob/main/docs/AGENT-WORKFLOW.md) describes the requirements,
implementation, review and completion roles, and the `agents/` directory holds the
role definitions. Human contributions do not need this workflow. Design decisions and
their rationale are recorded in [docs/DECISIONS.md](https://github.com/descipar/wled-mcp/blob/main/docs/DECISIONS.md) and, per issue, in
[docs/decisions/](https://github.com/descipar/wled-mcp/blob/main/docs/decisions/README.md).

## License

Licensed under the [Apache License 2.0](https://github.com/descipar/wled-mcp/blob/main/LICENSE). Redistributions, including modified
versions, must retain the copyright and attribution notice in [NOTICE](https://github.com/descipar/wled-mcp/blob/main/NOTICE).
The project is provided as is, without security support; see [SECURITY.md](https://github.com/descipar/wled-mcp/blob/main/SECURITY.md).
