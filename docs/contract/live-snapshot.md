# Live LED snapshot (LIVE-01, #150)

`wled_get_live_snapshot(device_id, max_runs=512)` is a read-class, idempotent,
non-destructive tool in every profile. It observes one configured controller with
fresh state, info and `/json/live` GETs under one device lock and total deadline.
It never writes, polls, stores observations or opens a stream. Both transports use
this same operation and contract. Read start and capture completion are UTC times;
these sequential reads are not an atomic device snapshot.

The result's `data` reports `status`, source endpoint, timestamps and firmware.
HTTP 404/501 returns `ok=true`, `status=unavailable`, the numeric `http_status`, no
segments and an explicit unknown cause (missing, disabled or unsupported). Other
HTTP failures, malformed live data, timeout and unreachable-device failures retain
the existing distinct safe error envelope. Empty valid samples have `status=empty`;
empty does not mean black. No raw info, addresses or response bodies are returned.

## Samples, ranges and limits

The live decoder requires up to 4096 six-digit RGB hexadecimal samples and a
positive non-boolean integer `n` (sampling step, at most 1,000,000). Optional `w`
and `h` must both be positive bounded integers. Common response byte, JSON depth,
node and deadline limits also apply.

For 1D, sample k observes LED index k*n. Only indices inside an active segment's
`[start,stop)` (exclusive stop) are mapped. Sparse segment IDs are retained;
zero-length inactive entries are omitted. A run contains `first_led`,
`sample_count` and `rgb`: its sampled indices are
`first_led + j*sampling_step`, for 0 <= j < sample_count. For a step above one,
**intervening LEDs remain unknown**, even in a run of identical sampled colors.

Each segment reports expected, available and returned sample counts, its number
of unsampled LEDs, and a status: `sampled`, `no_samples`, `missing_samples`,
`truncated`, `unknown_or_stale_geometry` or `unmapped_matrix`. Unknown LED count or
out-of-range segment geometry produces no invented runs. `source_count_matches_geometry`
reports whether the device's source count agrees with 1D info geometry; state and
live observations can differ while a device changes.

`gaps` and `overlaps` describe returned valid segment ranges, not inferred physical
wiring. They are explicitly scoped to those ranges when geometry is unknown or
segments are omitted. An overlapping segment may reference the same sample twice;
that is no attribution of which segment produced it.

Limits are global: `max_runs` is a strict integer 1–512, shared by every segment,
including overlaps. At most 128 active segments are returned; `omitted_segments`
reports the rest. `returned_runs`, `max_runs`, `max_segments` and per-segment
truncation/counts expose incomplete output. Color runs are not expanded to one
entry per physical LED. Serialized `data` is capped at 128 KiB; exceeding this
returns a safe `INVALID_RESPONSE` instead of an oversized result.

A reported matrix (`w`/`h` or matrix info) is explicitly unmapped: its source
geometry/count/step remain visible, but there are no per-segment color runs.
The firmware's matrix sampling skips rows, so flattening k*n would be incorrect.
2D mapping is outside this initial tool's scope.

## Interpretation and source

This is an observation, not calibrated physical color, animation simulation,
persistence or causal proof. WLED's live RGB combines the white channel into RGB
and scales by global brightness; it cannot recover separate RGBW channels.

Mapping/approximation source: WLED 16.0.1 pinned commit
[`29b389df1c1aaec6ff53aea742d17063b985906c`, `serveLiveLeds`](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp#L1394).
No firmware implementation was copied. Unsupported geometry is explicit rather
than inferred. Positive mapping evidence uses synthetic fixtures; the selected
hardware controller's live endpoint returned HTTP 501 (see validation record).
