# Command-line contract

The `wled-mcp` console commands for setup and diagnostics, introduced by
[#16](https://github.com/descipar/wled-mcp/issues/16) (S2-SETUP-01 to S2-SETUP-03,
DEV-03, OPS-04). Technical defaults: ISSUE-16-DEC-002
([decision log](../decisions/issue-16.md)); `config validate` plus restart instead of an
in-process reload: ISSUE-16-DEC-001. These commands are not MCP tools; the tool list is
unchanged. From M8 discovery and enrollment are also MCP tools on a shared engine (#199); see [discovery.md](discovery.md) and DEC-035, which supersedes ISSUE-16-DEC-001 in part. The statements here describe the released CLI.

## Serving and subcommands

- Without a subcommand the console serves MCP exactly as before:
  `wled-mcp --config <abs> --data-dir <abs> [--transport ...]` (or the
  `WLED_MCP_CONFIG`/`WLED_MCP_DATA_DIR` environment variables). Startup still stops
  with exit 2 and `Startup configuration error: ...` on stderr for an invalid
  configuration.
- New at startup (OPS-04): when `<data-dir>/backups` (or its nearest existing parent)
  is not writable for the service user, the server prints one advisory line on stderr
  and still starts. Writes that take a snapshot still fail closed with `BACKUP_FAILED`.
- Logging (#20): the serving process reads `WLED_MCP_LOG_LEVEL` (`warning`, the default, or
  `info`) and `WLED_MCP_LOG_FORMAT` (`text`, the default, or `json`) and writes one bounded
  line per tool call to stderr; an unsupported value is the startup configuration error
  above (exit 2, variable named, value not echoed). `info` also shows the startup event.
  See [diagnostics](diagnostics.md#logging). Subcommands ignore both variables.
- Subcommands: `config init`, `config add-device`, `config validate`, `doctor` and
  `discover`.
  Each one runs as its own short process, never serves MCP, never reads stdin and
  never prompts. It writes its result to stdout and unexpected diagnostics to stderr.
- `--profile read-only|control|full` selects the access profile and overrides
  `[access] profile` of the configuration (precedence option, file, `full`; no
  environment variable); see [profiles](profiles.md#configuration). An invalid value is
  the usage error below.
- Serve options (`--transport`, `--host`, `--profile`, ...) together with a subcommand are a usage
  error. So are unknown options and actions and, as for serving, abbreviated option
  names; their message is the fixed
  `Invalid command-line arguments. Use --help for supported options.`
- Every subcommand takes `--format text|json` (default `text`, no terminal detection).
  JSON output is one object with `"schema_version": 1`, `"command"` (for example
  `"config validate"`) and `"ok"`. Fields are only added within schema version 1
  ([versioning](versioning.md#schema-evolution)).
- Paths: `--config` and `--data-dir` (or the same environment variables) must be
  absolute. There is no platform-default lookup.

| Exit code | Meaning |
| --- | --- |
| 0 | Success; warnings are allowed |
| 1 | The command ran and found a problem or refused (invalid configuration, failed check, existing target, no discovery candidates) |
| 2 | Usage error: unknown or contradictory options, missing required value |
| 3 | Internal failure; stderr names the command only, without traceback or values |

No subcommand writes to a device, sends a POST to a device, changes lights or creates
the data directory. No output contains a credential, a token-file path or a URL
credential.

## `config init`

```text
wled-mcp config init --config <abs> [--device-id ID --device-name NAME --base-url URL] [--force]
```

- Writes a new schema 1 configuration with zero devices (`devices = []`) or one
  device (all three device options together, otherwise exit 2). The written document
  is validated with the startup validator before anything is written.
- Writes only the selected file: a temporary file in the same directory, fsync,
  `os.replace` (plus a directory fsync on POSIX). New files are created with mode
  0600 on POSIX. The directory fsync is best-effort: on a filesystem that does not
  support it the file is still written and reported as written, but the rename may not
  survive a power loss.
- Refuses with exit 1 and leaves everything unchanged when the target exists (without
  `--force`), is a symbolic link or not a regular file (also with `--force`), its
  directory does not exist (`PARENT_MISSING`) or exists but cannot be inspected or
  written (`PARENT_INACCESSIBLE`). `--force` keeps the replaced file's mode.
- Creates no data or backups directory, generates or stores no credential and contacts
  nothing.

## `config add-device`

```text
wled-mcp config add-device --config <abs> --device-id ID --device-name NAME --base-url URL
```

- Appends one `[[devices]]` block as text, so comments and every existing byte stay
  unchanged. Exception: a root-level `devices = []` line (the form `config init` writes
  for zero devices) cannot coexist with `[[devices]]` tables and is removed.
- Strings are written as TOML basic strings (quotes, backslashes and control characters
  escaped, other text kept as UTF-8) and checked by parsing them back.
- The complete result is validated with the startup validator (64 KiB, schema
  version, unique IDs, URL rules). The command also refuses a `base_url` equal to a
  configured one after normalization (case of scheme and host, default port, trailing
  slash).
- Refusals (exit 1, file byte-identical, no temporary file left): invalid existing
  file, duplicate ID (`DUPLICATE_ID`), equal URL (`DUPLICATE_URL`), invalid value
  (`CONFIG_INVALID`, with the positional message such as
  `devices[2].base_url: invalid`), result over 64 KiB, symbolic link, the file changed
  between reading and replacing it (`CONFIG_CHANGED`), a device value that is not
  valid Unicode text (`INVALID_TEXT`), failed write (`WRITE_FAILED`). A file that lists
  its devices as a non-empty inline array (`devices = [{...}]`) cannot take an appended
  `[[devices]]` table; the refusal is `INLINE_DEVICES_ARRAY` with the hint to rewrite
  the entries as `[[devices]]` tables first.
- Keeps the existing file mode. The change takes effect after a restart.

## `config validate`

```text
wled-mcp config validate --config <abs> [--data-dir <abs>] [--check-backups]
```

- Reads the file and validates it with the same function as startup
  (`wled_mcp.config.validate_document`): the problem message is the startup message,
  for example `Invalid inventory configuration (devices[1].base_url: invalid): ...` or
  `Unsupported inventory configuration schema_version 2; ...`. It never contacts a
  device or the network and never writes.
- `--data-dir` additionally checks that the data directory exists and is accessible
  (otherwise `DATA_DIR_NOT_FOUND`).
  `--check-backups` (needs `--data-dir`) adds the advisory backups writability check
  of `doctor` (`os.access`, nothing created).
- JSON fields: `device_count` (null when unreadable), `problems` (list of `code` and
  `message`) and, with `--check-backups`, `backups_writable`. When the file sets an
  access setting (`[access]` or a device `max_class`, #20) a valid result also has
  `access` (`profile`, `capped_devices`) and the text output one more line
  `Access (as configured; a serve --profile overrides it): ...`; without access
  settings both are absent and the output is unchanged. A file-system error while
  checking is reported as `CHECK_FAILED`; nothing is written.
- A location that cannot even be inspected, for example a data directory the user
  cannot search, counts as not writable (`BACKUPS_NOT_WRITABLE`), here, in `doctor` and
  for the startup advisory.
- Exit 0 when valid, 1 otherwise. This is the check step of the inventory change
  procedure: copy, edit, validate, restart
  ([DEPLOYMENT.md](../DEPLOYMENT.md#changing-the-inventory)).

## `doctor`

```text
wled-mcp doctor [--config <abs>] [--data-dir <abs>] [--offline]
                [--endpoint URL [--http-token-file <abs>]] [--format text|json | --export]
```

Read-only diagnostics. Checks run in this order and report one result per check:

| Category | Codes (status) |
| --- | --- |
| `runtime` | `RUNTIME_OK` (ok); `BUILD_UNKNOWN`, `PYTHON_UNTESTED`, `PLATFORM_EXPERIMENTAL`, `PLATFORM_UNTESTED` (warning) |
| `configuration` | `CONFIG_VALID` (ok); `CONFIG_PATH_MISSING`, `CONFIG_PATH_NOT_ABSOLUTE`, `CONFIG_NOT_FOUND`, `CONFIG_UNREADABLE`, `CONFIG_INVALID` (failed) |
| `storage` | `DATA_DIR_OK`, `BACKUPS_WRITABLE` (ok); `DATA_DIR_MISSING`, `DATA_DIR_NOT_ABSOLUTE`, `DATA_DIR_NOT_FOUND`, `BACKUPS_NOT_WRITABLE` (failed) |
| `device` | per device: `DEVICE_REACHABLE`, `FIRMWARE_SUPPORTED`, `CAPABILITIES_KNOWN` (ok); `FIRMWARE_UNSUPPORTED`, `FIRMWARE_UNRECOGNIZED`, `CAPABILITIES_UNKNOWN` (warning); `DEVICE_UNREACHABLE`, `DEVICE_TIMEOUT`, `DEVICE_INVALID_RESPONSE`, `DEVICE_READ_FAILED` (failed). Otherwise one of `DEVICES_NONE` (warning), `DEVICES_OFFLINE`, `DEVICES_SKIPPED` (skipped) |
| `endpoint` | only with `--endpoint`: `ENDPOINT_OK` (ok); `ENDPOINT_OTHER_SERVER` (warning); `ENDPOINT_URL_INVALID`, `ENDPOINT_CREDENTIAL_MISSING`, `ENDPOINT_CREDENTIAL_INVALID`, `ENDPOINT_UNREACHABLE`, `ENDPOINT_TIMEOUT`, `ENDPOINT_HOST_ORIGIN_REJECTED`, `ENDPOINT_CREDENTIAL_REJECTED`, `ENDPOINT_PROTOCOL_ERROR` (failed) |

- Exit 1 when any check failed, otherwise 0 (warnings and skipped checks allowed).
  Every warning and failure carries a fixed action text.
- Runtime: package version and build kind from the version label (`release`,
  `non-release` for a `+g...` label, `unknown` for `0+unknown`); Python and platform
  tiers per DEC-020 (`compat.python_tier`, `compat.platform_tier`): Linux supported,
  Windows and macOS experimental, others untested; only Python 3.13 is supported.
- Configuration: as `config validate`. Storage: data directory and the advisory
  backups check; hard-link support is not verified, because that needs a write.
- Devices (skipped with `--offline`, an empty inventory or an invalid configuration):
  doctor calls the registered read-only `wled_get_state` operation in-process for each
  device, at most eight at a time, each with the configured operation timeout. Only
  GET requests are sent. It reads only the versioned result envelope: `error.code`
  (`UNREACHABLE`, `TIMEOUT`, `INVALID_RESPONSE`, other), `data.firmware`
  (`version`, `build_id`, `arch`), `data.diagnostics.firmware_support.tier` and
  `data.diagnostics.unknown_capabilities`. Firmware text comes from
  `compat.support_warning`: `unsupported` and `unrecognized` firmware is a warning,
  never a failure ([compatibility](compatibility.md#wled-firmware-tiers)).
- Endpoint: only an explicit `--endpoint URL` (an empty path means `/mcp`; no URL
  credentials, query or fragment). The credential comes from `WLED_MCP_HTTP_TOKEN` or
  `--http-token-file` with the service's own rules; it is never a command-line value.
  Doctor sends MCP `initialize` and `ping` (10 s timeout, no redirects, no proxy
  environment) and no tool call. HTTP 403 or 421 means the service rejected the
  Host/Origin; 401 means the credential was rejected. The credential is sent to the
  URL given, so use `https` or a loopback address. The negotiated protocol version is
  shown and exported only when it has the date form `YYYY-MM-DD`; anything else is
  `ENDPOINT_PROTOCOL_ERROR`.
- When the file sets an access setting (#20), a `configuration` check `ACCESS_CONFIGURED`
  (ok) follows `CONFIG_VALID` with the configured profile and the number of capped
  devices (facts `profile`, `capped_devices`), and the JSON output gains `access`.
  Doctor reports the file's values; it has no `--profile` option. Without access
  settings nothing is added.
- `--format text` and `--format json` are local output: messages and configured device
  IDs, never URLs or credentials. `--export` and `--format` cannot be combined (exit 2).

### Sanitized export

`doctor --export` prints one JSON object meant for sharing in a report. It is built
from an allowlist:

- `schema_version` (1), `command` (`"doctor"`), `export` (true), `ok`;
- `runtime`: `package_version`, `build_kind`, `python_version`, `python_tier`,
  `platform_tier`;
- `transport_flags`: `offline`, `endpoint_checked`; `device_count`; and, only when the
  file sets an access setting, a top-level `access` object with `profile` (a profile
  name; it is not part of `transport_flags`);
- `checks`: `category`, `status`, `code`, for device checks `device` as
  `devices[i]`, for the endpoint check `protocol_version`;
- `devices`: per device `devices[i]` with `firmware` (`ver`, `vid`, `arch`, `tier`,
  `minimum_supported`), `unknown_capabilities` names and, for a capped device,
  `max_class` (a class name).

Never included: device IDs or names, URLs, hosts, addresses, MAC addresses, Wi-Fi
fields, paths, credentials, message texts and raw device responses. The staged
`RELEASE` file is not read. Nothing is sent anywhere; the user decides what to share.

## `discover`

```text
wled-mcp discover [--config <abs>] [--timeout SECONDS] [--format text|json]
```

Lists WLED controllers found by the shared discovery engine (`wled_mcp.discovery_engine`,
#199; DEC-035, which supersedes ISSUE-16-DEC-001 / TD-16-8 in part; contract in
[discovery.md](discovery.md)). It runs only when this command is invoked: never at
startup, in `doctor` or as a fallback. It never writes the inventory or a device; it
prints suggestions and the user runs `config add-device` explicitly.

- Network traffic: an IPv4 UDP socket on an ephemeral port sends up to 3 mDNS query
  rounds, 1 s apart inside a 6 s window, to 224.0.0.251:5353. Each round has PTR questions
  for `_wled._tcp.local` and the fallback `_http._tcp.local`; later rounds add at most one
  follow-up datagram for the SRV, TXT or A records the answers left out. No IPv6.
- Verification (new in #199, allowed by DEC-035): every addressable answer is verified with
  one `GET /json/info` (TCP port 80 only, 1.5 s, at most 64 KiB, no redirects, no proxy, fixed
  `User-Agent`) on the announced address, and only an address in RFC 1918 space is read. A
  controller is listed only when the answer is a WLED `/json/info` (docs/SOURCES.md), never
  because of a port or an mDNS name. An answer that fails is counted in
  `coverage.mdns.answers_rejected`. When `--config` is given and a candidate is not matched
  by address or stored MAC, the command reads `/json/info` of at most 16 configured entries
  that have no stored MAC, to detect a changed address (only configured hosts).
- Unicast probe: the engine also probes configured discovery ranges (`GET /json/info`
  over RFC 1918 ranges within the hard caps of discovery.md). The `[discovery].ranges`
  key is added by #202; until then the command passes no ranges and the report shows
  `unicast` as `skipped` with `no_ranges_configured`. The command has no range option:
  a scan never runs over ranges that were not configured.
- Deadline: `--timeout` lowers the overall deadline (0.5 to 10 seconds, outside: exit 2,
  nothing sent). Without it the engine limits apply (mDNS window 6 s, whole call 30 s).
- Limits for untrusted answers: datagrams up to 9000 bytes, at most 512 datagrams
  (dropped ones included) and 128 records per datagram, names up to 255 bytes,
  compression pointers only backwards and at most 16 per name, at most 64 TXT strings.
  A malformed datagram is dropped and counted (`malformed_responses`); it never stops
  the command. Junk datagrams or junk instances can fill these bounded collections
  early and so crowd out real controllers; a repeated run, or adding the controller by
  address, works around it.
- Source check (RFC 6762 section 6): only datagrams from an IPv4 address with source
  port 5353 are read; any other source is dropped and counted (`dropped_datagrams`).
  Answers are unauthenticated and there is no on-link check, so a host that can send to
  the ephemeral port can inject an answer; the `/json/info` verification means an injected
  address becomes a candidate only if a WLED controller answers there, and candidates are
  suggestions the user reviews. The query leaves through the default multicast interface
  only.
- Candidates: at most 64, merged by the MAC of `/json/info` across methods and addresses.
  Each has `address`, `base_url`, `suggested_id`, `suggested_name`, `mac`,
  `firmware_version`, `product`, `found_by`, `status` (`new`, `known`, `address_changed`),
  `known_device_id`, `configured_address` and `alternate_addresses`. The ID derives from the
  mDNS instance name or the controller name (`[a-z0-9-]`, unique against the configured IDs
  and the list); the name keeps only letters, digits, space, `.`, `_` and `-` (leading
  dashes removed), so the `add_device_command`
  (`wled-mcp config add-device --config <CONFIG> --device-id ID --device-name "NAME" --base-url URL`,
  literal `<CONFIG>` placeholder, only for `new`) is safe to paste into a POSIX shell,
  PowerShell or cmd.exe. A controller whose address changed is reported
  (`address_changed`), never rewritten.
- `--config` (or `WLED_MCP_CONFIG`) is optional and only read: it supplies the known-controller
  snapshot (ID and host of each entry). An invalid or missing file is refused (exit 1) before
  anything is sent.
- Answer text (instance names, controller names) is printed as ASCII only, in text and JSON
  alike: every character that is not printable ASCII becomes `?`. The output cannot fail on a
  non-UTF-8 stdout, and one odd responder cannot suppress the other candidates.
- JSON fields: `timeout_seconds`, `conclusion`, `candidate_count`, `malformed_responses`,
  `dropped_datagrams`, `candidates` (fields above plus `add_device_command`), `coverage`
  (the report of discovery.md: methods, per-range counters, caps, limits), `warnings` and
  `problems`. Text output starts with `Conclusion: <value>` and always names the methods
  and their status. This is local output; it contains addresses and MAC values.
- Exit 0 when at least one candidate was found. Exit 1 otherwise, never with a bare "no
  candidates": `MULTICAST_UNAVAILABLE` when the socket cannot be opened or the query cannot
  be sent, `NOT_LOOKED` when no method could run, `NO_CANDIDATES` when a method ran and
  found nothing. The message gives the coverage (`none_found_complete` only when both
  methods completed, otherwise the run was not exhaustive) and names the limits: multicast
  stays in the local network segment and does not cross VLANs or routed subnets, a
  container on a bridge network usually cannot use it, firewalls may block it, and a
  controller with an empty mDNS name does not announce itself. Adding a controller by
  address with `config add-device` always works.
- Answers arrive as unicast replies to the ephemeral port (RFC 6762 section 5.1); a host
  firewall that drops unsolicited UDP may need to allow them. The engine was not observed
  against hardware for #199 (live evidence is #204); the tests use fakes.

## OPS-04 conditions

| OPS-04 condition | Doctor result | Elsewhere |
| --- | --- | --- |
| Bad configuration | `CONFIG_INVALID`, `CONFIG_NOT_FOUND`, `CONFIG_PATH_NOT_ABSOLUTE`, ... | `config validate`; startup exit 2 |
| Unsupported firmware | `FIRMWARE_UNSUPPORTED`, `FIRMWARE_UNRECOGNIZED` (warning) | `wled_get_state` warning and `firmware_support` |
| Unavailable backup storage | `BACKUPS_NOT_WRITABLE`, `DATA_DIR_NOT_FOUND` | startup advisory line; tool-level `BACKUP_FAILED` |
| Offline device | `DEVICE_UNREACHABLE`, `DEVICE_TIMEOUT` | envelope `UNREACHABLE`/`TIMEOUT` |
| Invalid response | `DEVICE_INVALID_RESPONSE` | envelope `INVALID_RESPONSE` |

The doctor codes are part of this CLI contract, not MCP error codes; the result
envelope and `examples/contracts/errors.json` are unchanged.

## Not provided

No interactive wizard, no in-process or signal-triggered reload, no file watching, no
`config migrate` (only schema 1 exists; the first schema 2 change adds a migrating
writer, ISSUE-16-DEC-002), no device discovery outside `wled-mcp discover`, no MCP
tool (until #200), no health route, no telemetry. (From M8, not yet released: MCP discovery on the shared engine of #199 and in-process reload for tool-made changes; [discovery.md](discovery.md).)
