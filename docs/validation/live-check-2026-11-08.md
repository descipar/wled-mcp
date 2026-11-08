# Live check of the second release (2026-11-08)

One short, owner-authorized live check of the second release on the same target class and the
same single test controller as the first deployment check ([#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06)).
Host names, addresses, paths, user names and the controller's name are omitted. This is not a
broad hardware acceptance: it covers one controller on WLED 16.0.1 (ESP32-C3, 133 LEDs, one
segment), reads, master power and brightness, and segment effect changes.

Authorization: the owner approved the host inspection and the installation, named the same test
controller, limited the first writes to brightness with restoration, then approved a visible
power-and-brightness test, a brighter step, and a 60-second effect run with a master brightness
cap of 120, no flashing and no presets. Each run was authorized separately; none is standing
permission.

## Target and staging

- Target class: aarch64 single-board computer, Docker, MCPHub with the HTTP service in its own
  Compose project. The service ran an earlier build of the first release before the update.
- Staging ([DEC-026](../DECISIONS.md#dec-026--stage-releases-on-the-target-machine)): clean clone of
  the release tag on the target, `uv sync --locked`, `uv build --offline --wheel
  --no-build-isolation`, `deploy/stage_release.py` into the directory the hub mounts, then
  `sha256sum -c SHA256SUMS` (all four files OK) and the directory made read-only. The documented
  `check_distribution.py` step was not run on the target; CI runs it for the tag.
- Source commit `ea3c58cfdf64e993670e8fdb0853633445f17e03`, tree clean. Wheel SHA-256
  `5c6d394d8614194ef06fb04d8a277dce69f9b89ee91e8ec06789099e1076d4c1`, constraints SHA-256
  `53fc7b43a799ac376b4210cbfbdb21a60bf8368c91142da715ec702f7217d8ee` (the value recorded for the
  first release). A staging run on a Windows checkout produced other hashes for the wheel and
  three text files ([#131](https://github.com/descipar/wled-mcp/issues/131)); that directory was
  discarded and not copied.
- Backups before any change: the hub configuration and the Compose file. The data directory
  backup (inventory and three snapshots from the first deployment check) first failed because
  the container user owns the files, and was repeated with elevated rights (mode 0600).
- Previous images and release directories were kept as the rollback source. No rollback was run.

## HTTP service (the default transport)

| Check | Result |
| --- | --- |
| Image build on the target | image built from the staged directory |
| Update (`up -d --no-deps` of the service only) | recreated; `healthy` about 33 s after the start |
| First hub call after the update | failed once: "data must NOT have additional properties"; succeeded about one minute later after the hub refreshed its tool list ([#130](https://github.com/descipar/wled-mcp/issues/130)) |
| Service status | version of the second release, transport `streamable-http`, profile `full`, device `reachable` |
| Reads | device list with probe, state (firmware tier `tested`), effect and palette catalogs, preset list, snapshot list (the three snapshots of the first deployment check were read), group list (empty) |
| Writes (master only) | brightness 47 to 60 and back with the master off (no visible change, verified by readback); power on at 47, 120, 47, power off; then 200 with the owner confirming it was clearly visible, then 47 and off; every step `applied` and `verified` |
| Effect run | about 55 s lit: five calm phases chosen at random (Colorwaves, Color Clouds, Blends, Noise 3, Sine with Light Pink, Candy, Beach, Cyane, Pink Candy), master brightness 71 to 105, no strobe, blink or sparkle effects, no presets; 13 verified writes; cross-fades only for brightness, effect changes are immediate |
| Restoration | fade out, then effect 0, palette 11, speed and intensity 128 and the original colors, brightness 47, master off; the readbacks equal the state before the check |
| Service counters | read once after the first reads and the 47-60-47 test, before the visible tests and the effect run: 10 calls, all ok, 7 read and 3 control |

The owner's remarks: the run went well; some effects were barely visible (pale palettes at low
brightness, soft effects).

## stdio (README route, temporary)

| Check | Result |
| --- | --- |
| Hub entry | `uvx --isolated --python 3.13 --from git+https://github.com/descipar/wled-mcp@<release tag> wled-mcp --transport stdio ...` with the persistent uv cache; the hub container provides `git` and `uvx` |
| Cold first start | server process up in about 50 s (clone, build, install) |
| Through the hub | device list with probe `reachable`, state equal to the baseline, service status (transport `stdio`) |
| Write | brightness 47 to 60 and back with the master off, verified by readback (not visible) |
| Removal (owner request) | hub entry deleted through the hub API, no wled-mcp process left, the HTTP entry untouched |

The stdio entry and the HTTP service were never used at the same time.

## Not run

- Scenes, groups, preset save, delete, restore, import, export and playlists on the controller;
  segment geometry changes; CCT and 2D.
- A rollback of the HTTP service; a live check with an unreachable controller (H07); behavior
  with a settings PIN or OTA lock ([#128](https://github.com/descipar/wled-mcp/issues/128)).
- The documented `check_distribution.py` step on the target.

## Findings

- [#130](https://github.com/descipar/wled-mcp/issues/130): the hub rejected the new response
  right after the update (cached output schema).
- [#131](https://github.com/descipar/wled-mcp/issues/131): different bytes when staging on a
  Windows checkout.
- docs/DEPLOYMENT.md said a Git source is never pinned to a tag while the README uses one; the
  wording was reconciled in this change (tag to try, commit or release directory to deploy).
- A local maintenance script from the first deployment check had the first version number in
  the wheel file name and would have refused the new directory; a one-off variant without a
  fixed version was used and removed.
- Owner feedback on visibility of effects: noted on
  [#31](https://github.com/descipar/wled-mcp/issues/31) for the curated effect properties.
