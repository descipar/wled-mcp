# Stage 5 - public distribution and backlog

Planning baseline: 2026-11-08. Tracker: [#133](https://github.com/descipar/wled-mcp/issues/133).

Work order and grouping of these packages now follow the milestones in [ROADMAP.md](ROADMAP.md)
([DEC-029](DECISIONS.md#dec-029--milestones-instead-of-stages)); the packages and requirement
ownership below remain valid. Nothing here publishes a package or image, submits a listing or
changes repository settings; each of those needs the owner's explicit instruction
([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)).

## Work packages

| Issue | Owns | Note |
| --- | --- | --- |
| [#22](https://github.com/descipar/wled-mcp/issues/22) | S2-DIST-01 to 03 | PyPI and multi-architecture image pipeline; the PyPI publish workflow is prepared ([PUBLISHING.md](PUBLISHING.md), ISSUE-22-DEC-001), publishing stays with the owner; image, SBOM/provenance and vulnerability review open |
| [#23](https://github.com/descipar/wled-mcp/issues/23) | remaining S2-PUBLIC-02 and S2-PUBLIC-03 | tool reference, recipes, troubleshooting, templates, release policy |
| [#24](https://github.com/descipar/wled-mcp/issues/24) | S2-MARKET-01 to 03 | MCPHub and MCP Registry listings; the package prerequisite is met (PyPI, live since 0.1.2); the registry entry is published (2026-11-09); the MCPM and hosted-directory routes are not planned; the fresh-install test is open ([MARKETPLACE.md](MARKETPLACE.md#status-per-route)) |
| [#25](https://github.com/descipar/wled-mcp/issues/25) | S2-LAUNCH-01 and 02, H07, the live part of S2-COMPAT-03 | launch report; the live rollback after the first release that changes code; the simulator was dropped by the owner ([ISSUE-25-DEC-001](decisions/issue-25.md)) |
| [#151](https://github.com/descipar/wled-mcp/issues/151) | DIST-04 | Claude Desktop MCPB bundle built with every release by its own workflow job and attached to the GitHub release after the PyPI upload, untested and without warranty (ISSUE-151-DEC-001; [contract](contract/mcpb-bundle.md)); owner-published release needed for the first run |
| [#117](https://github.com/descipar/wled-mcp/issues/117) | none | backlog: bound the bundle import planning phase |

These are the stage-2 Launch requirements of [STAGE-2.md](STAGE-2.md) that were not met when stage 2
was closed out. They are not dropped and must not be described as delivered. Records that say
"moved to stage 2 (#25)" describe #25 as it was when they were written.
