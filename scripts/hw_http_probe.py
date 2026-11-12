"""Opt-in read-only probe for a deployed wled-mcp Streamable HTTP endpoint (issue #12).

Standard library only (Python 3.11 or later), so it runs with the service image's Python
or another host Python. It sends JSON-RPC ``ping``, ``tools/list`` or ``tools/call`` for
an allowlist of read-only tools and measures latency under configurable concurrency.
Any other tool name is refused before a connection is opened. The ``body-bound`` mode
posts a padded ``ping`` just under and one byte over the request-body bound and records
whether the service answers 413 for the oversized body.

The credential comes from exactly one of a file, a named environment variable or stdin.
It is sent only in the ``Authorization`` header and never printed or logged; the JSON
report is additionally scrubbed of it. Diagnostics go to stderr. ``--output`` creates the
report with file mode 0600 on POSIX; on Windows that mode only toggles the read-only
attribute and the file inherits the access control of its directory, so the script does not
protect it there (write it to a directory only you can read; it holds no credential, but
can hold the endpoint URL and, with ``--include-results``, device state).

This is a manual hardware/target tool (ISSUE-12-DEC-002, TD-12-4). It is never run
against devices or targets in CI; its tests use a loopback stub and the in-process
service.

Usage:
    python hw_http_probe.py --url http://wled-mcp:8000/mcp --token-file /run/secrets/x \\
        tools-list --concurrency 4 --requests 200
    python hw_http_probe.py --url URL --token-env NAME call --tool wled_get_state \\
        --arguments '{"device_id": "example"}' --concurrency 1 --requests 20
    python hw_http_probe.py --url URL --token-stdin body-bound < token-file
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import IO, Any
from urllib.parse import urlsplit

READ_ONLY_TOOLS = frozenset(
    {
        "wled_list_devices",
        "wled_get_state",
        "wled_get_effects",
        "wled_get_palettes",
        "wled_list_presets",
        "wled_get_preset",
    }
)
# Mirrors the service's MAX_REQUEST_BODY_BYTES (256 KiB); configurable with --limit.
DEFAULT_BODY_LIMIT = 262144
MAX_CONCURRENCY = 64
MAX_REQUESTS = 5000
# Device-bound reads stay light to protect the controller (packet L3).
MAX_CALL_CONCURRENCY = 8
MAX_CALL_REQUESTS = 100
MAX_REPORTED_ERRORS = 20
PERCENTILES = (50, 90, 95, 99)
REDACTED = "[redacted]"
USAGE_ERROR = 2


class ProbeError(Exception):
    """A refused or invalid probe configuration; nothing has been sent."""


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str
    port: int
    path: str
    host_header: str | None
    token: str
    timeout: float

    def describe(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}{self.path}"


@dataclass
class Sample:
    index: int
    request_bytes: int
    t_send: float
    t_response: float | None = None
    latency_ms: float | None = None
    status: int | None = None
    outcome: str = "pending"
    detail: str | None = None
    result: Any = None


# ----------------------------------------------------------------------------- inputs


def parse_target(url: str, host_header: str | None, token: str, timeout: float) -> Target:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ProbeError("--url must be an absolute http:// or https:// URL")
    if parts.username is not None or parts.password is not None:
        raise ProbeError("--url must not carry credentials; use a token source option")
    if parts.query or parts.fragment:
        raise ProbeError("--url must not carry a query or fragment")
    if not timeout > 0:
        raise ProbeError("--timeout must be positive")
    if host_header is not None and not _printable(host_header):
        raise ProbeError("--host-header must be printable ASCII without whitespace")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return Target(
        parts.scheme, parts.hostname, port, parts.path or "/", host_header, token, timeout
    )


def _printable(value: str) -> bool:
    return bool(value) and value.isascii() and all(0x21 <= ord(char) <= 0x7E for char in value)


def read_token(args: argparse.Namespace, environ: Mapping[str, str], stdin: IO[str]) -> str:
    if args.token_file is not None:
        try:
            with open(args.token_file, encoding="ascii") as handle:
                raw = handle.read(4097)
        except (OSError, UnicodeDecodeError):
            raise ProbeError("the token file could not be read") from None
    elif args.token_env is not None:
        if args.token_env not in environ:
            raise ProbeError("the named token environment variable is not set")
        raw = environ[args.token_env]
    else:
        raw = stdin.readline(4097)
    token = raw.removesuffix("\n").removesuffix("\r")
    if len(token) > 4096 or not _printable(token):
        # Never echo the value: it may be the credential or a fragment of it.
        raise ProbeError("the credential is empty or not printable ASCII without whitespace")
    return token


def check_tool(tool: str, arguments_text: str) -> dict[str, Any]:
    if tool not in READ_ONLY_TOOLS:
        raise ProbeError(
            f"refusing tool {tool!r}: only read-only tools are allowed "
            f"({', '.join(sorted(READ_ONLY_TOOLS))})"
        )
    try:
        arguments = json.loads(arguments_text)
    except json.JSONDecodeError:
        raise ProbeError("--arguments must be a JSON object") from None
    if not isinstance(arguments, dict):
        raise ProbeError("--arguments must be a JSON object")
    return arguments


def check_load(mode: str, concurrency: int, requests: int) -> None:
    max_concurrency, max_requests = (
        (MAX_CALL_CONCURRENCY, MAX_CALL_REQUESTS)
        if mode == "call"
        else (MAX_CONCURRENCY, MAX_REQUESTS)
    )
    if not 1 <= concurrency <= max_concurrency:
        raise ProbeError(f"--concurrency must be between 1 and {max_concurrency} for {mode}")
    if not 1 <= requests <= max_requests:
        raise ProbeError(f"--requests must be between 1 and {max_requests} for {mode}")


# --------------------------------------------------------------------------- requests


def request_body(mode: str, index: int, tool: str | None, arguments: dict[str, Any]) -> bytes:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": index + 1}
    if mode == "ping":
        message["method"] = "ping"
    elif mode == "tools-list":
        message["method"] = "tools/list"
    else:
        message["method"] = "tools/call"
        message["params"] = {"name": tool, "arguments": arguments}
    return json.dumps(message, separators=(",", ":")).encode()


def padded_ping(size: int) -> bytes:
    """A valid JSON-RPC ping padded with JSON whitespace to exactly ``size`` bytes."""
    base = b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
    if size < len(base):
        raise ProbeError(f"body size {size} is smaller than a ping ({len(base)} bytes)")
    return base + b" " * (size - len(base))


def headers_for(target: Target, body: bytes) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {target.token}",
        "Content-Length": str(len(body)),
        "User-Agent": "wled-mcp-hw-http-probe/1",
    }
    if target.host_header is not None:
        # http.client skips its own Host header when one is supplied.
        headers["Host"] = target.host_header
    return headers


def _decode_message(content_type: str, payload: bytes) -> Any:
    text = payload.decode("utf-8", errors="replace")
    if content_type.startswith("text/event-stream"):
        data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = data[-1] if data else ""
    return json.loads(text)


def classify(status: int, message: Any) -> str:
    if status != 200:
        return f"http_{status}"
    if not isinstance(message, dict):
        return "invalid_response"
    if "error" in message:
        return "jsonrpc_error"
    result = message.get("result")
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        if result.get("isError") is True or (
            isinstance(structured, dict) and structured.get("ok") is False
        ):
            return "tool_error"
    return "ok"


def send(target: Target, index: int, body: bytes, keep_result: bool) -> Sample:
    connection_class = (
        http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
    )
    sample = Sample(index=index, request_bytes=len(body), t_send=time.time())
    started = time.perf_counter()
    connection = connection_class(target.host, target.port, timeout=target.timeout)
    try:
        connection.request("POST", target.path, body=body, headers=headers_for(target, body))
        response = connection.getresponse()
        payload = response.read()
        sample.status = response.status
        content_type = response.getheader("content-type", "") or ""
    except TimeoutError:
        sample.outcome = "timeout"
        sample.detail = f"no response within {target.timeout} s"
        return sample
    except (OSError, http.client.HTTPException) as exc:
        sample.outcome = "connection_error"
        sample.detail = type(exc).__name__
        return sample
    finally:
        connection.close()
    sample.t_response = time.time()
    sample.latency_ms = (time.perf_counter() - started) * 1000
    try:
        message = _decode_message(content_type, payload) if payload else None
    except json.JSONDecodeError:
        message = None
    sample.outcome = classify(sample.status, message)
    if sample.outcome == "jsonrpc_error" and isinstance(message, dict):
        error = message.get("error")
        sample.detail = str(error.get("message")) if isinstance(error, dict) else None
    if keep_result and isinstance(message, dict):
        sample.result = message.get("result", message.get("error"))
    return sample


# ---------------------------------------------------------------------------- summary


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile: the smallest value with at least p % of values at or below."""
    if not values:
        return None
    if not 0 <= p <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def latency_summary(values: Sequence[float]) -> dict[str, float | int | None]:
    summary: dict[str, float | int | None] = {"count": len(values)}
    summary["min"] = round(min(values), 3) if values else None
    for p in PERCENTILES:
        value = percentile(values, p)
        summary[f"p{p}"] = round(value, 3) if value is not None else None
    summary["max"] = round(max(values), 3) if values else None
    summary["mean"] = round(sum(values) / len(values), 3) if values else None
    return summary


