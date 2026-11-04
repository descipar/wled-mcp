# Inventory and bounded client foundation

Issue #4 exposes `wled_list_devices(probe=false)` through stdio. It returns
configured IDs/names in configuration order, with `probe_status: untested`, without
HTTP or startup discovery. `probe=true` reads only configured `/json/info` URLs.
An object with a string `ver` is required to count as reachable. Each entry has
its own reachable/failed result; partial probe failures do not hide other devices.
URLs, response bodies and transport exception strings are excluded from results.
The list call itself succeeds when individual probe entries report failures.

## Configuration and limits

`examples/devices.example.toml` is executable synthetic configuration. The empty
bootstrap example still works. Schema version 1 requires a devices list (maximum
256), unique lower-case ASCII IDs of at most 64 characters, nonempty names of at
most 128 characters and explicit HTTP(S) root URLs. Root trailing slash, explicit
ports and bracketed IPv6 are accepted. Credentials, query/fragment, nonroot paths,
unknown fields and unsupported types/features fail before device access. TOML is
limited to 64 KiB; absolute path and CLI-over-environment rules are unchanged.

| HTTP setting | Default | Allowed bounds |
| --- | --- | --- |
| connect_timeout_seconds | 3 | 0.05–30, finite |
| operation_timeout_seconds | 10 | 0.05–120, finite |
| read_retries | 1 | 0 or 1 |
| max_request_bytes | 65536 | 128–1048576 |
| max_response_bytes | 2097152 | 128–8388608 |
| catalog_cache_seconds | 300 | 0–86400; retained cache-policy configuration for #5 |

`backups.retain_per_device` defaults to 20 (1–1000), carried by the shared backup
handle; it does not implement snapshot retention yet. `features.raw_state_patch`
accepts only false. All numeric settings reject booleans. Probe fan-out uses at
most eight workers, with one deadline per device including its retry; the complete
call is bounded by `ceil(device_count / 8) * operation_timeout_seconds` plus local
scheduling/serialization overhead. A 10-second per-device deadline is not a claim
that all 256 probes finish within 10 seconds.

## Internal operations

The maintained SDK dependency graph already uses HTTPX2 2.16.0; this project now
declares that dependency directly. One client uses verified TLS, `trust_env=false`,
no redirects and a pool of 16 connections/8 keepalive connections. Internal
endpoint identifiers allow only info/state/effects/palettes/presets reads and a
fixed state POST. No public tool accepts a host, URL, endpoint or raw state body.
Only transient connect/read/protocol transport errors and timeouts may receive
one safe read retry; statuses, parse/size/type errors are not retried. Writes have
one attempt and never replay automatically. Responses require uncompressed JSON;
the client requests identity encoding and rejects other encodings before reading.
Limits count actual streamed bytes, independent of Content-Length. JSON must have
finite values, at most 32 nesting levels/100000 nodes and the expected top-level
object/catalog shape. Requests are validated/serialized/size-checked before send.

One monotonic operation deadline includes lock wait, fresh reads, preparation,
POST and readback. An outer AnyIO deadline provides the total bound; HTTPX's
individual I/O timeout alone is insufficient. Before dispatch at least 20 ms must
remain; dispatch reserves 25% of remaining time, capped at one second, for
reconciliation. This is a bounded opportunity, not a network availability promise.

The internal `write_verified` seam runs a future domain preparation callback under
the same device lock and deadline, sends at most one POST, then checks fresh state.
ACK alone never proves success. Matching readback yields applied/verified;
mismatch yields unknown/mismatch, unavailable readback yields unknown/unknown.
Pre-dispatch validation/deadline failures remain not_attempted. Timeout/reset may
have applied; no compensation or blind retry follows. Postcondition readback does
not prove causal attribution against external clients. These mocked foundation
checks do not implement public setters or a complete firmware adapter.

Locks cover preparation through verification; different controllers progress
independently. Cancellation releases locks; if it occurs after dispatch no result
can be promised and the write must be treated as potentially applied. Resource
shutdown closes the client once. One worker/process is required; separate
processes and external WLED clients do not share these locks. The metadata cache
and backup handle are shared references, not implemented freshness/durability.
Actual HTTP sessions, authentication, Host/Origin handling and lifecycle remain
#14; its transport selector still fails before listening. Hardware is unverified.
