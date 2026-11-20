# Issue #14 decisions

Recorded 2026-11-05. Read with [DECISIONS.md](../DECISIONS.md). Only ISSUE-14-DEC-001
carries human authority; ISSUE-14-DEC-002 to -005 are agent technical designs refining the
documented contract, vetoable at review.

## ISSUE-14-DEC-001 — Scoped implementation authority

- Status: active for the #14 candidate; merge approval remains separate.
- Authority/source: human request to implement #14 with the defined workflow (DEC-001),
  coordinator session, 2026-11-05.
- Scope: implementation, tests, documentation, independent review and a PR. No merge,
  deployment, device or LAN action, publication, license selection or image/registry release.
- Supersession: none. Ends ISSUE-3-DEC-003's "HTTP fails before listening until #14" for
  this candidate only.

## ISSUE-14-DEC-002 — Access pipeline

- Status: active agent technical design, pending review/human merge.
- Authority/source: agent design checked against SDK 2.3.0, starlette 1.10.0, uvicorn 0.54.0;
  contract [TOOL-CONTRACT.md](../TOOL-CONTRACT.md#transport-access-and-lifecycle).
- Decision: an own pure-ASGI guard is the outermost layer and answers from headers only, in
  order: Host (exact allowlist) 403; Origin (exact allowlist when present) 403; bearer 401
  with `WWW-Authenticate: Bearer`; path other than `/mcp` 404; method other than POST 405;
  then the SDK stateless JSON app with a 256 KiB body limit. The SDK's own Host/Origin
  validation stays as defense in depth but the guard owns the status codes.
  `X-Forwarded-*` is never trusted; rejections log one fixed-class line, never header values.
- Affected: MCP-03, T18/T20.

## ISSUE-14-DEC-003 — Credential and configuration rules

- Status: active agent technical design, pending review/human merge.
- Scope: HTTP startup configuration only; stdio unaffected.
- Decision: exactly one bearer source (`WLED_MCP_HTTP_TOKEN` or `--http-token-file`); 32 to
  512 printable ASCII characters; a file is absolute, regular, at most 1 KiB, read once
  (rotation is a restart). Constant-time comparison over SHA-256 digests; single
  `Authorization: Bearer` header. No lockout or rate limiting in v1. Path fixed at `/mcp`.
  Defaults 127.0.0.1:8000 with allowed hosts `127.0.0.1:8000` and `localhost:8000`; any other
  host or port needs an explicit `--allowed-host`, which replaces the defaults (exact
  `host[:port]` or `scheme://host[:port]`, no wildcards, at most 16 entries). HTTP-only
  options with stdio, option abbreviations and a token CLI value fail with exit 2.
- Affected: MCP-03, OPS-03, T20.

## ISSUE-14-DEC-004 — Lifecycle

- Status: active agent technical design, pending review/human merge.
- Scope: HTTP process lifecycle and disconnect handling.
- Decision: stateless JSON, one worker, no sessions or server streams; a stale
  `Mcp-Session-Id` is ignored and DELETE is 405. One process-owned resource graph, closed
  once after the listener drained. The service owns SIGINT/SIGTERM (SIGBREAK on Windows) so
  a graceful stop exits 0; a second SIGINT forces exit and leaves interrupted writes
  uncertain. Drain timeout is the operation timeout rounded up plus 2 s (maximum 122 s). No
  unauthenticated health route; liveness is a TCP connect or authenticated `ping`. A
  dispatched handler keeps running on client disconnect (observed), so no extra shield.
- Deviation from the packet: resources close after `serve()` returns, not in the ASGI lifespan.
- Affected: MCP-04, REL-02, OPS-05, T21.

## ISSUE-14-DEC-005 — Evidence scope

- Status: active; limits what this candidate may claim.
- Authority/source: ISSUE-4-DEC-005 (actual HTTP T19 belongs to #14).
- Decision: the HTTP evidence is mock and loopback software evidence for T18-T21, not
  deployment, hub integration, resource measurement or hardware evidence (#10/#11, H02/H03);
  resource measurements stay pending; Windows signal delivery is a documented skip.
