"""Keep docs/WLED-COVERAGE.md and its completeness figures honest (issue #94).

The coverage list has one Markdown table per WLED feature area with the header
``| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |``. This script
parses the rows, recomputes the two figures and checks:

- C1 table structure: expected header, unique ``W-<AREA>-NN`` IDs of a known area,
  non-empty feature and key/route cells;
- C2 status in supported, partial, planned, unplanned, excluded (ISSUE-94-DEC-001);
- C3 supported/partial rows name at least one reference; every ``wled_*`` reference is a
  tool of the real registry (``build_operations`` on a synthetic inventory) and every
  ``cli: wled-mcp <command>`` reference is a subcommand of the real CLI parser;
- C4 planned/unplanned/excluded rows name no reference;
- C5 planned rows link exactly one issue of this repository that is in the stage-2 issue
  map or a stage-3 table (offline proxy; open state is checked in review);
- C6 excluded rows link at least one decision ID whose entry exists and is not
  superseded;
- C7 every registered tool is in a supported/partial row or in the "Tools without a WLED
  feature row" list, and every tool in that list is registered;
- C8 the generated figure blocks in WLED-COVERAGE.md and README.md equal the recomputed
  values;
- C9 the Basis paragraph names a WLED commit recorded in docs/SOURCES.md and the
  WLED 16.0.0 floor (DEC-020).

Figures: S = supported + 0.5 x partial; WLED coverage = S / all rows; planned-scope
coverage = S / (all rows - excluded rows); integer percent rounded half up.

``--update`` rewrites only the blocks between the ``wled-coverage`` markers. Building the
registry uses a mock transport that refuses every request: no device or network access.
Exit code 0 on success, 1 with findings on stderr.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ISSUES = "https://github.com/descipar/wled-mcp/issues/"
# README.md is also the PyPI project page, where relative links do not resolve (#22).
REPOSITORY_FILES = "https://github.com/descipar/wled-mcp/blob/main/"
HEADER = ["ID", "Feature", "WLED key / route", "Status", "Delivered by", "Link", "Notes"]
STATUSES = ("supported", "partial", "planned", "unplanned", "excluded")
DELIVERING = ("supported", "partial")
AREAS = {
    "STATE": "Master state",
    "SEG": "Segments",
    "CAT": "Effects and palettes",
    "PRESET": "Presets and playlists",
    "INFO": "Information and diagnostics",
    "CFG": "Configuration",
    "SYS": "System and maintenance",
    "RT": "Realtime and streaming",
    "UM": "Usermods",
}
START = "<!-- wled-coverage:start -->"
END = "<!-- wled-coverage:end -->"
SERVER_ONLY = "## Tools without a WLED feature row"
ROW_ID = re.compile(r"^W-([A-Z]+)-(\d{2})$")
REFERENCES = re.compile(r"^`[^`]+`(?:, `[^`]+`)*$")
TOOL_REF = re.compile(r"^wled_[a-z0-9_]+$")
CLI_REF = re.compile(r"^cli: wled-mcp((?: [a-z][a-z0-9-]*)+)$")
ISSUE_LINK = re.compile(re.escape(REPO_ISSUES) + r"(\d+)\b")
DECISION_ID = re.compile(r"(?<![\w-])((?:ISSUE-\d+-)?DEC-\d{3})(?![\w-])")
COMMIT = re.compile(r"\b[0-9a-f]{40}\b")
STATUS_LINE = re.compile(r"^- Status(?:/authority)?:\s*(.*)$")


@dataclass(frozen=True)
class Row:
    id: str
    area: str
    feature: str
    key: str
    status: str
    references: tuple[str, ...]
    link: str
    notes: str


@dataclass(frozen=True)
class Context:
    """Facts the rows are checked against; loaded from the repository or synthetic."""

    tools: frozenset[str]
    cli_commands: frozenset[tuple[str, ...]]
    roadmap_issues: frozenset[int]
    decisions: Mapping[str, str]  # decision ID -> status text
    sources: str


@dataclass
class Counts:
    total: int = 0
    by_status: dict[str, int] = field(default_factory=lambda: dict.fromkeys(STATUSES, 0))

    @property
    def score(self) -> Fraction:
        return self.by_status["supported"] + Fraction(self.by_status["partial"], 2)

    @property
    def in_scope(self) -> int:
        return self.total - self.by_status["excluded"]

    @property
    def overall(self) -> int | None:
        return percent(self.score, self.total)

    @property
    def planned_scope(self) -> int | None:
        return percent(self.score, self.in_scope)


def percent(score: Fraction, denominator: int) -> int | None:
    """Integer percent rounded half up; None when there is nothing to divide by."""
    if denominator == 0:
        return None
    return math.floor(score * 100 / denominator + Fraction(1, 2))


def show_percent(value: int | None) -> str:
    return "n/a" if value is None else f"{value} %"


def show_score(score: Fraction) -> str:
    return str(score.numerator) if score.denominator == 1 else f"{float(score):g}"


# --- Parsing -------------------------------------------------------------------------


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().removeprefix("|").removesuffix("|").split("|")]


def parse_rows(text: str) -> tuple[list[Row], list[str]]:
    """Rows of every table whose first header cell is ``ID``, plus C1/C2 problems."""
    rows: list[Row] = []
    problems: list[str] = []
    inside = False
    seen: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("|"):
            inside = False
            continue
        parts = cells(line)
        if not inside and parts[0] == "ID":
            if parts != HEADER:
                problems.append(f"C1 line {number}: table header differs from {HEADER}")
            inside = True
            continue
        if not inside or set(parts[0]) <= {"-", ":", " "}:
            continue
        if len(parts) != len(HEADER):
            problems.append(f"C1 line {number}: expected {len(HEADER)} cells, got {len(parts)}")
            continue
        row_id, feature, key, status, delivered, link, notes = parts
        match = ROW_ID.match(row_id)
        if match is None or match.group(1) not in AREAS:
            problems.append(f"C1 line {number}: malformed or unknown-area row ID {row_id!r}")
            continue
        if row_id in seen:
            problems.append(f"C1 {row_id}: duplicate row ID")
        seen.add(row_id)
        if not feature or feature == "-" or not key or key == "-":
            problems.append(f"C1 {row_id}: empty feature or WLED key/route cell")
        if status not in STATUSES:
            problems.append(f"C2 {row_id}: unknown status {status!r}")
        references: tuple[str, ...] = ()
        if delivered != "-":
            if not REFERENCES.match(delivered):
                problems.append(f"C3 {row_id}: Delivered by must be backticked references or -")
            references = tuple(re.findall(r"`([^`]+)`", delivered))
        rows.append(Row(row_id, match.group(1), feature, key, status, references, link, notes))
    if not rows:
        problems.append("C1: no coverage table rows found")
    return rows, problems


def server_only_tools(text: str) -> list[str]:
    """Tools listed as ``- `wled_x`: reason`` under the server-only heading."""
    section = text.partition(SERVER_ONLY + "\n")[2]
    section = re.split(r"^## ", section, maxsplit=1, flags=re.M)[0]
    return re.findall(r"^- `(wled_[a-z0-9_]+)`", section, flags=re.M)


# --- Figures and generated blocks ----------------------------------------------------


def tally(rows: Iterable[Row]) -> tuple[Counts, dict[str, Counts]]:
    overall = Counts()
    areas = {area: Counts() for area in AREAS}
    for row in rows:
        if row.status not in STATUSES:
            continue
        for counts in (overall, areas[row.area]):
            counts.total += 1
            counts.by_status[row.status] += 1
    return overall, areas


def coverage_block(rows: list[Row]) -> str:
    overall, areas = tally(rows)
    score = show_score(overall.score)
    lines = [
        f"**WLED coverage: {show_percent(overall.overall)}** ({score} of {overall.total} "
        f"features). **Planned-scope coverage: {show_percent(overall.planned_scope)}** "
        f"({score} of {overall.in_scope} features, excluded rows removed).",
        "",
        "| Area | Features | Supported | Partial | Planned | Unplanned | Excluded "
        "| Planned scope | WLED overall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    def line(label: str, counts: Counts) -> str:
        values = [counts.total, *(counts.by_status[status] for status in STATUSES)]
        numbers = " | ".join(str(value) for value in values)
        return (
            f"| {label} | {numbers} | {show_percent(counts.planned_scope)} "
            f"| {show_percent(counts.overall)} |"
        )

    for area, name in AREAS.items():
        if areas[area].total:
            lines.append(line(f"{name} ({area})", areas[area]))
    lines.append(line("**All**", overall))
    return "\n".join(lines)


def readme_block(rows: list[Row]) -> str:
    overall, _ = tally(rows)
    return (
        f"WLED feature coverage: {show_percent(overall.planned_scope)} of the planned scope, "
        f"{show_percent(overall.overall)} of WLED overall "
        f"([method and list]({REPOSITORY_FILES}docs/WLED-COVERAGE.md))."
    )


def block(text: str) -> str | None:
    """Content between the markers, or None when they are missing or repeated."""
    if text.count(START) != 1 or text.count(END) != 1:
        return None
    inner = text.partition(START)[2].partition(END)
    if not inner[1]:
        return None
    return inner[0].strip("\n")


def replace_block(text: str, content: str) -> str:
    before, _, rest = text.partition(START)
    _, _, after = rest.partition(END)
    return f"{before}{START}\n{content}\n{END}{after}"


# --- Checks --------------------------------------------------------------------------


def reference_problems(row: Row, context: Context) -> list[str]:
    problems = []
    if row.status in DELIVERING and not row.references:
        problems.append(f"C3 {row.id}: {row.status} row names no tool or CLI command")
    if row.status not in DELIVERING and row.references:
        problems.append(f"C4 {row.id}: {row.status} row must not name a Delivered by reference")
        return problems
    for reference in row.references:
        cli = CLI_REF.match(reference)
        if TOOL_REF.match(reference):
            if reference not in context.tools:
                problems.append(f"C3 {row.id}: {reference} is not a registered tool")
        elif cli:
            command = tuple(cli.group(1).split())
            if command not in context.cli_commands:
                problems.append(f"C3 {row.id}: 'wled-mcp {' '.join(command)}' is not a CLI command")
        else:
            problems.append(f"C3 {row.id}: unrecognized reference {reference!r}")
    return problems


def link_problems(row: Row, context: Context) -> list[str]:
    problems = []
    if row.status == "planned":
        issues = [int(number) for number in ISSUE_LINK.findall(row.link)]
        if len(issues) != 1:
            problems.append(f"C5 {row.id}: planned row must link exactly one issue")
        elif issues[0] not in context.roadmap_issues:
            problems.append(f"C5 {row.id}: issue #{issues[0]} is not in the stage-2/3 maps")
    if row.status == "excluded":
        ids = DECISION_ID.findall(row.link)
        if not ids:
            problems.append(f"C6 {row.id}: excluded row links no decision")
        for decision in ids:
            status = context.decisions.get(decision)
            if status is None:
                problems.append(f"C6 {row.id}: decision {decision} has no recorded entry")
            elif superseded(status):
                problems.append(f"C6 {row.id}: decision {decision} is superseded")
    return problems


def superseded(status: str) -> bool:
    return re.search(r"\bsuperseded\b(?! in part)", status, flags=re.I) is not None


def tool_problems(rows: list[Row], listed: list[str], tools: frozenset[str]) -> list[str]:
    placed = {ref for row in rows if row.status in DELIVERING for ref in row.references}
    problems = [
        f"C7 {tool}: registered tool is in no supported/partial row and not listed as server-only"
        for tool in sorted(tools - placed - set(listed))
    ]
    problems.extend(
        f"C7 {tool}: listed as server-only but not registered"
        for tool in listed
        if tool not in tools
    )
    return problems


def basis_problems(text: str, sources: str) -> list[str]:
    paragraph = re.search(r"^\*\*Basis:\*\*.*?(?=\n\s*\n|\Z)", text, flags=re.M | re.S)
    if paragraph is None:
        return ["C9: no **Basis:** paragraph"]
    basis = " ".join(paragraph.group(0).split())
    problems = []
    commits = COMMIT.findall(basis)
    if not commits or not all(commit in sources for commit in commits):
        problems.append("C9: Basis names no WLED commit recorded in docs/SOURCES.md")
    if "WLED 16.0.0" not in basis:
        problems.append("C9: Basis does not state the WLED 16.0.0 floor (DEC-020)")
    return problems


def check_texts(coverage: str, readme: str, context: Context) -> list[str]:
    rows, problems = parse_rows(coverage)
    for row in rows:
        problems.extend(reference_problems(row, context))
        problems.extend(link_problems(row, context))
    problems.extend(tool_problems(rows, server_only_tools(coverage), context.tools))
    for name, text, expected in (
        ("docs/WLED-COVERAGE.md", coverage, coverage_block(rows)),
        ("README.md", readme, readme_block(rows)),
    ):
        current = block(text)
        if current is None:
            problems.append(f"C8 {name}: missing or repeated wled-coverage markers")
        elif current != expected:
            problems.append(f"C8 {name}: figure block is stale; run check_coverage.py --update")
    problems.extend(basis_problems(coverage, context.sources))
    return problems


def update_texts(coverage: str, readme: str) -> tuple[str, str]:
    rows, _ = parse_rows(coverage)
    return (
        replace_block(coverage, coverage_block(rows)),
        replace_block(readme, readme_block(rows)),
    )


# --- Repository facts ----------------------------------------------------------------


def roadmap_issues(stage2: str, stage3: str, roadmap: str = "") -> frozenset[int]:
    """Issues in the stage-2 issue map (first cell), any stage-3 table and the roadmap table.

    Trackers named as ``Tracker: [#n]`` are removed.
    """
    numbers: set[int] = set()
    for line in stage2.splitlines():
        if line.startswith("| [#"):
            first = cells(line)[0]
            numbers.update(int(number) for number in ISSUE_LINK.findall(first))
    for line in stage3.splitlines():
        if line.startswith("|"):
            numbers.update(int(number) for number in ISSUE_LINK.findall(line))
    for line in roadmap.splitlines():
        if line.startswith("|"):
            numbers.update(int(number) for number in ISSUE_LINK.findall(line))
    trackers = re.findall(r"Tracker: \[#(\d+)\]", stage2 + "\n" + stage3)
    return frozenset(numbers - {int(number) for number in trackers})


def section_statuses(text: str, heading: re.Pattern[str]) -> dict[str, str]:
    """Decision ID -> first Status line below each matching heading."""
    statuses: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("#"):
            match = heading.match(line)
            current = match.group(1) if match else None
            if current:
                statuses.setdefault(current, "")
            continue
        status = STATUS_LINE.match(line)
        if current and status and not statuses[current]:
            statuses[current] = status.group(1)
    return statuses


def decision_entries(docs: Path) -> dict[str, str]:
    log = (docs / "DECISIONS.md").read_text(encoding="utf-8")
    entries = {match: "active" for match in re.findall(r"^\| (DEC-\d{3}) \|", log, flags=re.M)}
    for decision, status in section_statuses(log, re.compile(r"^#+ (DEC-\d{3})\b")).items():
        entries[decision] = status or entries.get(decision, "active")
    for path in sorted((docs / "decisions").glob("issue-*.md")):
        text = path.read_text(encoding="utf-8")
        entries.update(section_statuses(text, re.compile(r"^#+ (ISSUE-\d+-DEC-\d{3})\b")))
    return entries


def cli_commands() -> frozenset[tuple[str, ...]]:
    """Subcommand paths of the real ``wled-mcp`` parser (empty until #16 adds any)."""
    from wled_mcp import cli

    builder: Callable[[], argparse.ArgumentParser] | None = getattr(cli, "build_parser", None)
    if builder is not None:
        parser = builder()
    else:
        captured: list[argparse.ArgumentParser] = []

        class Captured(Exception):
            pass

        def grab(self: argparse.ArgumentParser, *args: object, **kwargs: object) -> None:
            captured.append(self)
            raise Captured

        original = cli.SafeParser.parse_args
        cli.SafeParser.parse_args = grab  # type: ignore[assignment,method-assign]
        try:
            cli.main([])
        except Captured:
            pass
        finally:
            cli.SafeParser.parse_args = original  # type: ignore[method-assign]
        if not captured:
            raise RuntimeError("could not read the wled-mcp argument parser")
        parser = captured[0]

    def walk(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> set[tuple[str, ...]]:
        found: set[tuple[str, ...]] = set()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    found.add((*prefix, name))
                    found |= walk(child, (*prefix, name))
        return found

    return frozenset(walk(parser, ()))


def registered_tools() -> frozenset[str]:
    """Tool names of the real registry, built on a synthetic inventory without network."""
    import anyio
    import httpx2 as httpx

    from wled_mcp.config import Device, StartupConfig
    from wled_mcp.operations import build_operations
    from wled_mcp.resources import Resources

    def refuse(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("check_coverage.py must not contact a device")

    async def collect(data_dir: Path) -> frozenset[str]:
        device = Device(id="synthetic", name="Synthetic", base_url="http://example.invalid")
        config = StartupConfig(data_dir / "config.toml", data_dir, (device,))
        async with Resources(config, transport=httpx.MockTransport(refuse)) as resources:
            return frozenset(operation.name for operation in build_operations(resources))

    with tempfile.TemporaryDirectory() as data_dir:
        return anyio.run(collect, Path(data_dir))


def load_context(root: Path) -> Context:
    docs = root / "docs"
    return Context(
        tools=registered_tools(),
        cli_commands=cli_commands(),
        roadmap_issues=roadmap_issues(
            (docs / "STAGE-2.md").read_text(encoding="utf-8"),
            (docs / "STAGE-3.md").read_text(encoding="utf-8"),
            (docs / "ROADMAP.md").read_text(encoding="utf-8"),
        ),
        decisions=decision_entries(docs),
        sources=(docs / "SOURCES.md").read_text(encoding="utf-8"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check docs/WLED-COVERAGE.md and its figures.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--coverage", type=Path, help="Override docs/WLED-COVERAGE.md.")
    parser.add_argument("--readme", type=Path, help="Override README.md.")
    parser.add_argument(
        "--update", action="store_true", help="Rewrite the generated figure blocks first."
    )
    args = parser.parse_args(argv)
    coverage_path = args.coverage or args.root / "docs" / "WLED-COVERAGE.md"
    readme_path = args.readme or args.root / "README.md"
    coverage = coverage_path.read_text(encoding="utf-8")
    readme = readme_path.read_text(encoding="utf-8")
    if args.update:
        missing = [
            str(path)
            for path, text in ((coverage_path, coverage), (readme_path, readme))
            if block(text) is None
        ]
        if missing:
            print(f"C8: missing or repeated wled-coverage markers in {missing}", file=sys.stderr)
            return 1
        coverage, readme = update_texts(coverage, readme)
        coverage_path.write_text(coverage, encoding="utf-8", newline="\n")
        readme_path.write_text(readme, encoding="utf-8", newline="\n")
    problems = check_texts(coverage, readme, load_context(args.root))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    rows, _ = parse_rows(coverage)
    overall, _ = tally(rows)
    print(
        f"WLED coverage: {len(rows)} features; {show_percent(overall.planned_scope)} of the "
        f"planned scope, {show_percent(overall.overall)} overall."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
