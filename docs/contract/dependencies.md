# Runtime dependencies

Contract for the runtime dependencies the package declares and the tested set a release was checked
with. Introduced by [#22](https://github.com/descipar/wled-mcp/issues/22) (acceptance item 4,
S2-DIST-03); decisions ISSUE-22-DEC-003 (owner: loosen the exact pins) and ISSUE-22-DEC-004
(technical defaults: the ranges below), in the [decision log](../decisions/stage-2.md). Evidence:
[validation record](../validation/stage-2-release.md#runtime-dependency-ranges).

## Declared ranges

`project.dependencies` in `pyproject.toml` (published as `Requires-Dist`) holds a lower and an upper
bound for every runtime dependency, and no exact pin:

| Dependency | Range | Lower bound | Upper bound |
| --- | --- | --- | --- |
| `mcp` | `>=2.3.0,<3` | First release with `Server(get_tool_input_schema=...)`, which the server uses. | Next major: the SDK breaks only in a new major. |
| `pydantic` | `>=2.12.0,<3` | Floor of `mcp` 2.3.0. | Next major. |
| `httpx2` | `>=2.16,<3` | Existing floor (`mcp` 2.3.0 needs 2.10.0 or later). | Next major. |
| `starlette` | `>=1.0.0,<2` | First stable release; only `starlette.types` is used. | Next major. |
| `uvicorn` | `>=0.31.1,<0.55` | Floor of `mcp` 2.3.0; cooperative signal handling the server overrides exists from 0.29.0. | Next minor: uvicorn is `0.x` without a compatibility policy and the server subclasses `uvicorn.Server` internals. |
| `anyio` | `>=4.10,<5` | Floor forced by `httpx2` 2.16. | Next major. |

`anyio` is declared because the package imports it directly. Every third-party module that
`src/wled_mcp` imports must be declared (`tests/test_dependency_ranges.py`). The ranges contain the
earlier exact pins (`mcp==2.3.0`, `starlette==1.10.0`, `uvicorn==0.54.0`).

## Tested set

- `uv.lock` (development lock) and `requirements-runtime.txt` (its runtime export,
  `uv export --locked --no-dev --no-emit-project --no-hashes --no-header`) are the tested set: CI
  runs the test suite and the distribution check on exactly these versions. They do not freeze
  transitive dependencies for package users: without constraints, a PyPI install resolves the newest
  versions inside the declared ranges.
- The release directory staged by `deploy/stage_release.py`, the HTTP container image
  (`deploy/http/Dockerfile`) and the stdio hub example (`examples/mcphub.example.json`) install the
  wheel with `requirements-runtime.txt` as constraints, so they run the tested set.
- A package user gets a release's tested set with its constraints:

  ```text
  uvx --constraints https://raw.githubusercontent.com/descipar/wled-mcp/v<version>/requirements-runtime.txt --from wled-mcp==<version> wled-mcp
  ```

- The lowest and highest combination the ranges allow were installed from the wheel and run with the
  mocked and loopback suite when the ranges were introduced (validation record); combinations in
  between rest on the upstream policies.

## Maintenance

- Raise a lower bound when the code needs a newer release; keep the lock inside the ranges
  (`tests/test_dependency_ranges.py`).
- Widening an upper bound needs a test run against the highest resolution first, recorded in a
  validation record.
- Changing a range changes the published metadata and needs a new release; regenerate the lock
  (`uv lock`) and the export. `scripts/check_distribution.py` checks that the wheel's
  `Requires-Dist` equals `project.dependencies`.
