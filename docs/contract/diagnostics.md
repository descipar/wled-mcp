# Runtime diagnostics (issue #20)

Contract for [issue #20](https://github.com/descipar/wled-mcp/issues/20) (S2-ACCESS-03, OPS-03,
OPS-05; scenarios T20-14 to T20-17): the correlation ID, bounded call logs and the
`wled_get_service_status` tool. Profiles and device ceilings are in [profiles.md](profiles.md).
Decisions:
[ISSUE-20-DEC-001](../decisions/issue-20.md#issue-20-dec-001--default-profile-device-restrictions-status-surface-classes)
(human: no unauthenticated health route, readiness as a read-class tool, a correlation ID as a
result-envelope field) and
[ISSUE-20-DEC-002](../decisions/issue-20.md#issue-20-dec-002--technical-defaults-td-20-1-to-td-20-15)
(coordinator, TD-20-9 to TD-20-12). Evidence: [validation/issue-20.md](../validation/issue-20.md)
(mock and loopback only; no hardware claim).

Everything here is local and passive: there is no outbound telemetry, no polling of controllers,
no file logging and no new network surface.

## Correlation ID

Every tool result carries `correlation_id` in its envelope: 16 lowercase hexadecimal characters
from the OS secure random source, generated per `tools/call`. It is the same in the result text,
in `structuredContent` and in the call's log line. It is never taken from client input: an
argument named `correlation_id` is an unknown field and a `VALIDATION_ERROR`.

- It is set on every envelope the dispatcher returns: successes, domain errors, validation errors
  and `ACCESS_DENIED`.
- An internal error (`-32603`) has no envelope; its fixed message ends with the ID:
  `Internal operation failure (correlation_id=<id>)`. Nothing else about the failure is returned
  or logged.
- An unknown or disabled tool is the protocol error `-32602` `Unknown tool`, byte-identical for
  both, so it carries no ID (it must not reveal which names exist). It is logged as
  `unknown_tool` with an ID in the log line only.
- The field is additive and optional (declared as an optional string, not in `required`); an
  envelope that was not served (a direct `execute` result, retained examples) omits it. Consumers
  comparing two served envelopes must ignore it.
- It correlates one result with one log line; it is not an identity, session or secret and is not
  unique across restarts.

## Logging

One line per tool call goes to **stderr** (never stdout, which is reserved for stdio MCP), built
from an allowlist; a field is omitted when it does not apply.

| Field | Content |
| --- | --- |
| `event` | `tool_call` |
| `tool` | the registered tool name, or `unknown_tool` for an unregistered or disabled name |
| `class` | `read`, `control` or `manage` (absent for `unknown_tool`) |
| `device_id` | the configured device ID, only if the call named a device of the inventory (an unknown ID is client input and is not logged) |
| `ok` | `true` or `false` |
| `application`, `verification` | the outcome axes of the envelope; absent for `unknown_tool`; see below for an internal failure |
| `error_code` | the domain error code, `UNKNOWN_TOOL` or `INTERNAL_FAILURE` |
| `duration_ms` | integer milliseconds |
| `correlation_id` | the ID of the result |

Never logged: argument values, scene or preset contents, URLs, hosts, headers, request or response
bodies, exception text, file paths or any credential. Every value comes from a fixed set or from
configuration; a line is at most 512 characters.

- An internal failure has no envelope, so its line has no `verification`. It names the configured
  `device_id` the call was validated against, and for a `control` or `manage` tool only
  `application=unknown` (a crash cannot tell "not attempted" from "possibly applied"). A `read`
  tool's line has no `application`.
- `WLED_MCP_LOG_LEVEL` selects `warning` (default) or `info`. A successful call is an INFO line, a
  failed one (`ok=false`, including `ACCESS_DENIED` and unknown tools) a WARNING line, so the
  default shows failures only. At `info` the startup event of
  [profiles.md](profiles.md#configuration) is shown too. The level applies to the `wled_mcp`
  loggers; other libraries stay at `warning` because their INFO lines can contain device URLs.
- `WLED_MCP_LOG_FORMAT` selects `text` (default) or `json` (one JSON object per line with `ts`,
  `level` and the fields above; non-call records carry `logger` and `message`).
- An unsupported value stops startup with exit 2 and a message naming the variable, never its
  value. The variables apply to the serving process, not to the subcommands of [cli.md](cli.md).
- Text example (one line):
  `2026-01-01T12:00:00Z WARNING wled_mcp.calls: event=tool_call tool=wled_set_state class=control device_id=desk ok=false application=not_attempted verification=not_requested error_code=ACCESS_DENIED duration_ms=0 correlation_id=0123456789abcdef`

The HTTP rejection events (wrong Host, Origin or credential) keep their fixed, value-free text and
share this format. There is no rate limiting.

## `wled_get_service_status`

Class `read`, no arguments, `readOnlyHint`, `idempotentHint` true, `openWorldHint` false.
Registered in every profile, second in the tool list. It reads process memory only: no device
request, no file write, nothing started; `wled_list_devices` with `probe=true` stays the explicit
live check.

`data` (all keys always present):

| Key | Content |
| --- | --- |
| `service` | `name`, `version`, `transport` (`stdio` or `streamable-http`; `unknown` for an embedding that did not say), `uptime_seconds` |
| `access` | `profile` and `devices`: per configured device `device_id`, `max_class` (its cap or `null`) and `effective_class` (the lower of profile and cap) |
| `liveness` | `status: "alive"` and a `definition` text |
| `readiness` | `basis` text, `counts` (`unknown`, `reachable`, `failed`) and `devices`: per configured device `device_id`, `state` and, once observed, `age_seconds`; a failed one also `error_code` |
| `calls` | counters since start: `total`, `ok`, `failed`, `unknown_tool`, `internal_failure`, `by_class` (`read`, `control`, `manage`) and `by_error_code` (only codes that occurred, from the fixed set of the logs) |
| `backups` | `writable_at_startup`: the one advisory startup check, `true`/`false`, or `null` when none was made (never reported writable without a check) |

- **Liveness** is the process answering: a TCP connect to the HTTP service port or an
  authenticated MCP `ping`; neither touches a device. There is no unauthenticated health route
  (ISSUE-14-DEC-004, ISSUE-20-DEC-001) and the status tool is not one: it needs the same access as
  every other tool.
- **Readiness** per device is the last outcome of a request this process actually sent to it,
  recorded by the device client during ordinary tool calls. `unknown`: no request observed since
  start (neither healthy nor failed). `reachable`: the last request succeeded, `age_seconds` says
  how long ago. `failed`: the domain code of the last failure (`UNREACHABLE`, `TIMEOUT` or
  `INVALID_RESPONSE`) and its age. A request that never left the process (exhausted deadline,
  unusable configured address) is not an observation.
- There is no aggregate "healthy" or "ready" flag: a fleet is summarized only by `counts`, and an
  old observation says nothing about the device now. A stale or unobserved device is never
  reported healthy, and calling the tool sends no request.
- Counters include calls to disabled tools and failed calls, not the call being answered; they
  reset on restart, hold no per-device or per-argument keys and cannot grow without bound.
- `data` contains no URL, host, address, path, credential or configuration text. Device IDs are
  those `wled_list_devices` returns.

## Credential rotation and tenancy

- Credential rotation is restart-based. The service reads its bearer credential once at startup
  (`WLED_MCP_HTTP_TOKEN` or `--http-token-file`); to rotate, replace the secret, restart the
  service and update the client or hub header ([DEPLOYMENT.md](../DEPLOYMENT.md)). There is no
  reload and no second credential. A stdio process has no service credential: the MCP host that
  starts it is its only caller.
- There are no per-credential scopes. One shared credential is one caller class: everyone who
  holds it has the whole reach of the profile (ISSUE-20-DEC-001).
- A shared credential does not give tenant isolation, and neither do profiles or device ceilings:
  a profile is a deployment setting, not a tenancy boundary. Two groups that must not share reach
  need two services (own credential, profile and inventory).

## Liveness and status checks, side by side

| Check | Device contact | Credential | Shows |
| --- | --- | --- | --- |
| TCP connect to the service port | none | none | the process listens |
| authenticated MCP `ping` | none | yes | the process serves MCP |
| `wled_get_service_status` | none | yes | the facts above, including the last observation per device |
| `wled_list_devices` with `probe=true` | one bounded read per device | yes | current reachability, explicitly requested |
| `wled-mcp doctor` | read-only probes when asked | as configured | configuration and firmware facts ([cli.md](cli.md)) |

## Compatibility

Additive ([versioning.md](versioning.md#schema-evolution)): a new tool, one optional output field
and no change to any existing tool's input or `data`. No migration note applies.
