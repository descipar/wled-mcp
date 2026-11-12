# Quickstarts and inventory

Step-by-step setup for both transports from a locally built release directory, the example
files, and the device inventory format. The shortest way to try the server, installing from
PyPI without building anything, is in the [README](../README.md#try-it). Operating the
deployment (verification, update, rollback, removal) is in [DEPLOYMENT.md](DEPLOYMENT.md).

## Build a release directory

Both quickstarts start from a local, versioned release directory. Stage it on the machine
that will run the server, from a clean checkout of the release tag or commit, and do not
build it elsewhere and copy it ([DEC-026](DECISIONS.md#dec-026--stage-releases-on-the-target-machine)):

```text
uv sync --locked
uv run --frozen python scripts/check_distribution.py
uv run --frozen python deploy/stage_release.py --output .artifacts/release
```

`check_distribution.py` builds `dist/wled_mcp-<version>-py3-none-any.whl` and verifies
it in a clean environment; `stage_release.py` writes `.artifacts/release/<version>/` with
the wheel, the pinned runtime constraints `requirements-runtime.txt`, the HTTP
`Dockerfile`, `SHA256SUMS` and the `RELEASE` record. `<version>` is the package version
from `pyproject.toml`, or `<version>+g<12hex>` (the first 12 hex digits of the source
commit) for a non-release build staged with `--non-release`
([versioning](contract/versioning.md)). Nothing is uploaded or published. Check the
directory with `sha256sum -c SHA256SUMS` before use. On
Windows, see [docs/DEVELOPMENT.md](DEVELOPMENT.md) for PowerShell commands.

## Example files

Copyable, synthetic starting points; replace every placeholder before use:

| File | Used by |
| --- | --- |
| [examples/mcphub.example.json](../examples/mcphub.example.json) | stdio: MCP host entry that runs the staged wheel through `uvx` |
| [examples/compose.http.example.yaml](../examples/compose.http.example.yaml) | HTTP: separate Compose project for the service |
| [examples/mcphub.http.example.json](../examples/mcphub.http.example.json) | HTTP: MCP host entry with the service URL and bearer header |
| [examples/devices.example.toml](../examples/devices.example.toml) | Both: device inventory |

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
   [examples/mcphub.example.json](../examples/mcphub.example.json); it runs:

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

### Installing without a release directory

The README try-it commands install a release from PyPI. If the version is not listed there
yet, replace `wled-mcp==<version>` with `git+https://github.com/descipar/wled-mcp@v<version>`,
which builds the package from the tag on your machine; without a tag, `uvx` takes the
current `main`, which can change at any time. Both routes need network access (the Git
route to GitHub as well as PyPI). The dependencies are resolved within the ranges the
package declares when `uvx` first creates the tool environment, so they can be newer than
the set the release was tested with; for that tested set add the release constraints
([dependency policy](contract/dependencies.md)). For a checksum-verified wheel use the
release directory above.

## Quickstart: Streamable HTTP service

The service needs Docker with Docker Compose. It runs as its own Compose project and the MCP host connects to it over
a private Docker network. No host port is published.

1. Build the image locally from the copied release directory (`<release-dir>`, for
   example `.artifacts/release/<version>` on the machine that runs the service); the image is never
   pulled or pushed. The tag is the release version, with `+` replaced by `-` for a
   non-release build (the `image_tag=` line of its `RELEASE`):

   ```text
   docker build --pull -t wled-mcp:<image-tag> <release-dir>
   ```

2. Prepare a deployment directory (the path is an example) with the
   [Compose file](../examples/compose.http.example.yaml), the inventory and a generated
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
   MCP host and `REPLACE_WITH_IMAGE_TAG` with the tag built in step 1. The credential
   stays in `secrets/wled_mcp_http_token`; never commit or print it.
3. Start and inspect only this project:

   ```text
   docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp
   docker compose -p wled-mcp-http -f compose.yaml ps
   docker compose -p wled-mcp-http -f compose.yaml logs --tail 50 wled-mcp
   ```

4. Register [examples/mcphub.http.example.json](../examples/mcphub.http.example.json) with
   your host: URL `http://wled-mcp:8000/mcp` and the header
   `Authorization: Bearer <credential>`, with the credential pasted into the host's
   protected configuration in place of `REPLACE_WITH_PRIVATE_SERVICE_TOKEN`.

The service accepts only requests whose Host header is on its allowlist
(`--allowed-host wled-mcp:8000` in the example) and that carry the bearer credential.
If you change the service name or port, change the Compose service, `--allowed-host`,
the healthcheck and the host URL together. Authentication in the MCP host does not
protect the service itself. Do not expose the endpoint to the internet; plain HTTP is
meant for a trusted, isolated network. [docs/DEPLOYMENT.md](DEPLOYMENT.md) covers
verification with an authenticated `ping`, updates, rollback and removal.

## Inventory

The server controls only the devices listed in its TOML inventory;
[examples/devices.example.toml](../examples/devices.example.toml) is a complete synthetic
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
  retention and similar limits; see [docs/INVENTORY-CLIENT.md](INVENTORY-CLIENT.md).
- An empty inventory (`devices = []`, as in
  [examples/bootstrap.toml](../examples/bootstrap.toml)) also starts.

`wled-mcp config init --config <abs>` writes a new inventory (optionally with one
device), `wled-mcp config add-device` appends a device and `wled-mcp config validate`
checks a file with the startup validator, without contacting any device. The file is
read once at startup. To change it, keep a copy of the working file, edit it, run
`config validate` and restart the server; there is no reload command
([procedure and rollback](DEPLOYMENT.md#changing-the-inventory)). An invalid file
stops startup with a message that names the rejected entry by position and field,
without echoing values. Nothing is discovered automatically: on request,
`wled-mcp discover` sends one mDNS query on the local network and prints the
`config add-device` command for each answering controller, without writing anything
(multicast does not cross VLANs and usually not a container bridge network). The
read-only `wled-mcp doctor` reports configuration, storage, device and endpoint
problems with fixed codes and a sanitized `--export` summary
([CLI contract](contract/cli.md)).
