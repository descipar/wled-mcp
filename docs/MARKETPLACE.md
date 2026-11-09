# Marketplace and public distribution plan

Research date: 2026-11-04, observations of schemas and tools updated 2026-11-09. Status: published to the official
MCP Registry on 2026-11-09 (visible in its search API; MCPHub tab and install not observed), drafts for two other routes kept unsubmitted. Owning issue [#24](https://github.com/descipar/wled-mcp/issues/24); stage-2 tracker [#15](https://github.com/descipar/wled-mcp/issues/15). Recheck submission rules and actual installed hub behavior at release.

## What users will install

The product is a self-hosted WLED MCP package/service. Users provide their own WLED controller configuration. Stdio uses a public-consumption Python package via uvx; HTTP uses their own deployed instance and `/mcp` address. We are not planning a central cloud service that can reach everyone's LED controllers.

A public package can support HTTP even if its registry package entry describes stdio execution. Do not publish a nonexistent shared `remotes` endpoint just to advertise HTTP, and never publish a private network address or a placeholder as a working public endpoint.

## Separate discovery routes

| Route | Observed mechanism | Prepared work | What is not established |
| --- | --- | --- | --- |
| MCPHub self-hosted local marketplace | Current source loads `servers.json`; UI labels the local source MCPM | Validate a catalog entry against actual schema and prepare an MCPM contribution; establish how a chosen MCPHub version receives it | No verified automatic MCPM-to-MCPHub synchronization or timing guarantee |
| Official MCP Registry tab in MCPHub | Current hub proxies `registry.modelcontextprotocol.io/v0.1/servers` | Public package plus ownership metadata, authenticated namespace, validated `server.json`, publisher workflow | Listing does not host/build the package or prove clean installation in every hub version |
| Public `mcphub.app/registry` directory | Search page offers a submit form; submission redirects to sign-in | Prepare concise English project/install/tool metadata and exact released artifact references | Form fields after login, review criteria, acceptance and linkage to self-hosted local catalog were not verified |

These routes are not interchangeable. Record current behavior with source/version evidence and do not claim all MCPHub users can see a listing merely because a different directory accepted it.

## Researched primary sources

- [MCPHub local market service](https://github.com/samanhappy/mcphub/blob/main/src/services/marketService.ts): loads local `servers.json`.
- [MCPHub marketplace UI](https://github.com/samanhappy/mcphub/blob/main/frontend/src/pages/MarketPage.tsx): local/MCPM and official-registry tabs.
- [MCPHub registry controller](https://github.com/samanhappy/mcphub/blob/main/src/controllers/registryController.ts): official-registry proxy.
- [Current local catalog](https://github.com/samanhappy/mcphub/blob/main/servers.json): inspect actual entries/schema before drafting an addition.
- [MCPM registry contribution instructions](https://github.com/pathintegral-institute/mcpm.sh/blob/main/mcp-registry/README.md): current issue/PR contribution paths and schema reference.
- [Hosted MCPHub directory](https://www.mcphub.app/registry/search) and [submission page](https://www.mcphub.app/registry/submit): authenticated external submission route.
- [Official MCP Registry quickstart](https://modelcontextprotocol.io/registry/quickstart), [package types](https://modelcontextprotocol.io/registry/package-types), [remote servers](https://modelcontextprotocol.io/registry/remote-servers), [publishing automation](https://modelcontextprotocol.io/registry/github-actions).

The MCPM guide contains older CLI examples; validate the current schema/tools instead of copying commands untested. External catalog maintainers decide admission and review timing.

## Proposed identities and artifacts

- Repository: `descipar/wled-mcp`; its visibility is an owner release decision ([#23](https://github.com/descipar/wled-mcp/issues/23), [#25](https://github.com/descipar/wled-mcp/issues/25)).
- Registry name: `io.github.descipar/wled-mcp` ([DEC-012](DECISIONS.md#dec-012--project-and-package-identity)); verify namespace ownership and current naming rules with the publisher tooling before preparing actual release metadata.
- Listing texts and package summaries state "unofficial, not affiliated with the WLED project" and use no WLED logo or logo imitation (DEC-012).
- PyPI distribution `wled-mcp` is live since 0.1.2 (the ownership marker for the registry is added in the next release, see the [changelog](../CHANGELOG.md)); the OCI repository name is decided/checked with the container work ([#156](https://github.com/descipar/wled-mcp/issues/156)). A repository name alone proves neither ownership nor availability.
- Console command can remain `wled-mcp` even if a distinct distribution name is needed; use uvx `--from` explicitly where names differ.
- Build wheel/sdist and versioned amd64/arm64 OCI artifacts first, then test clean install. Use immutable version/digest references in release metadata, and document user-driven updates.

The official registry currently supports public PyPI packages and verifies the matching MCP namespace marker in the package's rendered README/description. It also supports other package types, but this Python project does not need npm merely to enter a catalog. Prepared with the first release after 0.1.2: the marker in the README and the root [`server.json`](../server.json), validated locally against the published schema (see below).

For the official registry's `remotes` route the documented endpoint must actually be publicly accessible. Our private, per-user self-hosted HTTP deployment is not such a central remote. Prefer package metadata for discovery and document self-hosted HTTP separately. Revisit only if a real supported hosted product is commissioned.

## Proposed catalog content

Prepare a short English summary, author/repository/license/support links, keywords such as WLED/LED/smart lighting, actual tested tools, supported transports and hardware/firmware limits. Show exact required config/data paths and how users supply controller addresses. Required secrets must be marked as secrets in supported catalog input metadata, with no real credentials or private defaults.

Prefer clear descriptions over a long undifferentiated tool dump. Read-only setup must work before a user invokes lighting changes. Do not mark `is_official` true or use WLED affiliation language without real endorsement.

## Observed schemas and tools (2026-11-09)

- Official registry `server.json` schema: `2025-12-11`
  (`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`, JSON Schema
  draft-07). `description` is limited to 100 characters. The publisher tool `mcp-publisher`
  was observed at v1.8.8 on 2026-11-06 (release page); it is not installed or run in this repository.
  Its `validate` command sends the file to an external service, so local validation uses the
  published schema with a generic JSON Schema validator instead.
- MCPM manifest schema (`mcp-registry/schema/server-schema.json` in the MCPM repository, JSON
  Schema 2020-12): last changed 2025-07-08. Required fields: `name` (kebab-case),
  `display_name`, `description`, `repository`, `license`, `installations`.
- MCPHub's own `servers.json` uses the same manifest shape; the draft below is written to fit
  both and has not been compared with a chosen MCPHub version.
- Evidence and the exact commands: [validation/issue-24.md](validation/issue-24.md).

## Status per route

Vocabulary as above, plus **not planned** for a route the owner dropped for now
([ISSUE-24-DEC-003](decisions/issue-24.md)) and **not run** for a check that has not been
attempted. The goal is that the server is findable in the MCPHub registry, which is the
official MCP Registry, after milestone M1 closes. A row states only what was done; the next
state needs its own evidence.

| Route | State | What exists | Next step (owner instruction needed) |
| --- | --- | --- | --- |
| Official MCP Registry | visible | [`server.json`](../server.json) published with `mcp-publisher`; the registry search API returns one active, latest entry `io.github.descipar/wled-mcp` for the released version, no `remotes` ([record](validation/issue-24.md#release-and-registry-publication-2026-11-09)); an MCPHub registry tab was not observed | none for the entry; a new release needs its own owner-instructed publish ([PUBLISHING.md](PUBLISHING.md#registry-listing-after-the-pypi-release)) |
| MCPM / MCPHub local catalog | not planned | [`listings/mcpm-wled-mcp.json`](listings/mcpm-wled-mcp.json), an unsubmitted draft that passed the MCPM schema; dropped for now by ISSUE-24-DEC-003 | none; the owner may reinstate the route |
| Hosted mcphub.app directory | not planned | [`listings/mcphub-app-submission.md`](listings/mcphub-app-submission.md), an unsubmitted draft; form fields unverified (sign-in required); dropped for now by ISSUE-24-DEC-003 | none; the owner may reinstate the route |
| MCPHub fresh-install test (S2-MARKET-03) | not run | partial evidence only: the command composed from `server.json` was run locally with a stdio client and started the published package ([record](validation/issue-24.md#launch-check-of-the-composed-command-2026-11-10)); no hub involved | the hub-side test is run separately against a hub and is not claimed here; issue #24 stays open for it |

## Where the drafts live

- `server.json` (repository root): the registry metadata. It contains the version twice; both
  must equal `project.version` (`tests/test_registry_metadata.py`, and the literal is allowed
  there in `tests/test_version_source.py`).
- `docs/listings/`: drafts for the two routes that are not planned; they are not read by any
  tool, carry no version literal and are not kept current for a submission.

## HTTP is self-hosted

The registry entry has no `remotes`: a per-user HTTP deployment is not a public endpoint, and
no private or placeholder URL is listed. The listings point to the self-hosted setup instead:
[quickstart for the Streamable HTTP service](QUICKSTARTS.md#quickstart-streamable-http-service).

## Release and listing sequence

1. Complete relevant stage-1 evidence and stage-2 Launch requirements. Choose license, names and supported versions.
2. Build one reviewable release candidate, public docs and validated metadata/submission drafts. Inspect current history/artifacts for private content before a visibility change; a README edit does not remove secrets from Git history.
3. Exercise clean installs and catalog-generated configuration in an isolated MCPHub context. Test mocked controllers first; identify any later real hardware validation separately.
4. Obtain the concrete release instruction for the reviewed candidate and intended visibility/artifact/submission actions. Do not publish merely because an issue mentions marketplace.
5. Publish the authorized artifacts, authenticate the namespace and publish registry metadata; make authorized external submissions through their actual supported routes. Do not send external maintainer messages without an instruction covering that submission.
6. Verify real install from the published package/image. Query and inspect each selected discovery route, record version and installation behavior, and keep review/propagation delays explicit.

Status vocabulary: **draft**, **validated locally**, **submitted**, **accepted**, **visible**, **install-tested**. Evidence for one state does not imply the next, and an external rejection is not fixed by making a misleading metadata claim. The states are per route. For the official MCP Registry, **accepted** means the publish command succeeded and **visible** means the registry's own search API returns the entry; neither says that an MCPHub registry tab shows it or that an install works.

The official registry entry was published on 2026-11-09 on the owner's step-by-step instructions ([validation/issue-24.md](validation/issue-24.md#release-and-registry-publication-2026-11-09)); no MCPM or hosted-directory submission and no external issue or PR was sent.
