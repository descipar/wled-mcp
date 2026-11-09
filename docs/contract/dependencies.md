# Runtime dependencies

Contract for the runtime dependencies the package declares and the tested set a release
was checked with. Introduced by [#22](https://github.com/descipar/wled-mcp/issues/22)
(acceptance item 4, S2-DIST-03); decisions ISSUE-22-DEC-003 (owner: loosen the exact
pins) and ISSUE-22-DEC-004 (technical defaults: the ranges below), in the
[decision log](../decisions/issue-22.md). Evidence:
[validation record](../validation/issue-22.md#runtime-dependency-ranges).

## Declared ranges

`project.dependencies` in `pyproject.toml`, published as `Requires-Dist`, holds a range with
a lower and an upper bound for every runtime dependency, and no exact pin:

| Dependency | Range | Lower bound | Upper bound |
| --- | --- | --- | --- |
| `mcp` | `>=2.3.0,<3` | 2.3.0 is the first release with `Server(get_tool_input_schema=...)`, which the server uses. | Next major: the MCP Python SDK makes breaking changes only in a new major. |
| `pydantic` | `>=2.12.0,<3` | Floor of `mcp` 2.3.0. | Next major: Pydantic does not intentionally break V2 in minor releases. |
| `httpx2` | `>=2.16,<3` | Existing floor, unchanged (`mcp` 2.3.0 needs 2.10.0 or later). | Next major. |
| `starlette` | `>=1.0.0,<2` | First stable release; the server uses only `starlette.types`. | Next major: only experimental APIs may change in 1.x minors. |
| `uvicorn` | `>=0.31.1,<0.55` | Floor of `mcp` 2.3.0; the cooperative signal handling the server overrides exists from 0.29.0. | Next minor: uvicorn is `0.x` without a compatibility policy, minors have removed features, and the server subclasses `uvicorn.Server` internals. |
| `anyio` | `>=4.10,<5` | Floor already forced by `httpx2` 2.16. | Next major: AnyIO follows Semantic Versioning. |

`anyio` is declared because the package imports it directly; before #22 item 4 it was only
installed through `mcp`, `httpx2` and `starlette`. Every third-party module that
`src/wled_mcp` imports must be declared (`tests/test_dependency_ranges.py`).

The ranges contain the earlier exact pins (`mcp==2.3.0`, `starlette==1.10.0`,
`uvicorn==0.54.0`), so every environment that satisfied the earlier metadata still
satisfies it.

## Tested set

- `uv.lock` is the development lock and `requirements-runtime.txt` its runtime export
  (`uv export --locked --no-dev --no-emit-project --no-hashes --no-header`). Together they
  are the tested set: CI runs the test suite and the distribution check on exactly these
  versions. They are not a frozen transitive set for package users: without constraints, an
  installation from PyPI resolves the newest versions inside the declared ranges, including
  transitive dependencies newer than the lock.
- The release directory staged by `deploy/stage_release.py`, the HTTP container image
  (`deploy/http/Dockerfile`) and the stdio hub example (`examples/mcphub.example.json`)
  always install the wheel with `requirements-runtime.txt` as constraints, so they run the
  tested set.
- A package user gets the tested set of a release by adding that release's constraints:

  ```text
  uvx --constraints https://raw.githubusercontent.com/descipar/wled-mcp/v<version>/requirements-runtime.txt --from wled-mcp==<version> wled-mcp
  ```

- The lowest and the highest combination the ranges allow were installed from the wheel
  and run with the mocked and loopback test suite when the ranges were introduced; see
  the validation record. Combinations in between are covered by the upstream policies
  above, not by a test run.

## Maintenance

- Raise a lower bound when the code starts to need a newer release (a new API, a fixed
  bug); keep the lock inside the ranges (`tests/test_dependency_ranges.py`).
- Widening an upper bound (for example admitting uvicorn 0.55 or a new major) needs a run
  of the test suite against the highest resolution first, recorded in a validation record.
- Changing a range changes the published metadata and needs a new release; the lock and
  the export are regenerated with `uv lock` and the export command above, and
  `scripts/check_distribution.py` checks that the wheel's `Requires-Dist` equals
  `project.dependencies`.
