# Issue #53 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-53-DEC-001 — Precise socket guard for the listener-free stdio test

- ID: ISSUE-53-DEC-001
- Recorded date: 2026-11-05
- Status: active for issue #53 only.
- Authority: delegated decision. The human delegated the #52/#53 decisions to the
  coordinator ("decide as much as possible yourself", 2026-11-05, no permalink). The
  content was decided by the coordinator, not dictated by the human.
- Source: requirements packet for #53 with local Windows 11 / CPython 3.13.2 diagnostics:
  the only socket events during a default stdio start are the bind to 127.0.0.1:0 and the
  matching loopback connect made by `socket._fallback_socketpair` for the asyncio event
  loop's self-pipe; none originate in `wled_mcp` or the MCP SDK.
- Scope: `tests/test_http_cli.py` stdio no-listener check. No product change, no platform
  skip or `xfail`.
- Decision: fix the test, not the product. During a default stdio run the test allows
  only operations whose direct caller is `socket._fallback_socketpair`: a bind to a
  loopback address on port 0, that function's own `listen()`, and a connect to a loopback
  address. Every other bind, listen, connect, sendto, sendmsg or getaddrinfo is a
  violation. `listen()` is recorded by wrapping `socket.socket.listen` in the probe
  subprocess because CPython emits no `socket.listen` audit event. Negative controls
  prove the guard still catches a real listener, a wildcard bind, an unbound `listen()`,
  an asyncio server, a foreign loopback connect and a UDP send; they must not leave an
  externally reachable listener open.
- Applicability / conditions: CPython stdlib internals (`_fallback_socketpair`) may change
  in other Python versions; supported-version CI must keep the test green.
- Rationale: product-side avoidance is impossible (every asyncio loop on Windows creates
  the self-pipe); a platform skip would hide the Windows result, and the previous filter
  could not see `listen()` at all.
- Affected: MCP-03/OPS-05 listener-free stdio evidence (C14-08/09), docs/VALIDATION.md,
  tests/test_http_cli.py.
- Supersedes: none.
- Propagated to: `.agent-runs/issue-53/packet.md`, implementer and reviewer handoffs.
