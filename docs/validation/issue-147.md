# Issue #147 — agent guidance evidence

Requirements: AGENT-01/AGENT-02; M1. Mock/loopback checks only, no LAN or device writes.

`tests/test_agent_guidance.py` launches the real stdio console and a protected loopback Streamable HTTP
service and checks identical initialization instructions, `prompts/list` and `prompts/get`, rejection of
unknown prompts/arguments, descriptions in the served nested schemas, exclusive endpoints, descriptive
destructive tools, and scene/zone examples accepted by the existing parsers; no tool execution or device
request is recorded.

Validation (Python 3.13/macOS): five related test modules, 244 passed; mypy passed (50 source files);
ruff, agent setup, lock/export and private-identifier checks passed. Full suite, distribution and
container checks remain CI evidence.

Local stdio client check (2026-11-09): **done**. By owner decision
([ISSUE-147-DEC-001](../decisions/issue-147.md)) this replaces the MCPHub forwarding observation. A real
MCP client launched the console entry point of `main` at `08f38f0` over stdio with a local configuration
(no tool executed, no device request). `initialize` returned the served instructions (870 characters,
starting with reading `wled_get_state` first and the patch-versus-replace distinction); `prompts/list`
returned the single prompt `change_lighting_safely`; `prompts/get` returned one message with the
safe-change steps; the served `wled_patch_segments` schema carries field descriptions.

Not observed: whether MCPHub forwards the instructions and prompts. No hub update or deployment was
performed and the deployed hub runs a release without #147; no forwarding result is claimed. This is a
recorded limit, not a pass.
