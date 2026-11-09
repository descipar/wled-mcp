# Agent guidance — AGENT-01 and AGENT-02 (#147)

The shared MCP adapter serves the same static `instructions` in `initialize` over
stdio and Streamable HTTP. They explain the read-first workflow, smallest change,
patch versus complete layout replacement, exclusive `stop`/`stop_y`, preservation
of omitted fields, device-specific effect/palette IDs, dry run, verification,
uncertain writes and explicit preset overwrite with a durable snapshot.

`prompts/list` advertises one prompt, `change_lighting_safely`, with no arguments.
`prompts/get` returns one user-role text message describing that workflow. It reads
no devices or stored definitions and executes no tools. An unknown prompt name or
nonempty arguments return MCP invalid parameters (`-32602`). Both transports use
exactly the same handlers and content. Clients must expose instructions/prompts
to their agent for this guidance to be useful; the server cannot ensure forwarding.

The served `tools/list` input schemas describe segment/layout fields, including
nested models, and scene inputs. Free-form scene documents and zone `segments`
have examples. A zone accepts exactly one mutable-fields object without IDs,
ranges or master state: the stored zone selects the physical targets. For example:

```json
{"zone": "shelf", "segments": [{"colors": [[255, 96, 16]], "effect_name": "Solid"}], "dry_run": true}
```

Destructive tool descriptions state the discarded or replaced state and recommend
`dry_run=true` when the requested replacement or deletion is unclear. Guidance adds
no execution or confirmation mechanism: authorization remains with the MCP host,
and existing profiles, validation and write semantics still apply.

Actual MCPHub forwarding is recorded separately in
[validation/issue-147.md](../validation/issue-147.md); transport tests do not prove
that a particular host forwards the guidance.
