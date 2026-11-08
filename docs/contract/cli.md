# Command-line contract

The `wled-mcp` console commands for setup and diagnostics, introduced by
[#16](https://github.com/descipar/wled-mcp/issues/16) (S2-SETUP-01, S2-SETUP-03,
DEV-03, OPS-04). Technical defaults: ISSUE-16-DEC-002
([decision log](../decisions/issue-16.md)); `config validate` plus restart instead of an
in-process reload: ISSUE-16-DEC-001. These commands are not MCP tools; the tool list is
unchanged.

## Serving and subcommands

- Without a subcommand the console serves MCP exactly as before:
  `wled-mcp --config <abs> --data-dir <abs> [--transport ...]` (or the
  `WLED_MCP_CONFIG`/`WLED_MCP_DATA_DIR` environment variables). Startup still stops
  with exit 2 and `Startup configuration error: ...` on stderr for an invalid
  configuration.
- New at startup (OPS-04): when `<data-dir>/backups` (or its nearest existing parent)
  is not writable for the service user, the server prints one advisory line on stderr
  and still starts. Writes that take a snapshot still fail closed with `BACKUP_FAILED`.
- Subcommands: `config init`, `config add-device`, `config validate` and `doctor`.
  Each one runs as its own short process, never serves MCP, never reads stdin and
  never prompts. It writes its result to stdout and unexpected diagnostics to stderr.
- Serve options (`--transport`, `--host`, ...) together with a subcommand are a usage
  error. So are unknown options and actions; their message is the fixed
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
| 1 | The command ran and found a problem or refused (invalid configuration, failed check, existing target) |
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
  0600 on POSIX.
- Refuses with exit 1 and leaves everything unchanged when the target exists (without
  `--force`), is a symbolic link or not a regular file (also with `--force`), or its
  directory does not exist. `--force` keeps the replaced file's mode.
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
  between reading and replacing it (`CONFIG_CHANGED`), failed write (`WRITE_FAILED`).
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
- `--data-dir` additionally checks that the data directory exists.
  `--check-backups` (needs `--data-dir`) adds the advisory backups writability check
  of `doctor` (`os.access`, nothing created).
- JSON fields: `device_count` (null when unreadable), `problems` (list of `code` and
  `message`) and, with `--check-backups`, `backups_writable`.
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
  Host/Origin; 401 means the credential was rejected.
- `--format text` and `--format json` are local output: messages and configured device
  IDs, never URLs or credentials.

### Sanitized export

`doctor --export` prints one JSON object meant for sharing in a report. It is built
from an allowlist:

- `schema_version` (1), `command` (`"doctor"`), `export` (true), `ok`;
- `runtime`: `package_version`, `build_kind`, `python_version`, `python_tier`,
  `platform_tier`;
- `transport_flags`: `offline`, `endpoint_checked`; `device_count`;
- `checks`: `category`, `status`, `code`, for device checks `device` as
  `devices[i]`, for the endpoint check `protocol_version`;
- `devices`: per device `devices[i]` with `firmware` (`ver`, `vid`, `arch`, `tier`,
  `minimum_supported`) and `unknown_capabilities` names.

Never included: device IDs or names, URLs, hosts, addresses, MAC addresses, Wi-Fi
fields, paths, credentials, message texts and raw device responses. The staged
`RELEASE` file is not read. Nothing is sent anywhere; the user decides what to share.

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
writer, ISSUE-16-DEC-002), no device discovery in these commands, no MCP tool, no
health route, no telemetry. Discovery (`wled-mcp discover`) is planned as a separate,
explicitly invoked command in the second #16 change; it is not part of this one.
