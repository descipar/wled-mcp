# Compatibility and support matrix

What this server is tested on and how it treats WLED firmware versions. Introduced by
[#21](https://github.com/descipar/wled-mcp/issues/21) (S2-COMPAT-02); decisions DEC-020
(support and version policy), DEC-013 (no support commitment) and ISSUE-21-DEC-002
(technical defaults, [decision log](../decisions/issue-21.md)). Version and
schema-evolution rules are in [versioning.md](versioning.md).

"Supported" means "covered by the checks listed here". It is not a support commitment:
there is none, responses are best effort and there is no security support (DEC-013,
[README](../../README.md#support)).

## Support matrix

The README shows the first two columns of this table; `tests/test_readme.py` checks
that both agree.

<!-- support-matrix:start -->
| Area | Status | Evidence |
| --- | --- | --- |
| Python 3.13 | supported | CI `checks` job on both Linux runners; `requires-python` is `>=3.13,<3.14` |
| Linux amd64 | supported | CI `checks (ubuntu-latest, 3.13)`: lint, types, tests, `check_distribution.py` |
| Linux arm64 | supported | CI `checks (ubuntu-24.04-arm, 3.13)` on a native arm64 runner, same steps |
| HTTP container image, amd64 and arm64 | supported | CI `container` job per native architecture: image build, `--version`, loopback HTTP `tools/list`, `wled_list_devices`, clean stop |
| stdio via uvx on Linux | supported | `check_distribution.py` in both `checks` jobs: clean wheel install and uvx stdio handshake |
| Windows | experimental | No CI job; known local failures in [DEVELOPMENT.md](../DEVELOPMENT.md#platform-notes) |
| macOS | experimental | No CI job; not run |
| WLED 16.0.1 | tested | Hardware acceptance on one RGB controller ([VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06)) |
| WLED 16.x other than 16.0.1 | unknown | No claim; no source review recorded yet |
| WLED below 16.0.0, including 0.15.x | unsupported | Served with a warning, never refused |
<!-- support-matrix:end -->

What CI runs, exactly (`.github/workflows/ci.yml`):

- `checks` on `ubuntu-latest` (amd64) and `ubuntu-24.04-arm` (arm64), Python 3.13, on
  every push and pull request: ruff, ruff format, mypy, agent setup, lock, private
  identifiers, `pytest`, `check_distribution.py`.
- `container` on the same two runners, for pull requests and pushes to `main` only:
  stages a non-release build and runs `scripts/check_container.py`.
- Both architectures run natively; no emulation is used or presented as evidence. The
  container smoke uses an empty synthetic inventory: it shows that the image builds,
  starts, authenticates, serves the tool list and stops cleanly. It is not device or
  hardware-performance evidence.
- No check is technically required yet. Required-check enforcement comes with the
  DEC-018 branch ruleset after the visibility change (owner action, #90); until then
  review treats these jobs as required, and the ruleset will list them.
- Run evidence is in [validation/issue-21.md](../validation/issue-21.md).

Python 3.14 is not declared: it is added to CI and `requires-python` only when it
passes.

## WLED firmware tiers

DEC-020 sets the floor at WLED 16.0.0. `src/wled_mcp/compat.py` classifies the
firmware version reported in `info.ver`:

| Tier | Versions | Meaning | Warning |
| --- | --- | --- | --- |
| `tested` | 16.0.1 | Recorded hardware evidence | no |
| `expected` | none yet | Source-reviewed and mock-tested, without hardware evidence | no |
| `unknown` | every other release from 16.0.0 on | No claim either way | no |
| `unsupported` | below 16.0.0, including every 0.x release and any suffixed 16.0.0: pre-releases (`16.0.0-b1`) and builds (`16.0.0+mod`, `16.0.0-custom`) | Outside the support policy | yes |
| `unrecognized` | no leading ASCII-numeric `MAJOR.MINOR.PATCH` (other Unicode digits included) | Support cannot be determined | yes |

- `wled_get_state` reports `data.diagnostics.firmware_support` =
  `{"tier": ..., "minimum_supported": "16.0.0"}` and, for `unsupported` and
  `unrecognized`, one warning as the first entry of `warnings`. The warning does not
  repeat the device-supplied version, which stays in `data.firmware.version`.
- The tier is informational only. No tool refuses a request because of it, no write
  plan, payload or verification depends on it, and the other tools do not report it.
  `wled-mcp doctor` ([CLI](cli.md#doctor)) reads this tier from the `wled_get_state`
  result and uses `support_warning` instead of a second policy.
- A version is promoted only with recorded evidence: to `tested` with a hardware
  record, to `expected` with a recorded source review plus mock tests. Promotion edits
  `TESTED` or `EXPECTED` in `compat.py` and the matrix above in the same change.

### Firmware behavior baseline

The server has no per-version behavior. Its WLED model is "baseline profile 0": derived
from the WLED v0.15.1 source and observed unchanged on 16.0.1 in the hardware runs.
The one 16-specific difference found so far, the top-level `bs` blending key that
WLED 16 stores in presets, is accepted as light state on every firmware
(ISSUE-66-DEC-001). This handling stays (TD-21-7): an
older 0.15.x controller is served exactly like a supported one, only with the warning.
A new version-specific branch needs a reviewed 16.x difference first.

### Secured controllers

The server sends no device credentials and has no unlock path. Read-only probes of one
controller (WLED 16.0.1) in three states, settings PIN and OTA lock both enabled, PIN only
and OTA lock only, were all answered normally by every read tool
([validation/issue-128.md](../validation/issue-128.md), [#128](https://github.com/descipar/wled-mcp/issues/128)).
Writes under a lock are untested. A refused read (HTTP 401 or 403, for example from a
proxy) is reported as `INVALID_RESPONSE` with the status code and is not retried
(`tests/test_state_catalogs.py`); HTTP authentication in front of a controller stays
unsupported.

## Evidence

- Firmware tiers and transports: `tests/test_compat.py` (every tier, one warning,
  identical stdio and HTTP envelopes, identical writes on 0.15.1 and 16.0.1).
- Contract and data compatibility with retained releases:
  `tests/test_upgrade_compat.py`, fixtures in `tests/fixtures/compat/`.
- CI runs and limits: [validation/issue-21.md](../validation/issue-21.md).
