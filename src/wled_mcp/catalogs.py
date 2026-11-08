"""Effect/palette catalogs: ID-preserving reads, optional fxdata, cache and name resolver.

A catalog ID is the array index of the device list (`/json/eff`, `/json/pal`); lists
are never compacted. Unavailable effect slots are serialized by the baseline firmware
(profile 0: v0.15.1 source, observed on 16.0.1) as the literal name "RSVD" and are
flagged as placeholders. `/json/fxdata`
is optional metadata: a raw string per effect, never a source of names.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import anyio
from pydantic import JsonValue

from wled_mcp.client import ClientFailure, Deadline, Endpoint
from wled_mcp.readmodels import Collector, InfoIdentity, as_dict, opt_int, read_identity

if TYPE_CHECKING:
    from wled_mcp.resources import OperationContext

Kind = Literal["effects", "palettes"]
PLACEHOLDER_NAME = "RSVD"  # pinned source: FX.cpp `_data_RESERVED`
MAX_CANDIDATES = 10


@dataclass
class Clock:
    """Injectable time source so cache behavior is testable without sleeping."""

    monotonic: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = lambda: datetime.now(UTC)


@dataclass(frozen=True)
class CatalogEntry:
    names: tuple[str, ...]
    fxdata: tuple[str, ...] | None
    metadata_reason: str | None  # None when available (or not applicable)
    identity: InfoIdentity
    fetched_monotonic: float
    fetched_at: datetime
    warnings: tuple[str, ...]


class CatalogCache:
    """Per (device_id, kind) entries; TTL 0 disables storage. Never holds state/info."""

    def __init__(self, ttl_seconds: int, clock: Clock | None = None) -> None:
        self.ttl_seconds = ttl_seconds
        self.clock = clock if clock is not None else Clock()
        self._entries: dict[tuple[str, Kind], CatalogEntry] = {}

    def get(self, key: tuple[str, Kind]) -> CatalogEntry | None:
        """A live entry only; an expired one is removed and never served."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self.age(entry) >= self.ttl_seconds:
            del self._entries[key]
            return None
        return entry

    def put(self, key: tuple[str, Kind], entry: CatalogEntry) -> None:
        if self.ttl_seconds > 0:
            self._entries[key] = entry

    def drop(self, key: tuple[str, Kind]) -> None:
        self._entries.pop(key, None)

    def age(self, entry: CatalogEntry) -> float:
        return max(0.0, self.clock.monotonic() - entry.fetched_monotonic)

    def __len__(self) -> int:
        return len(self._entries)


@dataclass(frozen=True)
class CatalogView:
    entry: CatalogEntry
    source: Literal["device", "cache"]
    age_seconds: float
    refreshed: bool
    warnings: tuple[str, ...]


class AmbiguousName(ClientFailure):
    """AMBIGUOUS_NAME with bounded (id, name) candidates for the envelope data."""

    def __init__(self, candidates: list[JsonValue], total: int) -> None:
        super().__init__(
            "AMBIGUOUS_NAME", f"Name matches {total} catalog entries; choose an ID instead."
        )
        self.candidates = candidates
        self.total = total


def _count_warning(kind: Kind, listed: int, info: dict[str, JsonValue]) -> str | None:
    key = "fxcount" if kind == "effects" else "palcount"
    reported = opt_int(info, key, "", Collector())
    if reported is None or reported == listed:
        return None
    suffix = " Custom palettes are not part of /json/pal." if kind == "palettes" else ""
    return (
        f"Device reports {reported} {kind} but the catalog lists {listed}; "
        f"IDs are kept as listed.{suffix}"
    )


