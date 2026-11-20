# Issue #24 validation: registry metadata and listing drafts

Evidence for the bounded packet of [#24](https://github.com/descipar/wled-mcp/issues/24) (AC-24-01 to
AC-24-10); decisions [ISSUE-24-DEC-001 and ISSUE-24-DEC-002](../decisions/issue-24.md). Listing
status per route: [MARKETPLACE.md](../MARKETPLACE.md#status-per-route).

At the time of the packet nothing was published, tagged, uploaded or submitted; no `mcp-publisher`
was used; only plain `GET` requests (two schemas, one GitHub API read, package downloads) were made.
Publication happened later ([below](#release-and-registry-publication-2026-11-09)).

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| AC-24-01 marker | `tests/test_registry_metadata.py`: README holds exactly one `mcp-name:` marker outside a code fence, before the status paragraph, equal to the `server.json` name (negative controls: removed, other name, duplicate, in a fence). `scripts/check_distribution.py` requires it in the wheel `METADATA`; `tests/test_check_distribution.py` covers missing and wrong marker on synthetic wheels. |
| AC-24-02 shape | `server_problems` over the real file: current `$schema`, name pattern, description 1 to 100 characters with "Unofficial" and "not affiliated with the WLED project", exactly one `pypi` package (`uvx`, `stdio`), `repository.url` equal to pyproject, no `remotes`, no environment variables; 24 mutated copies reported. |
| AC-24-03 versions | `tests/test_version_source.py`: `server.json` `version` and `packages[0].version` equal `project.version`; mutations reported; drafts and documents use `<version>`. |
| AC-24-04 stdio launch | Command line composed from arguments: runtime `--isolated --python 3.13`, package `--transport stdio --config <path> --data-dir <path>`; variables required, `filepath`, not secret, no default; no absolute path, IP, host name, credential word or e-mail; `https://` only on allowed hosts; mutations reported. |
| AC-24-05 HTTP | `remotes` absent; `docs/MARKETPLACE.md` has "HTTP is self-hosted" with the quickstart link; listing URLs only on `github.com`, `pypi.org` or the schema host. |
| AC-24-06 MCPM draft | `mcpm_problems`: required fields, kebab-case name, no `is_official`, repository and licence equal to pyproject, unofficial wording, uvx arguments ending in `--transport stdio`, no pinned version, paths only via `${WLED_MCP_CONFIG}` / `${WLED_MCP_DATA_DIR}`; 18 mutations reported. |
| AC-24-07 hosted copy | `hosted_problems`: status draft, unofficial wording, no image, form fields stated as unverified, no endorsement, `<version>` placeholder, allowed link hosts; 9 mutations reported. |
| AC-24-08 status table (historical, superseded, see [Release and registry publication](#release-and-registry-publication-2026-11-09)) | `status_rows`: one row per route, state in the vocabulary (or "not run"), none later than "validated locally" at that time. |
| AC-24-09 release preparation | Version bumped, `uv.lock` refreshed (project entry only), CHANGELOG from `git log v0.1.2..HEAD`. |
| AC-24-10 no external effect | Statement at the top of this file. |

## Live schema validation (one run, 2026-11-09)

Plain `GET` of both schemas outside the repository, checked with `jsonschema` 4.26.0 from the locked
dev environment (`python -I`).

| Item | Observation |
| --- | --- |
| Official schema | `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`, draft-07, SHA-256 `3fba09590c99f61735d234822279f4223fab9e300c0a81e81c91ab62a4114de0`; `server.json` 0 errors, `$schema` equals `$id` |
| MCPM schema | `mcp-registry/schema/server-schema.json`, 2020-12, SHA-256 `db6a9e57a91c82a22c9ad6d57f65b8255dedb76e6dc24e9376501f821aa11b18`, last changed 2025-07-08; MCPM draft 0 errors |
| Negative controls | a `server.json` copy (101-character description, no transport) and an MCPM copy (name `WLED_MCP`, no licence) were rejected with 2 errors each |

Limits: `format` keywords not enforced, unknown properties are not forbidden by the schema, and the
publisher's own checks (namespace ownership, package verification, `mcp-publisher validate`) were
**not run**; schema-valid does not mean registry-accepted.

## Local checks

Windows 11, Python 3.13.2, uv 0.11.14, on the branch merged with `origin/main`.

| Command | Result |
| --- | --- |
| `uv sync --locked`, `check_lock.py` | passes (45 packages) |
| `ruff check` / `format --check`, `mypy` | pass (124 files; 51 source files) |
| `check_agent_setup.py`, `check_private_identifiers.py` | pass (286 files) |
| `uv run --frozen pytest` | 3147 passed, 30 skipped, 6 failed, 5 errors (known local Windows failures in `test_hw_http_probe.py` and `test_inventory_client.py`, identical on unchanged `origin/main`; Linux CI is authoritative, DEC-020) |
| `check_distribution.py` (checkout path without spaces) | PASS, 30 exact runtime versions incl. registry marker, stdio, HTTP restart, uvx |

In a checkout whose path contains a space the last step (stdio hub example) fails identically on
unchanged `origin/main`; it is environmental, not part of this change.

## Not run and limits

- No registry publication, listing or submission at that time; no MCPHub install test (S2-MARKET-03);
  the hosted directory's form (sign-in) was not seen, so its fields stay unverified.
- That a client turns the argument list into the intended command is not tested (`--isolated` is a
  positional argument with a fixed value; that is a reading of the schema).
- MCPM's handling of `${...}` in `env` was not observed. Only the Windows machine ran these checks.

## Follow-up: release 0.2.0 preparation (2026-11-09)

The 0.1.3 preparation was never published; [DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)
requires a minor release for M1, so the version became 0.2.0 (`pyproject.toml`, `uv.lock` project entry,
both `server.json` versions) and the changelog was rewritten.
[ISSUE-24-DEC-003](../decisions/issue-24.md) narrows listing routes to the official MCP Registry; the
MCPM and hosted drafts stay unsubmitted.

- Schema run repeated: same SHA-256 values, `server.json` 0 errors, MCPM draft 0 errors, both negative
  controls rejected; the stated limits apply.
- The status-vocabulary test accepts "not planned" only for a row citing ISSUE-24-DEC-003; the official
  registry row stays "validated locally" and the install test "not run" (at that time).
- README: M1 features and tool count 27 to 31. Nothing was tagged, released, uploaded or submitted.

## Release and registry publication 2026-11-09

Recorded from the coordinator's verification in the owner's #24 session, each step instructed
separately ([ISSUE-24-DEC-004](../decisions/issue-24.md)); a copy of what was reported, not a re-run.

- **Tag and release:** `v0.2.0` and a GitHub release at commit `b27180930febcee7985dce35282a05d8be0dc137`
  (main, CI green).
- **PyPI:** `publish.yml` run 42715819076 succeeded after the owner approved the `pypi` environment.
  Wheel SHA-256 `383cc49fb73f28bca2ffe2a4c1e2afa85f0d8ed0cc815a2c7dacdac47ec617e8`, sdist
  `67128a688faa27b10d717c336fa3ffd9c496d8b63f97213144b6d90c12550508`, identical to the job's
  `SHA256SUMS`. The PyPI description carries `mcp-name: io.github.descipar/wled-mcp`.
- **Install check:** `uvx --no-cache --isolated --python 3.13 --from wled-mcp==0.2.0 wled-mcp --version`
  printed `wled-mcp 0.2.0` (a first attempt failed only on a stale local index cache).
- **Registry publish:** `mcp-publisher` 1.8.8 (checksum equal to the release checksums file) after the
  owner's `mcp-publisher login github`; it printed "Successfully published
  io.github.descipar/wled-mcp version 0.2.0" with the `server.json` identical to main. This repository
  did not run `mcp-publisher validate`.
- **Readback:** the registry search API returns exactly one entry: version 0.2.0, pypi package, no
  `remotes`, status active, `isLatest` true, `publishedAt` 2026-11-09T22:58:41Z.

Status per route afterwards: official registry **accepted** and **visible** in the registry's search
API; MCPM and hosted directory not planned (ISSUE-24-DEC-003); fresh-install test **not run**. Not
observed: an MCPHub registry tab showing the entry, or how a host turns the entry into a launch
configuration. #24 item 6 is run separately and not claimed here.

### Launch check of the composed command (2026-11-10)

Reported by the coordinator, Windows, with a real stdio client from the locked `mcp` SDK (script not
in the repository). Command composed from `packages[0]` of `server.json`:

```text
uvx --isolated --python 3.13 wled-mcp==0.2.0 --transport stdio --config <copy of examples/devices.example.toml> --data-dir <existing empty directory>
```

It started the published package; `initialize` returned `wled-mcp 0.2.0`; `tools/list` returned 31
tools; `wled_list_devices` returned `ok: true` with the two synthetic devices (`probe_status`
"untested", no network contact). Two earlier attempts failed only on the stale uv index cache. This
shows that the argument composition, including the positional `--isolated`, gives a working command
for a generic composer; it is partial evidence, not the install test (no MCPHub involved).

### MCPHub Registry tab, observed install dialog (2026-11-10)

Observed by the owner in their MCPHub (admin only) from a screenshot of the Install dialog; not re-run
by an agent. The dialog was prefilled with type STDIO, command `uvx` and arguments `wled-mcp@0.2.0`,
`----transport`, `stdio`, `----config`, `{config_path}`, `----data-dir`, `{data_dir}`.

- This MCPHub prepends `--` to argument names that already start with `--`, leaves `{config_path}` and
  `{data_dir}` unresolved and drops the runtime arguments (`--isolated`, `--python 3.13`). The
  coordinator read the MCPHub source (`getArgs()`, main branch, 2026-11-10), which matches the dialog;
  whether the owner's build equals that revision was not checked.
- `server.json` conforms to the registry schema and was not changed; the deployment guide tells users to
  edit the dialog ([DEPLOYMENT](../DEPLOYMENT.md#installing-from-the-mcphub-registry-tab)).

Result for #24 item 6: a documented finding; the configuration this MCPHub generates is not runnable
without a manual edit. The hand-corrected entry was **not** started inside MCPHub: the owner decided on
2026-11-10 that this is not wanted ([ISSUE-24-DEC-005](../decisions/issue-24.md), waiver). Item 6 is
closed by that waiver, not by an observation; the install-test state stays "not run". The AC wording of
S2-MARKET-03 ("metadata-generated uvx configuration") is not met for this hub build.
