# Operations record (template)

Copy per deployment and per mode into a private location outside Git. Record facts as
observed; write "not run" with a reason instead of leaving a field implied. Never record
credentials, private hostnames or the real inventory in a shared copy.

## Release

- Date / operator role / authorization reference (scope, mode, target):
- Transport mode exercised (Streamable HTTP or stdio via uvx; one per record):
- Package version / source commit / `RELEASE` tree state:
- SHA-256 of the wheel and `requirements-runtime.txt` (from `SHA256SUMS`, verified on target):
- HTTP: image tag and image ID / base image tag and digest:
- stdio: uvx version / resolved Python version / uv cache, tool and Python paths:
- Python / MCP SDK / uvicorn versions and CPU architecture:

## Configuration (no secrets)

- Release directory / config path / data directory / process UID:GID:
- HTTP: Compose project and service name / network (sanitized) / bind / port:
- HTTP: `--allowed-host` entries / `--allowed-origin` entries / credential source (file path only):
- Hub entry type and URL or command (sanitized); where the hub stores the header value:
- Hub entry owner (HTTP: an admin user, see DEPLOYMENT.md "MCPHub notes") / entry reloaded after each edit:
- Inventory `base_url` hosts are RFC 1123 names resolving to one address, or addresses:
- Backups path writable and on a hard-link-capable filesystem (how checked):

## Checks

- Read-only device checks (H02) per selected device; sanitized device/firmware:
- Initialization, tool listing and a state read: directly and through the hub:
- HTTP: authenticated `ping` / healthcheck status / 401 and 403 negative checks:
- Startup-to-ready time and idle RSS (H03), with the measurement method (`ps` on the process when `docker stats` shows 0 B):
- Restart / reconnect / runtime recreation outcome; data and backups preserved:
- Update and rollback exercised (from version, to version, result):
- Optional authorized write checks and restoration (reference VALIDATION template):

## Not run / remaining risk

-
