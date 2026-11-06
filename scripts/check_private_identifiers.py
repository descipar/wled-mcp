"""Fail when repository text carries private identifiers of an installation (issue #62).

Scans every tracked file plus untracked, non-ignored files of the Git work tree
(``git ls-files``); outside a Git work tree the check fails closed. Files that are not
UTF-8 or contain a NUL byte are skipped as binary.

Rules (DEC-005, DEC-009, ISSUE-62-DEC-001):

- ``ipv4-private``: 10/8, 172.16/12, 192.168/16, 169.254/16 and 100.64/10, with a
  digit/dot boundary so that version strings such as ``3.10.0.1`` do not match.
  Loopback, ``0.0.0.0`` and the documentation ranges (TEST-NET-1/2/3) are allowed.
- ``ipv6-private``: link-local and unique-local addresses. Loopback, the unspecified
  address and the documentation prefix 2001:db8::/32 are allowed.
- ``home-path``: ``/home/<name>``, ``/Users/<name>`` and ``C:\\Users\\<name>``.
- ``local-hostname``: host names ending in a router- or site-local suffix (see
  ``LOCAL_SUFFIXES``). Synthetic examples use ``.example``, ``.invalid`` or ``.test``.
  In ``*.py`` files only host names in strings, URLs or userinfo count, so attribute access
  such as ``threading.local`` is not reported.
- ``mac-address``: colon/dash MAC addresses and ``"mac": "<12 hex>"`` values outside
  the RFC 7042 documentation block 00-00-5E-00-53-xx.
- ``email``: addresses outside the reserved example/invalid/test domains, except
  ``noreply`` addresses.
- ``denylist``: optional case-insensitive literals from an untracked file, read from
  ``$WLED_MCP_PRIVATE_DENYLIST`` or ``runtime/private-denylist.txt`` (git-ignored).

Intended synthetic fixtures (negative controls) are exempted one path/value pair at a
time by ``scripts/private_identifier_allowlist.toml``; an entry that no longer matches
fails the check. Findings name ``path:line: rule`` but never the matched value, so a
report cannot re-leak it into CI logs; ``--show-values`` prints values for local use.

Standard library only. Exit code 0 when clean, 1 with findings or stale allowlist
entries, 2 when the input cannot be checked (no Git work tree, invalid allowlist or
denylist).
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path("scripts/check_private_identifiers.py")
RULES_BEGIN = "# BEGIN RULE DEFINITIONS"
RULES_END = "# END RULE DEFINITIONS"
ALLOWLIST = Path("scripts/private_identifier_allowlist.toml")
DENYLIST_ENV = "WLED_MCP_PRIVATE_DENYLIST"
DEFAULT_DENYLIST = Path("runtime/private-denylist.txt")
MIN_DENYLIST_LENGTH = 3

# The block below is the only exempted text of this file: it defines what to find.
# BEGIN RULE DEFINITIONS
PRIVATE_V4 = tuple(
    ipaddress.IPv4Network(network)
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",  # link-local
        "100.64.0.0/10",  # shared address space (CGNAT, overlay VPNs)
    )
)
PRIVATE_V6 = (ipaddress.IPv6Network("fe80::/10"), ipaddress.IPv6Network("fc00::/7"))
LOCAL_SUFFIXES = (
    r"fritz\.box",
    r"home\.arpa",
    "localdomain",
    "intranet",
    "internal",
    "private",
    "local",
    "home",
    "corp",
    "lan",
)
EXAMPLE_MAIL_DOMAINS = ("example.com", "example.net", "example.org")
RESERVED_MAIL_SUFFIXES = (".example", ".invalid", ".test", ".localhost")
DOCUMENTATION_MAC_PREFIX = "00005e0053"
# END RULE DEFINITIONS

IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.]*\d)")
IPV6 = re.compile(r"(?<![\w:.])[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?:%[\w.-]+)?(?![\w:])")
HOME_PATH = re.compile(r"(?<![\w.~-])(?:/home/|/Users/|[A-Za-z]:\\{1,2}[Uu]sers\\{1,2})\w[\w.-]*")
LOCAL_HOST = re.compile(
    r"(?<![\w.-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    rf"(?:{'|'.join(LOCAL_SUFFIXES)})(?![\w-]|\.[\w-]|\()",
    re.IGNORECASE,
)
MAC = re.compile(r"(?<![\w:-])[0-9A-Fa-f]{2}([:-])[0-9A-Fa-f]{2}(?:\1[0-9A-Fa-f]{2}){4}(?![\w:-])")
MAC_FIELD = re.compile(r"""["']mac["']\s*[:=]\s*["']([0-9A-Fa-f]{12})["']""", re.IGNORECASE)
EMAIL = re.compile(
    r"(?<![\w.+%-])([A-Za-z0-9._%+-]+)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})(?![\w-]|\.[\w-])"
)


