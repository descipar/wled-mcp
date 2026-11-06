# Agent instructions

## Project and communication

- This is the standalone `descipar/wled-mcp` repository. Inspect `git status`, remotes, and existing changes before editing. Do not initialize Git in a parent directory.
- Use the maintainer's language in discussion. Keep committed documentation, code identifiers, issue text, and PR descriptions in English unless asked otherwise.
- Keep documentation and issues impersonal: use neutral roles and synthetic examples. Do not include personal names, private hostnames or details of an individual installation unless explicitly requested. Actual repository/issue URLs remain valid project references.
- Start with README.md and docs/AGENT-HANDOFF.md. Use GitHub issues and requirement IDs for scope and progress.
- Read docs/DECISIONS.md and applicable docs/decisions/issue-<number>.md entries at startup/resume and before repeated questions. The coordinator records clear human answers with source/scope/status, propagates them to the other roles and updates affected requirements/tests. Reuse applicable decisions; never generalize an issue answer into a global rule or reuse an expired operation approval. See the log's recording rules.
- Issue implementation uses the defined agent workflow by default in Codex and Claude Code. A request such as "Implement issue #2 and follow the defined workflow" is sufficient: read docs/AGENT-WORKFLOW.md and the shared coordinator instructions in agents/coordinator.md, then coordinate requirements, implementation and independent review with the other project roles. Derive stage/dependencies and use the issue's scope; do not require the user to repeat roles, paths, review steps or routine implementation authorization. Human merge approval remains part of the defined workflow. Opening the repository or reading a quoted example does not start implementation.
- Maintain roles only in agents/*.md; regenerate complete native client definitions with `python scripts/sync_agents.py` and verify with `--check`. Do not edit generated .codex/agents or .claude/agents copies independently. Models, providers, MCP and permissions remain client/session configuration.
- After verified human-authorized merge, the coordinator delegates to `wled_completion` to reconcile evidenced acceptance checkboxes and close only fully satisfied current issue scope. A merge alone does not prove completion. Follow the workflow's issue-body preservation/readback rules; no extra routine approval or background watcher is implied.
- Stage 1 is tracked by #1; future product/public-release work is tracked separately by #15 and docs/STAGE-2.md. Prepare public-ready artifacts and listing drafts when commissioned, but do not infer a visibility change, license choice, package publication or external submission from the roadmap alone.
- The five additional usability features are stage 3, tracked by #26 and docs/STAGE-3.md. They do not block stage-2 publication; do not merge the stages' acceptance criteria implicitly.
- Define scope from WLED capabilities and this project's requirements. Do not make features conditional on what a separate home-automation integration already provides.
- The original assignment created specifications and a backlog only. A later implementation instruction authorizes code work; it does not implicitly authorize deployment to an MCP hub or physical lighting changes. Follow the actual later instruction and do not ask again for actions already authorized.

## Implementation discipline

- Requirements marked confirmed reflect a recorded owner decision. Proposed defaults may be refined with a recorded rationale; do not present them as user-confirmed decisions.
- Keep runtime configuration, backups, captures, logs, and build artifacts in this project or its designated deployment directory. Never commit secrets or a real device inventory.
- Implement the documented distinction between patching selected segments and replacing the complete layout. Omitted fields are not reset requests.
- Validate a complete request before sending a write. Treat a timed-out write as possibly applied; do not retry it blindly.
- No silent preset overwrite, delete, arbitrary endpoint forwarding, device discovery scan, or configuration migration. Explicit requested operations can run without adding an interactive approval mechanism inside the plugin.
- Support both confirmed v1 transports: an independent Streamable HTTP service and client-managed stdio via uvx, sharing the same domain operations and tool contract.
- User authorization belongs to the MCP host/client. The independent HTTP endpoint also needs its own configured access protection and Host/Origin checks; hub authentication does not protect direct service access. Tool annotations are useful hints, not an execution barrier.
- Keep stdout reserved for stdio MCP. Diagnostics go to stderr and must omit secrets.
- Do not install a candidate upstream server as part of implementing this project. Upstream code reuse requires license review and preserved notices.

## Evidence and delivery

- Add meaningful tests for state merging, validation, failed/uncertain writes, preset handling, and protocol behavior. Avoid tests that merely repeat implementation constants.
- Tests must use mocks by default and must not contact LAN devices from ordinary CI.
- Never run a physical write as a routine smoke test. Use read-only probes first; run authorized hardware checks on explicitly selected devices and preserve a restorable state where supported.
- Update requirements, tool contract, issues, and validation status when decisions change. Never mark hardware acceptance or an issue complete from mocks alone when hardware evidence is required.
- Use a feature branch and a reviewable PR for later implementation unless the user specifies another workflow. Include actual validation and unresolved limits.
- No license selection, public publishing, registry release, or hub deployment is part of the current documentation assignment.
