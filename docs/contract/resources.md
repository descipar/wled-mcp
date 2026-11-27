# MCP resources (MCPRES-01 to MCPRES-08, #258)

Contract for milestone M9 (not yet released). The device list and the effect and palette catalog of one controller can
be read as MCP resources, so a client can fetch them without a tool call. Tools stay the primary
path: some MCP clients ignore resources, so no tool description or instruction depends on them.
Decision: [ISSUE-258-DEC-001](../decisions/m7-m8.md) (coordinator under the owner's instruction;
reviewed at merge). Evidence: [validation/m7-m8.md](../validation/m7-m8.md#issue-258-catalog-resources).
Both transports share these operations. Examples are synthetic.

## Requirements

| ID | Statement | Evidence |
| --- | --- | --- |
| MCPRES-01 | URIs `wled://devices`, `wled://devices/{controller}/effects` and `wled://devices/{controller}/palettes`; `resources/list` returns the static resource, `resources/templates/list` the two templates; no query string or fragment; `{controller}` is a configured device ID. | mocked |
| MCPRES-02 | The body (`application/json`) equals the mapped tool's result for default arguments, produced by the same adapter code; no refresh, no filters. | mocked |
| MCPRES-03 | A resource is registered if and only if its read tool is registered (the profile's classes AND the selected tool groups); it has no class, group or setting of its own. An unregistered resource is an unknown URI, before any I/O, and names no tool. | mocked |
| MCPRES-04 | Read-only, no new device access, same redaction (no address, credential or path), same cache and bounds as the tools. | mocked |
| MCPRES-05 | A failed read returns the tool's structured error object; an unknown URI returns a fixed "not found" error. | mocked |
| MCPRES-06 | Identical on stdio and Streamable HTTP and across sessions of one process. | mocked, installed console |
| MCPRES-07 | `tools/list`, instructions and prompts are unchanged; the tool-list token delta is recorded (none). | mocked |
| MCPRES-08 | The resources capability is advertised only when at least one resource is registered, without `subscribe` or `listChanged`; the client-support caveat is documented. | mocked |

## Resources

| URI | Mapped tool | Arguments used | Content |
| --- | --- | --- | --- |
| `wled://devices` | `wled_list_devices` | `probe=false` | Configured IDs, names, `probe_status` `untested`, room. No network access; no address. |
| `wled://devices/{controller}/effects` | `wled_get_effects` | `device_id={controller}`, no `refresh`, no filters | Effect catalog with metadata block and freshness. |
| `wled://devices/{controller}/palettes` | `wled_get_palettes` | `device_id={controller}`, no `refresh` | Palette catalog with freshness. |

`resources/list` returns only `wled://devices`. There is no concrete entry per controller: the
inventory can change in-process (DEC-035), so such a list would go stale. Per-controller URIs are
reached through the templates. There is no `listChanged`, no subscription, no resource for state,
presets, search or any write, and no `refresh` or filter parameter; a client that needs those uses the
tools.

The body is one text content with the tool's JSON result (`ok`, `operation`, `data`, `warnings`).
It equals the tool result except for `correlation_id`: a tool call gets a per-call `correlation_id`, a
resource read adds none (it is not a counted call, see Limits).
A resource read uses and fills the same bounded per-device cache as the tools and never refreshes
it, so a second read is served from the cache (`freshness.source` is `cache`). It takes the same
per-device lock and deadline.

## Registration

A resource follows its tool. `wled_list_devices`, `wled_get_effects` and `wled_get_palettes` are
all `core` and `read`, so every profile and group selection registers all three resources today; the
rule guards later moves of a tool. A resource whose tool is not registered is not listed, not
templated, and `resources/read` returns the same error as for a made-up URI before any I/O. Resources
are never a member of a group and the groups documentation lists none. When no resource is registered
the server advertises no `resources` capability at all.

## Errors

`resources/read` has no `isError`. A failed read (unknown controller, unreachable controller, invalid
device response and so on) is a JSON-RPC error with code `-32603`, the tool's error message and, in
`error.data`, the same structured envelope the tool returns, whose `error` member is identical to the
tool's. A controller that cannot be a configured ID (wrong characters or length) is the same
`UNKNOWN_DEVICE` error as for an unconfigured one. A URI outside the scheme, with a query or fragment,
with an unknown kind, or whose resource is not registered, gets code `-32002` and the fixed message
`Resource not found`; the URI is not echoed. An unexpected exception becomes `-32603` with a fixed
message and no detail.

## Limits

- Tool-call counters and the call log count tool calls only; resource reads are not extended with new
  machinery (DEC-028).
- Resources are read-only views of data the tools already serve; they add no device access.
- Size is that of the tool result; there is no extra cap.
- Measured only with in-memory servers and the installed console, not with a real MCP client; clients
  that ignore resources are unaffected and use the tools.
