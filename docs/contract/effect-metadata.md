# Effect metadata and filters — W-CAT-02, CAT-01 (#148)

`wled_get_effects` keeps the device's original effect IDs and names and the existing
firmware-aware cache, TTL, `refresh` and optional-endpoint behavior. It now excludes
`RSVD` placeholder effects, including without filters. IDs are never renumbered;
`count` is the number of returned effects. Palette listing is unchanged.

Optional filters intersect:

- `query`: case-folded substring of the device's effect name, at most 128 characters.
- `two_d`: explicit known 2D metadata must equal the requested boolean.
- `audio_reactive`: explicit known volume/frequency-reactive metadata must equal
  the requested boolean.

Unknown flags never satisfy either `true` or `false`. These filters report firmware
metadata, not verified hardware geometry, sound hardware or effect behavior.

Each effect with available metadata retains `metadata.fxdata` and adds
`metadata.parsed` and `metadata.warnings`. Parsing is lenient: an unrecognized
entry does not fail the catalog call, retains its raw string and reports a warning.
The result also warns when a returned effect was only partially parsed.

| Parsed field | Meaning |
| --- | --- |
| `sliders` | Labels keyed by `speed`, `intensity`, `custom1`–`custom3`. |
| `options` | Labels keyed by `check1`–`check3`. Generic `Check N` labels do not imply effect-specific semantics. |
| `color_slots` | Three positional color-slot labels. |
| `palette` | `selectable`, selector `label` and `fixed_palette_id`, each unknown when unavailable. A numeric token identifies a fixed palette and hides the selector. This is selector metadata, not a claim about every internal use of palettes. |
| `flags` | `zero_d`, `one_d`, `two_d`, `audio_reactive`, `volume_reactive`, `frequency_reactive`; booleans only for an explicit recognized flag section. |
| `defaults` | Present recognized defaults mapped from firmware keys to public field names; option defaults are booleans. No default is applied to lighting. |

`!` uses the firmware UI's default slider/color labels, `Palette`, or generic
checkbox labels. Empty control/color slots have null labels. With empty metadata
all labels and flags are unknown; a missing/empty flag section stays unknown rather
than assuming the firmware UI's 1D display fallback. Unknown flag characters make
the flags unknown. Invalid/unknown defaults are ignored with a warning; absent
defaults are never manufactured. Missing metadata still leaves names available.

The parser is based on the pinned WLED 16.0.1 source in [SOURCES.md](../SOURCES.md).
It does not change the curated properties or matching of `wled_search_effects`.
Effect/palette IDs remain device-specific; parsing does not authorize writes.
