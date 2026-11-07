"""Issue #90: the read-only issue/PR content scan (DEC-015 item 1a, DEC-018).

Drives ``scripts/check_issue_content.py`` against an in-memory fake of the GitHub GraphQL
API; nothing contacts GitHub, the network or a device. The fake serves small pages so
that every connection is paginated. Planted values are assembled from parts at runtime
(``"192.168" + ".7.9"``) so that this file stays clean for the repository scan.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_issue_content.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_issue_content", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


issue_content = load_module()

PRIVATE_V4 = "192.168" + ".7.9"
DENIED = "acme-" + "lab-unit"
PAGE = 2  # the fake's page size; every list below with more items spans pages

# ------------------------------------------------------------------ fixture model

_ids = itertools.count(1)


def node(**fields: Any) -> dict[str, Any]:
    return {"id": f"N{next(_ids)}", **fields}


def edit(diff: str | None, edited_at: str) -> dict[str, Any]:
    return {"editedAt": edited_at, "diff": diff}


def comment(body: str, edits: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return node(body=body, edits=edits or [])


def review(body: str, comments=(), edits=None) -> dict[str, Any]:
    return node(body=body, edits=edits or [], comments=list(comments))


def issue(number: int, title: str, body: str, *, edits=(), comments=(), renames=()):
    return node(
        number=number,
        title=title,
        body=body,
        edits=list(edits),
        comments=list(comments),
        renames=list(renames),
    )


def pull(number: int, title: str, body: str, *, reviews=(), head="feature/x", **kw):
    item = issue(number, title, body, **kw)
    item.update(reviews=list(reviews), headRefName=head, baseRefName="main")
    return item


class FakeGitHub:
    """Answers the script's GraphQL documents from the fixture, page by page."""

    def __init__(self, issues=(), pulls=(), labels=()):
        self.issues = {item["number"]: item for item in issues}
        self.pulls = {item["number"]: item for item in pulls}
        self.labels = list(labels)
        self.nodes: dict[str, dict[str, Any]] = {}
        for item in [*self.issues.values(), *self.pulls.values()]:
            self._register(item)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _register(self, item: dict[str, Any]) -> None:
        self.nodes[item["id"]] = item
        for child in [*item.get("comments", []), *item.get("reviews", [])]:
            self._register(child)

    @staticmethod
    def conn(items: list[Any], after: str | None, render) -> dict[str, Any]:
        start = int(after or 0)
        more = start + PAGE < len(items)
        return {
            "pageInfo": {"hasNextPage": more, "endCursor": str(start + PAGE) if more else None},
            "nodes": [render(item) for item in items[start : start + PAGE]],
        }

    def edits(self, obj, after=None):
        return self.conn(obj["edits"], after, dict)

    def comment(self, obj):
        return {"id": obj["id"], "body": obj["body"], "userContentEdits": self.edits(obj)}

    def review(self, obj):
        return {**self.comment(obj), "comments": self.conn(obj["comments"], None, self.comment)}

    def item(self, obj):
        rendered = {
            **self.comment(obj),
            "number": obj["number"],
            "title": obj["title"],
            "timelineItems": self.conn(obj["renames"], None, self.rename),
            "comments": self.conn(obj["comments"], None, self.comment),
        }
        if "reviews" in obj:
            rendered.update(
                headRefName=obj["headRefName"],
                baseRefName=obj["baseRefName"],
                reviews=self.conn(obj["reviews"], None, self.review),
            )
        return rendered

    @staticmethod
    def rename(previous):
        return {"previousTitle": previous}

    def __call__(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((query, dict(variables)))
        after = variables.get("after")
        if "node(id: $id)" in query:
            obj = self.nodes[variables["id"]]
            field = re.search(r"\.\.\. on \w+ \{ (\w+)\(", query).group(1)
            key, render = {
                "userContentEdits": ("edits", dict),
                "comments": ("comments", self.comment),
                "reviews": ("reviews", self.review),
                "timelineItems": ("renames", self.rename),
            }[field]
            return {"data": {"node": {field: self.conn(obj[key], after, render)}}}
        if "issue(number:" in query:
            item = self.issues.get(variables["number"])
            return {"data": {"repository": {"issue": item and self.item(item)}}}
        if "pullRequest(number:" in query:
            item = self.pulls.get(variables["number"])
            return {"data": {"repository": {"pullRequest": item and self.item(item)}}}
        field = re.search(r"\{ (\w+)\(first: 100", query).group(1)
        source = {
            "labels": self.labels,
            "issues": [{"number": n} for n in self.issues],
            "pullRequests": [{"number": n} for n in self.pulls],
        }[field]
        return {"data": {"repository": {field: self.conn(source, after, dict)}}}


def clean_fixture() -> FakeGitHub:
    return FakeGitHub(
        issues=[
            issue(
                1,
                "Synthetic issue",
                "Device wled-desk.example.invalid at 192.0.2.10",
                edits=[edit("first draft", "2026-01-01"), edit("second draft", "2026-01-02")],
                comments=[comment("ok"), comment("fine", [edit("typo", "2026-01-03")])],
                renames=["Old synthetic title"],
            ),
            issue(2, "Second", "", comments=[comment("a"), comment("b"), comment("c")]),
        ],
        pulls=[
            pull(
                3,
                "Synthetic PR",
                "Body",
                reviews=[
                    review("Looks good", comments=[comment("nit"), comment("nit 2")]),
                    review("", comments=[comment("x", [edit("y", "2026-01-04")])]),
                ],
            )
        ],
        labels=[{"name": "stage:2", "description": "Stage 2 work"}],
    )


@pytest.fixture
def run(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(issue_content.scanner.DENYLIST_ENV, raising=False)

    def invoke(fake, *args: str, denylist: str | None = None):
        if denylist is not None:
            path = tmp_path / "deny.txt"
            path.write_text(denylist, encoding="utf-8")
            monkeypatch.setenv(issue_content.scanner.DENYLIST_ENV, str(path))
        code = issue_content.main(["--root", str(tmp_path), *args], run_query=fake)
        out, err = capsys.readouterr()
        return code, out, err

    return invoke


def errors(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("ERROR")]


# --------------------------------------------------------------------- A90-01


def test_clean_fixture_passes_with_counts_of_every_scanned_item(run):
    code, out, err = run(clean_fixture())
    assert code == 0, err
    assert errors(err) == []
    assert (
        "Scanned 2 issues, 1 pull requests, 1 title renames, 5 comments, 2 reviews, "
        "3 review comments, 4 revisions, 0 deleted revisions, 1 labels "
        "(0 denylist entries)." in out
    )
    assert "No private identifiers found." in out
    assert "no private denylist" in err


# --------------------------------------------------------------------- A90-02


def test_private_address_in_a_review_comment_revision_is_located_without_echo(run):
    leaky = comment(
        "current text",
        [edit("current text", "2026-02-03"), edit(f"was {PRIVATE_V4}", "2026-02-02")],
    )
    leaky["edits"].append(edit("draft", "2026-02-01"))
    fake = FakeGitHub(
        pulls=[pull(7, "PR", "Body", reviews=[review("r1", comments=[comment("c1"), leaky])])]
    )
    code, out, err = run(fake)
    assert code == 1
    # Revisions count from the oldest: draft (1), the leak (2), current text (3).
    assert errors(err) == ["ERROR: pr #7 review 1 comment 2 revision 2:1: ipv4-private"]
    assert PRIVATE_V4 not in out + err
    assert "1 finding(s)." in out
    code, out, err = run(fake, "--show-values")
    assert code == 1
    assert f"revision 2:1: ipv4-private: {PRIVATE_V4}" in err


# --------------------------------------------------------------------- A90-03


def test_denylist_literal_in_a_previous_title_and_a_comment_is_reported_by_number(run):
    fake = FakeGitHub(
        issues=[
            issue(
                4,
                "Neutral title",
                "Body",
                renames=["fine", f"Lights at {DENIED.upper()}"],
                comments=[comment("hello"), comment(f"line one\nsee {DENIED.title()}")],
            )
        ]
    )
    code, out, err = run(fake, denylist=f"# synthetic\n{DENIED}\n")
    assert code == 1
    assert errors(err) == [
        "ERROR: issue #4 title-rename 2:1: denylist entry 1",
        "ERROR: issue #4 comment 2:2: denylist entry 1",
    ]
    assert DENIED not in (out + err).lower()
    assert "(1 denylist entries)" in out


def test_branch_names_and_labels_are_scanned(run):
    fake = FakeGitHub(
        pulls=[pull(9, "PR", "Body", head=f"fix/{DENIED}")],
        labels=[{"name": "ok", "description": None}, {"name": "x", "description": DENIED}],
    )
    code, _, err = run(fake, denylist=DENIED)
    assert code == 1
    assert errors(err) == [
        "ERROR: label 2 description:1: denylist entry 1",
        "ERROR: pr #9 head-ref:1: denylist entry 1",
    ]


# --------------------------------------------------------------------- A90-04


def test_every_page_of_every_connection_is_fetched_and_scanned(run):
    many_edits = [edit(f"rev {n}", f"2026-03-0{n}") for n in range(1, 6)]
    many_edits[-1]["diff"] = f"last {PRIVATE_V4}"
    comments = [comment(f"c{n}") for n in range(5)] + [comment("tail", many_edits)]
    fake = FakeGitHub(
        issues=[issue(n, f"I{n}", "b") for n in range(1, 4)]
        + [issue(10, "Paged", "b", comments=comments)]
    )
    code, out, err = run(fake)
    assert code == 1
    assert errors(err) == ["ERROR: issue #10 comment 6 revision 5:1: ipv4-private"]
    assert "4 issues" in out and "6 comments" in out and "5 revisions" in out
    cursors = [variables.get("after") for _, variables in fake.calls]
    assert "2" in cursors and "4" in cursors


@pytest.mark.parametrize(
    "response",
    [
        {"data": {"repository": {"labels": {"nodes": []}}}},
        {"data": {"repository": {"labels": {"pageInfo": {"hasNextPage": True}, "nodes": []}}}},
        {"data": {"repository": {"labels": {"pageInfo": {}, "nodes": []}}}},
        {"data": None, "errors": [{"type": "RATE_LIMITED", "message": "synthetic"}]},
        {"data": {"repository": None}},
    ],
    ids=["no-page-info", "next-without-cursor", "empty-page-info", "graphql-errors", "no-repo"],
)
def test_incomplete_responses_fail_closed_without_a_summary(run, response):
    code, out, err = run(lambda query, variables: response)
    assert code == 2
    assert out == ""
    assert errors(err) and "synthetic" not in err


def test_an_invalid_page_later_in_the_scan_fails_the_whole_scan(run):
    fake = clean_fixture()

    def broken(query, variables):
        result = fake(query, variables)
        if "userContentEdits(first: 50, after: $after)" in query:
            result["data"]["node"]["userContentEdits"]["pageInfo"] = None
            calls.append(variables["id"])
        return result

    calls: list[str] = []

    big = issue(5, "Big", "b", edits=[edit(str(n), f"2026-04-0{n}") for n in range(1, 4)])
    fake.issues[5] = big
    fake._register(big)
    code, out, err = run(broken)
    assert calls == [big["id"]], "the broken page is a later edit-history page"
    assert code == 2 and out == ""
    assert "invalid nodes or pageInfo" in err or "lacks the field" in err


def test_invalid_denylist_fails_closed(run):
    code, out, err = run(clean_fixture(), denylist="ab\n")
    assert code == 2 and out == ""
    assert "shorter than 3 characters" in err


# --------------------------------------------------------------------- A90-05


def completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


def test_missing_gh_fails_closed(run, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(issue_content.subprocess, "run", missing)
    code, out, err = run(issue_content.gh_query)
    assert code == 2 and out == ""
    assert "gh CLI not found" in err


def test_failing_gh_output_is_not_echoed(run, monkeypatch):
    token = "gho_" + "synthetic0123456789"
    body = "response body " + DENIED
    monkeypatch.setattr(
        issue_content.subprocess, "run", lambda *a, **k: completed(1, body, f"bad {token}")
    )
    code, out, err = run(issue_content.gh_query)
    assert code == 2 and out == ""
    assert "exited with code 1" in err
    assert token not in err and DENIED not in err


def test_non_json_gh_output_fails_closed(run, monkeypatch):
    monkeypatch.setattr(issue_content.subprocess, "run", lambda *a, **k: completed(0, "<html>"))
    code, out, err = run(issue_content.gh_query)
    assert code == 2 and "no JSON" in err and "<html>" not in err


# --------------------------------------------------------------------- A90-06


def test_every_document_is_a_read_only_query(run):
    fake = clean_fixture()
    assert run(fake)[0] == 0
    documents = {query for query, _ in fake.calls}
    assert len(documents) >= 5  # list, issue, pull request and node page documents
    for document in documents:
        assert document.lstrip().startswith("query(")
        assert "mutation" not in document.lower()


def test_gh_argv_is_a_plain_graphql_query(monkeypatch):
    seen: list[list[str]] = []

    def fake_run(argv, **kwargs):
        seen.append(argv)
        return completed(0, json.dumps({"data": {}}))

    monkeypatch.setattr(issue_content.subprocess, "run", fake_run)
    issue_content.gh_query("query($n: Int!) { x }", {"owner": "o", "n": 3, "after": None})
    (argv,) = seen
    assert argv[:3] == ["gh", "api", "graphql"]
    assert argv[3:] == ["-f", "query=query($n: Int!) { x }", "-f", "owner=o", "-F", "n=3"]
    for forbidden in ("-X", "--method", "--input"):
        assert forbidden not in argv
    assert not any("mutation" in part for part in argv)


@pytest.mark.parametrize(
    "document", ["mutation { deleteIssue(input: {}) { clientMutationId } }", "{ viewer { login } }"]
)
def test_gh_query_refuses_anything_but_a_query_operation(monkeypatch, document):
    monkeypatch.setattr(issue_content.subprocess, "run", pytest.fail)
    with pytest.raises(issue_content.CheckError, match="read-only query"):
        issue_content.gh_query(document, {})


# --------------------------------------------------------------------- A90-07


def test_deleted_revision_is_counted_as_not_scannable(run):
    fake = FakeGitHub(
        issues=[issue(6, "T", "b", edits=[edit(None, "2026-05-01"), edit("now", "2026-05-02")])]
    )
    code, out, err = run(fake)
    assert code == 0
    assert "NOTE: issue #6 body revision 1: deleted, not scannable" in err
    assert "2 revisions, 1 deleted revisions" in out
    assert "No private identifiers found." not in out
    assert "1 deleted revision(s) not scanned" in out


# --------------------------------------------------------------------- A90-08


def test_rules_come_from_the_repository_scanner(run, monkeypatch):
    assert Path(issue_content.scanner.__file__).resolve() == (
        ROOT / "scripts" / "check_private_identifiers.py"
    )
    assert issue_content.CheckError is issue_content.scanner.CheckError
    seen: list[str] = []
    original = issue_content.scanner.scan_text

    def spy(path, text):
        seen.append(path)
        return original(path, text)

    monkeypatch.setattr(issue_content.scanner, "scan_text", spy)
    assert run(clean_fixture())[0] == 0
    assert "issue #1 body revision 2" in seen and "pr #3 review 2 comment 1" in seen
    assert not any(path.endswith(".py") for path in seen)


# ------------------------------------------------------------------ report file


def test_output_file_holds_the_literal_free_report_even_with_values_shown(run, tmp_path):
    fake = FakeGitHub(issues=[issue(8, "T", f"at {PRIVATE_V4}")])
    target = tmp_path / "report" / "issue-scan.txt"
    code, _, err = run(fake, "--show-values", "--output", str(target))
    assert code == 1 and PRIVATE_V4 in err
    report = target.read_text("utf-8")
    assert "ERROR: issue #8 body:1: ipv4-private" in report
    assert "1 finding(s)." in report
    assert PRIVATE_V4 not in report
