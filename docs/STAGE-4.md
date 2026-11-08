# Stage 4 - verification with secured controllers

Planning baseline: 2026-11-08. Tracker: [#127](https://github.com/descipar/wled-mcp/issues/127).

**Order:** stage 4 is a plan only. Work on it starts after stage 3
([#26](https://github.com/descipar/wled-mcp/issues/26) and its children) is done, on the owner's
instruction ([DEC-025](DECISIONS.md#dec-025--stage-4-for-verification-with-secured-controllers)).

Stage 4 verifies the server against secured or restricted controllers and similar operating
conditions. It follows stage 1 (working server, [#1](https://github.com/descipar/wled-mcp/issues/1)),
stage 2 (public release readiness, [#15](https://github.com/descipar/wled-mcp/issues/15)) and
stage 3 (lighting experience, [#26](https://github.com/descipar/wled-mcp/issues/26)) and blocks
none of them. Creating it commissions no implementation, deployment or physical-device change
([DEC-025](DECISIONS.md#dec-025--stage-4-for-verification-with-secured-controllers)).

## Why

The official WLED documentation says that anyone with a controller's IP and port can control
the lights ([OTA lock](https://kno.wled.ge/advanced/ota-lock/)), that the settings PIN asks for a PIN
before a settings page opens, and that the OTA lock protects firmware updates
([settings](https://kno.wled.ge/features/settings/)). It does not say whether a lock affects
the JSON API or presets. This server sends no device credentials and rejects credentials in a
device URL. Its behavior against a PIN-locked or OTA-locked controller is therefore untested.

## Work packages

| ID | Package | Issue |
| --- | --- | --- |
| S4-SEC-01 | Behavior with the settings PIN and the OTA lock enabled: read-only probes first, then a minimal write set after a separate authorization, recording whether a lock changes any behavior. The result is written to `docs/validation/` and to the README and compatibility limits. | [#128](https://github.com/descipar/wled-mcp/issues/128) |

## Boundaries

- Single shared controller; every physical run needs its own explicit owner authorization and
  starts read-only. No routine smoke-test writes.
- The server never changes a controller's PIN, passphrase or other security setting and does
  not bypass a lock. A refusal by the controller is reported as such and not retried.
- No PIN, passphrase or credential value appears in any committed file or issue.
- HTTP authentication or a credentialed reverse proxy in front of a controller is a separate
  decision; credentials in a device URL stay rejected until then.
