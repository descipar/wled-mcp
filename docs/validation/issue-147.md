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

MCPHub forwarding check: **pending**. No runtime access was supplied for this run.
Neither forwarding of instructions nor availability of prompts through MCPHub is
claimed from the direct-client protocol checks. This remaining acceptance criterion
keeps issue #147 open until an authorized observation is recorded.
