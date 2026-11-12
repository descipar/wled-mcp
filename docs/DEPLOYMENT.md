# Deployment and operations

**Status: one live check of both modes on one target.** The artifacts and procedures
below (#11) are covered by device-free tests and were exercised once on one MCPHub target
for both modes (build, start, hub registration, reads, recreation, restart, idle
measurements, stdio entry removal, removal and redeploy of the HTTP service, catalog
and preset reads, a stdio environment rebuild, a hub container recreation, and an
authorized power on/off on one test controller); see
[VALIDATION.md](VALIDATION.md#issue-11-live-deployment-check-2026-11-06). Drain of an
in-flight call on the target and load measurements moved to
[#12](https://github.com/descipar/wled-mcp/issues/12) per ISSUE-11-DEC-008; HTTP-mode load
figures, a SIGTERM drain in which read calls sent before the stop command completed
with HTTP 200 and at least one was certainly in flight at the signal, and the #12
hardware acceptance on one
controller and firmware are recorded in
[VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) (no blanket
compatibility claim; see [#67](https://github.com/descipar/wled-mcp/issues/67)). A second
#12 run updated the HTTP service to a newer main build and recorded peak concurrent
connections, an in-flight write drain, stdio H04-H06, rate-limited stdio load through the
hub, a stdio drain finding (see the stdio notes below) and the hardware re-check of the
fixed [#66](https://github.com/descipar/wled-mcp/issues/66) in
[VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06). A third, owner-watched
HTTP run recorded visible effect animation, a speed change and a brightness transition,
and ISSUE-12-DEC-007 settles the remaining #12 scope (live H07 moved to stage 2,
[#25](https://github.com/descipar/wled-mcp/issues/25)) in
[VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06). Live update and
rollback between two versions moved to stage 2
([#21](https://github.com/descipar/wled-mcp/issues/21),
[#25](https://github.com/descipar/wled-mcp/issues/25)) per ISSUE-11-DEC-005; the
procedures below remain part of #11. All names, paths and networks below are
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

Inventory `base_url` host labels may contain letters, digits, hyphens and interior
underscores; each label starts and ends with a letter or digit (see
[INVENTORY-CLIENT.md](INVENTORY-CLIENT.md#configuration-and-limits)). A rejected entry
is named in the startup error by its zero-based `devices[<index>]` position and field.
An IPv4 address must be a canonical dotted quad (four decimal parts 0–255, no leading
zeros); short, hexadecimal or out-of-range numeric hosts are rejected.
Use a reserved DNS name that resolves to exactly one address from the service's
context, or the controller's address; a name resolving to several addresses makes
requests ambiguous.

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
- Access profile: `--profile read-only|control|full` or `[access] profile` in the inventory (default `full`) selects which tools the service registers; a per-device `max_class` caps single devices ([profiles](contract/profiles.md)). Both are restart-applied deployment settings, not per-user permissions.
- Rejections: wrong Host/Origin 403, missing or wrong credential 401, other path 404, any method except POST 405, body over 256 KiB 413, all before any tool or device work.
- Sessions: none. Responses carry no `Mcp-Session-Id`; a stale ID is ignored; reconnecting clients start new invocations and the service never replays a write. A client that disconnects during a call does not cancel it; verification and lock release continue.
- Shutdown: SIGTERM/SIGINT stop admission, drain in-flight calls for up to the configured operation timeout plus 2 s (at most 122 s), close shared resources once and exit 0. The example sets `stop_grace_period: 130s` and an exec-form entrypoint so PID 1 receives SIGTERM directly. Active temporary signals get one bounded (5 s) conditional restore attempt before exit ([signals](contract/signals.md#shutdown-and-restart)). A forced kill leaves a possibly applied write uncertain and a signal applied, and neither is resumed or restored on restart.
- Status: the read-class `wled_get_service_status` tool (authenticated like every tool, every profile) reports profile, per-device ceilings, the last observed outcome per device (`unknown` until a request was seen, never healthy by default) and call counters without contacting a device ([diagnostics](contract/diagnostics.md#wled_get_service_status)).
- Liveness without device access: there is no unauthenticated health route. The Compose healthcheck is a TCP connect to `127.0.0.1:8000` with the image's Python; the stronger manual check is an authenticated JSON-RPC `ping` (below). Neither contacts a device.
- Logging: diagnostics go to stderr only (stdout stays unused); the credential, supplied Host/Origin values, bodies and device URLs are not logged. One bounded line per tool call (tool, class, configured device ID, outcome axes, error code, duration, correlation ID, never argument values) is logged at WARNING for failed calls and at INFO for successful ones; `WLED_MCP_LOG_LEVEL=info` (default `warning`) shows them and the startup event, `WLED_MCP_LOG_FORMAT=json` selects JSON lines ([diagnostics](contract/diagnostics.md#logging)). There is no file logging and no outbound telemetry. Rejection events log a fixed class only and a flood can produce noise. There is no rate limiting or lockout; credential strength is the control for a private network, and plain HTTP is only for a trusted isolated network.

Hardening in the example: separate project, no `ports:`, joins the hub network as
`external`, `restart: unless-stopped`, read-only root filesystem with a writable data
bind mount and tmpfs `/tmp`, all capabilities dropped, `no-new-privileges`, non-root
UID/GID 10001 (build arguments `APP_UID`/`APP_GID`), no `environment` credential.

## Build and stage a release

Releases are immutable versioned directories. Both modes use the same directory, by
default `/app/binaries/wled-mcp/<version>/` on the target (TD-1). Stage the directory on
the machine that will run it, never on another machine or operating system followed by a
copy ([DEC-026](DECISIONS.md#dec-026--stage-releases-on-the-target-machine)), from a clean
checkout of the selected release tag or commit; give `--output` the host directory that
the hub mounts as `/app/binaries/wled-mcp`:

```text
uv sync --locked
uv run --frozen python scripts/check_distribution.py
uv run --frozen python deploy/stage_release.py --output .artifacts/release
```

`<version>` is `project.version` from `pyproject.toml`, the single version source
([versioning](contract/versioning.md)). `check_distribution.py` builds
`dist/wled_mcp-<version>-py3-none-any.whl` and verifies it
(clean install, stdio, HTTP restart, uvx and the stdio hub example). `stage_release.py`
creates `.artifacts/release/<version>/` with the wheel, `requirements-runtime.txt`, the
HTTP `Dockerfile`, its allowlist `.dockerignore`, `SHA256SUMS` and `RELEASE` (version,
source commit, clean/modified tree). It refuses to overwrite an existing version and
warns about a modified tree. Verify the directory before use (`<version>` is the
directory name):

```text
cd /app/binaries/wled-mcp/<version>
sha256sum -c SHA256SUMS
cat RELEASE
```

Publishing the package to PyPI is a separate, CI-built path:
[PUBLISHING.md](PUBLISHING.md).

The checksums are stored next to the artifacts, so they detect later changes of the
files, not a replaced directory: compare the wheel and constraints values with those
printed by `stage_release.py`. Record the source commit, wheel and
constraints SHA-256 values and, for HTTP, the image ID in the [operations record](../deploy/operations-record.template.md). Keep the
previous release directory until the new one is confirmed; it is the rollback source.

Alternatives, not the default: a Git source pinned to a full 40-hex commit
(`git+https://.../wled-mcp@<commit>`; a private repository needs credentials in the
execution context). A release tag, as in the [README](../README.md#try-it), is enough to
try the server, but a tag can be moved: a deployment pins the commit or uses the release
directory, never an unpinned branch. Another alternative is an offline wheelhouse (`--find-links <dir>
--no-index`, architecture-specific for the compiled dependencies). Runtime dependencies
otherwise come from the package index on first install, pinned by the constraints.
Constraints pin versions but do not enforce artifact hashes; keep the trusted wheel.
Never point a deployment at an editable checkout, `@latest`, an unpinned Git branch or
an index package of the same name.

### Non-release builds

A build of a commit that is not a release (a newer commit with an unchanged package
version) gets its own immutable identity, defined in
[versioning](contract/versioning.md#non-release-builds) and introduced by
[#70](https://github.com/descipar/wled-mcp/issues/70):

```text
uv sync --locked
uv run --frozen python deploy/stage_release.py --non-release --output .artifacts/release
```

`--non-release` exports the checked-out commit with `git archive`, rewrites the version
to `<base>+g<12 hex of the commit>` only in that exported copy, builds the wheel from it
and stages `.artifacts/release/<base>+g<12hex>/`. No tracked file is edited. The
wheel metadata, wheel file name, directory name, `RELEASE` and `SHA256SUMS` all carry
this PEP 440 version; `RELEASE` additionally records `build_kind=non-release`, the
`label` (`g<12hex>`), the full `source_commit` and the derived `image_tag`
(`wled-mcp:<base>-g<12hex>`, `+` mapped to `-` because image tags cannot contain `+`).
Uncommitted changes are not included; `--dirty` includes uncommitted changes to tracked
files, appends `.dirty` to the label and records `source_tree=modified`. Staging the
same commit again is refused like any other existing directory. In the procedures
below, `<version>` is the directory name and `<image-tag>` the `RELEASE` `image_tag`
(for a release, the version itself), so the same steps cover both kinds of build.

## HTTP service: build, start, verify

The image is built locally on the target from the staged directory and never pushed:

```text
docker build --pull -t wled-mcp:<image-tag> /app/binaries/wled-mcp/<version>
docker image inspect --format '{{.Id}}' wled-mcp:<image-tag>
```

The Dockerfile pins `python:3.13.18-slim-trixie` by tag and multi-architecture index
digest, requires exactly one wheel in the context, requires `SHA256SUMS` to list that
wheel and `requirements-runtime.txt` exactly once each and both to match (otherwise the
build fails), installs only the copied wheel with `--constraint requirements-runtime.txt` and creates `/app/data/wled-mcp` for the non-root
user. The allowlist `.dockerignore` keeps everything except the wheel, constraints and
`SHA256SUMS` out of the build context, so inventories, data, backups, `.env` files and
secrets cannot enter an image layer. To move to a newer Python 3.13 patch image, change
tag and digest together, rebuild and re-run the checks.

Prepare a dedicated deployment directory (for example `/srv/wled-mcp-http/`, a
placeholder) with the Compose file, inventory and credential. Replace
`REPLACE_WITH_HUB_NETWORK` with the hub's existing Docker network and
`REPLACE_WITH_IMAGE_TAG` with the built `<image-tag>`; do not edit the hub's own Compose
file:

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
the independently reachable endpoint; the bearer credential is mandatory, and it is one
shared credential, not tenant isolation. Check the
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
- Hub container recreation: recreating the hub container interrupts every hub entry,
  not only wled-mcp, for the time the hub needs to start again (about 30 s in the live
  check, with all hub servers starting concurrently); schedule it accordingly. Hub
  entries, including their owner, live in the hub's persisted settings and come back
  after the recreation. The independent HTTP service keeps running and the hub
  reconnects to it. For stdio, the uv tree under `/app/data/wled-mcp-uv/` and the data
  directory survive when they are on mounted persistent storage, so the entry restarts
  without downloading dependencies again. Other hub servers whose package caches live
  in the container filesystem (for example servers launched through `npx`) download
  their packages again; this is independent of wled-mcp. Recreating the hub is a hub
  operation and is never part of the wled-mcp update, rollback or removal procedures.
- Hub-side handling: through the hub's MCP endpoint, `ping` and `tools/list` are
  answered by the hub itself, so they do not reach or measure a stdio server process.
- Rate limit: MCPHub 1.2.1 returned HTTP 429 ("Too many requests") after about 200
  requests within its window in the second #12 run; load through the hub is bounded by
  that limit, not by the server.

### Installing from the MCPHub Registry tab

The MCPHub build observed for this project (the Install dialog of a Registry card, under
Packages, for administrators) does not produce a runnable entry from the registry listing: it
prefixes argument names that already start with `--` with another `--`, leaves `{config_path}`
and `{data_dir}` unresolved and omits the runtime arguments. Other hosts may handle the listing
differently, and this is a note about that build, not a claim that anything was fixed upstream.
Before saving, edit the dialog: command `uvx`; arguments, one per field, `--isolated`,
`--python`, `3.13`, `wled-mcp@<version>` (the listed version), `--transport`, `stdio`, `--config`,
`<absolute path of your devices.toml inside the hub container>`, `--data-dir` and
`<writable directory inside the hub container>`. Container paths, the uv environment variables
and a complete hub entry are in
[stdio via uvx](#stdio-via-uvx-register-update-rollback-rebuild-removal). The corrected entry
has not been started inside MCPHub yet.

## HTTP service: update, rollback, recreation, removal

All commands are scoped to the `wled-mcp-http` project and the `wled-mcp` service; none
of them restarts, recreates or removes the hub or its network.

- Update: stage and build the new version (`wled-mcp:<new image tag>`, a release or a
  non-release build), keep the previous image and release directory, change `image:` in
  `compose.yaml`, then
  `docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp`. Repeat
  `ps`, `logs` and the authenticated `ping`; the hub reconnects without replaying writes.
  Right after an update from a build from before the `correlation_id` of #119 (see
  [#130](https://github.com/descipar/wled-mcp/issues/130)) the hub rejects every response with
  "data must NOT have additional properties". Cause, confirmed for that path from the retained
  tool-list fixture, which is generated from such a build: that schema forbids unknown
  envelope properties and the server since #119 adds `correlation_id`; the hub still validates
  against the tool list it cached. Pre-#119 schemas also lack the later error codes
  (`STORAGE_FAILED`, `ACCESS_DENIED`). The tagged releases already serve `correlation_id`, so
  updating from them needs no refresh. Procedure: reload or refresh the hub entry; it cleared
  after about a minute once with the hub, other clients may cache longer; no server change is
  needed. This happens once: the schema served from
  the first release after 0.1.1 on (the #130 change, see the [CHANGELOG](../CHANGELOG.md)) allows additional envelope and error properties, so later additive
  fields do not recur. Fields inside `data` are not affected.
- Rollback: set `image:` back to the previous tag (rebuild it from the retained release
  directory if it was removed) and run the same `up -d --no-deps wled-mcp`. Configuration
  is never migrated in place; snapshot local data before any future schema change.
  Rolling back the code does not restore device state: lights, segments and presets
  stay as the newer version left them; restore them from the snapshots under the data
  directory if needed.
- Runtime recreation: data and inventory live in the bind mount, so recreating the
  container keeps them:

  ```text
  docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps --force-recreate wled-mcp
  ```

  An image rebuild uses the same staged directory and pinned base digest; re-run the
  checks afterwards.
- Credential rotation: replace the secret file, recreate the service as above, then
  update the hub header. The credential is shared: whoever holds it has the whole
  profile's reach (it is not a per-user permission and there are no per-credential
  scopes), so rotate it when a holder should lose access.
- Stop without removal: `docker compose -p wled-mcp-http -f compose.yaml stop wled-mcp`
  (graceful SIGTERM, up to 130 s).
- Removal of only this service, as separate steps: remove the hub entry in MCPHub; then

  ```text
  docker compose -p wled-mcp-http -f compose.yaml rm --stop --force wled-mcp
  docker image rm wled-mcp:<image-tag>
  ```

  Deleting `data/wled-mcp` is a further, explicit decision; backups are never pruned as
  part of update, rollback or removal.

## stdio via uvx: register, update, rollback, rebuild, removal

The hub entry ([mcphub.example.json](../examples/mcphub.example.json)) runs the staged
wheel with the exported constraints; every argument is a separate array element:

```text
uvx --isolated --python 3.13 \
  --constraints /app/binaries/wled-mcp/REPLACE_WITH_VERSION/requirements-runtime.txt \
  --from /app/binaries/wled-mcp/REPLACE_WITH_VERSION/wled_mcp-REPLACE_WITH_VERSION-py3-none-any.whl \
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
- `REPLACE_WITH_VERSION` is the release directory name, for a non-release build
  including its label (for example `1.2.3+g0123456789ab`); the wheel file name carries
  the same version.
- Update: stage the new version directory (release or non-release), change the version
  in `--constraints` and `--from` together, then restart only this hub entry. Keep the
  previous directory.
- Rollback: point both paths back to the previous version directory and restart only
  this entry. As for HTTP, this does not restore device state.
- Environment rebuild after a hub image, Python or architecture change: relaunch the
  entry; if it fails to start, stop the entry, delete only `/app/data/wled-mcp-uv/cache`
  (never `/app/data/wled-mcp`) and relaunch, then repeat the read-only checks.
- Removal: delete this single hub entry. The release directory, uv tree and data
  directory are removed only as separate explicit steps; backups are never pruned.

The distribution check runs this exact argument list through uvx with only the
wheel, constraints, config and data paths replaced by local ones.

Host-owned lifecycle: in stdio mode the host (here the hub) starts and stops the
subprocess and may not drain in-flight calls. In the second #12 run, disabling the entry
closed the connection at once: calls in flight got a "Connection closed" protocol error
from the hub, later calls "Tool not available", and the process was gone after about
0.9 s ([VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)). A write cut off this way may have been applied on the device while the
client sees only an error; read the state with `wled_get_state` (or the preset list)
before retrying it, and stop or disable the entry only when no write is in flight.
ISSUE-12-DEC-006 accepts this as a documented limitation of stdio mode; Streamable HTTP
is the preferred mode where in-flight calls must drain.

## Changing the inventory

The inventory file is read once at startup in both modes. A change takes effect
through a restart after `wled-mcp config validate` has accepted the edited file
(DEV-03); there is no in-process reload (ISSUE-16-DEC-001, closing the deferral of
ISSUE-13-DEC-001). The procedure is copy, edit, validate, restart. From M8 (not yet released; [contract/discovery.md](contract/discovery.md)) an agent can add a controller and set discovery ranges through tools that take effect by in-process reload; hand edits keep this procedure:

1. Keep a copy of the working file next to it, for example
   `devices.toml` -> `devices.toml.previous`, in the same config directory
   (`./data/wled-mcp/config/` next to `compose.yaml` for HTTP,
   `/app/data/wled-mcp/config/` in the hub container for stdio).
2. Edit `devices.toml`, or append a device with
   `wled-mcp config add-device --config <abs> --device-id ... --device-name ...
   --base-url ...` ([CLI](contract/cli.md#config-add-device)). Use synthetic or reserved
   names when sharing it, for example `base_url = "http://wled-desk.example"`.
3. Validate the edited file with the same validator as startup, without contacting a
   device: `wled-mcp config validate --config <abs> --data-dir <abs>`. For HTTP, run it
   in the image, for example
   `docker compose -p wled-mcp-http -f compose.yaml run --rm wled-mcp config validate
   --config /app/data/wled-mcp/config/devices.toml --data-dir /app/data/wled-mcp`;
   for stdio, use the hub entry's `uvx ... wled-mcp` command with `config validate`
   instead of the serve options. Restart only when it exits 0; otherwise fix the named
   entries (for example `devices[1].base_url: invalid`) or restore the copy.
4. Restart only this server, when no write is in flight:
   - Streamable HTTP:
     `docker compose -p wled-mcp-http -f compose.yaml restart wled-mcp`, then repeat
     `ps`, `logs` and the authenticated `ping`.
   - stdio via uvx: restart only this hub entry; the hub starts a new subprocess that
     reads the file. The hub does not drain in-flight calls on stop (ISSUE-12-DEC-006).
5. Confirm with `wled_list_devices` that the expected device IDs are listed, or run
   `wled-mcp doctor` with the same paths.

An invalid file never partially replaces the inventory: startup stops with exit code 2
before listening or writing to the data directory, and stderr carries
`Startup configuration error: ...`. A rejected device entry is named by position and
field only, for example `devices[1].base_url: invalid` or `devices[0].id: missing`;
values, URLs and credentials are not echoed (tests
`tests/test_bootstrap.py::test_invalid_configuration_is_safe`,
`test_console_names_rejected_device_entry_without_values` and
`test_console_rejects_non_canonical_ipv4_host_without_echo`). The previous process is
already stopped at that point, so the server is unavailable until rolled back or fixed;
step 3 finds the same problems before the restart.
With `restart: unless-stopped` the HTTP container keeps restarting and failing until the
file is valid.

Rollback: copy `devices.toml.previous` back to `devices.toml` and restart the same way,
then confirm with `wled_list_devices`. Snapshots stay under `backups/<device_id>/`; a
changed device `id` does not move or rename the existing snapshots of the old ID.

## Setup and diagnostics

Run the `config` commands and `doctor` as the service user (or in the image), so that
file modes and the backups writability check reflect what the server will see.

- `wled-mcp config init --config <abs> [--device-id ... --device-name ... --base-url ...]`
  writes a new schema 1 inventory and nothing else; it refuses an existing file unless
  `--force` is given. Create the data directory yourself.
- `wled-mcp config validate` checks a file as described above.
- `wled-mcp doctor --config <abs> --data-dir <abs>` reports runtime, configuration,
  storage and per-device results (reachability, firmware tier, unknown capabilities)
  with fixed codes and actions; it only reads. `--offline` skips the device reads,
  `--endpoint <url>` also checks a running Streamable HTTP service (credential from
  `WLED_MCP_HTTP_TOKEN` or `--http-token-file`), and `--export` prints a sanitized JSON
  summary that can be attached to a report.
- `wled-mcp discover [--config <abs>]` sends one mDNS query (plus at most one
  follow-up) for WLED controllers and lists the answers with a suggested `base_url`
  and the matching `config add-device` command. It runs only when invoked, writes
  nothing and contacts no candidate. Multicast stays in the local network segment: it
  does not cross VLANs or routed subnets, firewalls may block it, and a container on a
  Docker bridge network usually sees no answers. `network_mode: host` would let a
  container take part in multicast, but it also removes the network isolation of the
  service, so the documented deployment does not use it; run `discover` on the host
  instead, or skip it. The suggested URL uses the IPv4 address because container
  resolvers usually cannot resolve `.local` names; reserve the address in DHCP so that
  it stays valid. Adding a controller by address always works without discovery.

From M8 (not yet released) an agent can also discover controllers through an MCP tool, with an additional bounded unicast probe of configured private ranges that works from a container; see [contract/discovery.md](contract/discovery.md).

Commands, exit codes and the export allowlist: [contract/cli.md](contract/cli.md).

## Device restoration

Code update or rollback does not undo lighting or preset changes on a device. Restoring
a preset from a snapshot is a manual procedure described in
[TOOL-CONTRACT](TOOL-CONTRACT.md#snapshot-and-explicit-restoration); there is no restore
tool (ISSUE-8-DEC-001). Any write to a device, including a restoration, needs its own
authorization for the selected device. Snapshots stay under
`/app/data/wled-mcp/backups/<device_id>/` in both modes.

## Persistent paths

- `/app/data/wled-mcp/config/devices.toml`: local inventory, not in Git.
- `/app/data/wled-mcp/backups/<device_id>/<backup_id>.json`: persistent preset snapshots (directories 0700, files 0600, created on first snapshot; never in Git). The service user needs write access; keep the volume persistent and back it up like other runtime data. Snapshots are published with a hard link, so a filesystem without hard-link support (some network or FAT volumes) makes every snapshot fail closed with `BACKUP_FAILED`. When the backups location is not writable, the server prints one advisory line on stderr at startup and still starts; `wled-mcp doctor` reports it as `BACKUPS_NOT_WRITABLE` (hard-link support is not checked, because that needs a write).
- `/app/data/wled-mcp/groups/<id>.json` and `/app/data/wled-mcp/scenes/<id>.json`: device groups and scenes saved by the group and scene tools (directories 0700, files 0600, created on first save; never in Git); keep them on the persistent volume and back them up like other runtime data.
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
7. Run only specifically authorized hardware-write scenarios; record restoration and residual limitations. For a visual brightness or transition check, first read the controller's power estimate (`leds.pwr` in `/json/info`) and stay below its current-limiter (ABL) cap; at the cap the limiter scales the output and a brightness change is barely visible ([VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06)).
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

Resource measurements to collect on the actual target (moved to [#12](https://github.com/descipar/wled-mcp/issues/12) per ISSUE-11-DEC-008; the HTTP-mode figures, including CPU time per call, are in [VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06); peak concurrent connections and stdio-mode figures through the hub, limited by the hub's rate limit, are in [VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)): start-to-ready time, idle RSS, RSS and CPU under N parallel `tools/call` and `ping`, latency percentiles for `tools/list` and a read, open sockets after clients disconnect, signal-to-exit time idle and with an in-flight call, peak concurrent connections, the largest legitimate request body (to confirm the 256 KiB bound) and Python/SDK/uvicorn versions and architecture.
