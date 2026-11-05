# Proposed deployment and operations

**Planning only. No command in this document has deployed this server.** Commands are illustrative; paths, runtime and the HTTP service configuration must be checked on the actual installation.

## Two supported modes

Both modes are required v1 scope and use the same package/tools. Streamable HTTP is the independent-service deployment; stdio via uvx is the client-managed deployment. Each deployment selects one mode explicitly. Do not run two independently writing instances against the same controllers while assuming their process-local locks coordinate them.

| Mode | Lifecycle owner | MCPHub connection | Runtime context |
| --- | --- | --- | --- |
| Streamable HTTP | Separate Compose service or managed process | Private `/mcp` URL and configured service authentication | WLED-MCP service/container |
| stdio via uvx | MCPHub/client | Command plus separate arguments, `--transport stdio` | Hub/client-managed subprocess |

The default console mode is stdio and opens no listener. HTTP is selected with `--transport streamable-http`, configurable bind/port, one worker and SDK-managed lifecycle. Bind defaults to loopback; a separate container service explicitly binds its private container interface and restricts Host/Origin appropriately. Do not use the deprecated SSE-only transport.

## Streamable HTTP service configuration

The service exists as of the #14 candidate; it has not been deployed anywhere. Use synthetic placeholders below and adapt them to the actual installation.

```text
wled-mcp --config /app/data/wled-mcp/config/devices.toml --data-dir /app/data/wled-mcp \
  --transport streamable-http --host 0.0.0.0 --port 8000 \
  --allowed-host wled-mcp:8000 --http-token-file /run/secrets/wled_mcp_http_token
```

- Endpoint: fixed path `/mcp`; one worker; process-local locks do not coordinate a second process or worker against the same controllers.
- Credential: exactly one of `WLED_MCP_HTTP_TOKEN` or `--http-token-file` (absolute path, at most 1 KiB, read once at startup; rotate by restarting). 32 to 512 printable ASCII characters. The file must be readable only by the service user; permission modes are not enforced. Never pass the value as a CLI argument. A missing, conflicting or invalid credential exits 2 before listening.
- Bind and allowlists: the default is `127.0.0.1:8000` with allowed hosts `127.0.0.1:8000` and `localhost:8000`. A different host or port, including a wildcard bind such as `0.0.0.0` for a private container interface, requires explicit `--allowed-host` entries naming the authority clients use (exact, case-insensitive, no implicit default-port equivalence). `--allowed-origin` is empty by default; requests without Origin are accepted when authenticated. An authenticating proxy must forward the original authority in `Host` and be listed explicitly; forwarded headers are never trusted and no proxy trust option exists.
- Rejections: wrong Host/Origin 403, missing or wrong credential 401, other path 404, any method except POST 405, body over 256 KiB 413, all before any tool or device work.
- Sessions: none. Responses carry no `Mcp-Session-Id`; a stale ID is ignored; reconnecting clients start new invocations and the service never replays a write. A client that disconnects during a call does not cancel it; verification and lock release continue.
- Shutdown: SIGTERM/SIGINT stop admission, drain in-flight calls for up to the configured operation timeout plus 2 s (at most 122 s), close shared resources once and exit 0. Size the supervisor's stop grace period above that. A forced kill leaves a possibly applied write uncertain and it is never resumed.
- Liveness without device access: there is no unauthenticated health route. Use a TCP connect check or an authenticated JSON-RPC `ping`. Neither contacts a device.
- Logging: diagnostics go to stderr only (stdout stays unused); the credential, supplied Host/Origin values, bodies and device URLs are not logged. Rejection events log a fixed class only and a flood can produce noise. There is no rate limiting or lockout; credential strength is the control for a private network, and plain HTTP is only for a trusted isolated network.

Resource measurements to collect on the actual target (none are claimed yet): start-to-ready time, idle RSS, RSS and CPU under N parallel `tools/call` and `ping`, latency percentiles for `tools/list` and a read, open sockets after clients disconnect, signal-to-exit time idle and with an in-flight call, peak concurrent connections, the largest legitimate request body (to confirm the 256 KiB bound) and Python/SDK/uvicorn versions and architecture.

## Deployment context

For a Docker Compose deployment, inspect mounts, CPU architecture, installed Python/uv, network access, hub entry schema and lifecycle before choosing concrete paths. The `/app/data` and `/app/binaries` locations below are proposed container paths; they must be mapped explicitly for the selected installation. A separate HTTP container does not inherit the hub's mounts or Python runtime: define its own persistent config/data and network membership. Do not recreate or restart the entire hub just to test documentation.

Proposed deployment directories:

