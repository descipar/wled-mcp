# Local development and launch

The package supports Python 3.13 only (`>=3.13,<3.14`), locally tested on Windows/3.13.2; CI checks Linux amd64 and arm64 with Python 3.13 on native runners (`checks` job; documentation-only pull requests run a reduced set, see [Documentation-only pull requests](#documentation-only-pull-requests)) and builds and smoke-tests the HTTP image on both architectures (`container` job). Windows and macOS are experimental (DEC-020) and have no CI job; see [Platform notes](#platform-notes). The official MCP SDK 2.3.0 owns protocol handling. The tool set is in [TOOL-CONTRACT.md](TOOL-CONTRACT.md#tools-at-a-glance), checked against `tests/tool_contract.py`. `--transport streamable-http` starts the authenticated stateless HTTP service (below). Evidence: mock and loopback tests in CI plus the hardware and deployment runs in [VALIDATION.md](VALIDATION.md); procedures in [DEPLOYMENT.md](DEPLOYMENT.md). [TRACEABILITY.md](TRACEABILITY.md) maps requirements and T01-T21 to the automated evidence (`tests/test_traceability.py` runs `scripts/check_traceability.py` in CI).

## Checks and build

Install Python 3.13 and uv 0.11.14. PowerShell, from the repository root:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:UV_PYTHON_DOWNLOADS = 'never'
uv sync --locked
uv run --frozen ruff check src tests deploy scripts/check_lock.py scripts/check_distribution.py scripts/check_container.py scripts/check_traceability.py scripts/check_private_identifiers.py scripts/check_issue_content.py scripts/check_coverage.py scripts/ci_scope.py scripts/hw_http_probe.py
uv run --frozen ruff format --check src tests deploy scripts/check_lock.py scripts/check_distribution.py scripts/check_container.py scripts/check_traceability.py scripts/check_private_identifiers.py scripts/check_issue_content.py scripts/check_coverage.py scripts/ci_scope.py scripts/hw_http_probe.py
uv run --frozen ruff check src --select S --ignore S101
uv run --frozen mypy
uv run --frozen python scripts/check_agent_setup.py
uv run --frozen python scripts/check_lock.py
uv run --frozen python scripts/check_private_identifiers.py
uv run --frozen pytest
uv run --frozen python scripts/check_distribution.py
```

The Ruff file lists repeat those of the `checks` job in `.github/workflows/ci.yml`, which is authoritative. POSIX shells: `export UV_CACHE_DIR="$PWD/.uv-cache"` and `export UV_PYTHON_DOWNLOADS=never`; the rest is identical. Installation may access PyPI; tests use synthetic subprocesses, no LAN or devices.

CI runs the suite with `uv run --frozen pytest -n auto` (pytest-xdist, dev dependency); the same command is an optional local speed-up and plain `uv run --frozen pytest` stays supported. Each worker uses its own subdirectory of `.artifacts/pytest-temp`.

The security-lint job always runs Ruff S rules over `src` (S101 excluded for type/invariant assertions; false positives carry site-specific reasons). The CodeQL workflow analyzes Python with security-extended queries on PRs, main and weekly without building project code. Monthly grouped Dependabot PRs cover uv and Actions; they need review and are not auto-merged ([bounded review record](validation/m3-m6.md)).

### Documentation-only pull requests

For a pull request event, `checks` first runs `scripts/ci_scope.py`, which compares the merge commit with its first parent. When every changed path is a markdown file in the repository root or under `docs/` (no hidden path component, regular file mode), the job runs only `uv sync --locked`, `scripts/check_agent_setup.py`, the private-identifier scan, the test files in `DOC_READER_TESTS` and `git diff --exit-code`; Ruff, mypy, `check_lock`, the full test run and `check_distribution` are skipped. Both required `checks` names still report.

Everything else runs the complete job: pushes to `main`, other events, any code, test, script, workflow, dependency or non-markdown change, mixed changes, an empty diff and any diff that cannot be determined (every full-suite step is conditioned on `docs_only != 'true'`). `tests/test_ci_scope.py` keeps the reduced set complete: a static scan fails when a file naming a repository document is in neither `DOC_READER_TESTS` nor `DOC_READER_EXCLUSIONS` (with a reason); it is best effort and the next run on `main` covers a miss. The private-identifier denylist step and scan always run (asserted by the same test). Deleting the root `README.md` counts as a documentation change, but `tests/test_readme.py` then fails, as in the full suite. The `container` job is unchanged. Dry run on a local merge commit: `GITHUB_EVENT_NAME=pull_request python scripts/ci_scope.py`; reduced tests: `uv run --frozen pytest $(python scripts/ci_scope.py tests)`.

### Private-identifier and issue-content scans

`scripts/check_private_identifiers.py` scans every tracked (and untracked, non-ignored) text file for private addresses, home paths, router-local host names, MAC addresses and personal e-mail addresses. Findings name `path:line: rule` without the value; `--show-values` prints values locally. Intended synthetic fixtures need an entry with a reason in `scripts/private_identifier_allowlist.toml` (an unused entry fails). Real installation values never go there: list them one per line in the git-ignored `runtime/private-denylist.txt` (or a file named by `WLED_MCP_PRIVATE_DENYLIST`). In CI the denylist comes from the Actions secret `WLED_MCP_PRIVATE_DENYLIST`: a step writes it to a file under `RUNNER_TEMP`, sets the variable to that path and never echoes it (the log shows only the entry count). Without the secret (for example a fork PR) only the rule checks run.

`scripts/check_issue_content.py` applies the same rules and denylist to issue and pull request text (titles incl. renames, comments, reviews, review comments, every edit-history revision, branch names, labels). It is read-only (GraphQL through an authenticated `gh` CLI), runs on demand only, never in CI, and reports locators such as `pr #30 review 2 comment 1 revision 1:3: ipv4-private` without values; deleted revisions count as not scannable. Exit codes: 0 no findings, 1 findings, 2 incomplete.

```text
uv run --frozen python scripts/check_issue_content.py --output .agent-runs/issue-scan.txt
```

`--repo OWNER/NAME` selects another repository; `--show-values` is for local use only. The `--output` file never contains values; keep it in an ignored directory. Tests (`tests/test_issue_content.py`) use an in-memory fake of the GitHub API.

### Build and constraints

Build separately with `uv build --wheel --no-build-isolation --python .venv/Scripts/python.exe` (`.venv/bin/python` on POSIX) after a locked sync; the locked hatchling 1.27.0 builds the wheel. The distribution checker builds automatically, installs the wheel noneditably in a clean environment, verifies package/runtime versions, console commands and SDK negotiation/listing outside the source tree and repeats this through uvx for current and legacy protocol negotiation.

After intentional dependency updates regenerate constraints:

```text
uv export --locked --no-dev --no-emit-project --no-hashes --no-header --output-file requirements-runtime.txt
```

The lock checker rejects drift. uvx does **not** consume `uv.lock`; the runtime constraints pin its versions. Constraints do not enforce artifact hashes or authenticate the wheel (preserve a trusted wheel for private distribution); the lockfile retains the hashes. The package declares ranges, not exact versions: [contract/dependencies.md](contract/dependencies.md).

## Adding a tool

The expected tool contract lives in `tests/tool_contract.py` (ISSUE-98-DEC-001), the only hand-maintained tool list: tests compare the real registry and every served `tools/list` (stdio and HTTP) with it in both directions, and `scripts/check_distribution.py` loads it to check the installed wheel. A pull request that adds a tool therefore makes, together:

- one `ExpectedTool` entry in `tests/tool_contract.py` at the tool's registry position, with its class (`read`, `control` or `manage`, ISSUE-20-DEC-001) and destructive flag; the annotation test derives `read_only_hint`, `destructive_hint` and `idempotent_hint` from these;
- the same class as the required `tool_class=ToolClass.X` keyword of the `Operation` (a test compares both; an `Operation` without a class cannot be constructed). A tool that writes to a device does so only through the `Resources` write engines (or `Resources.require_write`), never through `WLEDClient.post_state` directly (a test pins the module list). A tool that reaches devices without a top-level `device_id` calls `Resources.require_access` in its preflight ([profiles](contract/profiles.md#enforcement));
- the affected rows in [WLED-COVERAGE.md](WLED-COVERAGE.md#maintenance) by ID (or an entry under "Tools without a WLED feature row"), then `python scripts/check_coverage.py --update` (ISSUE-94-DEC-002);
- its own behavior tests.

Do not add tool-name lists or counts to other tests; select a tool by name with `expected_names()`, `names_of()` or `expected_tool()`. The probe allowlists in `scripts/hw_http_probe.py` and `scripts/hw_read_only_probe.py` stay literal on purpose and are guarded by subset tests.

## Read-only hardware quick path

An optional check of the read tools (H01/H02) against one explicitly authorized device over local stdio, with no deployment and no write. Copy `examples/h01-h02.devices.example.toml` to `runtime/h01-h02/devices.toml` (git-ignored), put the selected device in it and record its timers, other API clients, playlists and realtime inputs without disabling any. Then run `uv run --frozen python scripts/hw_read_only_probe.py <device-id>`: it calls only `wled_list_devices(probe=true)`, `wled_get_state`, `wled_get_effects` and `wled_get_palettes`, refuses any other tool and writes to `runtime/h01-h02/out/`. Run `wled_get_effects` once with `refresh=true` to observe freshness; the preset part of H02 stays pending until it is actually run. Compare firmware, LED count, capabilities, effect/palette IDs and segments with the WLED UI. Record only a sanitized summary in [VALIDATION.md](VALIDATION.md); mismatches become issues. Real addresses and raw output never enter the repository.

## Snapshot store tests

`tests/test_backups.py` covers the #8 snapshot store with `tmp_path`, mock transports and no network, LAN or hardware access: `uv run --frozen pytest tests/test_backups.py`. Runtime backups live under the data directory (`backups/`, git-ignored; a test asserts they cannot be tracked). Never point tests at a real data directory.

## Streamable HTTP service and tests

The HTTP service needs a bearer credential before it listens: `WLED_MCP_HTTP_TOKEN` (32 to 512 printable ASCII characters) or `--http-token-file <absolute path>`, never the command line. Local loopback run (synthetic credential):

```text
WLED_MCP_HTTP_TOKEN=<synthetic-token-of-32-or-more-characters> \
  uv run --frozen wled-mcp --config <abs>/bootstrap.toml --data-dir <abs>/runtime \
  --transport streamable-http
```

The endpoint is `http://127.0.0.1:8000/mcp`; another host or port needs an explicit `--allowed-host host[:port]`; HTTP-only options with stdio exit 2. `tests/test_http_service.py` and `tests/test_http_cli.py` bind `127.0.0.1` ephemeral ports, use a mocked or synthetic loopback device and never contact a LAN device; the POSIX signal tests are skipped on Windows (in-process shutdown tests run everywhere). The distribution check also starts the installed console over HTTP on a loopback port, stops it with a signal and restarts it once on the same port and data directory. `tests/test_acceptance_parity.py` drives the installed console over stdio and HTTP against a synthetic `127.0.0.1` device. Run just these with `uv run --frozen pytest tests/test_http_service.py tests/test_http_cli.py`.

## Local wheel launch

Use `examples/bootstrap.toml` (`schema_version = 1`, `devices = []`), or the executable synthetic `examples/devices.example.toml` for configured devices; supported settings and probes are in [INVENTORY-CLIENT.md](INVENTORY-CLIENT.md). CLI paths override `WLED_MCP_CONFIG`/`WLED_MCP_DATA_DIR`; paths must be absolute and the data directory must exist. Startup reads configuration without probing devices or creating files.

PowerShell, after building:

```powershell
New-Item -ItemType Directory -Force runtime | Out-Null
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:UV_TOOL_DIR = Join-Path (Get-Location) '.uv-tools'
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location) '.uv-python'
$version = uv run --frozen python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
$wheelUri = ([System.Uri](Join-Path (Get-Location) "dist/wled_mcp-$version-py3-none-any.whl")).AbsoluteUri
$constraintsUri = ([System.Uri](Join-Path (Get-Location) 'requirements-runtime.txt')).AbsoluteUri
uvx --isolated --no-env-file --python 3.13 --constraints $constraintsUri --from $wheelUri wled-mcp --config (Join-Path (Get-Location) 'examples/bootstrap.toml') --data-dir (Join-Path (Get-Location) 'runtime')
```

File URIs preserve Windows paths with spaces; supply the exact wheel and matching constraints together. This runs a locally built wheel; released packages are installed as in [QUICKSTARTS.md](QUICKSTARTS.md). stdio waits for its host on stdin; stdout is protocol only, diagnostics use stderr, EOF closes the process. `--help`/`--version` need no configuration paths.

## Platform notes

Windows is a supported development platform (DEC-033): the checks and the complete test suite in [Checks and build](#checks-and-build) are expected to pass on a Windows checkout with PowerShell, uv and Python 3.13 (add `-n auto` for the parallel run); WSL is not required. Linux CI stays authoritative, and for users Windows remains experimental (DEC-020 item 4).

A test that fails only on Windows is a defect: fix it, or skip it on Windows with a stated reason where the behavior is POSIX-specific (signals, symlinks, `mkfifo`, permission bits, `sh`, `bash`, `sha256sum`, GNU `find`, root) or opt-in (the local Docker check). The offline guarantee holds on every platform. A test needing a symbolic link uses `symlink_or_skip` from `tests/symlink_support.py`, which skips with a stated reason without the privilege (Windows without Developer Mode, not elevated).

Known differences:

- File modes are not enforced. `--output` of `scripts/hw_http_probe.py` creates the report with mode 0600 on POSIX only; on Windows it inherits the directory's access control, so write it to a directory only you can read. Mode assertions in tests are skipped on Windows.
- asyncio uses the Proactor event loop, whose self-pipe is a loopback socketpair. The offline test guard (`tests/network_guard.py`, the `no_network` fixture of `tests/conftest.py`) allows exactly that connect and refuses every other connect, event-loop connect (`IocpProactor.connect`) and name resolution.
- `scripts/check_container.py` needs a Linux Docker host.
- `scripts/check_distribution.py` passes the hub example's staged wheel and constraints file to uv as file URIs when the checkout path contains whitespace, because uv would split a plain path ([#213](https://github.com/descipar/wled-mcp/issues/213)).

## Deployment artifact checks

`tests/test_deployment_artifacts.py` cross-checks the HTTP image (`deploy/http/Dockerfile` and its allowlist context), the Compose example, both hub examples, `deploy/stage_release.py` and the commands in [DEPLOYMENT.md](DEPLOYMENT.md) without Docker, a hub or a LAN device. It also runs the Compose command (paths, bind and port replaced; `127.0.0.1` only) with the hub example's Host and Authorization header shape against the installed console. The distribution check runs the stdio hub example through uvx with only its paths replaced. An optional `docker compose config` check runs only with `WLED_MCP_DOCKER_CHECKS=1` and a local Docker CLI, never in CI. Image builds are a manual, local step and nothing is pushed.

## License and remaining scope

Apache-2.0 with a NOTICE file (DEC-011). The official SDK package metadata declares MIT; the SDK and other dependencies retain their own notices. No upstream WLED server code was copied. Hardware, deployment and update/rollback evidence and its limits: [VALIDATION.md](VALIDATION.md) and the README [Limitations](../README.md#limitations).
