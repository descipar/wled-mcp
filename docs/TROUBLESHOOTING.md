# Troubleshooting

Symptom-driven recovery for the released server (the latest release and `main`). Nothing here needs a
controller unless a step says so, and no step writes to a device unless it names a write
tool. Examples are synthetic (`192.0.2.x`, `*.example.invalid`, `desk` and `shelf`).
Each recipe says whether it can be reproduced without hardware. Behavior that is not yet
released is not described here. There is no support commitment and no security support:
see [Support](../README.md#support) and [SECURITY.md](../SECURITY.md).

## First checks

None of these writes to a device.

- `wled-mcp --version` shows the installed version.
- `wled-mcp config validate --config <abs> [--data-dir <abs>]` runs the startup validator
  without contacting a device or the network. Exit 0 means valid, 1 means a problem.
- `wled-mcp doctor --config <abs> --data-dir <abs>` reads each device with GET requests only;
  `--offline` skips the devices. `--endpoint URL` also checks a running HTTP service with
  MCP `initialize` and `ping` (credential from `WLED_MCP_HTTP_TOKEN` or
  `--http-token-file <abs>`, never a command-line value). `doctor --export` prints a
  sanitized JSON summary for a report. Exit codes 0, 1, 2 (usage) and 3 (internal) and the
  code table are in [contract/cli.md](contract/cli.md#doctor). Paths must be absolute.
- Every served result envelope has `ok`, `application` (`not_attempted`, `not_applied`,
  `applied`, `unknown`), `verification` (`not_requested`, `verified`, `mismatch`,
  `unknown`) and, on failure, `error.code`, `error.read_retryable`, `error.write_retryable`
  (always false) and `error.reconciliation` ([TOOL-CONTRACT](TOOL-CONTRACT.md#results-and-errors),
  synthetic examples in [examples/contracts/errors.json](../examples/contracts/errors.json)).
- The server writes one stderr line per tool call; failures show at the default level and
  `WLED_MCP_LOG_LEVEL=info` adds successes (`WLED_MCP_LOG_FORMAT=json` for JSON lines). The
  line's `correlation_id` equals the one in the result. `wled_get_service_status` (read-only,
  no device contact) shows the profile, the last observed outcome per device and call
  counters ([contract/diagnostics.md](contract/diagnostics.md)).
- Liveness without touching a device is a TCP connect to the service port or an
  authenticated `ping`. There is no health route.

## Reading the outcome

| Observation | `application` | `verification` |
| --- | --- | --- |
| Successful read or valid dry run | `not_attempted` | `not_requested` |
| Failure before anything was sent (validation, capability, conflict, backup, access) | `not_attempted` | `not_requested` |
| Refusal known to have no side effect | `not_applied` | `not_requested` |
| Required postcondition observed | `applied` | `verified` |
| Acknowledged or possibly sent, readback unavailable | `unknown` | `unknown` |
| Possibly sent, readable state differs at the deadline | `unknown` | `mismatch` |
| Some steps proven applied, final postcondition not reached | `applied` | `mismatch` |

Readback proves only the state that was observed, not why it is so or that nobody changed
it later. The server never retries a mutation; a repeat request is a new invocation.

## Recipes

### 1. The server does not start or rejects the configuration

- **Symptom:** exit code 2 and `Startup configuration error: ...` on stderr; a container with
  `restart: unless-stopped` keeps restarting; `config validate` prints
  `Configuration check failed:` and exits 1.
- **Means:** the inventory failed the startup validator. The message names the entry and the
  field, never the value. Typical causes: a non-canonical IPv4 host (`127.1`, `0x7f.1`,
  `2130706433`, parts above 255), credentials in a URL, an unsupported `schema_version`,
  duplicate IDs, a file over 64 KiB, a relative or missing path (`doctor` reports
  `CONFIG_PATH_NOT_ABSOLUTE`, `CONFIG_NOT_FOUND`, `DATA_DIR_NOT_FOUND`). `config add-device`
  refuses with `DUPLICATE_ID`, `DUPLICATE_URL`, `INLINE_DEVICES_ARRAY` or `CONFIG_CHANGED`.
- **Do:** work on a copy, edit it, run `config validate`, and restart only when it exits 0.
  To roll back, copy `devices.toml.previous` back and restart. The previous process is
  already stopped, so the service stays unavailable until the file is valid. A change needs a
  restart; the released version has no reload.
- **Never:** edit the live file without keeping a copy.
- **Reproduce without hardware:** a file with `schema_version = 1`, a device `desk` (name `Desk strip`)
  at `http://192.0.2.10` and a device `shelf` (name `Shelf strip`) at `http://127.1`:

  ```text
  $ wled-mcp config validate --config <abs>/bad.toml
  Configuration check failed:
  - Invalid inventory configuration (devices[1].base_url: invalid): check schema version, unique device IDs, credential-free HTTP(S) root URLs and supported settings.
  $ echo $?
  1
  $ wled-mcp doctor --offline --config <abs>/bad.toml
  wled-mcp doctor (read-only)
  [ok] runtime RUNTIME_OK: wled-mcp <version> (release build), Python <python>.
  [warning] runtime PLATFORM_EXPERIMENTAL: This platform is experimental.
      action: See the support matrix in docs/contract/compatibility.md.
  [failed] configuration CONFIG_INVALID: Invalid inventory configuration (devices[1].base_url: invalid): check schema version, unique device IDs, credential-free HTTP(S) root URLs and supported settings.
      action: Fix the named entries and run `wled-mcp config validate`.
  [failed] storage DATA_DIR_MISSING: No data directory was given.
      action: Pass --data-dir or set WLED_MCP_DATA_DIR.
  [skipped] device DEVICES_SKIPPED: Device checks need a valid configuration.
  Summary: 2 failed, 1 warning(s).
  ```

  The output above was captured on Windows; the version and platform lines depend on the
  installation, and on Linux the `PLATFORM_EXPERIMENTAL` warning is absent. `doctor` exits 1.
- **Sources:** [contract/cli.md](contract/cli.md) (`config validate`, `config add-device`,
  `doctor`); [DEPLOYMENT.md](DEPLOYMENT.md#changing-the-inventory) and
  [Addresses and paths](DEPLOYMENT.md#addresses-and-paths-as-seen-from-each-context);
  [INVENTORY-CLIENT.md](INVENTORY-CLIENT.md#configuration-and-limits).

### 2. `UNKNOWN_DEVICE`

The `device_id` is not in the inventory and no request was sent. `wled_list_devices` shows
the configured IDs. Adding a device is an inventory edit: `wled-mcp config add-device`, then
`config validate`, then a restart (steps in
[DEPLOYMENT.md](DEPLOYMENT.md#changing-the-inventory)). Sources:
[TOOL-CONTRACT](TOOL-CONTRACT.md#results-and-errors), [contract/cli.md](contract/cli.md#config-add-device).

### 3. A controller is unreachable (`UNREACHABLE`, `TIMEOUT`, `INVALID_RESPONSE`)

- **Means:** the request failed or the deadline expired. A failure before dispatch is
  `application: not_attempted` with `read_retryable: true` and `write_retryable: false`.
  One offline controller fails alone; the others still answer. A timeout after a write may
  have been sent is a different case (recipe 4).
- **Do:** `wled_list_devices` with `probe=true` is an explicit bounded read per device;
  `wled-mcp doctor` reports `DEVICE_UNREACHABLE` or `DEVICE_TIMEOUT`. Check the address from
  the service's own context: `localhost` is the container or process doing the lookup, a
  container must reach the controller's network, and a name must resolve to exactly one
  address. Reserving the address in DHCP keeps it valid. `wled-mcp discover` (mDNS) often finds
  nothing from a container, across VLANs or behind a firewall; adding a controller by
  address always works.
- **`INVALID_RESPONSE`:** the reply was not a WLED answer. A refused read (HTTP 401 or 403, for
  example from a proxy in front of the controller) is reported this way with the status
  code and is not retried. The server sends no device credentials and a controller behind HTTP
  authentication is unsupported.
- **Firmware warnings:** firmware below 16.0.0 or unrecognized firmware is served with a
  warning and never refused; the tier is in `wled_get_state` `diagnostics.firmware_support`.
- **Evidence:** one recorded run on a deployed service used a configured entry at the
  documentation address `http://192.0.2.1`. It returned `TIMEOUT` with
  `application: not_attempted`, `read_retryable: true`, `write_retryable: false`, while the
  real controller stayed `reachable`. That address was never routed; it is not a controller
  that dropped mid-session ([validation/issue-25.md](validation/issue-25.md)).
- **Reproduce without hardware:** not offered; this recipe describes documented behavior and
  does not tell you to provoke a failure.
- **Sources:** [TOOL-CONTRACT](TOOL-CONTRACT.md#results-and-errors);
  [contract/compatibility.md](contract/compatibility.md#secured-controllers);
  [DEPLOYMENT.md](DEPLOYMENT.md#addresses-and-paths-as-seen-from-each-context);
  [contract/cli.md](contract/cli.md#discover).

### 4. An uncertain write (`application: unknown`)

Codes: `WRITE_OUTCOME_UNKNOWN`, `VERIFICATION_MISMATCH`, or `TIMEOUT` after the request may
have been sent.

- **Means:** the change may have been applied. A mismatch never proves it was not.
- **Do:** read the current state (`wled_get_state`; `wled_get_preset` or `wled_list_presets`
  for presets), compare it with the intent, then decide a new explicit request. Look for
  another writer: locks are per process, so another client, or a stdio entry and an HTTP
  service on the same controllers, are not coordinated. Multi-device scenes are not atomic;
  read each device's result.
- **Never:** replay the identical write blindly, or overwrite repeatedly to make a
  verification pass. The `reconciliation` text says the same.
- **Cases that stay uncertain:** the MCP host stops a stdio subprocess without waiting for a
  running call; a forced kill of the HTTP service. A disconnected client does not cancel a call;
  verification and lock release continue.
- **`PRESET_CONFLICT`:** a stored preset (or a playlist member, or a running playlist) changed
  between planning and the write, or the destination changed after the snapshot. Nothing was
  written for that step. Re-read and plan again.
- **Reproduce without hardware:** the synthetic cases in
  [examples/contracts/errors.json](../examples/contracts/errors.json); the mock test
  `tests/test_patches.py::test_T09_timed_out_dispatch_is_outcome_unknown` covers a timed-out dispatch.
- **Sources:** [TOOL-CONTRACT](TOOL-CONTRACT.md#results-and-errors) and
  [Transport access and lifecycle](TOOL-CONTRACT.md#transport-access-and-lifecycle);
  [VALIDATION.md](VALIDATION.md#known-limitations);
  [DEPLOYMENT.md](DEPLOYMENT.md#streamable-http-service-configuration);
  [contract/groups-scenes.md](contract/groups-scenes.md).

### 5. A preset was overwritten, deleted or restored wrongly

- **Facts:** overwriting or deleting a preset first stores a durable snapshot under
  `<data-dir>/backups/<device_id>/`. By default 20 snapshots per device are kept and no tool
  deletes one. Supplied-state stores (`wled_store_preset`), restores, imports and playlist saves change the live output on WLED 16 and the
  previous lighting is not restored.
- **Do:** `wled_list_snapshots` reads only the data directory (filter with `preset_id`; each
  entry shows `restorable`). Then run `wled_restore_preset` with `dry_run=true` first. The
  snapshot must belong to the same configured device and record the exact firmware version
  (otherwise `UNSUPPORTED_CAPABILITY`) and be a `state` or `playlist` entry. An occupied
  destination needs `overwrite=true` and takes its own prior snapshot. A playlist restore is
  refused with `PRESET_CONFLICT` while a playlist runs. A restore is one explicit write and
  is verified; if the result is uncertain, follow recipe 4.
- **Only for what the tool refuses** (`api-command` or `unknown` snapshots, a firmware
  version mismatch, playlists the firmware would not store reproducibly): the manual
  procedure in [TOOL-CONTRACT](TOOL-CONTRACT.md#snapshot-and-explicit-restoration), which is
  untested on hardware. A code update or rollback does not restore device state.
- **`BACKUP_FAILED`:** nothing was sent (`application: not_attempted`). The data directory is
  missing, not writable by the service user (the container runs as UID 10001), or does not
  support hard links. `doctor` shows `DATA_DIR_NOT_FOUND` or `BACKUPS_NOT_WRITABLE`; at
  startup the server prints one advisory line and still starts. Fix the path, then make a
  new explicit request.
- **Hardware:** restore evidence is mock tests plus one run on an unused slot. Restore onto an
  occupied slot and restore of a playlist were not run on hardware
  ([VALIDATION.md](VALIDATION.md#known-limitations)).
- **Sources:** [contract/presets.md](contract/presets.md#restore-wled_restore_preset) and
  [snapshot listing](contract/presets.md#snapshot-listing-wled_list_snapshots);
  [TOOL-CONTRACT](TOOL-CONTRACT.md#snapshot-and-explicit-restoration);
  [DEPLOYMENT.md](DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and
  [Persistent paths](DEPLOYMENT.md#persistent-paths); [contract/cli.md](contract/cli.md#ops-04-conditions).

### 6. HTTP service: 401, 403, 404, 405 or 413

The access guard answers before any tool or device work, in this order: Host and Origin,
then the bearer credential, then the path, then the method.

| Status | Meaning | Fix |
| --- | --- | --- |
| `403` | Host or Origin not allowed | The authority the client uses (host and port) must equal an `--allowed-host` entry exactly (case-insensitive, no implied default port, no wildcard; `X-Forwarded-*` is never consulted). A changed bind host or port needs explicit `--allowed-host`. `--allowed-origin` is empty by default and matters only for browser clients. Example authority: `wled-mcp.example.invalid:8000` |
| `401` | Missing or invalid credential (`WWW-Authenticate: Bearer`) | Send exactly one `Authorization: Bearer <credential>` header; the credential is 32 to 512 printable ASCII characters without whitespace. A file credential is read once at startup, so rotation is a restart. The hub does not expand placeholders such as `REPLACE_WITH_PRIVATE_SERVICE_TOKEN`. Hub authentication does not protect the service, and the credential is one shared credential |
| `404` | Path other than `/mcp` | Use `/mcp` |
| `405` | Any method except POST | The service is stateless and issues no session IDs; GET and DELETE are not supported |
| `413` | Body over 256 KiB | Send a smaller request |

- **Startup exit 2 before listening:** a missing, conflicting or invalid credential source; a
  changed host or port without `--allowed-host`; HTTP-only options together with stdio.
- **Not reachable from the host shell:** the Compose example publishes no host port. Run
  checks through `docker compose ... exec`.
- **`doctor --endpoint <url>`** names the case: `ENDPOINT_HOST_ORIGIN_REJECTED` (HTTP 403 or
  421), `ENDPOINT_CREDENTIAL_REJECTED` (401), `ENDPOINT_CREDENTIAL_MISSING`,
  `ENDPOINT_CREDENTIAL_INVALID`, `ENDPOINT_UNREACHABLE`, `ENDPOINT_TIMEOUT`,
  `ENDPOINT_OTHER_SERVER` or `ENDPOINT_PROTOCOL_ERROR`. It sends the credential to the given
  URL, so use a loopback address or HTTPS.
- **Reproduce without hardware:** run the service on loopback with a synthetic credential as in
  [DEVELOPMENT.md](DEVELOPMENT.md#streamable-http-service-and-tests), then
  `wled-mcp doctor --endpoint http://127.0.0.1:8000/mcp`. The wrong-Host and wrong-credential
  cases are covered by `tests/test_http_service.py`. The authenticated `ping` snippet is in
  [DEPLOYMENT.md](DEPLOYMENT.md#http-service-build-start-verify); never paste a real credential.
- **Sources:** [TOOL-CONTRACT](TOOL-CONTRACT.md#transport-access-and-lifecycle);
  [DEPLOYMENT.md](DEPLOYMENT.md#streamable-http-service-configuration) and
  [MCPHub notes](DEPLOYMENT.md#mcphub-notes); [contract/cli.md](contract/cli.md#doctor);
  [README](../README.md#safety-model).

### 7. A tool is missing or answers `ACCESS_DENIED`

A tool outside the active profile (`read-only`, `control` or `full`; default `full`) is
absent from `tools/list`, and calling it directly fails like an unknown tool (`-32602`,
`Unknown tool`). A call above a device's `max_class` ceiling returns `ACCESS_DENIED` with
`application: not_attempted`; nothing was sent and a retry does not change it. Change
`--profile` or `[access]` in the inventory and restart. Source:
[contract/profiles.md](contract/profiles.md#enforcement).

### 8. A request is rejected before any write

`VALIDATION_ERROR`, `AMBIGUOUS_NAME`, `PRESET_NOT_FOUND` and `UNSUPPORTED_CAPABILITY` mean
the whole request was checked against the current state and nothing was changed
(`application: not_attempted`). Fix the named field, use `dry_run=true` to preview, and
remember that omitted fields mean "unchanged" and only `wled_replace_layout` removes segments
that are not listed. Sources: [README](../README.md#safety-model),
[TOOL-CONTRACT](TOOL-CONTRACT.md#results-and-errors).

### 9. A change does not seem to show on the LEDs

`wled_explain_lighting` reads state and info once each (never a write) and returns
observations, candidate causes with limited confidence and next checks. `wled_get_live_snapshot`
reports sampled colours; on the one tested controller the live endpoint answered HTTP 501 and
the tool reported it as unavailable. Neither proves a cause or colour accuracy. Sources:
[contract/explain.md](contract/explain.md), [contract/live-snapshot.md](contract/live-snapshot.md),
[VALIDATION.md](VALIDATION.md#known-limitations).

### 10. Reporting a problem

Open a [GitHub issue](https://github.com/descipar/wled-mcp/issues); it is answered best
effort. Attach `wled-mcp doctor --export`, the tool name, `error.code`, the `correlation_id`
and the matching log line. Leave out hosts, addresses, tokens and file paths. There is no
security support ([SECURITY.md](../SECURITY.md), [CONTRIBUTING.md](../CONTRIBUTING.md)).

## Failure recovery overview

| Situation | Controller state | First action | Never |
| --- | --- | --- | --- |
| `VALIDATION_ERROR`, `UNSUPPORTED_CAPABILITY`, `ACCESS_DENIED`, `AMBIGUOUS_NAME` | unchanged | fix the request or the deployment setting | treat it as uncertain |
| `UNREACHABLE` or `TIMEOUT` before dispatch (`not_attempted`) | unchanged | check the address from the service's context, run `doctor` | assume the write happened |
| `BACKUP_FAILED` | unchanged (the snapshot is taken before the write) | fix the data directory (exists, writable, hard links) | skip the snapshot |
| Refusal with no side effect (`not_applied`) | unchanged | read the message | n/a |
| `unknown`, `WRITE_OUTCOME_UNKNOWN`, `TIMEOUT` after dispatch | unknown | read back, compare, decide a new explicit request | replay blindly |
| `VERIFICATION_MISMATCH` (`unknown` or `applied` with `mismatch`) | possibly or partly changed | read back; look for another writer | overwrite repeatedly to pass verification |
| `PRESET_CONFLICT` | unchanged for that step | re-read and plan again | force it |
| Preset lost or changed | a snapshot exists for overwrites and deletes | `wled_list_snapshots`, then `wled_restore_preset` (dry run first) | assume activating a preset restores storage |
| Forced stop, host kills the stdio process, crash | writes in flight stay uncertain; nothing resumes on restart | read back | assume it finished or was rolled back |
| Update or rollback of the code | unchanged: device state is never rolled back, snapshots stay | restore device state explicitly if wanted | expect the code rollback to restore lights or presets |
| Rejected inventory at startup | unchanged; the service is unavailable until fixed | `config validate`, fix or restore `devices.toml.previous`, restart | edit the live file without a copy |
| Credential rotation | unchanged | replace the secret, restart, update the client header | expect a reload |

Sources: [TOOL-CONTRACT](TOOL-CONTRACT.md#results-and-errors);
[DEPLOYMENT.md](DEPLOYMENT.md#http-service-update-rollback-recreation-removal) and
[Changing the inventory](DEPLOYMENT.md#changing-the-inventory);
[contract/diagnostics.md](contract/diagnostics.md#credential-rotation-and-tenancy).