class CheckError(Exception):
    """The input cannot be checked; the command fails closed with exit code 2."""


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    value: str

    def report(self, *, show_values: bool = False) -> str:
        suffix = f": {self.value}" if show_values else ""
        return f"{self.path}:{self.line}: {self.rule}{suffix}"


@dataclass(frozen=True)
class AllowEntry:
    path: str
    value: str
    reason: str


def _ipv4(match: re.Match[str]) -> bool:
    octets = [int(part) for part in match.groups()]
    if any(octet > 255 for octet in octets):
        return False
    address = ipaddress.IPv4Address(".".join(map(str, octets)))
    return any(address in network for network in PRIVATE_V4)


def _ipv6(candidate: str) -> bool:
    try:
        address = ipaddress.IPv6Address(candidate.split("%", 1)[0])
    except ValueError:
        return False
    return any(address in network for network in PRIVATE_V6)


def _python_host_context(text: str, start: int) -> bool:
    """In Python source only host names inside a string, URL or userinfo count.

    A name counts when an odd number of quotes of one kind precedes it on its line, or
    when it follows ``://`` or ``@``; ``threading.local`` or ``Path.home()`` do not.
    """
    if text[max(0, start - 3) : start] == "://" or text[start - 1 : start] == "@":
        return True
    prefix = text[text.rfind("\n", 0, start) + 1 : start]
    return prefix.count('"') % 2 == 1 or prefix.count("'") % 2 == 1


def _personal_email(local: str, domain: str) -> bool:
    domain = domain.lower()
    if "noreply" in local.lower():
        return False
    if domain in EXAMPLE_MAIL_DOMAINS or domain.endswith(RESERVED_MAIL_SUFFIXES):
        return False
    return True


def _documentation_mac(value: str) -> bool:
    return re.sub(r"[:-]", "", value).lower().startswith(DOCUMENTATION_MAC_PREFIX)


def _matches(path: str, text: str) -> Iterator[tuple[int, str, str]]:
    """``(offset, rule, value)`` for every rule hit in one file's text."""
    for match in IPV4.finditer(text):
        if _ipv4(match):
            yield match.start(), "ipv4-private", match.group()
    for match in IPV6.finditer(text):
        if _ipv6(match.group()):
            yield match.start(), "ipv6-private", match.group()
    for match in HOME_PATH.finditer(text):
        yield match.start(), "home-path", match.group()
    python = path.endswith(".py")
    for match in LOCAL_HOST.finditer(text):
        if not python or _python_host_context(text, match.start()):
            yield match.start(), "local-hostname", match.group()
    for match in MAC.finditer(text):
        if not _documentation_mac(match.group()):
            yield match.start(), "mac-address", match.group()
    for match in MAC_FIELD.finditer(text):
        if not _documentation_mac(match.group(1)):
            yield match.start(1), "mac-address", match.group(1)
    for match in EMAIL.finditer(text):
        if _personal_email(match.group(1), match.group(2)):
            yield match.start(), "email", match.group()


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_text(path: str, text: str) -> list[Finding]:
    """All rule findings of one file, ordered by position; no allowlist applied."""
    found = {
        Finding(path, _line(text, offset), rule, value)
        for offset, rule, value in _matches(path, text)
    }
    return sorted(found, key=lambda finding: (finding.line, finding.rule, finding.value))


def scan_denylist(path: str, text: str, entries: list[str]) -> list[Finding]:
    """Denylist hits; the rule names the entry number, never the private literal."""
    folded = text.casefold()
    findings = []
    for number, entry in enumerate(entries, start=1):
        needle = entry.casefold()
        start = folded.find(needle)
        while start != -1:
            findings.append(Finding(path, _line(text, start), f"denylist entry {number}", entry))
            start = folded.find(needle, start + 1)
    return findings


