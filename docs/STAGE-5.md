# Stage 5 - public distribution and backlog

Planning baseline: 2026-11-08. Tracker: [#133](https://github.com/descipar/wled-mcp/issues/133).

Stage 5 holds the work that makes the project easy to install and find for people who are not
the maintainer, plus low-value backlog. It is worked on a trigger, not in sequence: the owner
wants to be listed in a marketplace or registry, outside interest appears, or the stage-2
features are verified on hardware and should be offered
([DEC-027](DECISIONS.md#dec-027--re-stage-the-open-work-by-value-per-effort)). Nothing here
publishes a package or image, submits a listing or changes repository settings; each of those
needs the owner's explicit instruction ([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)).

## Work packages

| Issue | Owns | Note |
| --- | --- | --- |
| [#22](https://github.com/descipar/wled-mcp/issues/22) | S2-DIST-01 to 03 | PyPI and multi-architecture image pipeline; the PyPI publish workflow is prepared ([PUBLISHING.md](PUBLISHING.md), ISSUE-22-DEC-001), publishing stays with the owner; image, SBOM/provenance and vulnerability review open |
| [#23](https://github.com/descipar/wled-mcp/issues/23) | remaining S2-PUBLIC-02 and S2-PUBLIC-03 | tool reference, recipes, troubleshooting, templates, release policy |
| [#24](https://github.com/descipar/wled-mcp/issues/24) | S2-MARKET-01 to 03 | MCPHub and MCP Registry listings; needs a published package or image |
| [#25](https://github.com/descipar/wled-mcp/issues/25) | S2-LAUNCH-01 and 02, H07, the live part of S2-COMPAT-03 | simulator and launch report; the live rollback after the first release that changes code |
| [#117](https://github.com/descipar/wled-mcp/issues/117) | none | backlog: bound the bundle import planning phase |

These are the stage-2 Launch requirements of [STAGE-2.md](STAGE-2.md) that were not met when stage 2
was closed out. They are not dropped and must not be described as delivered. Records that say
"moved to stage 2 (#25)" describe #25 as it was when they were written.
