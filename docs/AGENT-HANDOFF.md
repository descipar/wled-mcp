# Handoff to the implementing agent

## Assignment to use later

> Implement the proposed first usable WLED MCP release in this private repository. Read AGENTS.md, README.md and docs/REQUIREMENTS.md, then follow the GitHub backlog linked from docs/IMPLEMENTATION-PLAN.md. Start with contract decisions and packaging. Implement and mock-test the server before requesting device information needed only for hardware validation. Keep runtime/hardware work within the user's actual authorization. Deliver a reviewable implementation with honest evidence and pending items.

This is a ready-to-use future prompt, not an instruction that implementation has already been commissioned in the original documentation chat.

## Checkout

```bash
git clone https://github.com/descipar/wled-mcp.git
cd wled-mcp
git status --short
git remote -v
```

Authenticate with the agent's existing authorized GitHub mechanism. Do not paste tokens into clone URLs, repository files or issue comments. The repository is private; inability to access it is an access issue, not a reason to make it public.

## First work session

1. Read the documents and current issue bodies/comments; check for changes since this handoff.
2. Confirm scope from the new user instruction. Distinguish implementation, installation, hub deployment and hardware writes.
3. Finalize patch-versus-replacement missing-field behavior and preset-save semantics in the contract issue. Read official WLED API documentation for the observed firmware; do not infer behavior solely from the reviewed candidate projects.
4. Bootstrap a package with a working console command, locked dependencies, meaningful mocks and an actual stdio integration test.
5. Implement named inventory/client/reads, then typed controls, layouts and persistent presets following dependency order.
6. Keep the optional raw tool out of the default surface until its allowlist and non-bypass behavior are defined; defer Should work explicitly if necessary.
7. Prepare deployment artifacts and instructions, then perform authorized read-only hub validation. Ask for missing device inputs only when they are actually needed.
8. Update issues with evidence, not just “done”; link PRs and note unrun physical checks.

## Questions to resolve at the appropriate point

- Which controllers and meaningful aliases, URLs, firmware and LED capabilities should be included?
- Is there a suitable device/range and unused preset slot for physical validation?
- Does the actual container runtime already provide compatible Python/uv and the required persistent mounts?
- Are CCT, 2D matrix, playlist editing or timers concrete needs? These are not inferred Must features.
- Is code reuse or eventual publication desired, and under what license? No license was selected in planning.

Do not block mocked implementation on access to the home network. Do not fabricate addresses, tests or device capabilities. Do not copy private context from unrelated DIY projects into this repository.

## Expected final delivery

- Working, versioned package with documented development and console commands.
- Requirements-to-test traceability, passing automated checks and relevant fixtures.
- Clear tool behavior for patch/replace, backups, persistence, concurrency and uncertain writes.
- Reproducible hub integration and rollback instructions with concrete paths chosen from observed runtime facts.
- Updated issue status, validation evidence and a concise German handoff to Kai stating what works, what was tested and what remains unverified.
