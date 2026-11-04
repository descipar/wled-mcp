# Shared workflow roles

Edit the five role sources here, then run from the repository root:

```bash
python scripts/sync_agents.py
python scripts/sync_agents.py --check
python scripts/check_agent_setup.py
python -m unittest discover -s tests -p "test_sync_agents.py"
```

Python 3.11+ and its standard library suffice. Each `.md` source has `+++`-delimited
TOML frontmatter with only `name` and `description`, followed immediately by the
complete role prompt. Both LF and CRLF sources are accepted and normalized to LF.
Identity must be `wled_<filename stem>` for these five source files:

| Source | Responsibility |
| --- | --- |
| [coordinator.md](coordinator.md) | Main session coordination and human decisions |
| [requirements.md](requirements.md) | Bounded requirements and acceptance packet |
| [implementer.md](implementer.md) | Scoped implementation and validation |
| [reviewer.md](reviewer.md) | Independent review at the exact candidate |
| [completion.md](completion.md) | Evidenced issue completion after verified merge |

The synchronizer produces complete native definitions in `.codex/agents/` and
`.claude/agents/`. Generated markers point back here; do not maintain adapters
separately. Native clients need no custom import mechanism to obtain role prompts.
Codex receives TOML strings; Claude receives YAML frontmatter using JSON-quoted
scalar metadata and the full Markdown prompt body. No model, permission, provider,
credential, tool or MCP override is generated. `.gitattributes` keeps source and
adapter checkouts at LF on Windows so byte-based drift checks remain deterministic.

`--check` reports missing/stale managed adapters with a nonzero exit status and
writes nothing. All five sources, rendered outputs and output paths are validated
before any update. Unknown Markdown source files are rejected (except this README);
other source files and unrelated adapter files are preserved. Only the ten named
adapter paths are managed and may be overwritten to repair drift. The setup checker
also rejects unexpected Codex roles; the synchronizer never deletes them.
Redirected source/output paths are rejected. Each file replacement is atomic,
but the whole batch is not transactional: a write failure can leave earlier files
updated. Fix the reported error and rerun sync/check; success is never inferred
from a partial batch. No model or network call is performed by these tools.

See [the workflow](../docs/AGENT-WORKFLOW.md) for client loading, explicit fallback,
acceptance rules and the distinction between static fidelity and a live agent run.
