"""Scan issue and pull request text, including edit histories, for private identifiers.

Issue #90 (DEC-015 item 1a, DEC-018).

An on-demand, read-only check that runs before the repository visibility changes. It
reads every issue and pull request of a GitHub repository, open and closed, through the
authenticated ``gh`` CLI (GraphQL queries only) and applies the rules and the private
denylist of ``scripts/check_private_identifiers.py`` to:

- titles and previous titles (rename events), bodies, issue/PR comments, PR review
  bodies and PR review (inline) comments;
- every revision in the edit history (``userContentEdits``) of each of these;
- PR head/base branch names and the repository's label names and descriptions.

Commit content is out of scope (DEC-014). Findings name a locator such as
``pr #30 review 2 comment 1 revision 1:3: ipv4-private`` or ``denylist entry 2``, never
the matched value; ``--show-values`` prints values for local use only. Revisions are
numbered from the oldest (1). A deleted revision has no text: it is counted and noted as
not scannable, never as clean.

The script never builds a mutation, never uses a REST method and never passes
``-X``/``--method`` to ``gh``. It is not run in CI: it needs network access and its
result depends on issue activity rather than on the commit under test. The mocked tests
in ``tests/test_issue_content.py`` run in CI.

Standard library only. Exit code 0 when no findings, 1 with findings, 2 when the
content cannot be checked completely (``gh`` missing or failing, GraphQL errors, an
unexpected response shape, an invalid denylist).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCANNER_PATH = Path(__file__).resolve().with_name("check_private_identifiers.py")
DEFAULT_REPO = "descipar/wled-mcp"
PAGE = 50  # nested connections; three levels stay far below GitHub's node limit
GH_TIMEOUT = 120

RunQuery = Callable[[str, dict[str, Any]], dict[str, Any]]


def _load_scanner() -> ModuleType:
    """The repository scanner, loaded by path (scripts are not a package)."""
    name = "check_private_identifiers"
    loaded = sys.modules.get(name)
    if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() == SCANNER_PATH:
        return loaded
    spec = importlib.util.spec_from_file_location(name, SCANNER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SCANNER_PATH.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner()
CheckError: type[Exception] = scanner.CheckError


def _connection(selection: str) -> str:
    return f"pageInfo {{ hasNextPage endCursor }} nodes {{ {selection} }}"


EDIT = "editedAt diff"
EDITS = f"userContentEdits(first: {PAGE}) {{ {_connection(EDIT)} }}"
RENAMES_ARGS = ", itemTypes: [RENAMED_TITLE_EVENT]"
RENAME = "... on RenamedTitleEvent { previousTitle }"
COMMENT = f"id body {EDITS}"
REVIEW = f"{COMMENT} comments(first: {PAGE}) {{ {_connection(COMMENT)} }}"
ISSUE_FIELDS = (
    f"id number title body {EDITS} "
    f"timelineItems(first: {PAGE}{RENAMES_ARGS}) {{ {_connection(RENAME)} }} "
    f"comments(first: {PAGE}) {{ {_connection(COMMENT)} }}"
)
PR_FIELDS = (
    f"{ISSUE_FIELDS} headRefName baseRefName reviews(first: {PAGE}) {{ {_connection(REVIEW)} }}"
)
REPOSITORY_LIST = (
    "query($owner: String!, $name: String!, $after: String) "
    "{{ repository(owner: $owner, name: $name) "
    "{{ {field}(first: 100, after: $after) {{ {connection} }} }} }}"
)
ITEM_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!) "
    "{{ repository(owner: $owner, name: $name) {{ {kind}(number: $number) {{ {fields} }} }} }}"
)
NODE_PAGE = (
    "query($id: ID!, $after: String) "
    "{{ node(id: $id) {{ ... on {typename} "
    "{{ {field}(first: {page}, after: $after{args}) {{ {connection} }} }} }} }}"
)


def gh_query(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """Run one read-only GraphQL query through ``gh api graphql``.

    ``gh`` handles authentication; this function never sees a token. Its stderr is not
    echoed because it can quote the request or response.
    """
    if not query.lstrip().startswith("query") or "mutation" in query:
        raise CheckError("refusing a GraphQL document that is not a read-only query")
    argv = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is None:
            continue
        flag = "-F" if isinstance(value, int) else "-f"
        argv += [flag, f"{key}={value}"]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GH_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        raise CheckError("gh CLI not found; install it and run `gh auth login`") from None
    except (OSError, subprocess.SubprocessError) as exc:
        raise CheckError(f"gh api graphql could not run ({type(exc).__name__})") from None
    if result.returncode != 0:
        raise CheckError(
            f"gh api graphql exited with code {result.returncode}; check `gh auth status` "
            "and the repository name"
        )
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise CheckError("gh api graphql returned no JSON document") from None
    if not isinstance(response, dict):
        raise CheckError("gh api graphql returned no JSON object")
    return response


def _data(response: dict[str, Any]) -> dict[str, Any]:
    errors = response.get("errors")
    if errors:
        kinds = sorted(
            {str(error.get("type", "unknown")) for error in errors if isinstance(error, dict)}
            or {"unknown"}
        )
        raise CheckError(f"GraphQL returned {len(errors)} error(s): {', '.join(kinds)}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise CheckError("GraphQL response lacks data")
    return data


def _field(node: Any, key: str) -> Any:
    if not isinstance(node, dict) or key not in node:
        raise CheckError(f"GraphQL response lacks the field {key!r}")
    return node[key]


def _page(connection: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Nodes of one page and the cursor of the next page (``None`` on the last page)."""
    nodes = _field(connection, "nodes")
    info = _field(connection, "pageInfo")
    has_next = _field(info, "hasNextPage")
    if not isinstance(nodes, list) or not isinstance(has_next, bool):
        raise CheckError("GraphQL connection has invalid nodes or pageInfo")
    if not all(isinstance(node, dict) for node in nodes):
        raise CheckError("GraphQL connection holds null nodes")
    cursor = _field(info, "endCursor") if has_next else None
    if has_next and not isinstance(cursor, str):
        raise CheckError("GraphQL pageInfo has a next page but no cursor")
    return nodes, cursor


