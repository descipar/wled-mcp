# Handoff to the implementing agent

## Assignment to use later

> Implement the proposed first usable WLED MCP release in this private repository. Read AGENTS.md, README.md and docs/REQUIREMENTS.md, then follow the GitHub backlog linked from docs/IMPLEMENTATION-PLAN.md. Start with contract decisions and packaging. Implement and mock-test the server before requesting device information needed only for hardware validation. Keep runtime/hardware work within the user's actual authorization. Deliver a reviewable implementation with honest evidence and pending items.

This is a ready-to-use future prompt, not an instruction that implementation has already been commissioned in the original documentation chat.

For a later stage-2 assignment, also read [STAGE-2.md](STAGE-2.md), [MARKETPLACE.md](MARKETPLACE.md) and [tracker #15](https://github.com/descipar/wled-mcp/issues/15). Keep Launch requirements and optional product features distinct. Public artifacts/submission drafts must be concrete and reviewable before the final release decision; do not publish from a planning instruction.

## Checkout

```bash
git clone https://github.com/descipar/wled-mcp.git
cd wled-mcp
git status --short
git remote -v
```

Authenticate with the agent's existing authorized GitHub mechanism. Do not paste tokens into clone URLs, repository files or issue comments. The repository is private; inability to access it is an access issue, not a reason to make it public.

## First work session

Issue #3 bootstrap commands exist in [DEVELOPMENT.md](DEVELOPMENT.md).
Read [its decisions](decisions/issue-3.md) before extending configuration/tools.
Issue #4 adds validated inventory, `wled_list_devices`, a bounded HTTP client and
shared process resources. Read [inventory/client behavior](INVENTORY-CLIENT.md)
and [issue-4 decisions](decisions/issue-4.md). Continue with #5 read/catalog tools;
HTTP fails before listening pending #14. Internal mocked write/reconciliation
tests do not establish actual WLED domain-control or hardware acceptance.

1. Read the documents and current issue bodies/comments; check for changes since this handoff.
2. Confirm scope from the new user instruction. Distinguish implementation, installation, hub deployment and hardware writes.
3. Read the issue-2 [contract](TOOL-CONTRACT.md), [scoped decisions](decisions/issue-2.md) and [synthetic examples](../examples/contracts/README.md). Preserve existing omitted state, explicitly default new IDs, verify firmware representability and persistently verify saves. Recheck the pinned source profile against observed firmware; source review is not hardware acceptance. Supplied-state save and restore execution remain deferred Should work.
4. Bootstrap one package with `--transport stdio|streamable-http`, default listener-free stdio, pinned uvx launch, locked dependencies and meaningful mocks. Test real stdio and loopback Streamable HTTP clients. Implement the independent HTTP service in #14 using the same tool/domain graph and process-wide per-device locks.
5. Implement named inventory/client/reads, then typed controls, layouts and persistent presets following dependency order.
6. Keep the optional raw tool out of the default surface until its allowlist and non-bypass behavior are defined; defer Should work explicitly if necessary.
7. Prepare both HTTP-service/Docker and uvx/stdio deployment artifacts/instructions, then perform authorized read-only hub validation. Protect the HTTP endpoint independently of hub authorization. Record which mode was actually deployed; ask for missing device inputs only when needed.
8. Update issues with evidence, not just “done”; link PRs and note unrun physical checks.
9. After the human-authorized merge is verified, the coordinator delegates to
   `wled_completion` using the [completion handoff](agent-workflow/completion.template.md).
   It checks evidenced acceptance items and closes only fully satisfied current
   issue scope. Preserve pending hardware/release criteria. This requires an
   active/resumed session; if the session ends first, save the resumable handoff.

## Questions to resolve at the appropriate point

- Which controllers and meaningful aliases, URLs, firmware and LED capabilities should be included?
- Is there a suitable device/range and unused preset slot for physical validation?
- Does the actual container runtime already provide compatible Python/uv and the required persistent mounts?
- For HTTP deployment, which private service address/network, Host/Origin allowlist and runtime credential source should be used? Both HTTP and stdio are confirmed v1 scope; only deployment details remain open.
- Are CCT, 2D matrix, playlist editing or timers concrete needs? These are not inferred Must features.
- Is code reuse or eventual publication desired, and under what license? No license was selected in planning.

Do not block mocked implementation on access to the home network. Do not fabricate addresses, tests or device capabilities. Do not copy private context from unrelated DIY projects into this repository.

## Expected final delivery

- Working, versioned package with documented development and console commands.
- Requirements-to-test traceability, passing automated checks and relevant fixtures.
- Clear tool behavior for patch/replace, backups, persistence, concurrency and uncertain writes.
- Reproducible hub integration and rollback instructions with concrete paths chosen from observed runtime facts.
- Updated issue status, validation evidence and a concise German handoff to the user stating what works, what was tested and what remains unverified.
