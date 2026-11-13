# Local development and launch

The package supports Python 3.13 only (`>=3.13,<3.14`), locally tested on
Windows/3.13.2; CI checks Linux amd64 and arm64 with Python 3.13 on native runners
(`checks` job; documentation-only pull requests run a reduced set, see
[Documentation-only pull requests](#documentation-only-pull-requests)) and builds and smoke-tests the HTTP image on both architectures
(`container` job, for pull requests and `main`). Windows and macOS are experimental
(DEC-020) and have no CI job; see [Platform notes](#platform-notes). Official MCP SDK
2.3.0 owns protocol handling.
The tool set is listed in [TOOL-CONTRACT.md](TOOL-CONTRACT.md#tools-at-a-glance) and checked against
`tests/tool_contract.py`. `--transport streamable-http` starts the authenticated stateless HTTP
service (see below). Evidence is mock and loopback tests in CI plus the recorded hardware and
deployment runs in [VALIDATION.md](VALIDATION.md); procedures are in [DEPLOYMENT.md](DEPLOYMENT.md).
[TRACEABILITY.md](TRACEABILITY.md) maps requirements and T01–T21 to the automated
evidence; `tests/test_traceability.py` runs `scripts/check_traceability.py` in CI.

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

CI runs the complete suite in parallel with `uv run --frozen pytest -n auto` (pytest-xdist, a
dev dependency); the same command is an optional local speed-up, and the plain serial
`uv run --frozen pytest` stays supported. Each worker uses its own subdirectory of
`.artifacts/pytest-temp`.

The independent security-lint job always runs Ruff S rules over `src`; S101 is excluded
for type/invariant assertions, and individual false positives carry site-specific reasons.
The separate CodeQL workflow analyzes Python with security-extended queries on PRs, main
and weekly without building project code. Weekly Dependabot PRs cover uv and Actions;
updates require review and are not automatically merged. See the
[bounded review record](validation/issue-181.md) for scope and limits.

### Documentation-only pull requests

For a pull request event, the `checks` job first runs `scripts/ci_scope.py`, which compares
the merge commit with its first parent. When every changed path is a markdown file in the
repository root or under `docs/` (no hidden path component, regular file mode), the job runs
only the steps that can read documents: `uv sync --locked`, `scripts/check_agent_setup.py`,
the private-identifier scan, the test files listed in `DOC_READER_TESTS` and
`git diff --exit-code`. Ruff, mypy, `check_lock`, the full test run and `check_distribution`
are skipped. Both required `checks` names still report.

Everything else runs the complete job unchanged: pushes to `main`, any other event, any
code, test, script, workflow, dependency or non-markdown change, mixed changes, an empty
diff and any diff that cannot be determined (the script exits 0 and every full-suite step is
conditioned on `docs_only != 'true'`). `tests/test_ci_scope.py` keeps the reduced set
complete: a static scan fails when a file that names a repository document is neither in
`DOC_READER_TESTS` nor in `DOC_READER_EXCLUSIONS` (with a reason). The scan is best effort;
a reader without any document literal is not found, and the next run on `main` covers it.
The `container` job is unchanged. Dry run on a local merge commit:
`GITHUB_EVENT_NAME=pull_request python scripts/ci_scope.py`; reduced tests:
`uv run --frozen pytest $(python scripts/ci_scope.py tests)`.

POSIX shells: `export UV_CACHE_DIR="$PWD/.uv-cache"` and
`export UV_PYTHON_DOWNLOADS=never`; remaining commands are identical. Dependency
installation may access PyPI. Tests use synthetic subprocesses, no LAN/devices.

`scripts/check_private_identifiers.py` scans every tracked (and untracked, non-ignored)
text file for private addresses, home paths, router-local host names, MAC addresses
and personal e-mail addresses. Findings name `path:line: rule` without the value;
`--show-values` prints values locally. Intended synthetic fixtures need an entry with a
reason in `scripts/private_identifier_allowlist.toml`; an unused entry fails. Values of
a real installation never go there: list them one per line in the git-ignored
`runtime/private-denylist.txt` (or a file named by `WLED_MCP_PRIVATE_DENYLIST`) so the
check also finds those literals.

In CI the denylist comes from the Actions secret `WLED_MCP_PRIVATE_DENYLIST`, which
holds the file content: a step before the scanner writes it to a file under
`RUNNER_TEMP` (outside the work tree) and sets `WLED_MCP_PRIVATE_DENYLIST` to that
path. The content is never echoed; the scanner log shows only the number of entries.
Without the secret (for example in a pull request from a fork) the step prints a note
and only the rule checks run.

`scripts/check_issue_content.py` applies the same rules and denylist to the
repository's issue and pull request text, including titles changed by renames, comments,
review bodies, review comments, every edit-history revision, branch names and labels.
It is read-only (GraphQL queries through an authenticated `gh` CLI), runs on demand
only and never in CI, and reports locators such as
`pr #30 review 2 comment 1 revision 1:3: ipv4-private` without values. Deleted
revisions are counted as not scannable. Exit codes: 0 no findings, 1 findings, 2 the
content could not be checked completely.

```text
uv run --frozen python scripts/check_issue_content.py --output .agent-runs/issue-scan.txt
```

`--repo OWNER/NAME` selects another repository; `--show-values` prints matched values
for local use only and never goes into CI logs, issues or pull requests. The `--output`
file never contains values; keep it in an ignored directory. Its tests
(`tests/test_issue_content.py`) use an in-memory fake of the GitHub API.

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
The lockfile separately retains dependency artifact hashes. The package itself declares
version ranges, not these exact versions; the ranges, their bounds and how a package user
gets the tested set are in [contract/dependencies.md](contract/dependencies.md).

## Adding a tool

The expected tool contract lives in `tests/tool_contract.py` (ISSUE-98-DEC-001). It
is the only hand-maintained tool list: tests compare the real registry and every
served `tools/list` (stdio and HTTP) with it in both directions, and
`scripts/check_distribution.py` loads it from the source checkout to check the
installed wheel. A pull request that adds a tool therefore makes, together:

- one `ExpectedTool` entry in `tests/tool_contract.py` at the tool's registry position,
  with its class (`read`, `control` or `manage`, ISSUE-20-DEC-001) and its destructive
  flag; the annotation test derives `read_only_hint`, `destructive_hint` and
  `idempotent_hint` from these;
- the same class as the required `tool_class=ToolClass.X` keyword of the `Operation`
  (production code cannot import the test helper; a test compares both, and an
  `Operation` without a class cannot be constructed). A tool that writes to a device does
  so only through the `Resources` write engines (or an explicit
  `Resources.require_write`), never through `WLEDClient.post_state` directly: a test
  pins the module list. A tool that reaches devices without a top-level `device_id`
  calls `Resources.require_access` in its preflight
  ([profiles](contract/profiles.md#enforcement));
- the affected rows in [WLED-COVERAGE.md](WLED-COVERAGE.md#maintenance) by ID (or an
  entry under "Tools without a WLED feature row"), followed by
  `python scripts/check_coverage.py --update` (ISSUE-94-DEC-002);
- its own behavior tests.

Do not add tool-name lists or tool counts to other tests; select a tool by name and use
`expected_names()`, `names_of()` or `expected_tool()` from the helper. The standalone
probe allowlists in `scripts/hw_http_probe.py` and `scripts/hw_read_only_probe.py`
stay literal on purpose and are guarded by subset tests.

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

## Local wheel launch

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
$version = uv run --frozen python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
$wheelUri = ([System.Uri](Join-Path (Get-Location) "dist/wled_mcp-$version-py3-none-any.whl")).AbsoluteUri
$constraintsUri = ([System.Uri](Join-Path (Get-Location) 'requirements-runtime.txt')).AbsoluteUri
uvx --isolated --no-env-file --python 3.13 --constraints $constraintsUri --from $wheelUri wled-mcp --config (Join-Path (Get-Location) 'examples/bootstrap.toml') --data-dir (Join-Path (Get-Location) 'runtime')
```

File URIs preserve Windows paths containing spaces. Supply the exact wheel and
matching constraints together. This section runs a locally built wheel; released packages
are installed as in [QUICKSTARTS.md](QUICKSTARTS.md). stdio
waits for its MCP host on stdin. stdout is protocol only; diagnostics use stderr;
EOF closes the process. `--help`/`--version` need no configuration paths.

## Platform notes

Windows is a supported development platform (DEC-033): the checks and the complete test
suite in [Checks and build](#checks-and-build) are expected to pass on a Windows checkout
with PowerShell, uv and Python 3.13 (add `-n auto` for the parallel run). WSL is not
required. Linux CI stays authoritative, and for users Windows remains experimental
(DEC-020 item 4): no CI job runs on it and nothing here promises that the service is
supported there.

A test that fails only on Windows is a defect. Fix it, or skip it on Windows with a stated
reason where the behavior is POSIX-specific (POSIX signals, symlinks and `mkfifo`,
permission bits, `sh`, `bash`, `sha256sum` and GNU `find`, root) or opt-in (the local Docker
check). The offline guarantee of the tests holds on every platform.

Known differences:

- File modes are not enforced. `--output` of `scripts/hw_http_probe.py` creates the report
  with mode 0600 on POSIX only; on Windows the file inherits the access control of its
  directory, so write it to a directory only you can read. Mode assertions in tests are
  skipped on Windows.
- asyncio uses the Proactor event loop, whose self-pipe is a loopback socketpair. The
  offline test guard (`tests/network_guard.py`) allows exactly that connect and refuses every
  other connect and name resolution.
- `scripts/check_container.py` needs a Linux Docker host.

Known Windows tooling limit, outside the test suite and not a test failure:
`scripts/check_distribution.py` exited 1 with `MCPError: Connection closed` at the uvx stdio
handshake on a checkout whose path contains a space. The same script passed on a clone at a
space-free path, so the space in the path is the cause. Run it from a space-free checkout
path until this is fixed ([#213](https://github.com/descipar/wled-mcp/issues/213)).

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

The project is licensed Apache-2.0 with a NOTICE file (DEC-011). The official SDK package
metadata declares MIT; the SDK and other dependencies retain their own notices and license
metadata. No upstream WLED server code was copied. Hardware, deployment and update/rollback
evidence and its limits are in [VALIDATION.md](VALIDATION.md) and the README
[Limitations](../README.md#limitations).
