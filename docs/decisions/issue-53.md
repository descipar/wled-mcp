# Issue #53 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-53-DEC-001 — Precise socket guard for the listener-free stdio test

- ID: ISSUE-53-DEC-001
- Status: active for issue #53 only.
- Authority: delegated decision; the owner delegated #52/#53 to the coordinator ("decide as much as
  possible yourself", 2026-11-05, no permalink). Based on Windows 11 / CPython 3.13.2 diagnostics:
  the only socket events during a default stdio start are a loopback bind to port 0 and the matching
  connect by `socket._fallback_socketpair` (asyncio self-pipe); none come from `wled_mcp` or the SDK.
- Scope: `tests/test_http_cli.py` stdio no-listener check. No product change, no skip or `xfail`.
- Decision: fix the test, not the product. During a default stdio run only operations whose direct
  caller is `socket._fallback_socketpair` are allowed: a loopback bind to port 0, that function's own
  `listen()`, and a loopback connect. Every other bind, listen, connect, sendto, sendmsg or
  getaddrinfo is a violation. `listen()` is recorded by wrapping `socket.socket.listen` in the probe
  subprocess (no audit event exists). Negative controls prove the guard catches a real listener, a
  wildcard bind, an unbound `listen()`, an asyncio server, a foreign loopback connect and a UDP send,
  without leaving an externally reachable listener open.
- Conditions: CPython internals may change in other versions; supported-version CI must stay green.
- Affected: MCP-03/OPS-05 (C14-08/09), tests/test_http_cli.py. Supersedes: none.
