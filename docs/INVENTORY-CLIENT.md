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

A `base_url` host name is ASCII, at most 253 characters, without a trailing dot. Each
dot-separated label has 1–63 characters from letters, digits, `-` and `_`, and starts
and ends with a letter or digit. Interior underscores (for example the synthetic
`http://wled_desk.example.invalid`, as some routers publish for DHCP clients) are
accepted; `_wled`, `wled_` or `_` labels are rejected. Single-label names are
accepted. IPv4 and bracketed IPv6 literals and percent-encoding rules are unchanged.
The configured case is kept; the HTTP client sends the host lower-cased and unchanged
otherwise (no IDNA conversion of ASCII names). Startup never resolves or probes names.

When a device entry is rejected, the startup error names it by its zero-based position
in the `[[devices]]` list and the field, for example
`Invalid inventory configuration (devices[1].base_url: invalid): ...`. Categories are
`missing`, `invalid` and `unsupported field` (an unknown key, whose name is not shown).
At most five entries are listed, followed by `and N more`. Values, URLs, host names,
IDs and names are never echoed. Errors that are not tied to one entry (schema version,
duplicate IDs, settings sections, TOML syntax) keep the generic message.

| HTTP setting | Default | Allowed bounds |
| --- | --- | --- |
| connect_timeout_seconds | 3 | 0.05–30, finite |
| operation_timeout_seconds | 10 | 0.05–120, finite |
| read_retries | 1 | 0 or 1 |
| max_request_bytes | 65536 | 128–1048576 |
| max_response_bytes | 2097152 | 128–8388608 |
| catalog_cache_seconds | 300 | 0–86400; TTL of the effect/palette catalog cache (0 disables) |

`backups.retain_per_device` defaults to 20 (1–1000), enforced by the shared snapshot
store (#8) after each durable snapshot. `features.raw_state_patch`
accepts only false. All numeric settings reject booleans. Probe fan-out uses at
most eight workers, with one deadline per device including its retry; the complete
call is bounded by `ceil(device_count / 8) * operation_timeout_seconds` plus local
scheduling/serialization overhead. A 10-second per-device deadline is not a claim
that all 256 probes finish within 10 seconds.

## Internal operations

The maintained SDK dependency graph already uses HTTPX2 2.16.0; this project now
declares that dependency directly. One client uses verified TLS, `trust_env=false`,
no redirects and a pool of 16 connections/8 keepalive connections. Internal
endpoint identifiers allow only info/state/effects/palettes/fxdata/presets reads and a
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
processes and external WLED clients do not share these locks. The catalog cache
(`metadata_cache`, issue #5; see [TOOL-CONTRACT](TOOL-CONTRACT.md#read-tools-state-and-catalogs-implemented-in-5))
and snapshot store (`resources.backups`, #8) are shared references; the store creates no directory until the first snapshot.
Client failures now name the fixed resource label and numeric HTTP status in their
message (never body, URL or exception text).
HTTP authentication, Host/Origin handling and the stateless lifecycle are implemented
by #14 (see [DEPLOYMENT.md](DEPLOYMENT.md)). Hardware is unverified.
