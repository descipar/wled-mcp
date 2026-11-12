# Tool profiles and device ceilings (issue #20)

Contract for [issue #20](https://github.com/descipar/wled-mcp/issues/20) (S2-ACCESS-01 and
S2-ACCESS-02; scenario S2-T02), first pull request: enforcement. The second pull request
added diagnostics (correlation ID, logs, status tool) in
[diagnostics.md](diagnostics.md).
Decisions: [ISSUE-20-DEC-001](../decisions/issue-20.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human: default `full`, per-device maximum class, vocabulary) and
[ISSUE-20-DEC-002](../decisions/issue-20.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator, technical defaults). Evidence: [validation/issue-20.md](../validation/issue-20.md)
(mock and loopback only; no hardware claim).

The deployment, not the MCP host, selects what the server will do. Tool annotations
(`readOnlyHint`, `destructiveHint`) stay hints; the server itself enforces the profile and
the device ceilings below, identically for stdio and Streamable HTTP and for all
concurrent sessions of one process.

## Classes and profiles

From M8 (not yet implemented) `wled_discover_devices` is `read`; `wled_set_discovery_ranges` and `wled_add_device` are `manage` ([discovery.md](discovery.md)). The tables below list the registered tools only.

Every tool has exactly one class, set on its `Operation` (`tool_class`, required, no
default). The class of a tool is the maximum over all its argument combinations:
`dry_run` does not lower it, so a preview of a `manage` tool is still a `manage` call
(TD-20-2). A read-only deployment previews through read-class plan tools where one
exists.

| Class | Meaning | Tools |
| --- | --- | --- |
| `read` | No live, storage or local file mutation | `wled_list_devices`, `wled_get_state`, `wled_get_effects`, `wled_get_palettes`, `wled_search_effects`, `wled_list_presets`, `wled_get_preset`, `wled_list_snapshots`, `wled_export_presets`, `wled_list_groups`, `wled_list_scenes`, `wled_plan_scene`, `wled_list_zones`, `wled_plan_zone`, `wled_preview_layout`, `wled_get_signal_status` |
| `control` | Live device output only; never device storage or a local persistent artifact | `wled_set_state`, `wled_patch_segments`, `wled_replace_layout`, `wled_activate_preset`, `wled_apply_scene`, `wled_apply_zone`, `wled_start_signal`, `wled_cancel_signal` |
| `manage` | Device storage or local persistent artifacts | `wled_save_preset`, `wled_delete_preset`, `wled_restore_preset`, `wled_store_preset`, `wled_save_playlist`, `wled_import_presets`, `wled_save_group`, `wled_delete_group`, `wled_save_scene`, `wled_delete_scene` |