async def _fetch(
    ctx: OperationContext,
    cache: CatalogCache,
    kind: Kind,
    identity: InfoIdentity,
    info: dict[str, JsonValue],
) -> CatalogEntry:
    endpoint = Endpoint.EFFECTS if kind == "effects" else Endpoint.PALETTES
    value = await ctx.read(endpoint)
    if not isinstance(value, list) or not all(isinstance(n, str) for n in value):
        raise ClientFailure("INVALID_RESPONSE", f"Device returned a malformed {endpoint.label}.")
    names = tuple(n for n in value if isinstance(n, str))
    warnings: list[str] = []
    fxdata: tuple[str, ...] | None = None
    reason: str | None = None
    if kind == "effects":
        try:
            # Optional metadata gets at most half of the remaining budget so that a
            # hanging /json/fxdata cannot consume the deadline of an otherwise good read.
            remaining = ctx.deadline.remaining()
            optional = Deadline(min(ctx.deadline.expires, anyio.current_time() + remaining / 2))
            raw = await ctx.client.read(ctx.device, Endpoint.FXDATA, optional)
            if not isinstance(raw, list) or not all(isinstance(n, str) for n in raw):
                raise ClientFailure("INVALID_RESPONSE", "Device returned a malformed fxdata.")
            if len(raw) != len(names):
                reason = "length_mismatch"
                warnings.append(
                    "Effect metadata length differs from the effect list; metadata unavailable."
                )
            else:
                fxdata = tuple(n for n in raw if isinstance(n, str))
        except ClientFailure as failure:
            reason = failure.error.code
            warnings.append(
                f"Effect metadata unavailable ({failure.error.code}); names are unaffected."
            )
    mismatch = _count_warning(kind, len(names), info)
    if mismatch:
        warnings.append(mismatch)
    return CatalogEntry(
        names=names,
        fxdata=fxdata,
        metadata_reason=reason,
        identity=identity,
        fetched_monotonic=cache.clock.monotonic(),
        fetched_at=cache.clock.now(),
        warnings=tuple(warnings),
    )


async def load_catalog(
    ctx: OperationContext, cache: CatalogCache, kind: Kind, refresh: bool = False
) -> CatalogView:
    """Fresh /json/info identity read, then cache hit or device read. Raises ClientFailure.

    A hit requires a live entry whose (ver, vid) equals the fresh info; a mismatch drops the
    entry and refetches. No stale fallback: info failure is an error. A failed refresh
    leaves the previous entry untouched.
    """
    raw_info = await ctx.read(Endpoint.INFO)
    identity = read_identity(raw_info)
    key = (ctx.device.id, kind)
    if not refresh:
        entry = cache.get(key)
        if entry is not None:
            if entry.identity == identity:
                return CatalogView(
                    entry, "cache", round(cache.age(entry), 3), False, entry.warnings
                )
            cache.drop(key)
    entry = await _fetch(ctx, cache, kind, identity, as_dict(raw_info))
    cache.put(key, entry)
    return CatalogView(entry, "device", 0.0, refresh, entry.warnings)


def catalog_items(entry: CatalogEntry, kind: Kind) -> list[JsonValue]:
    items: list[JsonValue] = []
    for index, name in enumerate(entry.names):
        item: dict[str, JsonValue] = {"id": index, "name": name}
        if kind == "effects":
            if name == PLACEHOLDER_NAME:
                item["placeholder"] = True
            if entry.fxdata is not None:
                item["metadata"] = {"fxdata": entry.fxdata[index]}
        items.append(item)
    return items


def resolve_name(entry: CatalogEntry, kind: Kind, query: str) -> int:
    """Internal resolver for later setters: exact, then unique case-folded trimmed match.

    Placeholders are never matched; there is no fuzzy matching. Raises AmbiguousName with
    bounded candidates or VALIDATION_ERROR when nothing matches.
    """
    candidates = [
        (index, name)
        for index, name in enumerate(entry.names)
        if not (kind == "effects" and name == PLACEHOLDER_NAME)
    ]
    if not query.strip():
        raise ClientFailure("VALIDATION_ERROR", f"A {kind[:-1]} name must not be blank.")
    for matches in (
        [c for c in candidates if c[1] == query],
        [c for c in candidates if c[1].strip().casefold() == query.strip().casefold()],
    ):
        if len(matches) == 1:
            return matches[0][0]
        if len(matches) > 1:
            raise AmbiguousName(
                [{"id": i, "name": n} for i, n in matches[:MAX_CANDIDATES]], len(matches)
            )
    raise ClientFailure("VALIDATION_ERROR", f"No {kind[:-1]} matches the requested name.")
