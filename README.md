# WLED MCP

An [MCP](https://modelcontextprotocol.io/) server that lets an AI agent inspect and
control [WLED](https://kno.wled.ge/) LED controllers by name: power and brightness,
segments and complete layouts, WLED's built-in effects and palettes, and persistent
presets. It talks to each controller's JSON API directly and runs either as a
subprocess of an MCP host (stdio via `uvx`) or as an independent Streamable HTTP
service.

## What it is and is not

- It is a self-hosted adapter for controllers you configure explicitly. Both
  transports expose the same tools and the same behavior.
- It is not affiliated with, endorsed by or supported by the WLED project or MCPHub.
  The names only describe what it works with.
- It is not a cloud service, a web interface, an animation engine or a home-automation
  integration. It needs no account, MQTT broker or public endpoint, and works
  independently of other home-automation systems.
- It does not discover devices, scan networks or forward arbitrary requests to a
  controller.
- It is not published as a package or container image yet. You build a wheel locally
  from this repository (see the quickstarts and [Project status](#project-status)).

## Features

- Named inventory of controllers in a TOML file; listing needs no network access, an
  optional probe checks reachability with bounded requests.
- Normalized state, capabilities and the device's own effect and palette catalogs,
  cached per firmware.
- Typed changes: master power/brightness/transition, a patch of selected segments, or
  a replacement of the complete segment layout. Omitted fields stay unchanged.
- Preset listing, inspection, activation, saving and deletion, with a durable snapshot
  before a preset is overwritten or deleted.
- `dry_run` on every write, read-back verification after writes, and explicit
  reporting of uncertain outcomes.
- Streamable HTTP service with its own bearer credential and Host/Origin allowlists;
  stdio keeps stdout for the protocol and writes diagnostics to stderr.

### Tools

Hints are MCP tool annotations for the host; they are advisory, not an authorization
barrier.

| Tool | Hint | Purpose |
| --- | --- | --- |
| `wled_list_devices` | read-only | Configured device IDs and names; optional bounded reachability probe |
| `wled_get_state` | read-only | Normalized current state, segments and essential capabilities |
| `wled_get_effects` | read-only | The device's effect IDs and names, with cache freshness |
| `wled_get_palettes` | read-only | The device's palette IDs and names, with cache freshness |
| `wled_set_state` | write | Master power, brightness and one-call transition |
| `wled_patch_segments` | write | Change selected existing segments by ID; others stay unchanged |
| `wled_replace_layout` | destructive | Set the complete active segment layout; unlisted segments are removed |
| `wled_list_presets` | read-only | Persistent preset IDs, names and types |
| `wled_get_preset` | read-only | One stored preset exactly as the device keeps it |
| `wled_activate_preset` | write | Activate an existing state preset or playlist; never edits storage |
| `wled_save_preset` | destructive | Save the current live state as a preset; overwriting needs `overwrite=true` |
| `wled_delete_preset` | destructive | Delete exactly one preset after a durable snapshot |
| `wled_list_snapshots` | read-only | The server's stored preset snapshots, newest first; no device read |
| `wled_restore_preset` | destructive | Restore one snapshot entry; applies it live (or starts the playlist), then stores it |
| `wled_store_preset` | destructive | Store a supplied, validated state as a preset; applies it live, then stores it |

The complete parameter and result contract is in
[docs/TOOL-CONTRACT.md](docs/TOOL-CONTRACT.md).

<!-- wled-coverage:start -->
WLED feature coverage: 43 % of the planned scope, 34 % of WLED overall ([method and list](docs/WLED-COVERAGE.md)).
<!-- wled-coverage:end -->

## Requirements

- Python 3.13 and [uv](https://docs.astral.sh/uv/) (0.11.14 is used in CI) to build the
  wheel and to run the stdio mode.
- An MCP host that can start a stdio server or connect to a Streamable HTTP endpoint,
  for example MCPHub; the examples use MCPHub's `mcpServers` format.
- For the HTTP service: Docker with Docker Compose.
- WLED controllers reachable over HTTP from where the server runs. Hardware acceptance
  so far covers one controller on WLED 16.0.1 (see
  [Validation status](#validation-status-and-limitations)).

## Build a release directory

Both quickstarts start from a local, versioned release directory. From a checkout:

```text
uv sync --locked
uv run --frozen python scripts/check_distribution.py
uv run --frozen python deploy/stage_release.py --output .artifacts/release
```

`check_distribution.py` builds `dist/wled_mcp-<version>-py3-none-any.whl` and verifies
it in a clean environment; `stage_release.py` writes `.artifacts/release/<version>/` with
the wheel, the pinned runtime constraints `requirements-runtime.txt`, the HTTP
`Dockerfile`, `SHA256SUMS` and the `RELEASE` record. `<version>` is the package version
from `pyproject.toml`, or `<version>+g<commit>` for a non-release build staged with
`--non-release` ([versioning](docs/contract/versioning.md)). Nothing is uploaded or published. Copy that directory unchanged to the
host that runs the server and check it there with `sha256sum -c SHA256SUMS`. On
Windows, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for PowerShell commands.

## Example files

Copyable, synthetic starting points; replace every placeholder before use:

| File | Used by |
| --- | --- |
| [examples/mcphub.example.json](examples/mcphub.example.json) | stdio: MCP host entry that runs the staged wheel through `uvx` |
| [examples/compose.http.example.yaml](examples/compose.http.example.yaml) | HTTP: separate Compose project for the service |
| [examples/mcphub.http.example.json](examples/mcphub.http.example.json) | HTTP: MCP host entry with the service URL and bearer header |
| [examples/devices.example.toml](examples/devices.example.toml) | Both: device inventory |

## Quickstart: stdio via uvx

The MCP host starts the server as a subprocess on demand.

1. Place the release directory where the host can read it. The example uses
   `/app/binaries/wled-mcp/REPLACE_WITH_VERSION/` and `/app/data/wled-mcp/` as seen from
   inside an MCPHub container; replace `REPLACE_WITH_VERSION` with the release directory
   name (the `version=` line of its `RELEASE`) and use your own absolute paths elsewhere.
2. Create the data directory and the inventory:

   ```text
   mkdir -p /app/data/wled-mcp/config
   cp examples/devices.example.toml /app/data/wled-mcp/config/devices.toml
   ```

   Edit `devices.toml` as described in [Inventory](#inventory).
3. Register the server with your host. Copy
   [examples/mcphub.example.json](examples/mcphub.example.json); it runs:

   ```text
   uvx --isolated --python 3.13 --constraints /app/binaries/wled-mcp/REPLACE_WITH_VERSION/requirements-runtime.txt --from /app/binaries/wled-mcp/REPLACE_WITH_VERSION/wled_mcp-REPLACE_WITH_VERSION-py3-none-any.whl wled-mcp --transport stdio --config /app/data/wled-mcp/config/devices.toml --data-dir /app/data/wled-mcp
   ```

   Keep each argument separate in the host configuration, and keep the `UV_CACHE_DIR`,
   `UV_TOOL_DIR` and `UV_PYTHON_INSTALL_DIR` variables from the example on persistent
   storage so the environment survives restarts. Other MCP hosts take the same command
   and arguments.
4. Ask the agent to call `wled_list_devices`.

stdout carries only MCP messages; diagnostics go to stderr. Run only one writer per
controller: do not register a stdio entry and an HTTP service against the same devices.

## Quickstart: Streamable HTTP service

The service runs as its own Docker Compose project and the MCP host connects to it over
a private Docker network. No host port is published.

1. Build the image locally from the copied release directory (`<release-dir>`, for
   example `.artifacts/release/<version>` on the build machine); the image is never
   pulled or pushed. The tag is the release version, with `+` replaced by `-` for a
   non-release build (the `image_tag=` line of its `RELEASE`):

   ```text
   docker build --pull -t wled-mcp:<image-tag> <release-dir>
   ```

2. Prepare a deployment directory (the path is an example) with the
   [Compose file](examples/compose.http.example.yaml), the inventory and a generated
   credential:

   ```text
   mkdir -p /srv/wled-mcp-http && cd /srv/wled-mcp-http
   cp <checkout>/examples/compose.http.example.yaml compose.yaml
   mkdir -p data/wled-mcp/config secrets
   cp <checkout>/examples/devices.example.toml data/wled-mcp/config/devices.toml
   (umask 077; python3 -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/wled_mcp_http_token)
   sudo chown -R 10001:10001 data/wled-mcp secrets/wled_mcp_http_token
   sudo chmod 0400 secrets/wled_mcp_http_token
   ```

   Edit `data/wled-mcp/config/devices.toml` ([Inventory](#inventory)), replace
   `REPLACE_WITH_HUB_NETWORK` in `compose.yaml` with the existing Docker network of your
   MCP host and `REPLACE_WITH_IMAGE_TAG` with the tag built in step 1. The credential stays in `secrets/wled_mcp_http_token`; never commit or
   print it.
3. Start and inspect only this project:

   ```text
   docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp
   docker compose -p wled-mcp-http -f compose.yaml ps
   docker compose -p wled-mcp-http -f compose.yaml logs --tail 50 wled-mcp
   ```

4. Register [examples/mcphub.http.example.json](examples/mcphub.http.example.json) with
   your host: URL `http://wled-mcp:8000/mcp` and the header
   `Authorization: Bearer <credential>`, with the credential pasted into the host's
   protected configuration in place of `REPLACE_WITH_PRIVATE_SERVICE_TOKEN`.

The service accepts only requests whose Host header is on its allowlist
(`--allowed-host wled-mcp:8000` in the example) and that carry the bearer credential.
If you change the service name or port, change the Compose service, `--allowed-host`,
the healthcheck and the host URL together. Authentication in the MCP host does not
protect the service itself. Do not expose the endpoint to the internet; plain HTTP is
meant for a trusted, isolated network. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) covers
verification with an authenticated `ping`, updates, rollback and removal.

## Inventory

The server controls only the devices listed in its TOML inventory;
[examples/devices.example.toml](examples/devices.example.toml) is a complete synthetic
example:

```toml
schema_version = 1

[[devices]]
id = "desk"
name = "Example desk strip"
base_url = "http://wled-desk.example.invalid"
```

- `id`: unique lower-case ASCII identifier used by every tool; `name`: display name.
- `base_url`: the controller's HTTP(S) root URL, a host name or a canonical IPv4/IPv6
  address with an optional port; no credentials, path or query.
- Optional `[http]`, `[backups]` and `[features]` tables set timeouts, snapshot
  retention and similar limits; see [docs/INVENTORY-CLIENT.md](docs/INVENTORY-CLIENT.md).
- An empty inventory (`devices = []`, as in
  [examples/bootstrap.toml](examples/bootstrap.toml)) also starts.

The file is read once at startup. To change it, keep a copy of the working file, edit
it and restart the server; there is no reload command
([procedure and rollback](docs/DEPLOYMENT.md#changing-the-inventory)). An invalid file
stops startup with a message that names the rejected entry by position and field,
without echoing values. Nothing is discovered automatically.

## Safety model

- **Validate first.** A complete request is validated against the current device state
  before the first write; unknown fields and out-of-range values are rejected.
  Omitted fields mean "unchanged", never "reset".
- **Patch versus replace.** `wled_patch_segments` changes only the named segments;
  only `wled_replace_layout` removes segments that are not listed.
- **Dry run.** Every write tool accepts `dry_run=true`, which performs bounded reads
  only and returns the plan without writing to the device or the data directory.
- **Verification.** Writes are read back. A write that timed out is reported as
  possibly applied and is never retried blindly.
- **Snapshots.** Overwriting or deleting a preset first stores a durable snapshot in
  the data directory (`backups/<device_id>/`). `wled_restore_preset` writes one
  snapshot entry back; like `wled_store_preset` it changes the live output before it
  stores, and the previous lighting is not restored.
- **No hidden reach.** No discovery, no arbitrary endpoints or caller-supplied hosts,
  no silent preset overwrite; overwriting needs `overwrite=true`.
- **Authorization.** Deciding whether a person may run a tool is the MCP host's job;
  the server adds no interactive approval. The HTTP service additionally requires its
  own bearer credential and Host allowlist. Tool annotations are hints only.

## Validation status and limitations

Automated tests use mocked or synthetic loopback devices and run in CI without
hardware. Hardware acceptance is partial: it was recorded for one RGB controller on WLED
16.0.1 in both transports, and one deployment of both modes on one MCPHub host was
checked. The live offline check (H07) moved to stage 2
([#25](https://github.com/descipar/wled-mcp/issues/25)), and reboot persistence and the
other "Not run" items remain pending; see [docs/VALIDATION.md](docs/VALIDATION.md) and
the status summary in [docs/PROJECT.md](docs/PROJECT.md). No compatibility with other
controllers or firmware versions is claimed.

Known limitations:

- Storing or restoring a preset without changing the live output is not possible on
  WLED 16; playlist authoring and preset import/export are pending
  ([#18](https://github.com/descipar/wled-mcp/issues/18)).
- No CCT white balance or 2D matrix layouts
  ([#19](https://github.com/descipar/wled-mcp/issues/19)); no raw state patch tool.
- No inventory reload or validate command; changes need a restart
  ([#16](https://github.com/descipar/wled-mcp/issues/16)).
- One writer per controller: locks are per process, so a second process or service
  against the same devices is not coordinated.
- In stdio mode the MCP host may stop the subprocess without waiting for a running
  call; a write interrupted that way stays uncertain.
- `tools/list` is CPU-heavy on small hosts
  ([#67](https://github.com/descipar/wled-mcp/issues/67)).
- No published package, image or registry entry; live updates between versions are
  part of stage 2 ([#21](https://github.com/descipar/wled-mcp/issues/21)).

## Documentation

| Document | Contents |
| --- | --- |
| [Deployment](docs/DEPLOYMENT.md) | Both transports in detail: staging, verification, update, rollback, removal |
| [Tool contract](docs/TOOL-CONTRACT.md) | Tools, parameters, results, errors and mutation semantics |
| [WLED feature coverage](docs/WLED-COVERAGE.md) | WLED features with support status, owning issue or decision, and coverage figures |
| [Inventory and client](docs/INVENTORY-CLIENT.md) | Inventory schema, limits and HTTP client behavior |
| [Development](docs/DEVELOPMENT.md) | Local checks, build and launch, including PowerShell |
| [Validation](docs/VALIDATION.md) | Automated checks, opt-in hardware checks and recorded evidence |
| [Architecture](docs/ARCHITECTURE.md) | Components, runtime and design decisions |
| [Contract examples](examples/contracts/README.md) | Synthetic request, result and snapshot examples |

## Project status

wled-mcp is pre-release software. No release has been made, and it is not published
to PyPI or GHCR: there is no package, container image or registry entry to install.
Build it locally from a checkout as described in the quickstarts. Future releases will
use `0.x` versions, which may contain breaking changes.

## Support

There is no support commitment. Questions and problems go to
[GitHub issues](https://github.com/descipar/wled-mcp/issues), which are answered best
effort, without any commitment to respond or fix. There is no security support; see
[SECURITY.md](SECURITY.md).

## Project and contributing

Project status, roadmap and the maintainer document index are in
[docs/PROJECT.md](docs/PROJECT.md). How to report problems and propose changes is in
[CONTRIBUTING.md](CONTRIBUTING.md). Issues: https://github.com/descipar/wled-mcp/issues.

### How this project is developed

The maintainer develops this project with coding agents that follow a documented
workflow: [AGENTS.md](AGENTS.md) holds the project rules,
[docs/AGENT-WORKFLOW.md](docs/AGENT-WORKFLOW.md) describes the requirements,
implementation, review and completion roles, and the `agents/` directory holds the
role definitions. Human contributions do not need this workflow. Design decisions and
their rationale are recorded in [docs/DECISIONS.md](docs/DECISIONS.md) and, per issue, in
[docs/decisions/](docs/decisions/README.md).

## License

Licensed under the [Apache License 2.0](LICENSE). Redistributions, including modified
versions, must retain the copyright and attribution notice in [NOTICE](NOTICE).
The project is provided as is, without security support; see [SECURITY.md](SECURITY.md).
