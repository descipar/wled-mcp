# Bootstrap development and private launch

Version 0.1.0 supports Python 3.13 only (`>=3.13,<3.14`), locally tested on
Windows/3.13.2; CI checks Linux/3.13. Official MCP SDK 2.3.0 owns protocol handling.
The production registry contains `wled_list_devices`, the three read tools from #5, `wled_set_state` and `wled_patch_segments` (#6) and `wled_replace_layout` (#7) and the persistent-preset tools `wled_list_presets`, `wled_get_preset`, `wled_activate_preset`, `wled_save_preset` and `wled_delete_preset` (#9; mock-tested, H06 pending). `--transport streamable-http` starts the
authenticated stateless HTTP service from #14 (see below); its software evidence is
mock/loopback only. Deployment artifacts for both modes (#11: Dockerfile, Compose
and hub examples, staging helper) are prepared and statically checked; actual
deployment and hub integration remain pending.
[TRACEABILITY.md](TRACEABILITY.md) maps requirements and T01–T21 to the automated
evidence; `tests/test_traceability.py` runs `scripts/check_traceability.py` in CI.

## Checks and build

Install Python 3.13 and uv 0.11.14. PowerShell, from the repository root:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:UV_PYTHON_DOWNLOADS = 'never'
uv sync --locked
uv run --frozen ruff check src tests deploy scripts/check_lock.py scripts/check_distribution.py scripts/check_traceability.py
uv run --frozen ruff format --check src tests deploy scripts/check_lock.py scripts/check_distribution.py scripts/check_traceability.py
uv run --frozen mypy
uv run --frozen python scripts/check_agent_setup.py
uv run --frozen python scripts/check_lock.py
uv run --frozen pytest
uv run --frozen python scripts/check_distribution.py
```

POSIX shells: `export UV_CACHE_DIR="$PWD/.uv-cache"` and
`export UV_PYTHON_DOWNLOADS=never`; remaining commands are identical. Dependency
installation may access PyPI. Tests use synthetic subprocesses, no LAN/devices.

Build separately with `uv build --wheel --no-build-isolation --python
.venv/Scripts/python.exe` (use `.venv/bin/python` on POSIX), after locked sync.
No build isolation means the locked installed hatchling 1.27.0 and its locked
dependencies build the wheel. The distribution checker builds automatically,
installs the wheel noneditably in a clean environment and verifies package/runtime
versions, console commands and SDK negotiation/listing outside the source tree.
It repeats these checks through uvx, for current and legacy protocol negotiation.

After intentional dependency updates regenerate constraints with:

```text
uv export --locked --no-dev --no-emit-project --no-hashes --no-header --output-file requirements-runtime.txt
```

The lock checker rejects drift. uvx does **not** consume `uv.lock`; runtime
constraints pin its versions. Constraints do not enforce artifact hashes or
authenticate the wheel; preserve a trusted wheel for private distribution.
The lockfile separately retains dependency artifact hashes.

## Snapshot store tests

`tests/test_backups.py` covers the #8 snapshot store with pytest `tmp_path`, mock
transports and no network, LAN or hardware access. Run it alone with
`uv run --frozen pytest tests/test_backups.py`. Runtime backups live under the
configured data directory (`backups/`, git-ignored; a test asserts they cannot be
tracked). Never point tests at a real data directory.

## Streamable HTTP service and tests

The HTTP service needs a bearer credential before it listens: set
`WLED_MCP_HTTP_TOKEN` (32 to 512 printable ASCII characters) or pass
`--http-token-file <absolute path>`; never pass the value on the command line.
Local loopback run (synthetic placeholder credential):

```text
WLED_MCP_HTTP_TOKEN=<synthetic-token-of-32-or-more-characters> \
  uv run --frozen wled-mcp --config <abs>/bootstrap.toml --data-dir <abs>/runtime \
  --transport streamable-http
```

The endpoint is `http://127.0.0.1:8000/mcp`. A different host or port requires an
explicit `--allowed-host host[:port]`. HTTP-only options with stdio exit 2.
`tests/test_http_service.py` and `tests/test_http_cli.py` bind `127.0.0.1`
ephemeral ports, use a mocked or synthetic loopback device and never contact a LAN
device; the POSIX signal tests are skipped on Windows (the in-process shutdown tests
run everywhere). The distribution check also starts the installed console over HTTP
on a loopback port, stops it with a signal and restarts it once on the same port and
data directory. `tests/test_acceptance_parity.py` drives the installed console over
stdio and HTTP against a synthetic `127.0.0.1` device. Run just these tests with
`uv run --frozen pytest tests/test_http_service.py tests/test_http_cli.py`.

## Private local wheel launch

Use `examples/bootstrap.toml`: `schema_version = 1` and `devices = []`.
For configured devices use the executable synthetic `examples/devices.example.toml`.
See [inventory/client limits](INVENTORY-CLIENT.md) for supported settings and probes.
CLI configuration/data paths override
`WLED_MCP_CONFIG`/`WLED_MCP_DATA_DIR`; paths must be absolute and the data directory
must exist. Startup reads configuration without probing devices or creating files.

PowerShell, after building:

```powershell
New-Item -ItemType Directory -Force runtime | Out-Null
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:UV_TOOL_DIR = Join-Path (Get-Location) '.uv-tools'
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location) '.uv-python'
$wheelUri = ([System.Uri](Join-Path (Get-Location) 'dist/wled_mcp-0.1.0-py3-none-any.whl')).AbsoluteUri
$constraintsUri = ([System.Uri](Join-Path (Get-Location) 'requirements-runtime.txt')).AbsoluteUri
uvx --isolated --no-env-file --python 3.13 --constraints $constraintsUri --from $wheelUri wled-mcp --config (Join-Path (Get-Location) 'examples/bootstrap.toml') --data-dir (Join-Path (Get-Location) 'runtime')
```

File URIs preserve Windows paths containing spaces. Supply the exact wheel and
matching constraints together; no public PyPI project package is assumed. stdio
waits for its MCP host on stdin. stdout is protocol only; diagnostics use stderr;
EOF closes the process. `--help`/`--version` need no configuration paths.

## Deployment artifact checks

`tests/test_deployment_artifacts.py` cross-checks the HTTP image
(`deploy/http/Dockerfile` and its allowlist build context), the Compose example, both
hub examples, `deploy/stage_release.py` and the commands in
[DEPLOYMENT.md](DEPLOYMENT.md) without Docker, a hub or a LAN device. It also runs the
Compose command (paths, bind and port replaced; `127.0.0.1` only) with the hub
example's Host and Authorization header shape against the installed console. The
distribution check runs the stdio hub example through uvx with only its paths
replaced. An optional `docker compose config` check runs only with
`WLED_MCP_DOCKER_CHECKS=1` and a local Docker CLI; it is never required in CI. Image
builds are a manual, local step (see DEPLOYMENT.md) and nothing is pushed.

## License and remaining scope

No outbound project license is selected and no package is published. Official
SDK package metadata declares MIT; dependencies retain their own notices and
license metadata. This does not license this repository or complete a distribution
license review. No upstream WLED server code was copied. T18–T21 and the device tools
are covered by mock/loopback tests; deployment artifacts are prepared, while actual
deployment, resource measurements and hardware evidence remain pending.
