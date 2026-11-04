# Bootstrap development and private launch

Version 0.1.0 supports Python 3.13 only (`>=3.13,<3.14`), locally tested on
Windows/3.13.2; CI checks Linux/3.13. Official MCP SDK 2.3.0 owns protocol handling.
The default production registry is empty. HTTP selection exits 2 before listening
pending authenticated service support in #14. Full dual-mode acceptance is pending.

## Checks and build

Install Python 3.13 and uv 0.11.14. PowerShell, from the repository root:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:UV_PYTHON_DOWNLOADS = 'never'
uv sync --locked
uv run --frozen ruff check src tests scripts/check_lock.py scripts/check_distribution.py
uv run --frozen ruff format --check src tests scripts/check_lock.py scripts/check_distribution.py
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

## Private local wheel launch

Use `examples/bootstrap.toml`: `schema_version = 1` and `devices = []`.
Other tables and nonempty inventory are explicitly rejected until #4. The full
inventory example remains proposed. CLI configuration/data paths override
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

## License and remaining scope

No outbound project license is selected and no package is published. Official
SDK package metadata declares MIT; dependencies retain their own notices and
license metadata. This does not license this repository or complete a distribution
license review. No upstream WLED server code was copied. T18–T21, device tools,
deployment, resource measurements and hardware evidence remain pending.
