# Deployment and operations

**Status: one live check of both modes on one target.** The artifacts and procedures
below (#11) are covered by device-free tests and were exercised once on one MCPHub target
for both modes (build, start, hub registration, reads, recreation, restart, idle
measurements, stdio entry removal and an authorized power on/off on one test controller);
see [VALIDATION.md](VALIDATION.md#issue-11-live-deployment-check-2026-11-06). Update and
rollback between two versions, removal of the HTTP service and hub container recreation
have not been run yet and remain pending. All names, paths and networks below are
synthetic placeholders; confirm them on the actual installation. Any further deployment
needs its own instruction naming the mode and target.

## Two supported modes

Both modes are required v1 scope and use the same package/tools. Streamable HTTP is the independent-service deployment; stdio via uvx is the client-managed deployment. Each deployment selects one mode explicitly. Do not run two independently writing instances against the same controllers while assuming their process-local locks coordinate them: an HTTP service and a stdio entry that are both active against the same controllers, or two HTTP replicas, are not coordinated.

| Mode | Lifecycle owner | MCPHub connection | Runtime context | Artifacts |
| --- | --- | --- | --- | --- |
| Streamable HTTP | Separate Compose project `wled-mcp-http` | Private `/mcp` URL and configured bearer credential | WLED-MCP service container | [Dockerfile](../deploy/http/Dockerfile), [build-context allowlist](../deploy/http/Dockerfile.dockerignore), [Compose example](../examples/compose.http.example.yaml), [hub HTTP entry](../examples/mcphub.http.example.json) |
| stdio via uvx | MCPHub/client | Command plus separate arguments, `--transport stdio` | Hub/client-managed subprocess | [hub stdio entry](../examples/mcphub.example.json) |

Both modes consume the same staged, versioned release directory (wheel plus runtime
constraints), see [Build and stage a release](#build-and-stage-a-release). The defaults
are agent proposals recorded as ISSUE-11-DEC-002 in
[decisions/issue-11.md](decisions/issue-11.md), not human decisions.

The default console mode is stdio and opens no listener. HTTP is selected with `--transport streamable-http`, configurable bind/port, one worker and SDK-managed lifecycle. Bind defaults to loopback; a separate container service explicitly binds its private container interface and restricts Host/Origin appropriately. Do not use the deprecated SSE-only transport.

## Addresses and paths as seen from each context

`localhost` always means the container or process doing the lookup. Inside MCPHub it is
the hub container itself, never the separate wled-mcp service.

| Seen from | HTTP service endpoint | Inventory / data directory |
| --- | --- | --- |
| Host shell | Not reachable: no host port is published. Use `docker compose -p wled-mcp-http -f compose.yaml exec` for checks. | `./data/wled-mcp/` next to the deployed `compose.yaml` |
| MCPHub container (same Docker network) | `http://wled-mcp:8000/mcp` (Compose service name and container port) | stdio mode: `/app/data/wled-mcp/` as mounted into the hub container |
| wled-mcp service container | Binds `0.0.0.0:8000`; `127.0.0.1:8000` only for the healthcheck and exec checks, still sending `Host: wled-mcp:8000` | `/app/data/wled-mcp/` (bind mount of the host directory) |
| stdio subprocess | No address, no listener | Paths inside the hub container |

Inventory `base_url` hosts must be valid RFC 1123 host labels: letters, digits and
hyphens, no underscore (an underscore name is currently rejected at startup, see
[#61](https://github.com/descipar/wled-mcp/issues/61)). Use a reserved DNS name that
resolves to exactly one address from the service's context, or the controller's
address; a name resolving to several addresses makes requests ambiguous.

The hub URL authority (`wled-mcp:8000`) must equal an `--allowed-host` entry exactly
(case-insensitive). If the actual service name, alias or port differs, change the
Compose service, `--allowed-host`, the healthcheck port and the hub URL together. The
service must also reach the configured WLED controllers from its own network.

## Streamable HTTP service configuration

The Compose example runs the image entrypoint `wled-mcp` with this exec-form command:

```text
wled-mcp --config /app/data/wled-mcp/config/devices.toml --data-dir /app/data/wled-mcp \
  --transport streamable-http --host 0.0.0.0 --port 8000 \
  --allowed-host wled-mcp:8000 --http-token-file /run/secrets/wled_mcp_http_token
```

- Endpoint: fixed path `/mcp`; one worker; process-local locks do not coordinate a second process or worker against the same controllers.
- Credential: exactly one of `WLED_MCP_HTTP_TOKEN` or `--http-token-file` (absolute path, at most 1 KiB, read once at startup; rotate by restarting). 32 to 512 printable ASCII characters. The file must be readable only by the service user; permission modes are not enforced. Never pass the value as a CLI argument. A missing, conflicting or invalid credential exits 2 before listening. The Compose example uses only the file form.
- Bind and allowlists: the default is `127.0.0.1:8000` with allowed hosts `127.0.0.1:8000` and `localhost:8000`. A different host or port, including a wildcard bind such as `0.0.0.0` for a private container interface, requires explicit `--allowed-host` entries naming the authority clients use (exact, case-insensitive, no implicit default-port equivalence). `--allowed-origin` is empty by default and stays empty in the example: MCPHub is a server-side client and sends no browser Origin; requests without Origin are accepted when authenticated. An authenticating proxy must forward the original authority in `Host` and be listed explicitly; forwarded headers are never trusted and no proxy trust option exists.
- Rejections: wrong Host/Origin 403, missing or wrong credential 401, other path 404, any method except POST 405, body over 256 KiB 413, all before any tool or device work.
- Sessions: none. Responses carry no `Mcp-Session-Id`; a stale ID is ignored; reconnecting clients start new invocations and the service never replays a write. A client that disconnects during a call does not cancel it; verification and lock release continue.
- Shutdown: SIGTERM/SIGINT stop admission, drain in-flight calls for up to the configured operation timeout plus 2 s (at most 122 s), close shared resources once and exit 0. The example sets `stop_grace_period: 130s` and an exec-form entrypoint so PID 1 receives SIGTERM directly. A forced kill leaves a possibly applied write uncertain and it is never resumed.
- Liveness without device access: there is no unauthenticated health route. The Compose healthcheck is a TCP connect to `127.0.0.1:8000` with the image's Python; the stronger manual check is an authenticated JSON-RPC `ping` (below). Neither contacts a device.
- Logging: diagnostics go to stderr only (stdout stays unused); the credential, supplied Host/Origin values, bodies and device URLs are not logged. Rejection events log a fixed class only and a flood can produce noise. There is no rate limiting or lockout; credential strength is the control for a private network, and plain HTTP is only for a trusted isolated network.

Hardening in the example: separate project, no `ports:`, joins the hub network as
`external`, `restart: unless-stopped`, read-only root filesystem with a writable data
bind mount and tmpfs `/tmp`, all capabilities dropped, `no-new-privileges`, non-root
UID/GID 10001 (build arguments `APP_UID`/`APP_GID`), no `environment` credential.

## Build and stage a release

Releases are immutable versioned directories. Both modes use the same directory, by
default `/app/binaries/wled-mcp/<version>/` on the target (TD-1). From a clean checkout
of the selected commit on a build machine:

```text
uv sync --locked
uv run --frozen python scripts/check_distribution.py
uv run --frozen python deploy/stage_release.py --output .artifacts/release
```

`check_distribution.py` builds `dist/wled_mcp-<version>-py3-none-any.whl` and verifies it
(clean install, stdio, HTTP restart, uvx and the stdio hub example). `stage_release.py`
creates `.artifacts/release/<version>/` with the wheel, `requirements-runtime.txt`, the
HTTP `Dockerfile`, its allowlist `.dockerignore`, `SHA256SUMS` and `RELEASE` (version,
source commit, clean/modified tree). It refuses to overwrite an existing version and
warns about a modified tree. Copy the directory unchanged to the target and verify it
there before use:

```text
cd /app/binaries/wled-mcp/0.1.0
sha256sum -c SHA256SUMS
cat RELEASE
```

The checksums travel with the artifacts, so they detect transit corruption, not a
replaced directory: compare the wheel and constraints values with those printed by
`stage_release.py` on the build machine. Record the source commit, wheel and
constraints SHA-256 values and, for HTTP, the image ID in the [operations record](../deploy/operations-record.template.md). Keep the
previous release directory until the new one is confirmed; it is the rollback source.

Alternatives, not the default: a private Git source pinned to a full 40-hex commit
(`git+https://.../wled-mcp@<commit>`; needs credentials in the execution context and is
never pinned to a branch or tag), and an offline wheelhouse (`--find-links <dir>
--no-index`, architecture-specific for the compiled dependencies). Runtime dependencies
otherwise come from the package index on first install, pinned by the constraints.
Constraints pin versions but do not enforce artifact hashes; keep the trusted wheel.
Never point a deployment at an editable checkout, `@latest`, an unpinned Git branch or
an index package of the same name.

## HTTP service: build, start, verify

The image is built locally on the target from the staged directory and never pushed:

```text
docker build --pull -t wled-mcp:0.1.0 /app/binaries/wled-mcp/0.1.0
docker image inspect --format '{{.Id}}' wled-mcp:0.1.0
```

The Dockerfile pins `python:3.13.18-slim-trixie` by tag and multi-architecture index
digest, requires `SHA256SUMS` to list the wheel and `requirements-runtime.txt` exactly
once each and both to match (otherwise the build fails), installs only the copied
wheel with `--constraint requirements-runtime.txt` and creates `/app/data/wled-mcp` for the non-root
user. The allowlist `.dockerignore` keeps everything except the wheel, constraints and
`SHA256SUMS` out of the build context, so inventories, data, backups, `.env` files and
secrets cannot enter an image layer. To move to a newer Python 3.13 patch image, change
tag and digest together, rebuild and re-run the checks.

Prepare a dedicated deployment directory (for example `/srv/wled-mcp-http/`, a
placeholder) with the Compose file, inventory and credential. Replace
`REPLACE_WITH_HUB_NETWORK` with the hub's existing Docker network; do not edit the hub's
own Compose file:

```text
cd /srv/wled-mcp-http
cp <checkout>/examples/compose.http.example.yaml compose.yaml
mkdir -p data/wled-mcp/config secrets
cp <local inventory> data/wled-mcp/config/devices.toml
(umask 077; python3 -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/wled_mcp_http_token)
sudo chown -R 10001:10001 data/wled-mcp secrets/wled_mcp_http_token
sudo chmod 0400 secrets/wled_mcp_http_token
docker compose -p wled-mcp-http -f compose.yaml config --quiet
docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp
docker compose -p wled-mcp-http -f compose.yaml ps
docker compose -p wled-mcp-http -f compose.yaml logs --tail 50 wled-mcp
```

The data directory must support hard links (snapshots fail closed with `BACKUP_FAILED`
otherwise) and be writable by the container UID. File secrets are bind-mounted with the
host file's ownership; the credential file must be readable by UID 10001. Never print
or commit the credential; `secrets/` and `data/` are git-ignored patterns.

Authenticated `ping` from inside the service container (no device contact, credential
read from the mounted file and never printed):

```text
docker compose -p wled-mcp-http -f compose.yaml exec -T wled-mcp python - <<'EOF'
import json, urllib.request
with open("/run/secrets/wled_mcp_http_token", encoding="ascii") as stream:
    secret = stream.read().strip()
request = urllib.request.Request(
    "http://127.0.0.1:8000/mcp",
    data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode(),
    headers={"Host": "wled-mcp:8000", "Authorization": "Bearer " + secret,
             "Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
)
with urllib.request.urlopen(request, timeout=5) as response:
    print(response.status, response.read().decode())
EOF
```

Expected output: `200` and an empty JSON-RPC result. Then register the hub entry from
[mcphub.http.example.json](../examples/mcphub.http.example.json): `type`
`streamable-http`, URL `http://wled-mcp:8000/mcp` and the header
`Authorization: Bearer <credential>` stored in the hub's protected configuration. The
example value `REPLACE_WITH_PRIVATE_SERVICE_TOKEN` is literal text; the hub does not
expand placeholders or environment variables there. Hub authentication does not protect
the independently reachable endpoint; the bearer credential is mandatory. Check the
actual MCPHub field names before registration, and the entry owner and reload steps in
[MCPHub notes](#mcphub-notes).

### MCPHub notes

Observed with MCPHub 1.2.1 in the live check:

- Entry owner: the hub's SSRF guard refuses `streamable-http` entries whose URL resolves
  to a private or container address unless the entry's owner is an admin user. An entry
  created with a system API key gets the owner `system` and fails with a message that the
  host "resolves to blocked address". Create the entry through the admin UI, or set its
  owner to an admin user, and then reload the entry. Do not disable the hub's guard
  globally to work around this.
- Reload: an edited entry reconnects only after a reload of that entry (the hub's
  `POST /api/servers/<name>/reload` route or the UI equivalent); this touches only that
  entry, not the hub container.
- The example [mcphub.http.example.json](../examples/mcphub.http.example.json) carries no
  owner field; ownership is hub-side state, not part of the entry schema used here.

## HTTP service: update, rollback, recreation, removal

All commands are scoped to the `wled-mcp-http` project and the `wled-mcp` service; none
of them restarts, recreates or removes the hub or its network.

- Update: stage and build the new version (`wled-mcp:<new>`), keep the previous image
  and release directory, change `image:` in `compose.yaml`, then
  `docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp`. Repeat
  `ps`, `logs` and the authenticated `ping`; the hub reconnects without replaying writes.
- Rollback: set `image:` back to the previous tag (rebuild it from the retained release
  directory if it was removed) and run the same `up -d --no-deps wled-mcp`. Configuration
  is never migrated in place; snapshot local data before any future schema change.
- Runtime recreation: data and inventory live in the bind mount, so recreating the
  container keeps them:

  ```text
  docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps --force-recreate wled-mcp
  ```

  An image rebuild uses the same staged directory and pinned base digest; re-run the
  checks afterwards.
- Credential rotation: replace the secret file, recreate the service as above, then
  update the hub header.
- Stop without removal: `docker compose -p wled-mcp-http -f compose.yaml stop wled-mcp`
  (graceful SIGTERM, up to 130 s).
- Removal of only this service, as separate steps: remove the hub entry in MCPHub; then

  ```text
  docker compose -p wled-mcp-http -f compose.yaml rm --stop --force wled-mcp
  docker image rm wled-mcp:0.1.0
  ```

  Deleting `data/wled-mcp` is a further, explicit decision; backups are never pruned as
  part of update, rollback or removal.

## stdio via uvx: register, update, rollback, rebuild, removal

The hub entry ([mcphub.example.json](../examples/mcphub.example.json)) runs the staged
wheel with the exported constraints; every argument is a separate array element:

```text
uvx --isolated --python 3.13 \
  --constraints /app/binaries/wled-mcp/0.1.0/requirements-runtime.txt \
  --from /app/binaries/wled-mcp/0.1.0/wled_mcp-0.1.0-py3-none-any.whl \
  wled-mcp --transport stdio --config /app/data/wled-mcp/config/devices.toml \
  --data-dir /app/data/wled-mcp
```

- `--constraints` pins every runtime dependency to the locked graph; uvx does not read
  `uv.lock`. `--python 3.13` matches `requires-python`. `--isolated` prevents uvx from
  reusing a separately installed `wled-mcp` tool of another version.
- The entry's `env` sets `UV_CACHE_DIR`, `UV_TOOL_DIR` and `UV_PYTHON_INSTALL_DIR` under
  `/app/data/wled-mcp-uv/`, a persistent tree separate from the server data directory,
  so a cache rebuild can never touch inventory or backups. A managed Python downloaded
  by uv lands in that tree and survives hub container recreation.
- stdio passes no HTTP option and no credential; it opens no listener and stdout carries
  protocol only. Diagnostics go to stderr.
- Prerequisites to verify in the hub container: `uvx` present, the release directory and
  `/app/data/wled-mcp/config/devices.toml` mounted persistently, the data directory
  existing and writable by the hub's process user, and outbound access to the package
  index on first launch (or an offline wheelhouse).
- Update: stage the new version directory, change the version in `--constraints` and
  `--from` together, then restart only this hub entry. Keep the previous directory.
- Rollback: point both paths back to the previous version directory and restart only
  this entry.
- Environment rebuild after a hub image, Python or architecture change: relaunch the
  entry; if it fails to start, stop the entry, delete only `/app/data/wled-mcp-uv/cache`
  (never `/app/data/wled-mcp`) and relaunch, then repeat the read-only checks.
- Removal: delete this single hub entry. The release directory, uv tree and data
  directory are removed only as separate explicit steps; backups are never pruned.

The distribution check runs this exact argument list through uvx with only the
wheel, constraints, config and data paths replaced by local ones.

## Device restoration

Code update or rollback does not undo lighting or preset changes on a device. Restoring
a preset from a snapshot is a manual procedure described in
[TOOL-CONTRACT](TOOL-CONTRACT.md#snapshot-and-explicit-restoration); there is no restore
tool (ISSUE-8-DEC-001). Any write to a device, including a restoration, needs its own
authorization for the selected device. Snapshots stay under
`/app/data/wled-mcp/backups/<device_id>/` in both modes.

## Persistent paths

- `/app/data/wled-mcp/config/devices.toml`: local inventory, not in Git.
- `/app/data/wled-mcp/backups/<device_id>/<backup_id>.json`: persistent preset snapshots (directories 0700, files 0600, created on first snapshot; never in Git). The service user needs write access; keep the volume persistent and back it up like other runtime data. Snapshots are published with a hard link, so a filesystem without hard-link support (some network or FAT volumes) makes every snapshot fail closed with `BACKUP_FAILED`.
- `/app/binaries/wled-mcp/<version>/`: immutable staged release (wheel, constraints, checksums).
- stdio only: `/app/data/wled-mcp-uv/{cache,tools,python}`: uv runtime environment, rebuildable.

Separate immutable code from mutable data and ensure each service user can write only
what is needed. A separate HTTP container does not inherit the hub's mounts or Python
runtime. Merely storing a virtualenv outside a container does not guarantee survival of
a base-image Python/ABI change; rebuild from the wheel and constraints instead. Never
rely on a manually installed package in a container's disposable filesystem.

## Ordered integration procedure

1. Confirm deployment was requested, select HTTP-service or uvx/stdio mode, inspect the actual mounts/runtime/network/architecture and hub entry schema, and preserve the prior hub entry if one exists.
2. Build, check and stage the release; record version, source commit and artifact hashes.
3. Place the release directory and local config in persistent paths with permissions suitable for the service user; never print credentials.
4. From the actual WLED-MCP execution context, read `/json/info` and `/json/state` only for selected configured controllers. Check DNS/IP/port reachability without changing network settings.
5. Start the HTTP service independently and verify its authenticated `/mcp` connection, or launch stdio via uvx. Check initialization, tool listing and a state read, then register the corresponding hub entry and repeat through the hub.
6. Verify the backups path is writable and persistent without invoking a lighting write or preset delete.
7. Run only specifically authorized hardware-write scenarios; record restoration and residual limitations.
8. Restart the independent HTTP service or stdio entry as appropriate. Test reconnect, shutdown and runtime recreation persistence when authorized and operationally appropriate; otherwise leave these items pending. Record which mode was exercised.

Neither mode requires public router forwarding. Plain HTTP is limited to an explicitly
trusted isolated network; use HTTPS when crossing an untrusted network. A full OAuth
product and public endpoint remain outside v1.

## Operations record

Use [deploy/operations-record.template.md](../deploy/operations-record.template.md) per
deployment and mode. Evidence from one live deployment does not prove the other mode was
deployed. Keep sensitive inventory outside Git and publish sanitized summaries only.

Measure idle RSS with `ps` on the container's process (for example via the PID from
`docker inspect`): `docker stats` may report 0 B memory on hosts without the memory
cgroup. Measurements from the live check are in
[VALIDATION.md](VALIDATION.md#issue-11-live-deployment-check-2026-11-06).

Resource measurements to collect on the actual target (load figures not yet measured): start-to-ready time, idle RSS, RSS and CPU under N parallel `tools/call` and `ping`, latency percentiles for `tools/list` and a read, open sockets after clients disconnect, signal-to-exit time idle and with an in-flight call, peak concurrent connections, the largest legitimate request body (to confirm the 256 KiB bound) and Python/SDK/uvicorn versions and architecture.
