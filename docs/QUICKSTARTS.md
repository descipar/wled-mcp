# Quickstarts and inventory

Setup for both transports from a locally built release directory, the example files and the inventory format. The shortest way to try the server (PyPI, no build) is in the [README](../README.md#try-it). Operating the deployment (verification, update, rollback, removal) is in [DEPLOYMENT.md](DEPLOYMENT.md).

## Build a release directory

Stage it on the machine that will run the server, from a clean checkout of the release tag or commit, never elsewhere and copied ([DEC-026](DECISIONS.md#dec-026--stage-releases-on-the-target-machine)):

```text
uv sync --locked
uv run --frozen python scripts/check_distribution.py
uv run --frozen python deploy/stage_release.py --output .artifacts/release
```

This writes `.artifacts/release/<version>/` (wheel, pinned `requirements-runtime.txt`, HTTP `Dockerfile`, `SHA256SUMS`, `RELEASE`); `<version>` is the `pyproject.toml` version, or `<version>+g<12hex>` with `--non-release`. Details, verification and non-release builds: [DEPLOYMENT.md](DEPLOYMENT.md#build-and-stage-a-release); Windows commands: [DEVELOPMENT.md](DEVELOPMENT.md).

## Example files

Synthetic starting points; replace every placeholder:

| File | Used by |
| --- | --- |
| [examples/mcphub.example.json](../examples/mcphub.example.json) | stdio: host entry that runs the staged wheel through `uvx` |
| [examples/compose.http.example.yaml](../examples/compose.http.example.yaml) | HTTP: separate Compose project |
| [examples/mcphub.http.example.json](../examples/mcphub.http.example.json) | HTTP: host entry with service URL and bearer header |
| [examples/devices.example.toml](../examples/devices.example.toml) | Both: device inventory |

## Quickstart: stdio via uvx

The MCP host starts the server as a subprocess on demand.

1. Place the release directory where the host can read it. The example uses `/app/binaries/wled-mcp/REPLACE_WITH_VERSION/` and `/app/data/wled-mcp/` as seen inside an MCPHub container; replace `REPLACE_WITH_VERSION` with the release directory name (the `version=` line of `RELEASE`) and use your own absolute paths elsewhere.
2. Create the data directory and inventory, then edit `devices.toml` ([Inventory](#inventory)):

   ```text
   mkdir -p /app/data/wled-mcp/config
   cp examples/devices.example.toml /app/data/wled-mcp/config/devices.toml
   ```

3. Register the server: copy [examples/mcphub.example.json](../examples/mcphub.example.json); it runs:

   ```text
   uvx --isolated --python 3.13 --constraints /app/binaries/wled-mcp/REPLACE_WITH_VERSION/requirements-runtime.txt --from /app/binaries/wled-mcp/REPLACE_WITH_VERSION/wled_mcp-REPLACE_WITH_VERSION-py3-none-any.whl wled-mcp --transport stdio --config /app/data/wled-mcp/config/devices.toml --data-dir /app/data/wled-mcp
   ```

   Keep each argument separate, and keep `UV_CACHE_DIR`, `UV_TOOL_DIR` and `UV_PYTHON_INSTALL_DIR` from the example on persistent storage. Other MCP hosts take the same command and arguments.
4. Ask the agent to call `wled_list_devices`.

stdout carries only MCP messages; diagnostics go to stderr. Run one writer per controller: not a stdio entry and an HTTP service against the same devices.

### Installing without a release directory

If the README try-it version is not on PyPI yet, replace `wled-mcp==<version>` with `git+https://github.com/descipar/wled-mcp@v<version>` (builds from the tag; without a tag `uvx` takes the current `main`, which can change at any time). Dependencies resolve within the declared ranges and can be newer than the tested set; add the release constraints for that set ([dependency policy](contract/dependencies.md)). For a checksum-verified wheel use the release directory above.

## Quickstart: Streamable HTTP service

Needs Docker with Docker Compose. The service is its own Compose project; the MCP host connects over a private Docker network and no host port is published.

1. Build the image locally from the release directory (`<release-dir>`, for example `.artifacts/release/<version>`); it is never pulled or pushed. The tag is the release version with `+` replaced by `-` for a non-release build (the `image_tag=` line of `RELEASE`):

   ```text
   docker build --pull -t wled-mcp:<image-tag> <release-dir>
   ```

2. Prepare a deployment directory (example path) with the [Compose file](../examples/compose.http.example.yaml), the inventory and a generated credential:

   ```text
   mkdir -p /srv/wled-mcp-http && cd /srv/wled-mcp-http
   cp <checkout>/examples/compose.http.example.yaml compose.yaml
   mkdir -p data/wled-mcp/config secrets
   cp <checkout>/examples/devices.example.toml data/wled-mcp/config/devices.toml
   (umask 077; python3 -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/wled_mcp_http_token)
   sudo chown -R 10001:10001 data/wled-mcp secrets/wled_mcp_http_token
   sudo chmod 0400 secrets/wled_mcp_http_token
   ```

   Edit `data/wled-mcp/config/devices.toml` ([Inventory](#inventory)), replace `REPLACE_WITH_HUB_NETWORK` in `compose.yaml` with your host's existing Docker network and `REPLACE_WITH_IMAGE_TAG` with the tag from step 1. The credential stays in `secrets/wled_mcp_http_token`; never commit or print it.
3. Start and inspect only this project:

   ```text
   docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp
   docker compose -p wled-mcp-http -f compose.yaml ps
   docker compose -p wled-mcp-http -f compose.yaml logs --tail 50 wled-mcp
   ```

4. Register [examples/mcphub.http.example.json](../examples/mcphub.http.example.json) with your host: URL `http://wled-mcp:8000/mcp` and the header `Authorization: Bearer <credential>`, the credential pasted into the host's protected configuration in place of `REPLACE_WITH_PRIVATE_SERVICE_TOKEN`.

The service accepts only requests whose Host is on its allowlist (`--allowed-host wled-mcp:8000` in the example) and that carry the bearer credential; if you change the service name or port, change the Compose service, `--allowed-host`, the healthcheck and the host URL together. Host authentication does not protect the service itself. Do not expose the endpoint to the internet; plain HTTP is for a trusted, isolated network. [DEPLOYMENT.md](DEPLOYMENT.md) covers the authenticated `ping`, updates, rollback and removal.

## Inventory

The server controls only the devices in its TOML inventory; [examples/devices.example.toml](../examples/devices.example.toml) is a complete synthetic example:

```toml
schema_version = 1

[[devices]]
id = "desk"
name = "Example desk strip"
base_url = "http://wled-desk.example.invalid"
```

- `id`: unique lower-case ASCII identifier used by every tool; `name`: display name.
- `base_url`: the controller's HTTP(S) root URL, a host name or canonical IPv4/IPv6 address with an optional port; no credentials, path or query.
- Optional `[http]`, `[backups]` and `[features]` tables set timeouts, snapshot retention and similar limits ([docs/INVENTORY-CLIENT.md](INVENTORY-CLIENT.md)).
- An empty inventory (`devices = []`, [examples/bootstrap.toml](../examples/bootstrap.toml)) also starts.

`wled-mcp config init --config <abs>` writes a new inventory (optionally with one device), `wled-mcp config add-device` appends one and `wled-mcp config validate` checks a file with the startup validator without contacting any device. The file is read at startup; to change it by hand keep a copy, edit, run `config validate` and restart ([procedure and rollback](DEPLOYMENT.md#changing-the-inventory)). An agent can change it without a restart through the M8 tools (merged, not yet released; below). An invalid file stops startup with a message naming the entry by position and field, without values. Nothing is discovered automatically: `wled-mcp discover` sends one mDNS query and prints the `config add-device` command per answering controller, writing nothing (multicast does not cross VLANs and usually not a container bridge network). The read-only `wled-mcp doctor` reports configuration, storage, device and endpoint problems with fixed codes and a sanitized `--export` summary ([CLI contract](contract/cli.md)).

### Agent-driven path (milestone M8, not yet released)

An agent can find and add controllers through the MCP client. The tools are merged but not in a released version; live evidence was recorded on 2026-11-20 ([validation/issue-204.md](validation/issue-204.md)). Each step is an explicit call; nothing runs at startup ([contract](contract/discovery.md)):

1. `wled_discover_devices` runs mDNS and, when ranges are stored, a bounded read-only `GET /json/info` probe of those RFC 1918 ranges (at most a /24 each). It lists candidates as `new`, `known` or `address_changed` plus a coverage report and writes nothing. From a container mDNS usually finds nothing, which the report states.
2. Optional: `wled_set_discovery_ranges` stores the private ranges to probe (the complete new list; `dry_run` shows the result). It writes only the inventory file and contacts no device. Without stored ranges only mDNS runs and proposed ranges are returned, never probed.
3. `wled_add_device` adds one candidate by IPv4 address after one verifying `GET /json/info`; the MCP client asks the person to confirm. The entry is in effect at once, without a restart, in stdio and HTTP; it never writes to the device. A duplicate ID, address or MAC is refused.

Both writing tools need the profile `full` and a config directory the server can write (a mounted directory, [Persistent paths](DEPLOYMENT.md#persistent-paths)). The CLI path stays available for hand editing.
