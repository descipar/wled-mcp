# Effect metadata and filters — W-CAT-02, CAT-01 (#148)

`wled_get_effects` keeps the device's original effect IDs and names and the firmware-aware cache,
TTL, `refresh` and optional-endpoint behavior. It excludes `RSVD` placeholder effects, also without
filters. IDs are never renumbered; `count` is the number of returned effects. Palette listing is
unchanged.

Optional filters intersect:

- `query`: case-folded substring of the effect name, at most 128 characters.
- `two_d`, `audio_reactive`: explicit known metadata (2D; volume/frequency-reactive) must equal the
  requested boolean. Unknown flags satisfy neither `true` nor `false`.

Filters report firmware metadata, not verified hardware geometry, sound hardware or effect behavior.

Each effect with metadata retains `metadata.fxdata` and adds `metadata.parsed` and
`metadata.warnings`. Parsing is lenient: an unrecognized entry keeps its raw string and warns; a
partially parsed returned effect warns too.

| Parsed field | Meaning |
| --- | --- |
| `sliders` | Labels keyed by `speed`, `intensity`, `custom1`-`custom3`. |
| `options` | Labels keyed by `check1`-`check3`. Generic `Check N` labels imply no effect-specific semantics. |
| `color_slots` | Three positional color-slot labels. |
| `palette` | `selectable`, selector `label` and `fixed_palette_id`, each unknown when unavailable. A numeric token identifies a fixed palette and hides the selector (selector metadata, not a claim about internal palette use). |
| `flags` | `zero_d`, `one_d`, `two_d`, `audio_reactive`, `volume_reactive`, `frequency_reactive`; booleans only for an explicit recognized flag section. |
| `defaults` | Recognized defaults mapped from firmware keys to public field names; option defaults are booleans. No default is applied to lighting. |

`!` uses the firmware UI's default slider/color labels, `Palette` or generic checkbox labels. Empty
control/color slots have null labels. With empty metadata all labels and flags are unknown; a
missing/empty flag section stays unknown (no 1D display fallback assumed); unknown flag characters
make the flags unknown. Invalid/unknown defaults are ignored with a warning; absent defaults are
never manufactured. Names stay available without metadata.

The parser is based on the pinned WLED 16.0.1 source ([SOURCES.md](../SOURCES.md)). It does not
change the curated properties or matching of `wled_search_effects`. Effect/palette IDs remain
device-specific; parsing authorizes no writes.
