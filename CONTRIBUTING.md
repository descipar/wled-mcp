# Contributing

wled-mcp is maintained best effort. There is no commitment to answer, review or merge
within any time frame; see [Support](README.md#support).

## Issues

- Use [GitHub issues](https://github.com/descipar/wled-mcp/issues) for bugs, questions
  and proposals; there is no other channel.
- Do not post details of your own installation: no credentials or tokens, private
  addresses, host names, device or network names, or personal names. Use synthetic
  examples such as `wled-desk.example.invalid` or `192.0.2.10`.
- Security problems follow [SECURITY.md](SECURITY.md): there is no security support
  and no private reporting channel, so do not include exploit details.

## Pull requests

- Keep a change focused and describe its behavior, the requirement or issue it
  addresses, and how you validated it.
- Run the local checks from [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#checks-and-build)
  before you open a pull request; CI runs the same checks.
- Tests use mocks or synthetic loopback devices and never contact LAN devices or real
  controllers.
- `scripts/check_private_identifiers.py` must pass: no private addresses, home paths,
  local host names, MAC addresses or personal e-mail addresses in the repository.
- The agent workflow described in [AGENTS.md](AGENTS.md) and
  [docs/AGENT-WORKFLOW.md](docs/AGENT-WORKFLOW.md) is how the maintainer works with
  coding agents; human contributions do not need to follow it. Design decisions are
  recorded in [docs/DECISIONS.md](docs/DECISIONS.md).

## License

The project is licensed under the [Apache License 2.0](LICENSE). As stated in its
Section 5, a contribution you intentionally submit for inclusion is licensed under the
same terms, unless you explicitly state otherwise.