@dataclass
class Report:
    findings: list[Any] = field(default_factory=list)  # check_private_identifiers.Finding
    notes: list[str] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)


class IssueScan:
    def __init__(self, run_query: RunQuery, owner: str, name: str, denylist: list[str]):
        self.run_query = run_query
        self.repository = {"owner": owner, "name": name}
        self.denylist = denylist
        self.report = Report()

    # ------------------------------------------------------------------ transport

    def query(self, document: str, variables: dict[str, Any]) -> dict[str, Any]:
        return _data(self.run_query(document, variables))

    def repository_nodes(self, field_name: str, selection: str) -> list[dict[str, Any]]:
        document = REPOSITORY_LIST.format(field=field_name, connection=_connection(selection))
        nodes: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            data = self.query(document, {**self.repository, "after": cursor})
            repository = _field(data, "repository")
            if repository is None:
                raise CheckError("repository not found or not accessible")
            page, cursor = _page(_field(repository, field_name))
            nodes += page
            if cursor is None:
                return nodes

    def all_nodes(
        self,
        owner: dict[str, Any],
        typename: str,
        field_name: str,
        selection: str,
        args: str = "",
    ) -> list[dict[str, Any]]:
        """Every node of ``owner``'s connection, fetching further pages by node ID."""
        nodes, cursor = _page(_field(owner, field_name))
        document = NODE_PAGE.format(
            typename=typename,
            field=field_name,
            page=PAGE,
            args=args,
            connection=_connection(selection),
        )
        while cursor is not None:
            data = self.query(document, {"id": _field(owner, "id"), "after": cursor})
            page, cursor = _page(_field(_field(data, "node"), field_name))
            nodes += page
        return nodes

    # ------------------------------------------------------------------- scanning

    def text(self, locator: str, value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            raise CheckError(f"{locator}: GraphQL text field is not a string")
        self.report.findings += scanner.scan_text(locator, value)
        self.report.findings += scanner.scan_denylist(locator, value, self.denylist)

    def edits(self, locator: str, node: dict[str, Any], typename: str) -> None:
        edits = self.all_nodes(node, typename, "userContentEdits", EDIT)
        edits.sort(key=lambda edit: str(edit.get("editedAt") or ""))
        for number, edit in enumerate(edits, start=1):
            self.report.counts["revisions"] += 1
            diff = _field(edit, "diff")
            if diff is None:
                self.report.counts["deleted revisions"] += 1
                self.report.notes.append(f"{locator} revision {number}: deleted, not scannable")
                continue
            self.text(f"{locator} revision {number}", diff)

    def editable(self, locator: str, node: dict[str, Any], typename: str) -> None:
        self.text(locator, _field(node, "body"))
        self.edits(locator, node, typename)

    def item(self, kind: str, number: int) -> None:
        pull = kind == "pr"
        document = ITEM_QUERY.format(
            kind="pullRequest" if pull else "issue", fields=PR_FIELDS if pull else ISSUE_FIELDS
        )
        data = self.query(document, {**self.repository, "number": number})
        node = _field(_field(data, "repository"), "pullRequest" if pull else "issue")
        if not isinstance(node, dict):
            raise CheckError(f"{kind} #{number} disappeared during the scan")
        typename = "PullRequest" if pull else "Issue"
        base = f"{kind} #{number}"
        self.report.counts["pull requests" if pull else "issues"] += 1
        self.text(f"{base} title", _field(node, "title"))
        renames = self.all_nodes(node, typename, "timelineItems", RENAME, RENAMES_ARGS)
        for index, rename in enumerate(renames, start=1):
            self.report.counts["title renames"] += 1
            self.text(f"{base} title-rename {index}", _field(rename, "previousTitle"))
        self.editable(f"{base} body", node, typename)
        for index, comment in enumerate(
            self.all_nodes(node, typename, "comments", COMMENT), start=1
        ):
            self.report.counts["comments"] += 1
            self.editable(f"{base} comment {index}", comment, "IssueComment")
        if not pull:
            return
        self.text(f"{base} head-ref", _field(node, "headRefName"))
        self.text(f"{base} base-ref", _field(node, "baseRefName"))
        for r_index, review in enumerate(
            self.all_nodes(node, typename, "reviews", REVIEW), start=1
        ):
            self.report.counts["reviews"] += 1
            self.editable(f"{base} review {r_index}", review, "PullRequestReview")
            for c_index, comment in enumerate(
                self.all_nodes(review, "PullRequestReview", "comments", COMMENT), start=1
            ):
                self.report.counts["review comments"] += 1
                self.editable(
                    f"{base} review {r_index} comment {c_index}",
                    comment,
                    "PullRequestReviewComment",
                )

    def run(self) -> Report:
        for index, label in enumerate(self.repository_nodes("labels", "name description"), start=1):
            self.report.counts["labels"] += 1
            self.text(f"label {index} name", _field(label, "name"))
            self.text(f"label {index} description", _field(label, "description"))
        for kind, field_name in (("issue", "issues"), ("pr", "pullRequests")):
            for node in self.repository_nodes(field_name, "number"):
                number = _field(node, "number")
                if not isinstance(number, int):
                    raise CheckError(f"{field_name}: GraphQL number is not an integer")
                self.item(kind, number)
        return self.report


SUMMARY_KEYS = (
    "issues",
    "pull requests",
    "title renames",
    "comments",
    "reviews",
    "review comments",
    "revisions",
    "deleted revisions",
    "labels",
)


def summary(report: Report, denylist_entries: int) -> str:
    counts = ", ".join(f"{report.counts[key]} {key}" for key in SUMMARY_KEYS)
    return f"Scanned {counts} ({denylist_entries} denylist entries)."


def parse_repo(value: str) -> tuple[str, str]:
    owner, _, name = value.partition("/")
    if not owner or not name or "/" in name:
        raise argparse.ArgumentTypeError("expected OWNER/NAME")
    return owner, name


def main(argv: list[str] | None = None, run_query: RunQuery = gh_query) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--repo", type=parse_repo, default=parse_repo(DEFAULT_REPO), help="OWNER/NAME"
    )
    parser.add_argument(
        "--root", type=Path, default=ROOT, help="checkout whose runtime/ denylist is used"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="also write the literal-free report to this local file (never with values)",
    )
    parser.add_argument(
        "--show-values",
        action="store_true",
        help="print matched values (local use only; never in CI logs or posted text)",
    )
    args = parser.parse_args(argv)
    owner, name = args.repo
    try:
        deny_file = scanner.denylist_path(args.root.resolve())
        denylist: list[str] = scanner.load_denylist(deny_file) if deny_file else []
        if deny_file is None:
            print(
                f"note: no private denylist ({scanner.DENYLIST_ENV} or "
                f"{scanner.DEFAULT_DENYLIST}); rule checks only",
                file=sys.stderr,
            )
        report = IssueScan(run_query, owner, name, denylist).run()
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    lines = [f"ERROR: {finding.report()}" for finding in report.findings]
    lines += [f"NOTE: {note}" for note in report.notes]
    for finding in report.findings:
        print(f"ERROR: {finding.report(show_values=args.show_values)}", file=sys.stderr)
    for note in report.notes:
        print(f"NOTE: {note}", file=sys.stderr)
    deleted = report.counts["deleted revisions"]
    if report.findings:
        verdict = f"{len(report.findings)} finding(s)."
    elif deleted:
        verdict = f"No findings in the scannable text; {deleted} deleted revision(s) not scanned."
    else:
        verdict = "No private identifiers found."
    lines += [summary(report, len(denylist)), verdict]
    print(lines[-2])
    print(lines[-1])
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
