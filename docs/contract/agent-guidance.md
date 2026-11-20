# Agent guidance — AGENT-01 and AGENT-02 (#147)

The shared MCP adapter serves the same static `instructions` in `initialize` over stdio and
Streamable HTTP: read-first workflow, smallest change, patch versus complete layout replacement,
exclusive `stop`/`stop_y`, preservation of omitted fields, device-specific effect/palette IDs, dry
run, verification, uncertain writes and explicit preset overwrite with a durable snapshot.

`prompts/list` advertises one prompt, `change_lighting_safely`, with no arguments. `prompts/get`
returns one user-role text message describing that workflow; it reads no devices or stored
definitions and executes no tools. An unknown prompt name or nonempty arguments return `-32602`.
Clients must expose instructions/prompts to their agent; the server cannot ensure forwarding.

The served `tools/list` input schemas describe segment/layout fields (including nested models) and
scene inputs. Free-form scene documents and zone `segments` have examples. A zone accepts exactly one
mutable-fields object without IDs, ranges or master state (the stored zone selects the targets):

```json
{"zone": "shelf", "segments": [{"colors": [[255, 96, 16]], "effect_name": "Solid"}], "dry_run": true}
```

The instructions also say when to use a room, group, zone or single device: a room (a group saved
with `kind=room`, at most one per controller) is where controllers are and `wled_apply_room` applies
a state or scene across it; a plain group is any other set of controllers; a zone is part of a
controller; `wled_set_state` is one controller ([rooms.md](rooms.md)). The prompt's first step names
the stored room as a target.

Destructive tool descriptions state the discarded or replaced state and recommend `dry_run=true`
when the replacement or deletion is unclear. Guidance adds no execution or confirmation mechanism:
authorization stays with the MCP host, and profiles, validation and write semantics still apply.

The stdio client check and the not-observed status of MCPHub forwarding
([ISSUE-147-DEC-001](../decisions/issue-147.md)) are in
[validation/issue-147.md](../validation/issue-147.md); transport tests do not prove a host forwards
the guidance.
