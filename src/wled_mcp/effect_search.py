"""Device-aware effect search over a small curated property catalog (#31).

The catalog (``catalog_data/effect_properties.json``) is reviewed project data, shipped in the
package. It is never fetched, edited at runtime or guessed from names. Search intersects
it with the device's real effect list: a catalog entry is usable only when the device
lists that exact name (at the catalog ID, or flagged ``id_changed`` elsewhere). Contract:
docs/contract/effect-search.md.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from wled_mcp import compat
from wled_mcp.catalogs import MAX_CANDIDATES, PLACEHOLDER_NAME

SCHEMA_VERSION: Final = 1
MAX_EVIDENCE = 400

Confidence = Literal["recommended", "verified"]
Basis = Literal["source_review", "observed_run", "author_judgement"]
Motion = Literal["static", "calm", "moderate", "lively"]
Flashing = Literal["none", "occasional", "frequent"]
Level = Literal["low", "medium", "high"]
Length = Literal["short", "medium", "long"]

CONFIDENCE_RANK: Final = {"recommended": 1, "verified": 2}
LEVELS: Final = ("low", "medium", "high")

# property -> (JSON value validation, subjective). Subjective properties are curated
# judgement and can never be ``verified``.
OBJECTIVE: Final = frozenset({"flashing", "colors", "uses_palette"})
PROPERTIES: Final = (
    "motion",
    "flashing",
    "colors",
    "uses_palette",
    "strip_length",
    "visibility",
    "palette_saturation_need",
)

NOTE: Final = (
    "Properties are curated for a small set of effects. Subjective ones (motion, strip "
    "length, visibility, palette saturation need) are recommendations, not guarantees. "
    "flashing is a comfort property, not a photosensitivity or safety guarantee. Apply a "
    "result with an existing control tool using the returned ID."
)


class CatalogFileError(Exception):
    """The shipped catalog is invalid or from a newer schema; a packaging/test failure."""


def _check_value(prop: str, value: object) -> None:
    ok: bool
    if prop == "flashing":
        ok = value in ("none", "occasional", "frequent")
    elif prop == "motion":
        ok = value in ("static", "calm", "moderate", "lively")
    elif prop in ("visibility", "palette_saturation_need"):
        ok = value in LEVELS
    elif prop == "colors":
        ok = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3
    elif prop == "uses_palette":
        ok = isinstance(value, bool)
    elif prop == "strip_length":
        ok = (
            isinstance(value, list)
            and bool(value)
            and len(set(value)) == len(value)
            and all(v in ("short", "medium", "long") for v in value)
        )
    else:
        raise ValueError(f"unknown property {prop!r}")
    if not ok:
        raise ValueError(f"invalid value {value!r} for property {prop!r}")


class PropertyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    value: JsonValue
    confidence: Confidence
    basis: Basis
    evidence: str = Field(min_length=1, max_length=MAX_EVIDENCE)


class EffectEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=64)
    properties: dict[str, PropertyEntry]

    @model_validator(mode="after")
    def _check(self) -> EffectEntry:
        if self.name == PLACEHOLDER_NAME:
            raise ValueError("a placeholder name cannot be catalogued")
        for prop, entry in self.properties.items():
            _check_value(prop, entry.value)
            if entry.confidence == "verified":
                if prop not in OBJECTIVE:
                    raise ValueError(f"subjective property {prop!r} cannot be verified")
                if entry.basis == "author_judgement":
                    raise ValueError(f"verified {prop!r} needs a source or observation basis")
        return self


class FirmwareInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    reviewed: list[str] = Field(min_length=1)
    source: str = Field(min_length=1)


class EffectCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: int
    data_version: str = Field(min_length=1)
    property_notes: str
    firmware: FirmwareInfo
    effects: list[EffectEntry]

    @model_validator(mode="after")
    def _unique(self) -> EffectCatalog:
        ids = [e.id for e in self.effects]
        names = [e.name for e in self.effects]
        if len(set(ids)) != len(ids) or len(set(names)) != len(names):
            raise ValueError("effect IDs and names must be unique")
        return self


def parse_catalog(text: str) -> EffectCatalog:
    """Validate catalog JSON. Rejects an unknown or higher schema version by name."""
    try:
        raw = json.loads(text)
    except ValueError as error:
        raise CatalogFileError(f"effect catalog is not valid JSON: {error}") from error
    version = raw.get("schema_version") if isinstance(raw, dict) else None
    if not isinstance(version, int) or isinstance(version, bool) or version != SCHEMA_VERSION:
        raise CatalogFileError(
            f"effect catalog schema_version {version!r} is not supported; this server "
            f"reads schema_version {SCHEMA_VERSION}"
        )
    try:
        return EffectCatalog.model_validate(raw)
    except ValidationError as error:
        raise CatalogFileError(f"effect catalog is invalid: {error}") from error


@functools.cache
def shipped_catalog() -> EffectCatalog:
    text = (
        resources.files("wled_mcp")
        .joinpath("catalog_data/effect_properties.json")
        .read_text("utf-8")
    )
    return parse_catalog(text)


class SearchEffectsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)
    refresh: bool = False
    motion: list[Motion] | None = Field(default=None, min_length=1, max_length=4)
    flashing: list[Flashing] | None = Field(default=None, min_length=1, max_length=3)
    colors_min: int | None = Field(default=None, ge=0, le=3)
    colors_max: int | None = Field(default=None, ge=0, le=3)
    uses_palette: bool | None = None
    strip_length: Length | None = None
    min_visibility: Level | None = None
    max_palette_saturation_need: Level | None = None
    strict: bool = True
    min_confidence: Confidence = "recommended"
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def _range(self) -> SearchEffectsRequest:
        if (
            self.colors_min is not None
            and self.colors_max is not None
            and self.colors_min > self.colors_max
        ):
            raise ValueError("colors_min must not exceed colors_max")
        return self


@dataclass(frozen=True)
class Filter:
    prop: str
    requested: JsonValue
    test: Any  # callable(value) -> bool


def build_filters(request: SearchEffectsRequest) -> list[Filter]:
    filters: list[Filter] = []
    if request.motion is not None:
        allowed = list(request.motion)
        filters.append(Filter("motion", list(allowed), lambda v: v in allowed))
    if request.flashing is not None:
        allowed_f = list(request.flashing)
        filters.append(Filter("flashing", list(allowed_f), lambda v: v in allowed_f))
    if request.colors_min is not None or request.colors_max is not None:
        low = 0 if request.colors_min is None else request.colors_min
        high = 3 if request.colors_max is None else request.colors_max
        filters.append(Filter("colors", {"min": low, "max": high}, lambda v: low <= v <= high))
    if request.uses_palette is not None:
        wanted = request.uses_palette
        filters.append(Filter("uses_palette", wanted, lambda v: v is wanted))
    if request.strip_length is not None:
        length = request.strip_length
        filters.append(Filter("strip_length", length, lambda v: length in v))
    if request.min_visibility is not None:
        floor = LEVELS.index(request.min_visibility)
        filters.append(
            Filter("visibility", request.min_visibility, lambda v: LEVELS.index(v) >= floor)
        )
    if request.max_palette_saturation_need is not None:
        ceiling = LEVELS.index(request.max_palette_saturation_need)
        filters.append(
            Filter(
                "palette_saturation_need",
                request.max_palette_saturation_need,
                lambda v: LEVELS.index(v) <= ceiling,
            )
        )
    return filters


def _entry_json(entry: PropertyEntry) -> dict[str, JsonValue]:
    return {
        "value": entry.value,
        "confidence": entry.confidence,
        "basis": entry.basis,
        "evidence": entry.evidence,
    }


def _normalized_query(request: SearchEffectsRequest) -> dict[str, JsonValue]:
    query: dict[str, JsonValue] = {}
    for key in (
        "motion",
        "flashing",
        "colors_min",
        "colors_max",
        "uses_palette",
        "strip_length",
        "min_visibility",
        "max_palette_saturation_need",
    ):
        value = getattr(request, key)
        if value is not None:
            query[key] = list(value) if isinstance(value, list) else value
    query["strict"] = request.strict
    query["min_confidence"] = request.min_confidence
    query["limit"] = request.limit
    return query


def search(
    catalog: EffectCatalog,
    device_names: tuple[str, ...],
    firmware_version: str,
    request: SearchEffectsRequest,
) -> tuple[dict[str, JsonValue], list[str]]:
    """Pure matcher: the ``data`` object of the envelope and its warnings."""
    tier = compat.classify(firmware_version)
    warnings: list[str] = []
    applicable = tier not in ("unsupported", "unrecognized")
    if not applicable:
        tier_warning = compat.support_warning(tier)
        if tier_warning:
            warnings.append(tier_warning)
        warnings.append("The curated effect catalog was not applied to this firmware.")
    reviewed = applicable and firmware_version in catalog.firmware.reviewed
    if applicable and not reviewed:
        warnings.append(
            "The firmware version was not reviewed for the effect catalog "
            f"(reviewed: {', '.join(catalog.firmware.reviewed)}); exact name and ID matches "
            "are still returned."
        )
    firmware_match = (
        "not_applicable" if not applicable else ("reviewed" if reviewed else "unreviewed")
    )

    filters = build_filters(request)
    min_rank = CONFIDENCE_RANK[request.min_confidence]
    stale: list[JsonValue] = []
    ambiguous: list[JsonValue] = []
    absent = 0
    present = 0
    claimed: set[int] = set()
    known_fail = unverified_excluded = stale_excluded = 0
    full: list[tuple[int, dict[str, JsonValue]]] = []
    partial: list[tuple[int, dict[str, JsonValue]]] = []

    for entry in catalog.effects if applicable else []:
        positions = [i for i, n in enumerate(device_names) if n == entry.name]
        if len(positions) > 1:
            claimed.update(positions)
            ambiguous.append(
                {
                    "name": entry.name,
                    "catalog_id": entry.id,
                    "candidates": [
                        {"id": i, "name": entry.name} for i in positions[:MAX_CANDIDATES]
                    ],
                    "total": len(positions),
                }
            )
            continue
        if not positions:
            at_id = device_names[entry.id] if entry.id < len(device_names) else None
            if at_id is not None and at_id != PLACEHOLDER_NAME:
                stale.append(
                    {"catalog_id": entry.id, "catalog_name": entry.name, "device_name": at_id}
                )
            else:
                absent += 1
            continue
        device_id = positions[0]
        claimed.add(device_id)
        present += 1
        mapping = "exact" if device_id == entry.id else "id_changed"

        matched: list[JsonValue] = []
        unverified: list[JsonValue] = []
        failed = False
        for flt in filters:
            prop = entry.properties.get(flt.prop)
            if prop is None or CONFIDENCE_RANK[prop.confidence] < min_rank:
                unverified.append(flt.prop)
                continue
            if not flt.test(prop.value):
                failed = True
                break
            matched.append(
                {
                    "property": flt.prop,
                    "requested": flt.requested,
                    "value": prop.value,
                    "confidence": prop.confidence,
                    "basis": prop.basis,
                }
            )
        if failed:
            known_fail += 1
            continue
        if mapping == "id_changed" and request.strict:
            stale_excluded += 1
            continue
        if unverified and request.strict:
            unverified_excluded += 1
            continue
        is_full = not unverified and mapping == "exact"
        result: dict[str, JsonValue] = {
            "id": device_id,
            "name": entry.name,
            "match": "full" if is_full else "partial",
            "mapping": mapping,
            "matched": matched,
            "unverified": unverified,
            "properties": {k: _entry_json(v) for k, v in entry.properties.items()},
        }
        if mapping == "id_changed":
            result["stale_reason"] = (
                f"The catalog lists this effect at ID {entry.id}; the device lists it at ID "
                f"{device_id}."
            )
        (full if is_full else partial).append((device_id, result))

    ordered = [r for _, r in sorted(full, key=lambda x: x[0])] + [
        r for _, r in sorted(partial, key=lambda x: x[0])
    ]
    total = len(ordered)
    results = ordered[: request.limit]
    usable = [n for n in device_names if n != PLACEHOLDER_NAME]
    data: dict[str, JsonValue] = {
        "query": _normalized_query(request),
        "results": list(results),
        "total_matches": total,
        "truncated": total > len(results),
        "catalog": {
            "schema_version": catalog.schema_version,
            "data_version": catalog.data_version,
            "firmware_match": firmware_match,
            "reviewed_firmware": list(catalog.firmware.reviewed),
        },
        "diagnostics": {
            "covered_in_catalog": len(catalog.effects),
            "present_on_device": present,
            "not_on_device_count": absent,
            "stale_mappings": stale[:MAX_CANDIDATES],
            "stale_mappings_total": len(stale),
            "ambiguous": ambiguous[:MAX_CANDIDATES],
            "ambiguous_total": len(ambiguous),
            "device_effects_without_curation": max(
                0, len(usable) - len([i for i in claimed if device_names[i] != PLACEHOLDER_NAME])
            ),
        },
        "note": NOTE,
    }
    if total == 0:
        if not applicable:
            reason, detail = (
                "catalog_not_applicable",
                "The firmware version is outside the supported range; the catalog was not applied.",
            )
        elif present == 0:
            reason, detail = (
                "no_curated_overlap",
                "The device lists none of the curated effects with a usable name.",
            )
        elif unverified_excluded:
            reason, detail = (
                "only_unverified_candidates",
                f"{unverified_excluded} effect(s) were excluded only because a requested "
                "property is unknown or below min_confidence; use strict=false, a lower "
                "min_confidence or fewer filters.",
            )
        elif stale_excluded:
            reason, detail = (
                "only_stale_candidates",
                f"{stale_excluded} effect(s) were found at another ID than the catalog "
                "lists; strict=false returns them flagged id_changed.",
            )
        else:
            reason, detail = (
                "excluded_by_known_properties",
                f"{known_fail} effect(s) have known properties that fail the filters.",
            )
        data["no_match"] = {
            "reason": reason,
            "detail": detail,
            "counts": {
                "known_property_mismatch": known_fail,
                "unverified": unverified_excluded,
                "stale": stale_excluded,
            },
        }
    return data, warnings
