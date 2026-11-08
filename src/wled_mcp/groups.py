"""Device group format 1 (issue #17): strict parser and document builder.

A group is a named, ordered list of configured devices with optional explicit segment
IDs per member. It holds no device address, credential or inventory data: members name
configured device IDs, which are rechecked against the inventory at every use (a member
that left the inventory is reported, never silently dropped). Nothing is enrolled or
discovered implicitly (S2-GROUP-01).

Schema evolution follows TD-21-5 through ``formats.check_format``. No I/O.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

from pydantic import JsonValue

from wled_mcp.formats import check_format, decode_document, echo, invalid, is_int

GROUP_FORMAT: Final = "wled-mcp.group"
GROUP_FORMAT_VERSION: Final = 1
SUPPORTED_GROUP_VERSIONS: Final = frozenset({GROUP_FORMAT_VERSION})
MAX_DOCUMENT_BYTES: Final = 64 * 1024
MAX_MEMBERS: Final = 16
MAX_SEGMENT_ID: Final = 254
MAX_MEMBER_SEGMENTS: Final = 64
MAX_NAME: Final = 128

ID_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
GROUP_KEYS: Final = ("format", "format_version", "id", "name", "members")
MEMBER_KEYS: Final = frozenset({"device", "segments"})


@dataclass(frozen=True)
class Member:
    device: str
    # Explicit designation only; ``None`` never means "all segments".
    segments: tuple[int, ...] | None = None


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    members: tuple[Member, ...]


def check_id(value: object, label: str) -> str:
    """An ID in the configured-device pattern; also keeps it path-safe."""
    if not isinstance(value, str) or ID_RE.match(value) is None:
        raise invalid(f"The {label} must match [a-z0-9][a-z0-9_-]{{0,63}}.")
    return value


def check_name(value: object, label: str) -> str:
    """1-128 characters, not blank, no control characters (the device name rule)."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_NAME
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise invalid(
            f"The {label} must be 1-{MAX_NAME} characters, not blank and without control "
            "characters."
        )
    return value


def check_segment_ids(value: object, where: str, key: str = "segments") -> tuple[int, ...]:
    """A nonempty list of unique explicit segment IDs 0-254."""
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MEMBER_SEGMENTS:
        raise invalid(f"{where}: '{key}' must list 1-{MAX_MEMBER_SEGMENTS} segment IDs.")
    for item in value:
        if not is_int(item) or not 0 <= item <= MAX_SEGMENT_ID:
            raise invalid(f"{where}: segment IDs must be integers 0-{MAX_SEGMENT_ID}.")
    ids = tuple(int(item) for item in value)
    if len(set(ids)) != len(ids):
        raise invalid(f"{where}: segment IDs must be unique.")
    return ids


def _parse_members(value: object) -> tuple[Member, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MEMBERS:
        raise invalid(f"'members' must list 1-{MAX_MEMBERS} entries.")
    members: list[Member] = []
    for position, item in enumerate(value, start=1):
        where = f"Member {position}"
        if not isinstance(item, dict):
            raise invalid(f"{where} must be an object.")
        unknown = sorted(str(key) for key in item if key not in MEMBER_KEYS)
        if unknown:
            raise invalid(f"{where}: unknown key {echo(unknown[0])}.")
        device = check_id(item.get("device"), f"device ID of member {position}")
        segments = check_segment_ids(item["segments"], where) if "segments" in item else None
        members.append(Member(device, segments))
    seen: dict[str, Member] = {}
    for position, member in enumerate(members, start=1):
        previous = seen.get(member.device)
        if previous is not None:
            if previous.segments != member.segments:
                raise invalid(
                    f"Device {member.device!r} is listed twice with conflicting segment lists "
                    f"(member {position}); a device may appear once per group."
                )
            raise invalid(
                f"Device {member.device!r} is listed twice (member {position}); a device may "
                "appear once per group."
            )
        seen[member.device] = member
    return tuple(members)


def parse_group(raw: str | bytes | dict[str, JsonValue]) -> Group:
    """Strictly validate a group document (JSON text, bytes or object); VALIDATION_ERROR."""
    document = decode_document(raw, "group document", MAX_DOCUMENT_BYTES)
    if not isinstance(document, dict):
        raise invalid("A group document must be a JSON object.")
    check_format(
        document,
        format_name=GROUP_FORMAT,
        label="group",
        supported=SUPPORTED_GROUP_VERSIONS,
        current=GROUP_FORMAT_VERSION,
    )
    unknown = sorted(str(key) for key in document if key not in GROUP_KEYS)
    if unknown:
        raise invalid(f"Unknown group key {echo(unknown[0])}.")
    missing = [key for key in GROUP_KEYS if key not in document]
    if missing:
        raise invalid(f"Missing group key {missing[0]!r}.")
    return Group(
        check_id(document["id"], "group ID"),
        check_name(document["name"], "group name"),
        _parse_members(document["members"]),
    )


def group_document(group: Group) -> dict[str, JsonValue]:
    """The stored (and returned) document of a group; ``parse_group`` reads it back."""
    members: list[JsonValue] = []
    for member in group.members:
        entry: dict[str, JsonValue] = {"device": member.device}
        if member.segments is not None:
            entry["segments"] = list(member.segments)
        members.append(entry)
    return {
        "format": GROUP_FORMAT,
        "format_version": GROUP_FORMAT_VERSION,
        "id": group.id,
        "name": group.name,
        "members": members,
    }


def member_views(group: Group, configured: Collection[str]) -> list[JsonValue]:
    """The exact expansion of a group; flags a member that is not in the inventory."""
    return [
        {
            "member": position,
            "device_id": member.device,
            "segments": list(member.segments) if member.segments is not None else None,
            "in_inventory": member.device in configured,
        }
        for position, member in enumerate(group.members, start=1)
    ]
