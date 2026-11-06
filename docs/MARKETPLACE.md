# Marketplace and public distribution plan

Research date: 2026-11-04. Status: planning only. Owning issue [#24](https://github.com/descipar/wled-mcp/issues/24); stage-2 tracker [#15](https://github.com/descipar/wled-mcp/issues/15). Recheck submission rules and actual installed hub behavior at release.

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
- Registry namespace placeholder: `io.github.<publisher>/wled-mcp`; choose the publishing identity and verify ownership/current naming rules before preparing actual release metadata.
- PyPI distribution and OCI repository names: decide/check before release; repository name alone proves neither ownership nor availability. PyPI `wled-mcp` returned 404 during this research, which reserves nothing and does not establish a final name.
- Console command can remain `wled-mcp` even if a distinct distribution name is needed; use uvx `--from` explicitly where names differ.
- Build wheel/sdist and versioned amd64/arm64 OCI artifacts first, then test clean install. Use immutable version/digest references in release metadata, and document user-driven updates.

The official registry currently supports public PyPI packages and verifies the matching MCP namespace marker in the package's rendered README/description. Prepare that marker only after identity is decided. It also supports other package types, but this Python project does not need npm merely to enter a catalog. Generate/validate metadata against the current schema with the publisher tooling during implementation.

For the official registry's `remotes` route the documented endpoint must actually be publicly accessible. Our private, per-user self-hosted HTTP deployment is not such a central remote. Prefer package metadata for discovery and document self-hosted HTTP separately. Revisit only if a real supported hosted product is commissioned.

## Proposed catalog content

Prepare a short English summary, author/repository/license/support links, keywords such as WLED/LED/smart lighting, actual tested tools, supported transports and hardware/firmware limits. Show exact required config/data paths and how users supply controller addresses. Required secrets must be marked as secrets in supported catalog input metadata, with no real credentials or private defaults.

Prefer clear descriptions over a long undifferentiated tool dump. Read-only setup must work before a user invokes lighting changes. Do not mark `is_official` true or use WLED affiliation language without real endorsement.

## Release and listing sequence

1. Complete relevant stage-1 evidence and stage-2 Launch requirements. Choose license, names and supported versions.
2. Build one reviewable release candidate, public docs and validated metadata/submission drafts. Inspect current history/artifacts for private content before a visibility change; a README edit does not remove secrets from Git history.
3. Exercise clean installs and catalog-generated configuration in an isolated MCPHub context. Test mocked controllers first; identify any later real hardware validation separately.
4. Obtain the concrete release instruction for the reviewed candidate and intended visibility/artifact/submission actions. Do not publish merely because an issue mentions marketplace.
5. Publish the authorized artifacts, authenticate the namespace and publish registry metadata; make authorized external submissions through their actual supported routes. Do not send external maintainer messages without an instruction covering that submission.
6. Verify real install from the published package/image. Query and inspect each selected discovery route, record version and installation behavior, and keep review/propagation delays explicit.

Status vocabulary: **draft**, **validated locally**, **submitted**, **accepted**, **visible**, **install-tested**. Evidence for one state does not imply the next, and an external rejection is not fixed by making a misleading metadata claim.

No package, image, registry record, external issue/PR or hosted-directory submission was published by this planning task.
