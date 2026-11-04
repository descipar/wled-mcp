# Validation and acceptance plan

Current result: **not run — no implementation exists**. The following are future acceptance scenarios, not test results.

## Automated checks, without hardware

| ID | Scenario and expected evidence | Requirements |
| --- | --- | --- |
| T01 | Invalid/duplicate inventory, URL credentials, path traversal and arbitrary host inputs fail before HTTP; valid explicit ports work | DEV-01, OPS-03 |
| T02 | One offline probe does not hide other configured devices; list without probe performs no HTTP | DEV-02, MULTI-01 |
| T03 | Effect/palette IDs remain correct with gaps and unknown metadata; name ambiguity is explicit; optional metadata endpoint failure does not erase catalogs | READ-02–03 |
| T04 | Patch `speed=0`, `on=false`, `brightness=0` preserves omitted fields; updates explicit ID 2 without rewriting ID 0 or deleting others | CTRL-01, SEG-01 |
| T05 | Replacement starting with noncontiguous existing IDs deletes exactly old-minus-desired IDs; no fixed tail of dummy deletions; new/existing defaults match the finalized contract | SEG-02 |
| T06 | Bad ranges, excessive LEDs/segments, duplicated IDs, invalid RGBW, invalid effect IDs and malformed payloads reject the entire operation with zero POSTs | SEG-03 |
| T07 | Dry runs perform no POST, no backup writes and no slot reservation; plans clearly distinguish patch and replace | SEG-04 |
| T08 | HTTP success with mismatching readback is a verification failure; ignored writes and unsupported features are visible | SEG-04, MCP-02 |
| T09 | Timeout after a possible write returns unknown outcome; no POST retry; read retry/deadlines remain bounded | REL-01–02 |
| T10 | Two writes to one device cannot interleave with readback; different-device calls can progress; tests do not claim to serialize other WLED API clients | MULTI-01, REL-03 |
| T11 | Existing preset ID without overwrite fails; free allocation checks collisions; unknown fields and playlist type survive read/backup | PRE-01–02, PLAY-01 |
| T12 | Backup failure prevents overwrite/delete; atomic snapshot and retention never delete unrelated files; restore validates target and snapshot | PRE-04 |
| T13 | Delayed preset persistence is observed with a bounded poll; uncertain save/delete is not replayed | PRE-05, REL-02 |
| T14 | Real subprocess stdio handshake, tool listing and calls work with SDK client; stdout contains no diagnostics; error flags and structured/text fallback agree | MCP-01–02 |
| T15 | Mocked HTTP redirect, HTML response, malformed JSON, huge response, missing capabilities and connection reset return actionable bounded errors | READ-01, REL-01, OPS-03 |
| T16 | Build a wheel and start the installed console command in a clean environment using pinned dependencies; README command matches reality | OPS-02 |
| T17 | If optional raw tool is enabled, reject endpoints, hosts, persistence keys, layout deletion/replacement and unallowlisted fields that bypass typed rules | ADV-01 |

CI should run on supported Python versions and a Linux environment, with lint/type checking proportional to the implementation. Protocol tests must run the actual console entry point, catching the missing-main class of issue observed in a candidate project. Build/dependency errors must not be hidden by mocks.

## Read-only hardware checks

H01: Record selected device alias, firmware, LED count, RGB/RGBW/CCT and segment capabilities from real responses. Sanitize any committed fixture.

H02: Read state/catalogs/presets from the actual hub container execution context, then through MCPHub. Compare observed IDs/names and capability interpretation with the WLED UI. No discovery scan or state write is needed.

H03: Start/restart the server entry, record startup and idle memory, confirm logs/protocol separation, verify persistence paths. Hub/container recreation is a distinct operational check and must be recorded as pending if not performed.

## Opt-in physical write checks

Choose an explicitly authorized device and test ranges/slots first. Record the pre-test state and relevant persistent preset snapshots. A visually animated state is not necessarily restorable frame-for-frame; preserve its configuration and note limits. Do not edit existing household presets for convenience when an agreed unused slot works.

H04: Change power/brightness/color and one effect's speed/intensity; verify state and visible behavior. Restore original configuration where supported.

H05: Patch one selected segment, confirm unrelated segments remain unchanged; replace with an agreed small layout, verify stale IDs removed, restore original layout. Account for timers, other API clients, playlists or realtime inputs if verification is affected; never disable them silently.

H06: Save to an agreed unused persistent preset ID, activate, read back, test explicit overwrite with snapshot, then delete the test slot. Test explicit restoration of its saved contents if authorized. Confirm persistent data, not just the current live effect.

H07: Observe an offline/unreachable device using an already unavailable target or approved test method; do not unplug production devices or change networking merely to create a failure. Simulated transport tests can remain the evidence for otherwise disruptive scenarios.

## Evidence template

```text
Date / operator / source commit:
Package / Python / SDK / hub runtime:
Sanitized device and firmware / relevant capabilities:
Scenario IDs run:
Before state and snapshot references (local, no secrets):
Expected and observed results:
Restoration performed and verified:
Not run / reason / remaining risk:
```

## Release decision

All Must requirements need evidence. Mock implementation can be merged while hardware checks are pending if clearly labeled. “Production validated”, “all firmware supported”, “rollback tested” and “container-recreation persistent” require their own actual observations. Keep the integration issue open until its stated checks are met or explicitly revise the scope with a documented user decision.
