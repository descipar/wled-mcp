# Security policy

wled-mcp is a privately maintained hobby project. It is provided "as is" under the
[Apache License 2.0](LICENSE) (see Sections 7 and 8: no warranty, no liability). Use it
at your own risk.

- There is no security support: no private reporting channel, no response commitment,
  no guaranteed fixes, no advisories and no bug bounty.
- You may report a problem as a regular
  [GitHub issue](https://github.com/descipar/wled-mcp/issues). Do not include exploit
  details, credentials or information about your own installation. You are also free to
  fix it in a fork under the license terms.
- Run the Streamable HTTP service only on a network you trust, with its access token
  and Host/Origin allowlist configured as described in the README. Do not expose it to
  the internet.

## Practical limits

A bounded source review and automated static checks are recorded in
[issue #181 validation](docs/validation/issue-181.md). This was one pass over selected
areas, not an exhaustive audit or a security guarantee.

- Hub authentication does not protect the service's direct endpoint. The service's
  own bearer credential and exact Host/Origin allowlists are required. A caller with
  that credential can bypass hub-specific permissions; server profiles still apply.
- HTTP has no built-in TLS, per-user identity or rate limiting. Use a trusted network
  and protect the credential in transit. The defaults bind to loopback; changing the
  binding requires an explicit Host allowlist. Do not expose the service to the internet.
- The operator controls the inventory and DNS. Configured HTTP(S) root URLs may use
  non-default ports and reach any address the process can reach; inventory validation
  is not an outbound firewall. Redirects and environment proxies are disabled. Limit
  process network access to the controllers it needs.
- Keep configuration, token files and the data directory private and operator-owned.
  Created storage files use 0600 and directories 0700 on POSIX; existing permissions
  are not repaired and Windows permission semantics differ. Shared storage with a
  hostile concurrent writer is not supported ([#220](https://github.com/descipar/wled-mcp/issues/220)).
- Results intentionally carry lighting content, configured names/IDs and discovery
  candidates. Do not put credentials or installation details in names, presets or
  imported content, or paste those results into public reports. Diagnostic redaction
  is not a general-purpose content scrubber.

Ruff security rules and CodeQL supplement review. Dependabot proposes weekly dependency
and action updates for review; updates are not automatically merged or deployed. These
checks do not create security support or a commitment to triage or respond.