`wled_replace_layout` is `control` (ISSUE-20-DEC-001, D1): it changes the live segment
layout, which is device output, even though the call is destructive for the current
layout. `wled_import_presets` and `wled_restore_preset` are `manage` although they also
change live output. The group and scene tools that store or delete a definition file are
`manage` (a local persistent artifact; [groups-scenes.md](groups-scenes.md)); they take no
`device_id`, so only the registration filter applies to them. `wled_plan_scene` is `read`
because it never writes. `wled_apply_scene` (#17) is `control`, applies
through the write engines and calls `Resources.require_access` in its preflight, once per
expanded device (it has no single `device_id`; [groups-scenes.md](groups-scenes.md#apply-wled_apply_scene)).

A delayed write has no request of its own to inherit a class from. The temporary-signal task
(`wled_start_signal`, [signals.md](signals.md#locks-and-access-context)) therefore sets the class
`control` explicitly for its whole life, so its restore at expiry, cancel or shutdown is checked as
a `control` operation against the device ceiling and is never the ambient "unknown, assume
`manage`" case that a restricted deployment refuses.

Profiles are cumulative sets of classes:

| Profile | Classes registered |
| --- | --- |
| `read-only` | `read` |
| `control` | `read`, `control` |
| `full` (default) | `read`, `control`, `manage` |

A new tool is classified in its own pull request (`tests/tool_contract.py` and the
`Operation`); the expectation data and the production table are compared by a test.

## Configuration

Both settings are optional and additive; `schema_version` stays 1.

```toml
schema_version = 1

[access]
profile = "control"        # "read-only" | "control" | "full" (default)

[[devices]]
id = "desk"
name = "Example desk"
base_url = "http://192.0.2.10"
max_class = "read"         # optional: "read" | "control" | "manage" (no cap in effect)
```

- Without `[access]` the profile is `full`; without `max_class` a device has no cap.
  Existing configurations and hub entries keep working unchanged.
- Write the root keys (`schema_version`, an inline `devices = [...]`) before any table
  header: a key after a `[table]` header belongs to that table. Place `[access]` before the
  first `[[devices]]` table by convention; TOML itself accepts it in either position, and
  `config add-device` appends its block after the file so an existing `[access]` table
  stays valid.
- The serve option `--profile read-only|control|full` overrides `[access] profile`.
  Precedence: option, then file, then `full`. There is no environment variable. The
  option is a serve option: together with a subcommand it is the usual usage error
  (exit 2), and it is not a file format, so it needs no migration note. An older server
  rejects it as an unknown option (exit 2).
- The effective class for a device is the lower of the profile and the device's
  `max_class`.
- Invalid values stop startup with exit 2 and a positional message that never echoes the
  value: `access.profile: invalid`, `devices[i].max_class: invalid`, or
  `access: unsupported field` for an unknown key (the same wording as
  `devices[i]: unsupported field`; the key's name is never shown). A profile outside the
  three names on the command line is the fixed usage error.
- `wled-mcp config validate` and `doctor` report the profile and the number of capped
  devices only when the file sets an access setting; their output is otherwise unchanged
  ([cli.md](cli.md)). The reported profile is the file's ("as configured"); a serve
  `--profile` overrides it. `doctor --export` carries the profile name and each device's
  `max_class` (class names only; no device ID, URL or path). `config add-device` appends
  a `[[devices]]` block after an existing `[access]` table without changing earlier
  bytes; there is no option for `max_class` yet, edit the file and run `config validate`.
- A restart applies a changed profile or cap; there is no reload.
- The startup event (`service starting: transport=... profile=... capped_devices=N`) is an
  INFO line of the `wled_mcp` logger. The default log level is `warning`, so it is not
  shown unless `WLED_MCP_LOG_LEVEL=info` is set ([diagnostics.md](diagnostics.md#logging)).

## Enforcement

Three layers, all in the server process, none depending on the client:

1. **Registration filter (G1).** `create_server` registers only the operations whose
   class is in the profile. `tools/list`, `tools/call` and the SDK's tool-schema lookup
   (used for the `Mcp-Param` path) read that one registry. A tool outside the profile is
   absent from the list, and a direct `tools/call` of it fails exactly like a made-up
   tool name: JSON-RPC error `-32602` with the message `Unknown tool`, before any device,
   file or network I/O. No message lists disabled tools. Restricting a profile only
   removes tools; each remaining tool's schema and description are byte-identical to the
   `full` list. `build_operations` itself stays unfiltered.
2. **Device ceiling at dispatch (G2).** After schema validation and before the tool runs,
   a call whose validated arguments carry a `device_id` is refused when its tool class is
   above that device's effective ceiling. This covers `dry_run` calls. An unknown device
   falls through to the tool's own `UNKNOWN_DEVICE`; an invalid request is still a
   `VALIDATION_ERROR` first.
3. **Write engines (G3).** Every device state write goes through `WLEDClient.post_state`,
   reached only from the three write engines of `Resources` (`write_verified`,
   `write_sequence_verified`, `write_polled`) and the preset import path. Each of them
   checks first, before taking the device lock and before any I/O, using the class of the
   tool call in progress (an ambient value set by the dispatcher and inherited by
   tasks and threads the call starts). A `read` call may never write; a `control` or
   `manage` call is refused when it exceeds the device's ceiling. Composite tools that
   reach devices without a top-level `device_id` (for example scenes of #17) therefore
   cannot write to a device above its ceiling even when the composite is listed.
   Outside any tool call (in-process callers) the class counts as `manage`: nothing
   changes under the default policy, and under any restriction the call is refused.
   `Resources.require_access(device_id, tool_class)` is the same check in raising form,
   for composite preflights that must refuse a capped device before reading it.

A refusal by G2 or G3 is a domain result, not a protocol error:

| Field | Value |
| --- | --- |
| `ok` | `false` (`isError` true) |
| `error.code` | `ACCESS_DENIED` |
| `application` / `verification` | `not_attempted` / `not_requested` |
| `device_id` | the requested configured device |
| `error.message` | fixed text naming only the device ID and class names |
| `error.write_retryable` | `false` |

Nothing was sent to the device and nothing was written, so the refusal is not an
uncertain write. A call that is refused does not change after a retry unless the
deployment configuration changes. `ACCESS_DENIED` joins the stable codes of the
[tool contract](../TOOL-CONTRACT.md#results-and-errors); adding an output enum value is
non-breaking ([versioning.md](versioning.md#schema-evolution)).

## What a profile is not

- Profiles and ceilings are deployment settings, not tenancy. A profile applies to the
  whole process: every caller of one stdio process or one HTTP service gets the same tools.
  A shared HTTP credential is not a per-user permission: everyone who holds it has the
  profile's full reach, and there are no per-credential scopes (ISSUE-20-DEC-001).
- They do not replace the service's own access protection: the HTTP endpoint still needs
  its credential and Host/Origin allowlist, and hub authentication does not protect direct
  service access ([DEPLOYMENT.md](../DEPLOYMENT.md#streamable-http-service-configuration)).
- Rotating the credential is restart-based; changing a profile or cap is a restart too.
- The raw state patch stays excluded (ISSUE-13-DEC-001); a future one would have to obey
  the profiles.
- `wled_list_devices` is unchanged: it does not report caps.

## Upgrade and downgrade

The two new keys are listed in the machine-readable migration notes of
[versioning.md](versioning.md#migration-notes) with the release `0.1.0`, the first one
that contains them. A build from before #20 (never released) rejects `[access]` and `max_class` at startup
(exit 2) rather than ignoring a restriction silently; after a downgrade, use the configuration kept for that
version. Upgrading needs no change: absent keys mean `full` and no caps. The `tools/list`
of a `full` server only gained the `ACCESS_DENIED` enum value in the error schema; no tool
changed.
