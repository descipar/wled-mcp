# Issue #147 — agent guidance evidence

Requirements: AGENT-01/AGENT-02; M1. Mock/loopback checks only, no LAN or device writes.

`tests/test_agent_guidance.py` launches the real stdio console and a protected
loopback Streamable HTTP service. It checks identical initialization instructions,
`prompts/list` and `prompts/get`, rejection of unknown prompts/arguments, descriptions
in the served nested schemas, exclusive endpoints, descriptive destructive tools,
and scene/zone examples accepted by the existing parsers. The HTTP harness records
no tool execution or device request during those checks.

Validation on Python 3.13/macOS:

- `uv run --frozen pytest -q tests/test_agent_guidance.py tests/test_bootstrap.py tests/test_groups.py tests/test_scenes.py tests/test_zones.py --basetemp=.artifacts/pytest-147`: 244 passed.
- `uv run --frozen mypy`: passed (50 source files).
- Repository CI-equivalent ruff check/format, agent setup, lock/export consistency
  and private-identifier checks: passed.

The complete suite, distribution and container checks remain for CI.

Local stdio client check (2026-11-09): **done**. By owner decision
([ISSUE-147-DEC-001](../decisions/issue-147.md)) this replaces the MCPHub forwarding
observation. A real MCP client launched the console entry point of `main` at `08f38f0`
over stdio with a local configuration (the server was not asked to execute any tool and
no device request was needed for these calls). Results: `initialize` returned the served
instructions (870 characters, starting with reading `wled_get_state` first and the
patch-versus-replace distinction); `prompts/list` returned the single prompt
`change_lighting_safely`; `prompts/get` returned one message with the safe-change steps; the
served `wled_patch_segments` input schema carries field descriptions.

Not observed: whether MCPHub forwards the instructions and prompts. No hub update or
deployment was performed, the deployed hub service runs a release without #147, and
no forwarding result is claimed. This is a recorded limit, not a pass.