def load_allowlist(path: Path) -> list[AllowEntry]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise CheckError(f"allowlist {path.name}: {exc}") from exc
    if set(data) - {"allow"}:
        raise CheckError(f"allowlist {path.name}: only [[allow]] tables are supported")
    raw = data.get("allow", [])
    if not isinstance(raw, list):
        raise CheckError(f"allowlist {path.name}: allow must be an array of tables")
    entries = []
    for number, item in enumerate(raw, start=1):
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "value", "reason"}
            or not all(isinstance(item[key], str) and item[key].strip() for key in item)
        ):
            raise CheckError(
                f"allowlist {path.name}: entry {number} needs nonempty path, value and reason"
            )
        entries.append(AllowEntry(item["path"], item["value"], item["reason"]))
    return entries


def load_denylist(path: Path) -> list[str]:
    """Literal private values, one per line; ``#`` starts a comment line."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CheckError(
            f"denylist: cannot read the configured file ({type(exc).__name__})"
        ) from None
    entries: list[str] = []
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if len(entry) < MIN_DENYLIST_LENGTH:
            raise CheckError(
                f"denylist entry {len(entries) + 1}: shorter than {MIN_DENYLIST_LENGTH} "
                "characters; it would match ordinary text"
            )
        entries.append(entry)
    return entries


def candidate_files(root: Path) -> list[str]:
    """Tracked plus untracked, non-ignored paths; fails closed outside a Git work tree."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CheckError(f"git ls-files failed: {exc}") from exc
    if result.returncode != 0:
        raise CheckError("not a Git work tree; refusing to check an unknown file set")
    return sorted({name for name in result.stdout.decode("utf-8").split("\0") if name})


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError):
        return None  # deleted in the work tree, or a submodule entry
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


@dataclass
class Result:
    findings: list[Finding]
    stale: list[AllowEntry]
    files: int


def rule_definition_lines(text: str) -> range:
    """Line numbers of this scanner's own rule-definition block (exempt by definition)."""
    lines = text.splitlines()
    try:
        begin = lines.index(RULES_BEGIN) + 1
        end = lines.index(RULES_END) + 1
    except ValueError as exc:
        raise CheckError(f"{SELF}: rule-definition markers missing") from exc
    return range(begin, end + 1)


def check(root: Path, allowlist: Path, denylist: list[str]) -> Result:
    entries = load_allowlist(root / allowlist)
    allowed_values = {entry.value for entry in entries}
    used: set[AllowEntry] = set()
    findings: list[Finding] = []
    files = 0
    for name in candidate_files(root):
        text = read_text(root / name)
        if text is None:
            continue
        files += 1
        exempt = rule_definition_lines(text) if name == SELF.as_posix() else range(0)
        for finding in scan_text(name, text):
            if finding.line in exempt:
                continue
            if name == allowlist.as_posix() and finding.value in allowed_values:
                continue  # the allowlist names only values it exempts elsewhere
            entry = next((e for e in entries if e.path == name and e.value == finding.value), None)
            if entry is not None:
                used.add(entry)
                continue
            findings.append(finding)
        findings.extend(scan_denylist(name, text, denylist))
    stale = [entry for entry in entries if entry not in used]
    return Result(findings, stale, files)


def denylist_path(root: Path) -> Path | None:
    configured = os.environ.get(DENYLIST_ENV)
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise CheckError(f"{DENYLIST_ENV} does not name a readable file")
        return path
    default = root / DEFAULT_DENYLIST
    return default if default.is_file() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=ROOT, help="Git work tree to check")
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST, help="relative to --root")
    parser.add_argument(
        "--show-values",
        action="store_true",
        help="print matched values (local use only; never in CI logs)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        deny_file = denylist_path(root)
        denylist = load_denylist(deny_file) if deny_file else []
        if deny_file is None:
            print(
                f"note: no private denylist ({DENYLIST_ENV} or {DEFAULT_DENYLIST}); "
                "rule checks only",
                file=sys.stderr,
            )
        result = check(root, args.allowlist, denylist)
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for finding in result.findings:
        print(f"ERROR: {finding.report(show_values=args.show_values)}", file=sys.stderr)
    for entry in result.stale:
        print(
            f"ERROR: stale allowlist entry for {entry.path} ({entry.reason}); "
            "it matches nothing, remove it",
            file=sys.stderr,
        )
    if result.findings or result.stale:
        return 1
    print(f"No private identifiers in {result.files} files ({len(denylist)} denylist entries).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
