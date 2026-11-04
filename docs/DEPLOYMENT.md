# Proposed deployment and operations

**Planning only. No command in this document has deployed this server.** Commands are illustrative until packaging exists and paths/runtime are checked.

## Known target context

MCPHub is currently documented in the separate maintenance project as a Docker Compose deployment on `serviceplasma`. Its historical mounts expose `/app/data` and `/app/binaries`. Recheck mounts, CPU architecture, installed Python/uv, network access, hub entry schema and lifecycle before choosing concrete paths. Do not recreate or restart the entire hub just to test documentation.

Proposed deployment directories:

- `/app/data/wled-mcp/config/devices.toml`: local inventory, not in Git.
- `/app/data/wled-mcp/backups/`: persistent preset snapshots.
- `/app/data/wled-mcp/releases/<version>/`: versioned application artifact if suitable for the actual runtime.
- A stable launcher/configured executable path that resolves an explicitly selected release and its locked environment.

Directory names are proposals, not existing files. Separate immutable code from mutable data and ensure the hub service user can write only what is needed.

## Packaging options to decide during implementation

Preferred: a versioned Python wheel plus a reproducible environment installed in a persistent location, or an equivalent pinned `uv` launch with its cache/environment persistence verified. Merely storing a virtualenv outside the container does not guarantee survival of a base-image Python/ABI change. Document environment rebuild from the wheel and lockfile and test it after hub/container recreation. Never rely on a manually installed package in the container's disposable filesystem.

Do not point the production hub at an editable developer checkout, `@latest`, an unpinned Git branch, or a different unrelated package with the same name.

## Hub entry

[mcphub.example.json](../examples/mcphub.example.json) illustrates the proposed shape. Each argument must be a separate array element/field. The executable path is intentionally a placeholder until the bootstrap/deployment issues are done. Stdio output must contain protocol messages only.

## Ordered integration procedure

1. Confirm deployment was requested, inspect the actual Compose mounts/runtime and preserve the prior hub entry if one exists.
2. Build/check the package and lockfile in an isolated project environment; record version, source commit and artifact hash.
3. Place immutable artifact and local config in persistent project paths. Set filesystem permissions suitable for that service user; never print credentials.
4. From the actual execution context, read `/json/info` and `/json/state` only for selected configured controllers. Check DNS/IP/port reachability without changing network settings.
5. Start the executable through stdio and verify MCP initialization, tool listing and a state read. Register the hub entry and perform the same read through the hub.
6. Verify backups path is writable and persistent without invoking a lighting write or preset delete.
7. Run only specifically authorized hardware-write scenarios; record restoration and residual limitations.
8. Restart only the new server entry as needed. Test hub/container recreation persistence when authorized and operationally appropriate; otherwise leave this item pending.

## Update and rollback

Retain previous known-working artifact/version and compatible lock/config. Validate new configuration without migration in place; snapshot local data before any schema migration. Switch the launch target explicitly, restart the entry, then perform read-only health checks. On failure, restore the prior launch target/config and restart that entry. Code rollback does not undo lighting or preset changes; use explicit state/preset restoration when needed and authorized.

Never prune user backups as part of uninstall/update. Removal of a hub entry and removal of its data are distinct operations. No public port or router forwarding is required for the stdio design.

## Operations record to complete later

Record package/commit, dependency lock hash, actual Python/SDK versions, architecture, deployment path, UID, config/data paths, startup time, idle RSS, known firmware devices, read-only hub checks, optional write checks, restart/recreation outcome and rollback evidence. Keep sensitive inventory outside Git and publish sanitized summaries only.
