# Tool profiles and device ceilings (issue #20)

Contract for [issue #20](https://github.com/descipar/wled-mcp/issues/20) (S2-ACCESS-01 and
S2-ACCESS-02; scenario S2-T02). Enforcement is described here, diagnostics (correlation ID, logs,
status tool) in [diagnostics.md](diagnostics.md).
Decisions: [ISSUE-20-DEC-001](../decisions/stage-2.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human: default `full`, per-device maximum class, vocabulary) and
[ISSUE-20-DEC-002](../decisions/stage-2.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator, technical defaults). Evidence: [validation/stage-2-core.md](../validation/stage-2-core.md)
(mock and loopback only; no hardware claim).

The deployment, not the MCP host, selects what the server will do. Tool annotations stay hints;
the server enforces the profile and the device ceilings, identically for stdio and Streamable HTTP
and for all concurrent sessions of one process.

## Classes and profiles

`wled_discover_devices` (#200) is `read`; `wled_set_discovery_ranges` (#202) and `wled_add_device`
(#203) are `manage` ([discovery.md](discovery.md)).

Every tool has exactly one class, set on its `Operation` (`tool_class`, required, no default). The
class is the maximum over all argument combinations: `dry_run` does not lower it, so a preview of a
`manage` tool is still `manage` (TD-20-2). A read-only deployment previews through read-class plan
tools where one exists.

| Class | Meaning | Tools |
| --- | --- | --- |
| `read` | No live, storage or local file mutation | `wled_list_devices`, `wled_get_state`, `wled_get_effects`, `wled_get_palettes`, `wled_search_effects`, `wled_list_presets`, `wled_get_preset`, `wled_list_snapshots`, `wled_export_presets`, `wled_list_groups`, `wled_list_scenes`, `wled_plan_scene`, `wled_list_zones`, `wled_plan_zone`, `wled_preview_layout`, `wled_get_signal_status`, `wled_discover_devices` |
| `control` | Live device output only; never device storage or a local persistent artifact | `wled_set_state`, `wled_patch_segments`, `wled_replace_layout`, `wled_activate_preset`, `wled_apply_scene`, `wled_apply_zone`, `wled_apply_room`, `wled_start_signal`, `wled_cancel_signal` |
| `manage` | Device storage or local persistent artifacts | `wled_save_preset`, `wled_delete_preset`, `wled_restore_preset`, `wled_store_preset`, `wled_save_playlist`, `wled_import_presets`, `wled_save_group`, `wled_delete_group`, `wled_save_scene`, `wled_delete_scene`, `wled_set_discovery_ranges`, `wled_add_device` |

`wled_replace_layout` is `control` (ISSUE-20-DEC-001, D1): the live segment layout is device
output, although the call is destructive for the current layout. `wled_import_presets` and
`wled_restore_preset` are `manage` although they also change live output. Group and scene tools
that store or delete a definition file are `manage` ([groups-scenes.md](groups-scenes.md)); they
take no `device_id`, so only the registration filter applies. `wled_plan_scene` is `read`.
`wled_apply_scene` (#17) is `control`, applies through the write engines and calls
`Resources.require_access` in its preflight once per expanded device
([groups-scenes.md](groups-scenes.md#apply-wled_apply_scene)).

A delayed write has no request to inherit a class from. The temporary-signal task
([signals.md](signals.md#locks-and-access-context)) sets `control` explicitly for its whole life,
so its restore is checked as a `control` operation against the device ceiling and is never the
ambient "unknown, assume `manage`" case that a restricted deployment refuses.

Profiles are cumulative sets of classes:

| Profile | Classes registered |
| --- | --- |
| `read-only` | `read` |
| `control` | `read`, `control` |
| `full` (default) | `read`, `control`, `manage` |

A new tool is classified in its own pull request (`tests/tool_contract.py` and the `Operation`); a
test compares the expectation data with the production table.

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

- Without `[access]` the profile is `full`; without `max_class` a device has no cap. Existing
  configurations and hub entries keep working.
- Write root keys (`schema_version`, an inline `devices = [...]`) before any table header: a key
  after a `[table]` header belongs to that table. By convention `[access]` precedes the first
  `[[devices]]`; `config add-device` appends its block after the file, so an existing `[access]`
  stays valid.
- A `[discovery]` table (`ranges`, #202) is separate and is applied by the in-process reload of
  `wled_set_discovery_ranges`; profile and caps need a restart
  ([discovery.md](discovery.md#reload-semantics)). Place it before the first `[[devices]]` too.
- The serve option `--profile read-only|control|full` overrides `[access] profile`. Precedence:
  option, file, `full`. There is no environment variable. With a subcommand it is the usual usage
  error (exit 2); an older server rejects it as an unknown option (exit 2).
- The effective class for a device is the lower of the profile and the device's `max_class`.
- Invalid values stop startup with exit 2 and a positional message that never echoes the value:
  `access.profile: invalid`, `devices[i].max_class: invalid`, or `access: unsupported field` for
  an unknown key (key name never shown). A profile outside the three names on the command line is
  the fixed usage error.
- `wled-mcp config validate` and `doctor` report the profile ("as configured"; a serve
  `--profile` overrides it) and the number of capped devices only when the file sets an access
  setting ([cli.md](cli.md)). `doctor --export` carries the profile name and each device's
  `max_class` (class names only). `config add-device` has no `max_class` option; edit the file and
  run `config validate`.
- A restart applies a changed profile or cap; there is no reload.
- The startup event (`service starting: transport=... profile=... capped_devices=N`) is an INFO
  line of the `wled_mcp` logger, shown only with `WLED_MCP_LOG_LEVEL=info`
  ([diagnostics.md](diagnostics.md#logging)).

## Enforcement

Three layers, all in the server process, none depending on the client:

1. **Registration filter (G1).** `create_server` registers only operations whose class is in the
   profile. `tools/list`, `tools/call` and the SDK's tool-schema lookup (the `Mcp-Param` path)
   read that one registry. A tool outside the profile is absent from the list, and a direct
   `tools/call` fails like a made-up name: JSON-RPC error `-32602` with `Unknown tool`, before any
   I/O. No message lists disabled tools. Remaining tools' schemas and descriptions are
   byte-identical to the `full` list. `build_operations` stays unfiltered.
2. **Device ceiling at dispatch (G2).** After schema validation and before the tool runs, a call
   whose validated arguments carry a `device_id` is refused when its tool class is above that
   device's effective ceiling, including `dry_run`. An unknown device falls through to
   `UNKNOWN_DEVICE`; an invalid request is a `VALIDATION_ERROR` first.
3. **Write engines (G3).** Every device state write goes through `WLEDClient.post_state`, reached
   only from the write engines of `Resources` (`write_verified`, `write_sequence_verified`,
   `write_polled`) and the preset import path. Each checks first, before the device lock and any
   I/O, using the class of the tool call in progress (an ambient value set by the dispatcher and
   inherited by tasks and threads the call starts). A `read` call may never write; a `control` or
   `manage` call is refused above the device's ceiling. Composite tools without a top-level
   `device_id` (for example scenes, #17) therefore cannot write to a device above its ceiling.
   Outside any tool call (in-process callers) the class counts as `manage`: nothing changes under
   the default policy, and under any restriction the call is refused.
   `Resources.require_access(device_id, tool_class)` is the raising form, for composite
   preflights that must refuse a capped device before reading it.

A refusal by G2 or G3 is a domain result, not a protocol error:

| Field | Value |
| --- | --- |
| `ok` | `false` (`isError` true) |
| `error.code` | `ACCESS_DENIED` |
| `application` / `verification` | `not_attempted` / `not_requested` |
| `device_id` | the requested configured device |
| `error.message` | fixed text naming only the device ID and class names |
| `error.write_retryable` | `false` |

Nothing was sent or written, so the refusal is not an uncertain write and does not change on retry
unless the deployment configuration changes. `ACCESS_DENIED` joins the stable codes of the
[tool contract](../TOOL-CONTRACT.md#results-and-errors); a new output enum value is non-breaking
([versioning.md](versioning.md#schema-evolution)).

## What a profile is not

- Profiles and ceilings are deployment settings, not tenancy. A profile applies to the whole
  process: every caller of one stdio process or HTTP service gets the same tools. A shared HTTP
  credential is not a per-user permission; there are no per-credential scopes (ISSUE-20-DEC-001).
- They do not replace the service's own access protection: the HTTP endpoint still needs its
  credential and Host/Origin allowlist, and hub authentication does not protect direct service
  access ([DEPLOYMENT.md](../DEPLOYMENT.md#streamable-http-service-configuration)).
- Rotating the credential, a profile or a cap is restart-based.
- The raw state patch stays excluded (ISSUE-13-DEC-001); a future one would have to obey the
  profiles.
- `wled_list_devices` does not report caps.

## Upgrade and downgrade

The two keys are listed in the migration notes of [versioning.md](versioning.md#migration-notes)
with release `0.1.0`. A build from before #20 (never released) rejects `[access]` and `max_class`
at startup (exit 2) instead of ignoring a restriction; after a downgrade use the configuration
kept for that version. Upgrading needs no change: absent keys mean `full` and no caps. The
`tools/list` of a `full` server only gained the `ACCESS_DENIED` enum value in the error schema.
