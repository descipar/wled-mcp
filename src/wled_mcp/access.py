"""Tool classes, access profiles and per-device ceilings (issue #20, ISSUE-20-DEC-001/-002).

Pure types and policy arithmetic; no I/O and no imports from the rest of the package, so
configuration, the server adapter and the resource engines can all depend on it.

The vocabulary is ``read`` (no live, storage or local file mutation), ``control`` (live
device output only) and ``manage`` (device storage or local persistent artifacts). A
profile is a cumulative set of classes; a device may carry a lower ceiling. The effective
ceiling for a device is the lower of the two.
"""

from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Literal, get_args


class ToolClass(StrEnum):
    """Tool classes of ISSUE-20-DEC-001; ordered READ < CONTROL < MANAGE."""

    READ = "read"
    CONTROL = "control"
    MANAGE = "manage"

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK = {ToolClass.READ: 0, ToolClass.CONTROL: 1, ToolClass.MANAGE: 2}

ProfileName = Literal["read-only", "control", "full"]
ClassName = Literal["read", "control", "manage"]
PROFILE_NAMES: tuple[str, ...] = get_args(ProfileName)
DEFAULT_PROFILE: ProfileName = "full"

# Cumulative profiles (TD-20-1). A tool is registered when its class is in the set.
PROFILES: Mapping[str, frozenset[ToolClass]] = MappingProxyType(
    {
        "read-only": frozenset({ToolClass.READ}),
        "control": frozenset({ToolClass.READ, ToolClass.CONTROL}),
        "full": frozenset({ToolClass.READ, ToolClass.CONTROL, ToolClass.MANAGE}),
    }
)


# Tool groups (issue #236, ISSUE-236-DEC-001). ``core`` is always registered; ``all`` is the
# reserved word for every group and the default.
TOOL_GROUPS: tuple[str, ...] = (
    "core",
    "presets",
    "scenes",
    "layout",
    "signals",
    "diagnostics",
    "discovery",
)
GROUP_ALL = "all"
CORE_GROUP = "core"
ALL_GROUPS: frozenset[str] = frozenset(TOOL_GROUPS)


def parse_group_names(names: Sequence[str]) -> frozenset[str]:
    """The effective group set for validated names: ``core`` plus the listed groups.

    ``all`` anywhere selects every group. Names must already be validated.
    """
    if GROUP_ALL in names:
        return ALL_GROUPS
    return frozenset(names) | {CORE_GROUP}


def lower(first: ToolClass, second: ToolClass) -> ToolClass:
    """The lower of two classes."""
    return first if first.rank <= second.rank else second


def profile_ceiling(profile: str) -> ToolClass:
    """The highest class a profile includes."""
    return max(PROFILES[profile], key=lambda tool_class: tool_class.rank)


@dataclass(frozen=True)
class AccessPolicy:
    """Process profile plus optional per-device ceilings; the default is ``full``, no caps."""

    profile: ProfileName = DEFAULT_PROFILE
    caps: Mapping[str, ToolClass] = field(default_factory=lambda: MappingProxyType({}))
    groups: frozenset[str] = ALL_GROUPS

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            raise ValueError("Unknown access profile")
        if not self.groups <= ALL_GROUPS or CORE_GROUP not in self.groups:
            raise ValueError("Unknown tool group set")
        object.__setattr__(self, "caps", MappingProxyType(dict(self.caps)))

    @property
    def classes(self) -> frozenset[ToolClass]:
        """Classes whose tools a server with this profile registers."""
        return PROFILES[self.profile]

    def ceiling(self, device_id: str | None = None) -> ToolClass:
        """Effective ceiling: the lower of the profile and the device cap (if any)."""
        base = profile_ceiling(self.profile)
        cap = self.caps.get(device_id) if device_id is not None else None
        return base if cap is None else lower(base, cap)

    def permits_class(self, tool_class: ToolClass) -> bool:
        """Whether the profile registers tools of this class."""
        return tool_class in self.classes

    def registers(self, tool_class: ToolClass, group: str) -> bool:
        """Whether a tool is registered: its class is in the profile AND its group is selected."""
        return self.permits_class(tool_class) and group in self.groups

    def permits(self, tool_class: ToolClass, device_id: str | None = None) -> bool:
        """Whether a tool of this class may act on the device (or at all, without one)."""
        return tool_class.rank <= self.ceiling(device_id).rank


# The class of the tool call being executed, set by the server dispatcher for the duration
# of ``execute`` (G3). Tasks started inside the call inherit it. ``None`` outside a tool
# call; the write engines then assume the highest class, so with any restriction an engine
# call outside a tool context is refused.
CURRENT_TOOL_CLASS: ContextVar[ToolClass | None] = ContextVar("wled_mcp_tool_class", default=None)


def denial_message(device_id: str, tool_class: ToolClass, ceiling: ToolClass) -> str:
    """Fixed refusal text naming only the device ID and class names, never any tool."""
    return (
        f"Device '{device_id}' allows at most {ceiling.value} operations in this deployment; "
        f"this operation needs {tool_class.value}."
    )
