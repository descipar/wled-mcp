# Live check of the second release (2026-11-08)

One owner-authorized live check of the second release on the same target class and single test
controller as the first deployment check ([#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06)).
Host names, addresses and paths are omitted. Not a broad hardware acceptance: one controller on WLED
16.0.1 (ESP32-C3, 133 LEDs, one segment), reads, master power and brightness, and segment effects.
Each write run was authorized separately (brightness with restoration, a visible power test, a brighter
step, a 60 s effect run with master brightness capped at 120, no flashing, no presets); none is standing
permission.

## Target and staging

- aarch64 single-board computer, Docker, MCPHub with the HTTP service in its own Compose project.
- Staging ([DEC-026](../DECISIONS.md#dec-026--stage-releases-on-the-target-machine)): clean clone of the
  release tag on the target, `uv sync --locked`, offline wheel build, `deploy/stage_release.py`,
  `sha256sum -c SHA256SUMS` all OK, directory made read-only. `check_distribution.py` was not run on the
  target (CI runs it for the tag).
- Source commit `ea3c58cfdf64e993670e8fdb0853633445f17e03`, tree clean; wheel SHA-256
  `5c6d394d8614194ef06fb04d8a277dce69f9b89ee91e8ec06789099e1076d4c1`. A staging run on a Windows
  checkout produced other hashes ([#131](https://github.com/descipar/wled-mcp/issues/131)); that
  directory was discarded.
- Hub configuration and Compose file backed up; the data directory backup needed elevated rights
  (container-owned files). Previous images and directories kept; no rollback was run.

## HTTP service (default transport)

| Check | Result |
| --- | --- |
| Update (`up -d --no-deps`) | recreated; `healthy` about 33 s after start |
| First hub call after the update | failed once ("data must NOT have additional properties"); succeeded about a minute later after the hub refreshed its tool list ([#130](https://github.com/descipar/wled-mcp/issues/130)) |
| Service status | second-release version, `streamable-http`, profile `full`, device `reachable` |
| Reads | device list with probe, state (tier `tested`), catalogs, presets, snapshots (the three of the first check), groups (empty) |
| Writes (master only) | brightness 47 to 60 and back (master off, verified by readback); power on at 47, 120, 47, off; 200 confirmed clearly visible by the owner, then 47 and off; every step `applied`/`verified` |
| Effect run | about 55 s: five calm phases (random effects and palettes), master brightness 71 to 105, no strobe or sparkle effects, no presets; 13 verified writes |
| Restoration | fade out, then effect 0, palette 11, speed and intensity 128, original colors, brightness 47, master off; readbacks equal the earlier state |
| Counters (read before the visible tests) | 10 calls, all ok, 7 read and 3 control |

Owner remark: went well; some effects were barely visible (pale palettes, low brightness).

## stdio (README route, temporary)

Hub entry via `uvx --isolated --python 3.13 --from git+...@<release tag>`; cold first start about 50 s.
Through the hub: device list with probe `reachable`, state equal to baseline, service status (`stdio`);
one write (brightness 47 to 60 and back, verified, not visible). Entry deleted at the owner's request,
no process left, HTTP entry untouched. The two transports were never used at the same time.

## Not run

- Scenes, groups, preset save/delete/restore/import/export and playlists on the controller; segment
  geometry; CCT and 2D.
- A rollback of the HTTP service; an unreachable controller (H07); settings PIN or OTA lock
  ([#128](https://github.com/descipar/wled-mcp/issues/128)); `check_distribution.py` on the target.

## Findings

- [#130](https://github.com/descipar/wled-mcp/issues/130): the hub rejected the new response right after
  the update (cached output schema).
- [#131](https://github.com/descipar/wled-mcp/issues/131): different bytes when staging on Windows.
- DEPLOYMENT.md said a Git source is never pinned to a tag while the README uses one; reconciled.
- Owner feedback on effect visibility: noted on [#31](https://github.com/descipar/wled-mcp/issues/31).