- `/app/data/wled-mcp/config/devices.toml`: local inventory, not in Git.
- `/app/data/wled-mcp/backups/<device_id>/<backup_id>.json`: persistent preset snapshots (directories 0700, files 0600, created on first snapshot; never in Git). The service user needs write access; keep the volume persistent and back it up like other runtime data. To restore by hand see the manual procedure in [TOOL-CONTRACT](TOOL-CONTRACT.md#snapshot-and-explicit-restoration); restoration execution is not automated.
- `/app/data/wled-mcp/releases/<version>/`: versioned application artifact if suitable for the actual runtime.
- A stable launcher/configured executable path that resolves an explicitly selected release and its locked environment.

Directory names are proposals, not existing files. Separate immutable code from mutable data and ensure the hub service user can write only what is needed.

## Packaging options to decide during implementation

Build one versioned Python wheel plus locked dependencies. For HTTP, provide a Dockerfile/Compose service or equivalent managed service based on a pinned artifact/runtime, with explicit transport/bind/port, one worker, persistent data, bounded shutdown and a device-independent liveness check. Restart/update it separately from MCPHub. Build/release image publishing is not authorized merely by preparing a Dockerfile.

For stdio, use a pinned `uvx --from <versioned-wheel-or-private-Git-source> wled-mcp --transport stdio ...` invocation with cache/data persistence verified. Private Git requires credentials in the actual execution context; a pre-staged local wheel avoids Git access on every deployment. Do not assume uvx automatically installs from the repository lockfile: verify the selected artifact's dependency reproducibility, for example with an exported constraints strategy or a prebuilt locked environment. Final packaging choice belongs to #3/#11.

Merely storing a virtualenv outside a container does not guarantee survival of a base-image Python/ABI change. Document environment rebuild from the wheel and locked dependencies and test it after runtime recreation. Never rely on a manually installed package in a container's disposable filesystem.

Do not point the production hub at an editable developer checkout, `@latest`, an unpinned Git branch, or a different unrelated package with the same name.

## Hub entry

[mcphub.example.json](../examples/mcphub.example.json) illustrates uvx/stdio with a placeholder local wheel path. Each argument is separate; stdout contains protocol only. [mcphub.http.example.json](../examples/mcphub.http.example.json) illustrates a private service URL and placeholder credential. Check actual installed MCPHub field names/type before deployment; neither example is already operational.

`wled-mcp` in the example URL is a proposed Compose service name resolvable only when both services share the intended network. `localhost` inside MCPHub would refer to that container, not a separate service. Choose actual routing rather than exposing a host port for convenience. The service must also reach the configured WLED controllers.

Protect `/mcp` with a runtime bearer credential or documented equivalent authenticated proxy. Hub authentication alone does not protect the independently reachable endpoint. Inject credentials through runtime secret files/environment and the hub's protected header configuration; example placeholders are literal text, not automatic environment expansion. Never commit real tokens or pass them as CLI values. Define Host/Origin allowlists for the actual service name. Plain HTTP is limited to an explicitly trusted isolated network; use HTTPS when crossing an untrusted network. A full OAuth product and public endpoint remain outside v1.

## Ordered integration procedure

1. Confirm deployment was requested, select HTTP-service or uvx/stdio mode, inspect the actual mounts/runtime/network and preserve the prior hub entry if one exists.
2. Build/check the package and lockfile in an isolated project environment; record version, source commit and artifact hash.
3. Place immutable artifact and local config in persistent project paths. Set filesystem permissions suitable for that service user; never print credentials.
4. From the actual WLED-MCP execution context, read `/json/info` and `/json/state` only for selected configured controllers. Check DNS/IP/port reachability without changing network settings.
5. Start the HTTP service independently and verify its authenticated `/mcp` connection, or launch stdio via uvx. Check initialization, tool listing and a state read, then register the corresponding hub entry and repeat through the hub. Verify both modes with automated SDK clients even if only one is deployed live.
6. Verify backups path is writable and persistent without invoking a lighting write or preset delete.
7. Run only specifically authorized hardware-write scenarios; record restoration and residual limitations.
8. Restart the independent HTTP service or stdio entry as appropriate. Test reconnect, shutdown and runtime recreation persistence when authorized and operationally appropriate; otherwise leave these items pending. Record which mode was exercised.

## Update and rollback

Retain previous known-working wheel/image/version and compatible lock/config. Validate new configuration without migration in place; snapshot local data before any schema migration. Switch the launch artifact or service image explicitly, restart the relevant process, then perform read-only health checks. HTTP updates/restarts are independent from MCPHub; the hub reconnects without replaying writes. On failure, restore the prior artifact/config and restart that process. Code rollback does not undo lighting or preset changes; use explicit state/preset restoration when needed and authorized.

Never prune user backups as part of uninstall/update. Removing a hub entry, stopping an independent HTTP service and deleting its data are distinct operations. Neither mode requires public router forwarding.

## Operations record to complete later

Record transport mode, package/commit/image, dependency lock hash, actual Python/SDK versions, architecture, deployment path, UID, config/data paths, startup time, idle RSS, known firmware devices, read-only hub checks, optional write checks, restart/recreation outcome and rollback evidence. HTTP records also identify bind/network, Host/Origin/auth configuration without secrets, liveness and reconnect outcomes. Evidence from one live deployment does not prove the other was deployed. Keep sensitive inventory outside Git and publish sanitized summaries only.
