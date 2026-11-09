# Roadmap

Open and new work is organised by GitHub milestones ([DEC-029](DECISIONS.md#dec-029--milestones-instead-of-stages)).
Every open or new issue has exactly one milestone (Backlog counts) and no `Stage N: ` title prefix or
`stage:N` label. Closed issues, requirement IDs and the stage documents ([STAGE-2.md](STAGE-2.md),
[STAGE-3.md](STAGE-3.md), [STAGE-5.md](STAGE-5.md)) keep their stage history; the requirement tables
there remain the source for requirement IDs. The goals and exit criteria below mirror the milestone
descriptions on GitHub; the milestone is authoritative if they differ.

Order: M1, M2, M3, M4, M5, M6, then Backlog. Timers (W-CFG-04) stay excluded.
Merge approval: milestones M1 and M2 have a bounded standing approval (DEC-029 item 4, DEC-022 item 4);
issues that write to devices (#149, #27, #28) keep per-PR approval. Nothing is published, submitted or
announced without the owner's explicit instruction ([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)).

| Milestone | Goal | Exit criterion | Issues |
| --- | --- | --- | --- |
| M1: Agent guidance | An agent chooses the right tool, fields, effects and palettes without trial and error. | Guidance (A), effect metadata parsing (B) and effect/palette names in segment tools (C) merged; W-CAT-02 supported; one read-only live fxdata check on the test controller. | [#147](https://github.com/descipar/wled-mcp/issues/147), [#148](https://github.com/descipar/wled-mcp/issues/148), [#149](https://github.com/descipar/wled-mcp/issues/149) |
| M2: Observe and explain | An agent can see what the LEDs actually show and why a change did not take effect. | The live colour snapshot and #30 merged with mocked tests and one authorized read-only live run; no corrective writes. | [#150](https://github.com/descipar/wled-mcp/issues/150), [#30](https://github.com/descipar/wled-mcp/issues/30) |
| M3: Layout and zones | Users address and inspect physical regions instead of segment IDs. | #29 and #27 merged with S3-T01 and S3-T03 evidence. | [#29](https://github.com/descipar/wled-mcp/issues/29), [#27](https://github.com/descipar/wled-mcp/issues/27) |
| M4: Temporary signals | A bounded signal restores prior state safely or reports uncertainty. | #28 merged with S3-T02 evidence. | [#28](https://github.com/descipar/wled-mcp/issues/28) |
| M5: Secured controllers | Behavior with settings-PIN-locked and OTA-locked controllers is verified. | Authorized hardware evidence recorded (#128). | [#128](https://github.com/descipar/wled-mcp/issues/128) |
| M6: Public distribution | People outside the project can install the server and find it listed. | The stage-2 Launch requirements owned by #22 to #25 have evidence or are explicitly dropped by the owner; nothing is published, submitted or announced without the owner's explicit instruction. | [#22](https://github.com/descipar/wled-mcp/issues/22), [#23](https://github.com/descipar/wled-mcp/issues/23), [#24](https://github.com/descipar/wled-mcp/issues/24), [#25](https://github.com/descipar/wled-mcp/issues/25), [#151](https://github.com/descipar/wled-mcp/issues/151) |
| Backlog | Small maintenance work picked when it fits. | None; reviewed when a milestone closes. | [#138](https://github.com/descipar/wled-mcp/issues/138), [#117](https://github.com/descipar/wled-mcp/issues/117), [#152](https://github.com/descipar/wled-mcp/issues/152) |

The superseded stage trackers (#26, #127, #133) are closed; the acceptance line of the stage-5 tracker
is carried by the M6 exit criterion.
