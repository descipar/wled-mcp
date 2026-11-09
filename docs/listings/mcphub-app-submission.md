# Hosted mcphub.app submission copy (draft)

Status: **draft**. Not submitted. Issue [#24](https://github.com/descipar/wled-mcp/issues/24),
requirement S2-MARKET-02, route "hosted mcphub.app directory" in
[MARKETPLACE.md](../MARKETPLACE.md).

The submission form of the hosted directory needs a sign-in, and its fields, review criteria
and linkage to a self-hosted MCPHub were not observed. The copy below is therefore a
neutral text block to adapt to the form, not a record of the form's fields. Submitting it is a
separate action that needs the owner's instruction after the package is on PyPI
([PUBLISHING.md](../PUBLISHING.md)); an acceptance by that directory would not mean that a
self-hosted MCPHub lists the server (these routes are independent).

Placeholders: `<version>` is the released version (the Git tag is `v<version>`). Fill it from
the PyPI project page at submission time; this file never carries a literal version.

## Name

WLED MCP (unofficial)

## One-line description

Unofficial MCP server for WLED LED controllers; not affiliated with the WLED project.

## Description

WLED MCP lets an AI agent read and control WLED LED controllers by name over MCP: power,
brightness, segments, effects, palettes, presets, device groups, scenes and named lighting
zones. It talks to each controller's JSON API on the user's own network, validates a complete
change before sending it and reads it back afterwards. Patching selected segments and
replacing the complete layout are separate tools; omitted fields mean "unchanged", never
"reset". Overwriting or deleting a preset stores a durable snapshot first.

It is self-hosted: there is no cloud service, account or public endpoint, and the user supplies
the list of their own controllers. This project is unofficial. It is not affiliated with,
endorsed by or supported by the WLED project, and it uses no WLED logo.

## Links and metadata

- Repository: https://github.com/descipar/wled-mcp
- Package: https://pypi.org/project/wled-mcp/ (version `<version>`)
- Licence: Apache-2.0
- Transports: stdio (started by the MCP host through `uvx`) and Streamable HTTP (a separate
  service the user deploys)
- Tool reference: [TOOL-CONTRACT.md](https://github.com/descipar/wled-mcp/blob/main/docs/TOOL-CONTRACT.md#tools-at-a-glance)
  lists every tool with its read-only, write or destructive hint
- Suggested keywords: wled, led, lighting, mcp

## Install (stdio)

Command `uvx` with these arguments, each one separate, and absolute paths of the user's own
files:

```text
--isolated --python 3.13 --from wled-mcp==<version> wled-mcp --transport stdio --config <absolute path to devices.toml> --data-dir <absolute path to an existing data directory>
```

The inventory (`devices.toml`) is created with `wled-mcp config init`; the README's
["Try it"](https://github.com/descipar/wled-mcp#try-it) section shows the three steps
(check the installation, create the inventory, register the server). No secret is required
for stdio.

## HTTP (self-hosted)

The HTTP service is not a hosted endpoint and is not listed as one: each user runs their own
instance next to their own controllers and connects to its `/mcp` address with a bearer
credential. Setup:
[quickstart for the Streamable HTTP service](https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md#quickstart-streamable-http-service).
The container image is not published; the quickstart builds it locally.

## Tested and limits

- Automated tests use mocks and synthetic loopback devices. Hardware testing so far covers
  one controller running WLED 16.0.1; other firmware versions are untested. Support starts at
  WLED 16.0.0 and is best effort, without a commitment.
- Early software: `0.x` versions can change between releases.
- WLED has no authentication for its light API; a controller behind HTTP authentication or a
  credentialed proxy is not supported. The HTTP service must not be exposed to the internet.
- Windows and macOS are experimental; Linux is the supported platform.

## Not claimed

No official status, endorsement or WLED affiliation; no hosted service; no claim that other
MCPHub users can already see this server; no fields of the submission form are asserted.
