# Marketplace and public distribution plan

Research 2026-11-04, schema and tool observations updated 2026-11-09. Status: published to the official MCP Registry on 2026-11-09 (visible in its search API; MCPHub tab and install not observed); drafts for two other routes kept unsubmitted. Owning issue [#24](https://github.com/descipar/wled-mcp/issues/24); stage-2 tracker [#15](https://github.com/descipar/wled-mcp/issues/15). Recheck submission rules and actual hub behavior at release.

## What users will install

A self-hosted WLED MCP package/service; users provide their own controller configuration. Stdio uses the public Python package via uvx; HTTP uses the user's own deployed instance and `/mcp` address. No central cloud service that reaches everyone's controllers is planned. A package can support HTTP even if its registry entry describes stdio; never publish a nonexistent shared `remotes` endpoint, a private network address or a placeholder as a working public endpoint.

## Separate discovery routes

| Route | Observed mechanism | Prepared work | Not established |
| --- | --- | --- | --- |
| MCPHub self-hosted local marketplace | Source loads `servers.json`; UI labels the local source MCPM | Validate a catalog entry against the schema, prepare an MCPM contribution | Automatic MCPM-to-MCPHub synchronization or timing |
| Official MCP Registry tab in MCPHub | Hub proxies `registry.modelcontextprotocol.io/v0.1/servers` | Public package plus ownership metadata, authenticated namespace, validated `server.json` | That a listing builds the package or installs cleanly in every hub version |
| Public `mcphub.app/registry` directory | Search page with a submit form; submission redirects to sign-in | English project/install/tool metadata and exact released artifact references | Form fields after login, review criteria, acceptance, linkage to a self-hosted catalog |

The routes are not interchangeable: do not claim all MCPHub users see a listing because a different directory accepted it.

## Primary sources

[MCPHub local market service](https://github.com/samanhappy/mcphub/blob/main/src/services/marketService.ts), [marketplace UI](https://github.com/samanhappy/mcphub/blob/main/frontend/src/pages/MarketPage.tsx), [registry controller](https://github.com/samanhappy/mcphub/blob/main/src/controllers/registryController.ts), [local catalog](https://github.com/samanhappy/mcphub/blob/main/servers.json), [MCPM contribution instructions](https://github.com/pathintegral-institute/mcpm.sh/blob/main/mcp-registry/README.md) (older CLI examples: validate the current schema instead of copying commands), [hosted directory](https://www.mcphub.app/registry/search) and [submission page](https://www.mcphub.app/registry/submit), [registry quickstart](https://modelcontextprotocol.io/registry/quickstart), [package types](https://modelcontextprotocol.io/registry/package-types), [remote servers](https://modelcontextprotocol.io/registry/remote-servers), [publishing automation](https://modelcontextprotocol.io/registry/github-actions). External maintainers decide admission and review timing.

## Identities and artifacts

- Repository `descipar/wled-mcp`; visibility is an owner release decision ([#23](https://github.com/descipar/wled-mcp/issues/23), [#25](https://github.com/descipar/wled-mcp/issues/25)).
- Registry name `io.github.descipar/wled-mcp` ([DEC-012](DECISIONS.md#dec-012--project-and-package-identity)); verify namespace ownership and naming rules with the publisher tooling.
- Listing texts state "unofficial, not affiliated with the WLED project" and use no WLED logo (DEC-012).
- PyPI `wled-mcp` is live since 0.1.2 (the registry ownership marker is in the package since 0.2.0, see the [changelog](../CHANGELOG.md)); the OCI repository name is decided with [#156](https://github.com/descipar/wled-mcp/issues/156). A repository name proves neither ownership nor availability.
- The console command stays `wled-mcp`; use uvx `--from` where names differ.
- Build wheel/sdist and versioned amd64/arm64 OCI artifacts first, test a clean install, and use immutable version/digest references in release metadata.

The official registry supports public PyPI packages and verifies the namespace marker in the package's rendered README/description; this project needs no npm package to enter a catalog. Prepared since the first release after 0.1.2: the marker in the README and the root [`server.json`](../server.json), validated locally against the published schema. The registry's `remotes` route needs a publicly accessible endpoint, which a per-user self-hosted HTTP deployment is not: prefer package metadata and document self-hosted HTTP separately; revisit only for a commissioned hosted product.

## Catalog content

A short English summary, author/repository/license/support links, keywords (WLED, LED, smart lighting), actual tested tools, supported transports and hardware/firmware limits, the required config/data paths and how users supply controller addresses. Required secrets are marked as secrets in catalog input metadata, with no real credentials or private defaults. Prefer clear descriptions to a long tool dump; read-only setup must work before any lighting change. Do not mark `is_official` true or use WLED affiliation language without real endorsement.

## Observed schemas and tools (2026-11-09)

- Official registry `server.json` schema `2025-12-11` (`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`, draft-07); `description` at most 100 characters. `mcp-publisher` was observed at v1.8.8 on 2026-11-06; it is not installed or run in this repository, and its `validate` command sends the file to an external service, so local validation uses the published schema with a generic validator.
- MCPM manifest schema (`mcp-registry/schema/server-schema.json`, JSON Schema 2020-12, last changed 2025-07-08). Required: `name` (kebab-case), `display_name`, `description`, `repository`, `license`, `installations`.
- MCPHub's `servers.json` uses the same manifest shape; the draft fits both and was not compared with a chosen MCPHub version.
- Evidence and commands: [validation/stage-2-release.md](validation/stage-2-release.md).

## Status per route

Vocabulary: **draft**, **validated locally**, **submitted**, **accepted**, **visible**, **install-tested**, plus **not planned** for a route the owner dropped ([ISSUE-24-DEC-003](decisions/stage-2.md)) and **not run** for an unattempted check. The goal is findability in the MCPHub registry (the official MCP Registry) after milestone M1. A row states only what was done; the next state needs its own evidence, and states are per route. For the official registry **accepted** means the publish command succeeded and **visible** means its own search API returns the entry; neither says an MCPHub registry tab shows it or that an install works.

| Route | State | What exists | Next step (owner instruction needed) |
| --- | --- | --- | --- |
| Official MCP Registry | visible | [`server.json`](../server.json) published with `mcp-publisher`; the registry search API returns one active, latest entry `io.github.descipar/wled-mcp` for the released version, no `remotes` ([record](validation/stage-2-release.md#release-and-registry-publication-2026-11-09)); an MCPHub registry tab was not observed | none for the entry; a new release needs its own owner-instructed publish ([PUBLISHING.md](PUBLISHING.md#registry-listing-after-the-pypi-release)) |
| MCPM / MCPHub local catalog | not planned | [`listings/mcpm-wled-mcp.json`](listings/mcpm-wled-mcp.json), an unsubmitted draft that passed the MCPM schema; dropped for now by ISSUE-24-DEC-003 | none; the owner may reinstate the route |
| Hosted mcphub.app directory | not planned | [`listings/mcphub-app-submission.md`](listings/mcphub-app-submission.md), an unsubmitted draft; form fields unverified (sign-in required); dropped for now by ISSUE-24-DEC-003 | none; the owner may reinstate the route |
| MCPHub fresh-install test (S2-MARKET-03) | not run | partial evidence only: the command composed from `server.json` was run locally with a stdio client and started the published package ([record](validation/stage-2-release.md#launch-check-of-the-composed-command-2026-11-10)); no hub involved; the observed MCPHub install dialog does not generate a runnable entry from the listing without manual edits ([record](validation/stage-2-release.md#mcphub-registry-tab-observed-install-dialog-2026-11-10)) | waived by the owner, ISSUE-24-DEC-005: generated dialog observed, hub-side start not observed; not "install-tested" |

## Where the drafts live

- `server.json` (repository root): registry metadata with the version twice; both must equal `project.version` (`tests/test_registry_metadata.py`; the literal is allowed in `tests/test_version_source.py`).
- `docs/listings/`: drafts for the two routes not planned; read by no tool, no version literal, not kept current for a submission.

## HTTP is self-hosted

The registry entry has no `remotes`: a per-user HTTP deployment is not a public endpoint, and no private or placeholder URL is listed. The listings point to the [quickstart for the Streamable HTTP service](QUICKSTARTS.md#quickstart-streamable-http-service).

## Claude Desktop MCPB bundle

Each release workflow run also builds a Claude Desktop bundle, `wled-mcp-<version>.mcpb` ([#151](https://github.com/descipar/wled-mcp/issues/151), requirement DIST-04, [contract](contract/mcpb-bundle.md)). **The bundle is built along with each release, not tested by the project, no warranty.** No Claude Desktop install run was made; whether Claude Desktop accepts a Python-type bundle that starts `uvx` was not verified.

- **What it is.** An MCPB manifest (version 0.3) that makes Claude Desktop run the released PyPI package through `uvx`, pinned to the release version, over stdio only. No server code, secret, inventory, device address or HTTP service.
- **Prerequisites.** `uv` (`uvx`) on the PATH Claude Desktop sees; an inventory made with `wled-mcp config init` ([README](../README.md#try-it)); an existing data directory. The install dialog asks for exactly these two paths.
- **Flow.** The release workflow builds the bundle from the tagged version after the release guard in its own job; a separate job attaches `wled-mcp-<version>.mcpb` and `wled-mcp-<version>.mcpb.sha256` to the GitHub release only after the PyPI upload succeeded and never replaces an asset. A bundle-job failure does not affect the PyPI upload ([PUBLISHING.md](PUBLISHING.md#mcpb-bundle-151)). The jobs first ran with the release of 2026-11-13, which carries the first bundle.
- **Verify the download.** `sha256sum --check wled-mcp-<version>.mcpb.sha256` or, in PowerShell, compare `Get-FileHash -Algorithm SHA256 wled-mcp-<version>.mcpb` with the file's hash. The bundle is unsigned and has no attestation, and the checksum comes from the same workflow: it detects a damaged download and does not prove origin.
- **Manifest facts.** Validated against a vendored copy of the upstream JSON schema (tag v2.1.2, [provenance](SOURCES.md#issue-151-mcpb-manifest-schema)); `uvx` runs `--isolated --python 3.13 --from wled-mcp==<version> wled-mcp --transport stdio`. Marked unofficial, not affiliated with the WLED project, no icon (DEC-012).
- **Directories.** Submitting the bundle to any directory is an owner action, neither planned nor done ([DEC-023](DECISIONS.md#dec-023--staged-first-public-release)); it adds no row to the status table.

## Release and listing sequence

1. Complete the relevant stage-1 evidence and stage-2 Launch requirements; choose license, names and supported versions.
2. Build one reviewable release candidate, public docs and validated metadata and submission drafts. Inspect history and artifacts for private content before a visibility change (a README edit does not remove secrets from Git history).
3. Exercise clean installs and catalog-generated configuration in an isolated MCPHub context, mocked controllers first; real hardware validation is identified separately.
4. Obtain the concrete release instruction for the reviewed candidate and the intended visibility, artifact and submission actions; an issue mentioning a marketplace is not one.
5. Publish the authorized artifacts, authenticate the namespace, publish registry metadata and make authorized submissions through their supported routes; send no external maintainer message without an instruction covering it.
6. Verify a real install from the published package/image; query each selected route, record version and install behavior, and keep review and propagation delays explicit.

Evidence for one state does not imply the next, and an external rejection is not fixed by a misleading metadata claim. The official registry entry was published on 2026-11-09 on the owner's step-by-step instructions ([record](validation/stage-2-release.md#release-and-registry-publication-2026-11-09)); no MCPM or hosted-directory submission and no external issue or PR was sent.
