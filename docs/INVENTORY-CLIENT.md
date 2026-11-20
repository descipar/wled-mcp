# Inventory and bounded client foundation

`wled_list_devices(probe=false)` (stdio) returns configured IDs/names in configuration order with `probe_status: untested`, without HTTP or startup discovery. `probe=true` reads only configured `/json/info` URLs; an object with a string `ver` counts as reachable. Each entry has its own reachable/failed result, so partial failures do not hide other devices, and the call itself succeeds. URLs, response bodies and transport exception strings are excluded from results.

## Configuration and limits

`examples/devices.example.toml` is executable synthetic configuration; the empty bootstrap example also works. Schema version 1 requires a devices list (maximum 256), unique lower-case ASCII IDs (at most 64 characters), nonempty names (at most 128) and explicit HTTP(S) root URLs. A root trailing slash, explicit ports and bracketed IPv6 are accepted. Credentials, query/fragment, nonroot paths, unknown fields and unsupported types/features fail before device access. TOML is limited to 64 KiB; paths are absolute and CLI overrides environment. `wled-mcp config validate --config <abs>` applies exactly these rules (same validator and messages as startup) without starting the server or contacting a device; `config init` and `config add-device` write files that pass it ([CLI contract](contract/cli.md)).

A `base_url` host name is ASCII, at most 253 characters, without a trailing dot. Each dot-separated label has 1-63 characters from letters, digits, `-` and `_`, and starts and ends with a letter or digit. Interior underscores (synthetic `http://wled_desk.example.invalid`, as some routers publish) are accepted; `_wled`, `wled_` or `_` labels are rejected; single-label names are accepted.

A host whose last dot-separated label is all decimal digits, or `0x` plus hex digits, is read as IPv4 and must be a canonical dotted quad: exactly four decimal parts 0-255 without leading zeros (synthetic `http://192.0.2.10`). Forms such as `1.2.3`, `127.1`, `0x7f.1`, `2130706433`, `999.1.1.1` and names ending in a numeric label such as `desk.123` are rejected at startup because a system resolver could map them silently to another address. Names whose last label contains another letter (`123.example.invalid`, `desk.1a`, `1e3`) follow the DNS label rules. Valid special addresses are not restricted further. The configured case is kept; the HTTP client sends the host lower-cased (no IDNA conversion). Startup never resolves or probes names.

A rejected device entry is named by its zero-based `[[devices]]` position and field, for example `Invalid inventory configuration (devices[1].base_url: invalid): ...`. Categories: `missing`, `invalid`, `unsupported field` (an unknown key, whose name is not shown). At most five entries are listed, then `and N more`. Values, URLs, host names, IDs and names are never echoed. Errors not tied to one entry (schema version, duplicate IDs, settings sections, TOML syntax) keep the generic message.

| HTTP setting | Default | Allowed bounds |
| --- | --- | --- |
| connect_timeout_seconds | 3 | 0.05-30, finite |
| operation_timeout_seconds | 10 | 0.05-120, finite |
| read_retries | 1 | 0 or 1 |
| max_request_bytes | 65536 | 128-1048576 |
| max_response_bytes | 2097152 | 128-8388608 |
| catalog_cache_seconds | 300 | 0-86400; TTL of the effect/palette catalog cache (0 disables) |

`backups.retain_per_device` defaults to 20 (1-1000), enforced by the shared snapshot store (#8) after each durable snapshot. `features.raw_state_patch` accepts only false. Numeric settings reject booleans. Probe fan-out uses at most eight workers with one deadline per device including its retry; the whole call is bounded by `ceil(device_count / 8) * operation_timeout_seconds` plus local overhead, which is not a claim that 256 probes finish within 10 seconds.

## Internal operations

One HTTPX2 2.16.0 client (declared directly) uses verified TLS, `trust_env=false`, no redirects and a pool of 16 connections/8 keepalive. Internal endpoint identifiers allow only info/state/effects/palettes/fxdata/presets reads and a fixed state POST; no public tool accepts a host, URL, endpoint or raw state body. Only transient connect/read/protocol transport errors and timeouts get one safe read retry (not statuses or parse/size/type errors); writes have one attempt and never replay. Responses require uncompressed JSON (identity encoding requested, other encodings rejected before reading). Limits count streamed bytes independent of Content-Length. JSON must have finite values, at most 32 nesting levels/100000 nodes and the expected top-level shape. Requests are validated, serialized and size-checked before send. If the HTTP client rejects a configured address while building the request (an entry that bypassed validation), the call fails with `CONFIG_ERROR` before any request, without retry and without echoing URL or host: a write ends `not_attempted`, a probe reports the entry `failed`.

One monotonic operation deadline covers lock wait, fresh reads, preparation, POST and readback; an outer AnyIO deadline gives the total bound, as HTTPX's per-I/O timeout alone is insufficient. At least 20 ms must remain before dispatch; dispatch reserves 25% of the remaining time, capped at one second, for reconciliation (a bounded opportunity, not an availability promise).

The internal `write_verified` seam runs a domain preparation callback under the same device lock and deadline, sends at most one POST, then checks fresh state. ACK alone never proves success: matching readback is applied/verified, mismatch is unknown/mismatch, unavailable readback is unknown/unknown. Pre-dispatch validation/deadline failures stay not_attempted. A timeout/reset may have applied; no compensation or blind retry follows. Readback does not prove causal attribution against external clients.

Locks cover preparation through verification; different controllers progress independently. Cancellation releases locks; after dispatch no result can be promised and the write is potentially applied. Resource shutdown closes the client once. One worker/process is required; separate processes and external WLED clients do not share these locks. The catalog cache (`metadata_cache`, issue #5; [TOOL-CONTRACT](TOOL-CONTRACT.md#read-tools-state-and-catalogs-implemented-in-5)) and the snapshot store (`resources.backups`, #8; no directory until the first snapshot) are shared references. Client failures name the fixed resource label and numeric HTTP status, never body, URL or exception text. HTTP authentication, Host/Origin handling and the stateless lifecycle are in #14 ([DEPLOYMENT.md](DEPLOYMENT.md)). Hardware is unverified.

The fixed `/json/live` read uses a dedicated bounded RGB-sample decoder; 404/501 availability is reported explicitly by `wled_get_live_snapshot` ([contract](contract/live-snapshot.md)). It does not enable arbitrary endpoints.