def summarize(samples: list[Sample], wall_seconds: float) -> dict[str, Any]:
    latencies = [s.latency_ms for s in samples if s.latency_ms is not None]
    statuses = Counter(
        str(s.status) if s.status is not None else s.outcome for s in sorted(samples, key=_idx)
    )
    errors = [
        {"index": s.index, "outcome": s.outcome, "status": s.status, "detail": s.detail}
        for s in sorted(samples, key=_idx)
        if s.outcome != "ok"
    ]
    return {
        "completed": len(samples),
        "wall_seconds": round(wall_seconds, 3),
        "throughput_rps": round(len(samples) / wall_seconds, 3) if wall_seconds > 0 else None,
        "status_counts": dict(sorted(statuses.items())),
        "outcome_counts": dict(sorted(Counter(s.outcome for s in samples).items())),
        "latency_ms": latency_summary(latencies),
        "largest_request_bytes": max((s.request_bytes for s in samples), default=0),
        "errors": errors[:MAX_REPORTED_ERRORS],
        "errors_truncated": len(errors) > MAX_REPORTED_ERRORS,
    }


def _idx(sample: Sample) -> int:
    return sample.index


def sample_record(sample: Sample) -> dict[str, Any]:
    return {
        "index": sample.index,
        "t_send": round(sample.t_send, 6),
        "t_response": round(sample.t_response, 6) if sample.t_response is not None else None,
        "latency_ms": round(sample.latency_ms, 3) if sample.latency_ms is not None else None,
        "status": sample.status,
        "outcome": sample.outcome,
    }


