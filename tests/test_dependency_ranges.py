"""Issue #22 acceptance item 4 (AC-22R-01, AC-22R-02): runtime dependencies are ranges.

The published metadata declares a lower and an upper bound for every runtime dependency
instead of exact pins, every third-party module the package imports is declared, and the
tested set held by ``uv.lock`` and ``requirements-runtime.txt`` lies inside the ranges
(docs/contract/dependencies.md). Each check has a negative control on a mutated copy. No
network access; the import scan reads the source tree and the installed distributions.
"""

from __future__ import annotations

import ast
import importlib.metadata
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "wled_mcp"
LOCK = ROOT / "uv.lock"
CONSTRAINTS = ROOT / "requirements-runtime.txt"


def declared(root: Path = ROOT) -> list[str]:
    with (root / "pyproject.toml").open("rb") as stream:
        return [str(item) for item in tomllib.load(stream)["project"]["dependencies"]]


# ------------------------------------------------------------------- (a) bounded ranges


def range_problems(requirements: list[str]) -> list[str]:
    """Every requirement has a ``>=`` floor and a ``<`` cap, no pin, URL, marker or extra."""
    problems = []
    for text in requirements:
        requirement = Requirement(text)
        operators = {item.operator for item in requirement.specifier}
        if requirement.url or requirement.marker or requirement.extras:
            problems.append(f"{text}: URL, marker or extra")
        if operators & {"==", "===", "~=", "!="}:
            problems.append(f"{text}: exact or compatible-release pin")
        if ">=" not in operators:
            problems.append(f"{text}: no '>=' lower bound")
        if "<" not in operators:
            problems.append(f"{text}: no '<' upper bound")
    return problems


def test_every_runtime_requirement_is_a_bounded_range():
    assert declared(), "pyproject.toml declares no runtime dependency"
    assert range_problems(declared()) == []


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        ("mcp==2.3.0", "exact or compatible-release pin"),
        ("mcp===2.3.0", "exact or compatible-release pin"),
        ("mcp~=2.3", "exact or compatible-release pin"),
        ("mcp>=2.3.0", "no '<' upper bound"),
        ("mcp<3", "no '>=' lower bound"),
        ("mcp>2.3.0,<3", "no '>=' lower bound"),
        ("mcp @ https://example.invalid/mcp.whl", "URL, marker or extra"),
        ("mcp>=2.3.0,<3; sys_platform == 'linux'", "URL, marker or extra"),
        ("uvicorn[standard]>=0.31.1,<0.55", "URL, marker or extra"),
    ],
)
def test_range_check_rejects_pins_and_open_ends(requirement, expected):
    others = [text for text in declared() if not text.startswith(Requirement(requirement).name)]
    problems = range_problems([*others, requirement])
    assert any(expected in problem for problem in problems), problems


# ---------------------------------------------------------- (b) every import is declared


def imported_top_modules(sources: dict[str, str]) -> set[str]:
    """Absolute top-level modules imported anywhere in ``sources`` (name -> code)."""
    modules = set()
    for name, code in sources.items():
        for node in ast.walk(ast.parse(code, filename=name)):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".", 1)[0])
    return modules


def package_sources(package: Path = PACKAGE) -> dict[str, str]:
    return {
        path.relative_to(package).as_posix(): path.read_text("utf-8")
        for path in sorted(package.rglob("*.py"))
    }


def undeclared_import_problems(sources: dict[str, str], requirements: list[str]) -> list[str]:
    """Third-party modules imported by ``sources`` whose distribution is not declared."""
    names = {canonicalize_name(Requirement(text).name) for text in requirements}
    owners = importlib.metadata.packages_distributions()
    problems = []
    for module in sorted(imported_top_modules(sources)):
        if module in sys.stdlib_module_names or module in ("__future__", "wled_mcp"):
            continue
        distributions = {canonicalize_name(name) for name in owners.get(module, [])}
        if not distributions:
            problems.append(f"{module}: no installed distribution provides it")
        elif not distributions & names:
            problems.append(f"{module}: imported but {sorted(distributions)} not declared")
    return problems


