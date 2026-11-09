# Issue #24 validation: registry metadata and listing drafts

Evidence for the bounded packet of [#24](https://github.com/descipar/wled-mcp/issues/24)
(acceptance scenarios AC-24-01 to AC-24-10); decisions
[ISSUE-24-DEC-001 and ISSUE-24-DEC-002](../decisions/issue-24.md). Listing status per route:
[MARKETPLACE.md](../MARKETPLACE.md#status-per-route).

Nothing was published, tagged, uploaded or submitted. No `mcp-publisher` was installed, logged
in to, validated with or run; no external issue, pull request or form was sent; no LAN device
was contacted. The only network use was plain `GET` requests: the two published schemas, one
read-only GitHub API request for the MCPM schema's last change, and the package downloads of
the local checks. #24 stays open: the fresh-MCPHub install test (S2-MARKET-03) needs the
published package and was not run.

## Scenario to evidence

| Scenario | Evidence |
| --- | --- |
| AC-24-01 marker | `tests/test_registry_metadata.py`: the README holds exactly one `mcp-name:` marker, outside a code fence, before the status paragraph, equal to the `server.json` name; negative controls: marker removed, other name, duplicate, inside a code fence. `scripts/check_distribution.py` requires `mcp-name: <server.json name>` in the wheel `METADATA` and rejects another name; `tests/test_check_distribution.py` runs `main` on synthetic wheels: without the marker and with another name it exits before any install, with the marker it reaches the install step. The real built wheel passes (see the run below). |
| AC-24-02 shape | `server_problems` over the real file: current `$schema`, name pattern, description 1 to 100 characters with "Unofficial" and "not affiliated with the WLED project", title marking, exactly one package (`pypi`, identifier equal to the pyproject name, `uvx`, `stdio`), `repository.url` equal to the pyproject Repository URL, no `remotes`, no environment variables; 24 mutated copies are each reported. Live-schema run below. |
| AC-24-03 versions | `tests/test_version_source.py`: `server.json` is allowlisted for the literal and has its own test (`version` and `packages[0].version` equal `project.version`); mutating either, removing the package version or adding a second package is reported. The literal guard still passes: drafts and documents use `<version>`. |
| AC-24-04 stdio launch | `compose` builds the command line from the arguments: runtime `--isolated --python 3.13`, package `--transport stdio --config <path> --data-dir <path>`; both variables are required, `filepath`, not secret, with a description and no default, value or placeholder. No absolute path, IP address, host name, credential word or e-mail address in any value; `https://` appears only in `$schema`, `repository.url` and `websiteUrl`, on an allowed host. Mutations (path in a value, secret flag, default, other host, IP URL) are reported. |
| AC-24-05 HTTP | `remotes` is absent (mutation with a `remotes` entry reported); `docs/MARKETPLACE.md` has the section "HTTP is self-hosted" with the quickstart link, and the hosted copy carries the same link; every URL in the three listing files must be on `github.com`, `pypi.org` or the schema host. |
| AC-24-06 MCPM draft | `mcpm_problems`: required fields, kebab-case name, no `is_official`, no tools array, repository and licence equal to pyproject, unofficial wording, uvx command and arguments ending in `--transport stdio`, no pinned version and no current version literal, paths only through the `WLED_MCP_CONFIG` and `WLED_MCP_DATA_DIR` `${...}` references with required arguments and `/path/to/` examples, no http installation; 18 mutated copies are each reported. Live-schema run below. |
| AC-24-07 hosted copy | `hosted_problems`: status draft, unofficial and not affiliated wording, no image reference, impersonal, form fields stated as unverified, no endorsement claim, `<version>` placeholder, no literal version, allowed link hosts only; 9 mutations reported. |
| AC-24-08 status table | `status_rows`: one row per route in `MARKETPLACE.md`, each state in the vocabulary (or "not run") and none later than "validated locally". Rows: official registry and MCPM manifest validated locally, hosted copy draft, MCPHub fresh-install test not run. |
| AC-24-09 release preparation | Version bumped, `uv.lock` refreshed (only the project entry changed), CHANGELOG section written from `git log v0.1.2..HEAD`. Runs below. |
| AC-24-10 no external effect | The statement at the top of this file. |

## Live schema validation (one run, 2026-11-09)

Both schemas were downloaded with a plain `GET` into a directory outside the repository and
checked with `jsonschema` 4.26.0 (Python 3.13.2) from the project's locked development
environment, where it is already installed as a dependency of the MCP SDK; no dependency was
added or changed. The script ran in isolated mode (`python -I`) and read the schemas as data.

| Item | Observation |
| --- | --- |
| Official schema | `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`, JSON Schema draft-07, SHA-256 `3fba09590c99f61735d234822279f4223fab9e300c0a81e81c91ab62a4114de0` |
| `server.json` against it | `Draft7Validator`, 0 errors; its `$schema` equals the schema's `$id` |
| MCPM schema | `mcp-registry/schema/server-schema.json` of the MCPM repository, JSON Schema 2020-12, SHA-256 `db6a9e57a91c82a22c9ad6d57f65b8255dedb76e6dc24e9376501f821aa11b18`; last changed 2025-07-08 (commit `1885d056`, read with one `gh api` GET of the commit list for that path) |
| MCPM draft against it | `Draft202012Validator`, 0 errors |
| Negative controls | the same validators rejected a `server.json` copy with a 101-character description and no transport (2 errors) and an MCPM copy with name `WLED_MCP` and no licence (2 errors) |

Limits of this run: `format` keywords (`uri`) were not enforced because the optional format
packages are not installed; the schema does not forbid unknown properties, so a misspelled
optional key would pass (the offline tests pin the keys that matter); and the publisher's own
semantic checks (namespace ownership, package verification, `mcp-publisher validate`) were
**not run**. The result says the files are schema-valid, not that the registry will accept them.

## Local checks

Windows 11, Python 3.13.2, uv 0.11.14, `jsonschema` 4.26.0, from the checkout root, on the
branch merged with `origin/main` through the #149 and #166 merges.

| Command | Result |
| --- | --- |
| `uv sync --locked`; `uv run --frozen python scripts/check_lock.py` | passes (45 resolved packages) |
| `ruff check` and `ruff format --check` on the `ci.yml` path list | all checks passed; 124 files formatted |
| `uv run --frozen mypy` | no issues in 51 source files |
| `scripts/check_agent_setup.py`, `scripts/check_private_identifiers.py` | pass (286 files scanned, no denylist) |
| `uv run --frozen pytest` | 3147 passed, 30 skipped, 6 failed, 5 errors (see below) |
| `uv run --frozen python scripts/check_distribution.py` from a checkout path without spaces | PASS, 30 exact runtime versions: wheel metadata incl. the registry marker, clean install, setup commands, stdio, read-only profile, HTTP restart, uvx and the stdio hub example |

The six failures and five errors are the known local Windows ones
(`test_hw_http_probe.py::test_credential_from_environment_and_stdin_and_output_file` and five
tests of `test_invalid_url_*` in `test_inventory_client.py`); both files run on unchanged
`origin/main` (`ebe4711`, in a separate worktree) with the same 6 failures and 5 errors.
Linux CI is authoritative (DEC-020). The same `check_distribution.py` run in a checkout whose
path contains a space fails at its last step, the stdio hub example (`uv` reports a file
not found for the path cut at its first space); it fails identically on unchanged `origin/main`
(`08f38f0`), after every step this change touches had passed, so it is environmental and not
part of this change.

## Not run and limits

- No registry publication, namespace login, listing or submission; no installation test of any
  MCPHub (S2-MARKET-03); no look at the hosted directory's form (sign-in needed), so its
  fields and review criteria remain unverified.
- Whether a client turns the argument list into the intended command is not tested. In
  particular `--isolated` is a positional argument with a fixed value so that no client has to
  decide what to do with a valueless named flag; that is a reading of the schema, not an
  observation of a client.
- MCPM's handling of `${...}` references in `env` was not observed in a running MCPM or MCPHub;
  the draft follows the manifest schema and its field descriptions only.
- Only the Windows development machine ran these checks; the Linux CI run is the evidence for
  the full suite and the distribution check on the supported platform.

## Follow-up: release 0.2.0 preparation (2026-11-09)

The 0.1.3 preparation was merged but never tagged or published; [DEC-030](../DECISIONS.md#dec-030--milestone-closure-includes-a-minor-release)
requires a minor release for milestone M1, so the version became 0.2.0 in `pyproject.toml`,
`uv.lock` (project entry only) and both versions of `server.json`, and the changelog section was
rewritten. [ISSUE-24-DEC-003](../decisions/issue-24.md) narrows the listing routes to the
official MCP Registry; the MCPM and hosted-directory drafts stay unsubmitted.

- Live schema run repeated against freshly downloaded schemas: the official schema still has
  SHA-256 `3fba09590c99f61735d234822279f4223fab9e300c0a81e81c91ab62a4114de0` and the MCPM schema
  `db6a9e57a91c82a22c9ad6d57f65b8255dedb76e6dc24e9376501f821aa11b18`; `server.json` against the
  2025-12-11 schema 0 errors (`Draft7Validator`, `jsonschema` 4.26.0), the MCPM draft 0 errors,
  both negative controls rejected. The limits stated above apply unchanged (publisher checks not
  run, `format` keywords not enforced).
- The status table, `PUBLISHING.md` release chain and the changed status-vocabulary test are in
  the same change. The test now accepts the state "not planned" only for a row that cites
  ISSUE-24-DEC-003; the official registry row must stay "validated locally" and the install test
  "not run".
- README: the M1 features, tool count (27 to 31, from the tool contract and the registered tools)
  and the limitation sentence for features without a hardware run. The README still says there
  is no registry entry.
- Nothing was tagged, released, uploaded or submitted; `mcp-publisher` was not used.
