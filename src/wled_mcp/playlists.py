"""Playlist authoring of issue #18: typed request, unit conversion and the playlist object.

No network I/O. The object is written through the playlist route of
``preset_writes`` (ISSUE-18-DEC-001): the save starts the playlist, then the firmware
stores it re-serialized. Bounds follow the pinned WLED v16.0.1 ``playlist.cpp``
(docs/SOURCES.md "Issue-18 WLED 16 preset write evidence"):

- ``dur`` is kept in tenths of a second and constrained to 0-42949670; 0 keeps the
  entry until playback is advanced.
- The per-entry ``transition`` is a 16-bit tenths value that is multiplied by 100 into
  the 16-bit live transition, so more than 655 tenths would wrap.
- ``repeat`` is stored in a byte after adding one extra pass, so more than 254 would
  wrap (255 becomes endless); a negative value means "endless and shuffled".
- ``end`` is a byte; 255 restores the previous preset and is refused, as for
  activation; 251-254 mean no end preset and are not accepted either.

Values the firmware would wrap, clamp or reinterpret are rejected, never normalized.
"""

from __future__ import annotations

import math
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from wled_mcp.preset_writes import (
    MAX_PLAYLIST_DURATION,
    MAX_PLAYLIST_ENTRIES,
    MAX_PLAYLIST_REPEAT,
)
from wled_mcp.presets import DeviceId, PresetId, validate_preset_name

# Live transition: tenths x 100 must fit the firmware's 16-bit millisecond value.
MAX_AUTHORED_TRANSITION: Final = 655
# repeat is stored in a byte after one extra pass is added.
MAX_REPEAT: Final = MAX_PLAYLIST_REPEAT
TENTHS_TOLERANCE: Final = 1e-6


def to_tenths(seconds: float, label: str, upper: int) -> int:
    """Exact seconds to tenths; a value that is not a multiple of 0.1 s is rejected."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"{label} must be a finite, non-negative number of seconds")
    scaled = seconds * 10
    tenths = round(scaled)
    if abs(scaled - tenths) > TENTHS_TOLERANCE:
        raise ValueError(f"{label} must be a multiple of 0.1 seconds (the firmware unit)")
    if tenths > upper:
        raise ValueError(f"{label} exceeds {upper / 10:g} seconds")
    return tenths


class PlaylistMember(BaseModel):
    """One playlist step: an existing state preset, its duration and transition."""

    model_config = ConfigDict(extra="forbid", strict=True)
    preset_id: PresetId
    duration_s: float = Field(
        ge=0, description="Seconds in steps of 0.1; 0 keeps the entry until advanced"
    )
    transition_s: float = Field(ge=0, description="Seconds in steps of 0.1, at most 65.5")

    @field_validator("duration_s")
    @classmethod
    def valid_duration(cls, value: float) -> float:
        to_tenths(value, "duration_s", MAX_PLAYLIST_DURATION)
        return value

    @field_validator("transition_s")
    @classmethod
    def valid_transition(cls, value: float) -> float:
        to_tenths(value, "transition_s", MAX_AUTHORED_TRANSITION)
        return value


class SavePlaylistRequest(BaseModel):
    """Create or replace one native WLED playlist; saving starts it."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    name: str
    entries: list[PlaylistMember] = Field(min_length=1, max_length=MAX_PLAYLIST_ENTRIES)
    repeat: int = Field(ge=0, le=MAX_REPEAT, description="0 = endless, n = n passes")
    shuffle: bool
    end_preset_id: PresetId | None = None
    preset_id: PresetId | None = None
    overwrite: bool = False
    dry_run: bool = False

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_preset_name(value)

    @model_validator(mode="after")
    def overwrite_needs_explicit_id(self) -> SavePlaylistRequest:
        if self.overwrite and self.preset_id is None:
            raise ValueError("overwrite=true requires an explicit preset_id")
        return self


def playlist_object(request: SavePlaylistRequest) -> dict[str, JsonValue]:
    """The exact entry that is sent: full per-entry arrays, explicit repeat/end/shuffle."""
    playlist: dict[str, JsonValue] = {
        "ps": [member.preset_id for member in request.entries],
        "dur": [
            to_tenths(member.duration_s, "duration_s", MAX_PLAYLIST_DURATION)
            for member in request.entries
        ],
        "transition": [
            to_tenths(member.transition_s, "transition_s", MAX_AUTHORED_TRANSITION)
            for member in request.entries
        ],
        "repeat": request.repeat,
        "end": request.end_preset_id or 0,
        "r": request.shuffle,
    }
    return {"playlist": playlist, "n": request.name}


def playback_notes(
    members: list[int], before: dict[str, JsonValue], target: int
) -> dict[str, JsonValue]:
    """What the save does to playback, for the preview and the result."""
    active = before.get("active_preset_id")
    return {
        "starts_playlist": True,
        "active_preset_id": active,
        "active_preset_is_member": isinstance(active, int) and active in members,
        "destination_is_active_preset": active == target,
        "running_playlist_hazard": (
            "Saving is refused while any playlist runs (state.pl > 0), checked during "
            "planning and again after the snapshot: the firmware could keep the running "
            "playlist and store it instead of this one."
        ),
    }