# ------------------------------------------------------------------------------- modes


def run_burst(
    target: Target,
    mode: str,
    concurrency: int,
    requests: int,
    tool: str | None,
    arguments: dict[str, Any],
    *,
    include_samples: bool,
    include_results: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(send, target, i, request_body(mode, i, tool, arguments), include_results)
            for i in range(requests)
        ]
        samples = [future.result() for future in futures]
    report = summarize(samples, time.perf_counter() - started)
    if include_samples:
        report["samples"] = [sample_record(s) for s in samples]
    if include_results:
        report["results"] = [s.result for s in samples]
    return report


def run_body_bound(target: Target, limit: int) -> dict[str, Any]:
    probes = []
    for label, size, expectation in (
        ("under", limit - 1, "200_ok"),
        ("over", limit + 1, "413"),
    ):
        sample = send(target, 0, padded_ping(size), False)
        # Below the bound only a successful ping proves acceptance; a 400/401/500 would
        # hide a bound that rejects too early behind an unrelated failure.
        met = (
            sample.status == 413
            if expectation == "413"
            else (sample.status == 200 and sample.outcome == "ok")
        )
        probes.append(
            {
                "label": label,
                "bytes": size,
                "expectation": expectation,
                "status": sample.status,
                "outcome": sample.outcome,
                "detail": sample.detail,
                "latency_ms": round(sample.latency_ms, 3)
                if sample.latency_ms is not None
                else None,
                "met": met,
            }
        )
    return {
        "limit_bytes": limit,
        "probes": probes,
        "met": all(probe["met"] for probe in probes),
        "largest_request_bytes": limit + 1,
    }


