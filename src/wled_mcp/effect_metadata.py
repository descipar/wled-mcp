"""Lenient interpretation of explicit WLED fxdata; never an effect classifier.

Format evidence: WLED v16.0.1, 29b389df1c1aaec6ff53aea742d17063b985906c,
index.js 1612–1739 and FX_fcn.cpp 599–617. Unknown data stays unknown.
"""

from pydantic import JsonValue

SLIDERS = ("speed", "intensity", "custom1", "custom2", "custom3")
OPTIONS = ("check1", "check2", "check3")
DEFAULT_LABELS = (
    "Effect speed",
    "Effect intensity",
    "Custom 1",
    "Custom 2",
    "Custom 3",
    "Check 1",
    "Check 2",
    "Check 3",
)
COLOR_LABELS = ("Fx color", "Background color", "Custom")
DEFAULT_KEYS = {
    "sx": ("speed", 255),
    "ix": ("intensity", 255),
    "c1": ("custom1", 255),
    "c2": ("custom2", 255),
    "c3": ("custom3", 31),
    "o1": ("check1", 1),
    "o2": ("check2", 1),
    "o3": ("check3", 1),
    "pal": ("palette_id", 255),
    "m12": ("map_1d_2d", 4),
    "si": ("sound_simulation", 3),
}


def parse_fxdata(raw: str) -> tuple[dict[str, JsonValue], list[str]]:
    """Return partial parsed data and bounded, value-free warnings; raw is kept by caller."""
    parsed: dict[str, JsonValue] = {
        "sliders": {key: None for key in SLIDERS},
        "options": {key: None for key in OPTIONS},
        "color_slots": [None, None, None],
        "palette": {"selectable": None, "label": None, "fixed_palette_id": None},
        "flags": {
            key: None
            for key in (
                "zero_d",
                "one_d",
                "two_d",
                "audio_reactive",
                "volume_reactive",
                "frequency_reactive",
            )
        },
        "defaults": {},
    }
    warnings: list[str] = []
    if not raw:
        return parsed, warnings
    parts = raw.split(";")
    if len(parts) < 3 or len(parts) > 5 or "@" in raw or any(ord(c) < 32 for c in raw):
        return parsed, ["Unrecognized effect metadata structure; parsed properties are unknown."]
    controls = parts[0].split(",")
    if len(controls) > 8:
        warnings.append("Extra control labels were ignored.")
    labels: dict[str, JsonValue] = {}
    for i, key in enumerate((*SLIDERS, *OPTIONS)):
        token = controls[i].strip() if i < len(controls) else ""
        labels[key] = DEFAULT_LABELS[i] if token == "!" else token or None
    parsed["sliders"] = {key: labels[key] for key in SLIDERS}
    parsed["options"] = {key: labels[key] for key in OPTIONS}
    colors = parts[1].split(",")
    if len(colors) > 3:
        warnings.append("Extra color labels were ignored.")
    parsed["color_slots"] = [
        COLOR_LABELS[i] if token == "!" else token or None
        for i in range(3)
        for token in [colors[i].strip() if i < len(colors) else ""]
    ]
    palette = parts[2].strip()
    if palette.isdecimal():
        number = int(palette) if len(palette) <= 3 else 256
        if number <= 255:
            parsed["palette"] = {"selectable": False, "label": None, "fixed_palette_id": number}
        else:
            warnings.append("Invalid fixed palette ID; palette metadata is unknown.")
    else:
        parsed["palette"] = {
            "selectable": bool(palette),
            "label": "Palette" if palette == "!" else palette or None,
            "fixed_palette_id": None,
        }
    if len(parts) >= 4 and parts[3]:
        flags = parts[3]
        if set(flags) <= set("012vf"):
            parsed["flags"] = {
                "zero_d": "0" in flags,
                "one_d": "1" in flags,
                "two_d": "2" in flags,
                "audio_reactive": "v" in flags or "f" in flags,
                "volume_reactive": "v" in flags,
                "frequency_reactive": "f" in flags,
            }
        else:
            warnings.append(
                "Unrecognized effect flags; dimension and audio properties are unknown."
            )
    defaults: dict[str, JsonValue] = {}
    if len(parts) >= 5 and parts[4]:
        for token in parts[4].split(","):
            key, separator, value = token.partition("=")
            if (
                separator
                and key in DEFAULT_KEYS
                and value.isascii()
                and value.isdecimal()
                and len(value) <= 3
            ):
                field, maximum = DEFAULT_KEYS[key]
                number = int(value)
                if number <= maximum and field not in defaults:
                    defaults[field] = bool(number) if field in OPTIONS else number
                    continue
            if (
                "Some effect defaults were not recognized or valid; they were ignored."
                not in warnings
            ):
                warnings.append(
                    "Some effect defaults were not recognized or valid; they were ignored."
                )
    parsed["defaults"] = defaults
    return parsed, warnings
