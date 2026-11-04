# Agent instructions

## Project and communication

- This is the standalone `descipar/wled-mcp` repository. Inspect `git status`, remotes, and existing changes before editing. Do not initialize Git in the surrounding DIY directory.
- Discuss work with the user in German. Keep committed documentation, code identifiers, issue text, and PR descriptions in English unless asked otherwise.
- Keep documentation and issues impersonal: use neutral roles and synthetic examples. Do not include personal names, private hostnames or details of an individual installation unless explicitly requested. Actual repository/issue URLs remain valid project references.
- Start with README.md and docs/AGENT-HANDOFF.md. Use GitHub issues and requirement IDs for scope and progress.
- Stage 1 is tracked by #1; future product/public-release work is tracked separately by #15 and docs/STAGE-2.md. Prepare public-ready artifacts and listing drafts when commissioned, but do not infer a visibility change, license choice, package publication or external submission from the roadmap alone.
- The five additional usability features are stage 3, tracked by #26 and docs/STAGE-3.md. They do not block stage-2 publication; do not merge the stages' acceptance criteria implicitly.
- Define scope from WLED capabilities and this project's requirements. Do not make features conditional on what a separate home-automation integration already provides.
- The original assignment created specifications and a backlog only. A later implementation instruction authorizes code work; it does not implicitly authorize deployment to the home hub or physical lighting changes. Follow the actual later instruction and do not ask again for actions already authorized.

## Implementation discipline

- Requirements marked confirmed reflect the conversation. Proposed defaults may be refined with a recorded rationale; do not present them as user-confirmed decisions.
- Keep runtime configuration, backups, captures, logs, and build artifacts in this project or its designated deployment directory. Never commit secrets or real household inventory.
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