def test_every_third_party_import_of_the_package_is_declared():
    sources = package_sources()
    modules = imported_top_modules(sources)
    assert {"mcp", "pydantic", "httpx2", "starlette", "uvicorn", "anyio"} <= modules
    assert undeclared_import_problems(sources, declared()) == []


def test_import_check_finds_a_dependency_used_only_transitively():
    # Before #22 item 4 anyio was imported by 11 modules but only installed through mcp,
    # httpx2 and starlette.
    without = [text for text in declared() if Requirement(text).name != "anyio"]
    assert undeclared_import_problems(package_sources(), without) == [
        "anyio: imported but ['anyio'] not declared"
    ]


def test_import_check_finds_a_planted_undeclared_import():
    without = [text for text in declared() if Requirement(text).name != "uvicorn"]
    planted = {"planted.py": "from uvicorn.config import Config\n"}
    assert undeclared_import_problems(planted, without) == [
        "uvicorn: imported but ['uvicorn'] not declared"
    ]
    assert undeclared_import_problems({"planted.py": "import not_a_module_xyz\n"}, []) == [
        "not_a_module_xyz: no installed distribution provides it"
    ]
    relative = {"planted.py": "from . import cli\nfrom .client import WledClient\n"}
    assert undeclared_import_problems(relative, []) == []


# ------------------------------------------------- (c) the tested set lies in the ranges


def lock_versions(text: str) -> dict[str, str]:
    return {
        canonicalize_name(package["name"]): package["version"]
        for package in tomllib.loads(text)["package"]
        if "version" in package
    }


def constraint_versions(text: str) -> dict[str, str]:
    versions = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        versions[canonicalize_name(requirement.name)] = next(iter(requirement.specifier)).version
    return versions


def locked_version_problems(
    requirements: list[str], source: str, versions: dict[str, str]
) -> list[str]:
    problems = []
    for text in requirements:
        requirement = Requirement(text)
        version = versions.get(canonicalize_name(requirement.name))
        if version is None:
            problems.append(f"{source}: {requirement.name} missing")
        elif not requirement.specifier.contains(Version(version), prereleases=True):
            problems.append(f"{source}: {requirement.name} {version} outside {text}")
    return problems


def test_locked_and_exported_versions_satisfy_the_ranges():
    lock = lock_versions(LOCK.read_text("utf-8"))
    exported = constraint_versions(CONSTRAINTS.read_text("utf-8"))
    assert locked_version_problems(declared(), "uv.lock", lock) == []
    assert locked_version_problems(declared(), "requirements-runtime.txt", exported) == []
    # The export is the lock's runtime subset; the same versions in both.
    assert {name: lock[name] for name in exported} == exported


def test_tested_set_check_rejects_a_version_outside_a_range():
    text = CONSTRAINTS.read_text("utf-8")
    assert "\nuvicorn==0.54.0\n" in text
    exported = constraint_versions(text.replace("\nuvicorn==0.54.0\n", "\nuvicorn==0.55.0\n"))
    assert locked_version_problems(declared(), "requirements-runtime.txt", exported) == [
        "requirements-runtime.txt: uvicorn 0.55.0 outside uvicorn>=0.31.1,<0.55"
    ]
    lock = lock_versions(LOCK.read_text("utf-8"))
    lock.pop("anyio")
    assert locked_version_problems(declared(), "uv.lock", lock) == ["uv.lock: anyio missing"]


# --------------------------------------------------------------------- (d) no duplicates


def duplicate_problems(requirements: list[str]) -> list[str]:
    names = [canonicalize_name(Requirement(text).name) for text in requirements]
    return sorted(
        f"{name} declared {names.count(name)} times" for name in set(names) if names.count(name) > 1
    )


def test_no_runtime_requirement_is_declared_twice():
    assert duplicate_problems(declared()) == []
    assert duplicate_problems([*declared(), "Starlette>=1.0.0,<2"]) == [
        "starlette declared 2 times"
    ]