# -------------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Opt-in read-only probe for a wled-mcp Streamable HTTP endpoint."
    )
    parser.add_argument("--url", required=True, help="Endpoint URL, e.g. http://host:8000/mcp")
    parser.add_argument("--host-header", help="Host header to send instead of the URL host")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--token-file", help="Path of a file holding the bearer credential")
    source.add_argument("--token-env", help="Name of an environment variable with the credential")
    source.add_argument("--token-stdin", action="store_true", help="Read the credential from stdin")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (s)")
    parser.add_argument(
        "--output",
        help="Write the JSON report here instead of stdout (mode 0600 on POSIX; on Windows "
        "the file inherits its directory's access control and is not protected by the script)",
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    for name in ("ping", "tools-list", "call"):
        mode = modes.add_parser(name)
        mode.add_argument("--concurrency", type=int, default=1)
        mode.add_argument("--requests", type=int, default=1)
        mode.add_argument(
            "--include-samples", action="store_true", help="Per-request send/response times"
        )
        if name == "call":
            mode.add_argument("--tool", required=True, help="One of the read-only tools")
            mode.add_argument("--arguments", default="{}", help="Tool arguments as JSON object")
            mode.add_argument(
                "--include-results", action="store_true", help="Include each JSON-RPC result"
            )
    bound = modes.add_parser("body-bound")
    bound.add_argument("--limit", type=int, default=DEFAULT_BODY_LIMIT)
    return parser


def redact(text: str, token: str) -> str:
    return text.replace(token, REDACTED) if token else text


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdin: IO[str] | None = None,
    stdout: IO[str] | None = None,
    stderr: IO[str] | None = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    token = ""
    try:
        tool: str | None = None
        arguments: dict[str, Any] = {}
        if args.mode == "call":
            # Refuse before reading the credential or opening any connection.
            arguments = check_tool(args.tool, args.arguments)
            tool = args.tool
        if args.mode == "body-bound":
            if args.limit < 64:
                raise ProbeError("--limit is too small for a padded ping")
        else:
            check_load(args.mode, args.concurrency, args.requests)
        token = read_token(args, os.environ if environ is None else environ, stdin or sys.stdin)
        target = parse_target(args.url, args.host_header, token, args.timeout)
    except ProbeError as exc:
        print(f"hw_http_probe: {redact(str(exc), token)}", file=err)
        return USAGE_ERROR
    report: dict[str, Any] = {
        "probe": "wled-mcp hw_http_probe",
        "format": 1,
        "mode": args.mode,
        "url": target.describe(),
        "host_header": target.host_header,
        "timeout_seconds": target.timeout,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if args.mode == "body-bound":
        report["body_bound"] = run_body_bound(target, args.limit)
    else:
        report.update(
            {
                "tool": tool,
                "arguments": arguments if tool is not None else None,
                "concurrency": args.concurrency,
                "requests": args.requests,
            }
        )
        report.update(
            run_burst(
                target,
                args.mode,
                args.concurrency,
                args.requests,
                tool,
                arguments,
                include_samples=args.include_samples,
                include_results=getattr(args, "include_results", False),
            )
        )
    text = redact(json.dumps(report, indent=2, ensure_ascii=False, default=str), token)
    if args.output:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"hw_http_probe: report written to {args.output}", file=err)
    else:
        print(text, file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
