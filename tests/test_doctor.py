"""Read-only ``wled-mcp doctor`` (issue #16: S16-T04, -T05, -T08).

Devices are a mock transport that fails any non-GET request; the endpoint checks use the
loopback in-process service of ``tests/http_support.py`` or mock transports. Nothing
contacts a LAN device.
"""

import ast
import json
import os
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest

from tests.http_support import TOKEN, WRONG_TOKEN, running_service
from tests.state_catalog_support import Router, make_info, make_state
from wled_mcp import cli, doctor, setup
from wled_mcp.compat import UNRECOGNIZED_WARNING, UNSUPPORTED_WARNING

ROOT = Path(__file__).resolve().parents[1]
SECRET = "synthetic-secret-marker"
DESK, SHELF = "desk.invalid", "shelf.invalid"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("WLED_MCP_"):
            monkeypatch.delenv(name)


def write_config(directory: Path, *hosts: str, extra: str = "") -> Path:
    blocks = (
        "".join(
            f'[[devices]]\nid = "dev{index}"\nname = "Example {index}"\nbase_url = "http://{host}"\n'
            for index, host in enumerate(hosts)
        )
        or "devices = []\n"
    )
    config = directory / "devices.toml"
    config.write_text(f"schema_version = 1\n{extra}{blocks}", encoding="utf-8")
    return config


def layout(tmp_path: Path, *hosts: str) -> tuple[Path, Path]:
    data = tmp_path / "data"
    data.mkdir()
    return write_config(tmp_path, *hosts), data


def tree(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))


def diagnose(
    config: Path | str | None,
    data: Path | str | None,
    router: Router | None = None,
    *,
    environ: dict[str, str] | None = None,
    endpoint_transport: httpx.AsyncBaseTransport | None = None,
    **options: Any,
) -> doctor.Report:
    async def go() -> doctor.Report:
        return await doctor.diagnose(
            doctor.DoctorOptions(
                config=None if config is None else str(config),
                data_dir=None if data is None else str(data),
                **options,
            ),
            environ or {},
            device_transport=router.transport() if router is not None else None,
            endpoint_transport=endpoint_transport,
            system="Linux",
            python=(3, 13, 1),
        )

    return anyio.run(go)


def codes(report: doctor.Report, category: str | None = None) -> list[str]:
    return [c.code for c in report.checks if category is None or c.category == category]


def find(report: doctor.Report, code: str) -> doctor.Check:
    return next(c for c in report.checks if c.code == code)


# ------------------------------------------------------------------ S16-T04 categories


def test_healthy_inventory_reads_only_with_get_and_changes_nothing(tmp_path):
    config, data = layout(tmp_path, DESK, SHELF)
    router = Router()
    router.device(DESK)
    router.device(SHELF)
    before = tree(tmp_path)
    report = diagnose(config, data, router)
    assert report.exit_code == 0
    assert [c.category for c in report.checks] == sorted(
        (c.category for c in report.checks), key=doctor.CATEGORIES.index
    )
    assert (
        codes(report, "device")
        == [
            "DEVICE_REACHABLE",
            "FIRMWARE_SUPPORTED",
            "CAPABILITIES_KNOWN",
        ]
        * 2
    )
    # Router asserts GET on every request; only the state read's two endpoints are used.
    assert set(router.calls) == {
        (h, p) for h in (DESK, SHELF) for p in ("/json/state", "/json/info")
    }
    assert tree(tmp_path) == before
    assert find(report, "FIRMWARE_SUPPORTED").facts["tier"] == "tested"


@pytest.mark.parametrize(
    ("config_arg", "code"),
    [
        (None, "CONFIG_PATH_MISSING"),
        ("relative.toml", "CONFIG_PATH_NOT_ABSOLUTE"),
        ("absent", "CONFIG_NOT_FOUND"),
        ("directory", "CONFIG_UNREADABLE"),
    ],
)
def test_configuration_path_problems(tmp_path, config_arg, code):
    _, data = layout(tmp_path)
    if config_arg in ("absent", "directory"):
        config_arg = str(tmp_path / ("absent.toml" if config_arg == "absent" else "data"))
    report = diagnose(config_arg, data)
    assert report.exit_code == 1
    assert codes(report, "configuration") == [code]
    assert codes(report, "device") == ["DEVICES_SKIPPED"]
    assert find(report, code).action


def test_invalid_inventory_entry_is_positional_and_value_free(tmp_path):
    config, data = layout(tmp_path)
    config.write_text(
        "schema_version = 1\n"
        '[[devices]]\nid = "ok"\nname = "Example"\nbase_url = "http://a.invalid"\n'
        f'[[devices]]\nid = "bad"\nname = "Example"\nbase_url = "http://u:{SECRET}@b.invalid"\n',
        encoding="utf-8",
    )
    report = diagnose(config, data)
    check = find(report, "CONFIG_INVALID")
    assert check.status == "failed" and "devices[1].base_url: invalid" in check.message
    assert SECRET not in doctor.render_text(report)


def test_data_directory_missing(tmp_path):
    config, _ = layout(tmp_path)
    for data, code in [
        (None, "DATA_DIR_MISSING"),
        ("data-rel", "DATA_DIR_NOT_ABSOLUTE"),
        (tmp_path / "absent", "DATA_DIR_NOT_FOUND"),
    ]:
        report = diagnose(config, data, offline=True)
        assert codes(report, "storage") == [code] and report.exit_code == 1


def test_backups_not_writable_is_advisory_and_creates_nothing(tmp_path, monkeypatch):
    config, data = layout(tmp_path)
    monkeypatch.setattr(setup.os, "access", lambda *args: False)
    report = diagnose(config, data, offline=True)
    assert find(report, "BACKUPS_NOT_WRITABLE").status == "failed"
    assert report.exit_code == 1
    assert list(data.iterdir()) == []


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (httpx.ConnectError("synthetic"), "DEVICE_UNREACHABLE"),
        (httpx.ReadTimeout("synthetic"), "DEVICE_TIMEOUT"),
        (httpx.Response(200, text="<html>not json</html>"), "DEVICE_INVALID_RESPONSE"),
        ({"no": "version"}, "DEVICE_INVALID_RESPONSE"),
    ],
    ids=["unreachable", "timeout", "not-json", "no-version"],
)
def test_device_failures_are_classified(tmp_path, failure, code):
    config, data = layout(tmp_path, DESK, SHELF)
    router = Router()
    router.device(DESK)
    router.device(SHELF, info=failure)
    if not isinstance(failure, dict):
        router.set(SHELF, "/json/state", failure)
    report = diagnose(config, data, router)
    assert report.exit_code == 1
    shelf = [c for c in report.checks if c.device_index == 1]
    assert [(c.status, c.code) for c in shelf] == [("failed", code)]
    assert [c.code for c in report.checks if c.device_index == 0][0] == "DEVICE_REACHABLE"


@pytest.mark.parametrize(
    ("version", "code", "warning"),
    [
        ("0.15.1", "FIRMWARE_UNSUPPORTED", UNSUPPORTED_WARNING),
        ("16.0.0-b1", "FIRMWARE_UNSUPPORTED", UNSUPPORTED_WARNING),
        ("custom-build", "FIRMWARE_UNRECOGNIZED", UNRECOGNIZED_WARNING),
    ],
)
def test_firmware_outside_support_is_a_warning_not_a_failure(tmp_path, version, code, warning):
    config, data = layout(tmp_path, DESK)
    router = Router()
    router.device(DESK, info=make_info(ver=version))
    report = diagnose(config, data, router)
    check = find(report, code)
    assert check.status == "warning" and check.message == warning
    assert report.exit_code == 0


def test_unknown_capabilities_are_a_warning(tmp_path):
    config, data = layout(tmp_path, DESK)
    router = Router()
    router.device(DESK, info=make_info(leds={"count": 90}))
    report = diagnose(config, data, router)
    check = find(report, "CAPABILITIES_UNKNOWN")
    assert check.status == "warning" and report.exit_code == 0
    assert "max_segments" in check.facts["unknown_capabilities"]


def test_empty_inventory_and_offline_mode(tmp_path):
    config, data = layout(tmp_path)
    assert codes(diagnose(config, data), "device") == ["DEVICES_NONE"]
    config = write_config(tmp_path, DESK)
    report = diagnose(config, data, offline=True)
    assert codes(report, "device") == ["DEVICES_OFFLINE"] and report.exit_code == 0


def test_runtime_tiers_follow_dec_020(tmp_path):
    async def run_on(system: str, python: tuple[int, ...]) -> list[str]:
        report = await doctor.diagnose(
            doctor.DoctorOptions(None, None), {}, system=system, python=python
        )
        return codes(report, "runtime")

    assert "PLATFORM_EXPERIMENTAL" in anyio.run(run_on, "Windows", (3, 13, 0))
    assert "PLATFORM_UNTESTED" in anyio.run(run_on, "Plan9", (3, 13, 0))
    assert "PYTHON_UNTESTED" in anyio.run(run_on, "Linux", (3, 14, 0))
    assert doctor.build_kind("9.8.7") == "release"
    assert doctor.build_kind("9.8.7+g0123456789ab.dirty") == "non-release"
    assert doctor.build_kind("0+unknown") == "unknown"


def test_doctor_depends_only_on_the_envelope_not_on_read_models():
    tree_ = ast.parse((ROOT / "src" / "wled_mcp" / "doctor.py").read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree_)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not {"wled_mcp.readmodels", "wled_mcp.capabilities"} & imported


# ------------------------------------------------------------------ endpoint checks


@pytest.mark.anyio
async def test_endpoint_ok_against_the_loopback_service(tmp_path):
    async with running_service(tmp_path) as running:
        checks = await doctor.endpoint_checks(running.url, None, {"WLED_MCP_HTTP_TOKEN": TOKEN})
        assert [(c.status, c.code) for c in checks] == [("ok", "ENDPOINT_OK")]
        # Without a path the default /mcp is used.
        base = running.url.removesuffix("/mcp")
        checks = await doctor.endpoint_checks(base, None, {"WLED_MCP_HTTP_TOKEN": TOKEN})
        assert checks[0].code == "ENDPOINT_OK"
        assert running.executions == []  # no tool ran


@pytest.mark.anyio
async def test_endpoint_rejections_are_classified(tmp_path):
    async with running_service(tmp_path) as running:
        wrong = await doctor.endpoint_checks(
            running.url, None, {"WLED_MCP_HTTP_TOKEN": WRONG_TOKEN}
        )
        assert wrong[0].code == "ENDPOINT_CREDENTIAL_REJECTED"
        other_host = running.url.replace("127.0.0.1", "localhost")
        host = await doctor.endpoint_checks(other_host, None, {"WLED_MCP_HTTP_TOKEN": TOKEN})
        assert host[0].code == "ENDPOINT_HOST_ORIGIN_REJECTED"


@pytest.mark.anyio
async def test_endpoint_connect_failure(tmp_path):
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    checks = await doctor.endpoint_checks(
        f"http://127.0.0.1:{port}/mcp", None, {"WLED_MCP_HTTP_TOKEN": TOKEN}
    )
    assert checks[0].code == "ENDPOINT_UNREACHABLE"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(200, text="<html>router login</html>"), "ENDPOINT_PROTOCOL_ERROR"),
        (httpx.Response(404, json={"detail": "Not Found"}), "ENDPOINT_PROTOCOL_ERROR"),
        (httpx.Response(421), "ENDPOINT_HOST_ORIGIN_REJECTED"),
        (httpx.ReadTimeout("synthetic"), "ENDPOINT_TIMEOUT"),
    ],
)
async def test_non_mcp_endpoint_answers(response, code):
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    checks = await doctor.endpoint_checks(
        "http://127.0.0.1:9/mcp",
        None,
        {"WLED_MCP_HTTP_TOKEN": TOKEN},
        httpx.MockTransport(handler),
    )
    assert [(c.status, c.code) for c in checks] == [("failed", code)]


@pytest.mark.anyio
async def test_endpoint_credential_and_url_problems_send_nothing(tmp_path):
    sent: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(500))
    cases = [
        ("http://127.0.0.1:9/mcp", None, {}, "ENDPOINT_CREDENTIAL_MISSING"),
        (
            "http://127.0.0.1:9/mcp",
            None,
            {"WLED_MCP_HTTP_TOKEN": "short"},
            "ENDPOINT_CREDENTIAL_INVALID",
        ),
        ("http://127.0.0.1:9/mcp", "relative", {}, "ENDPOINT_CREDENTIAL_INVALID"),
        (
            f"http://u:{SECRET}@127.0.0.1:9/mcp",
            None,
            {"WLED_MCP_HTTP_TOKEN": TOKEN},
            "ENDPOINT_URL_INVALID",
        ),
        ("ftp://127.0.0.1/mcp", None, {"WLED_MCP_HTTP_TOKEN": TOKEN}, "ENDPOINT_URL_INVALID"),
    ]
    for url, token_file, environ, code in cases:
        checks = await doctor.endpoint_checks(url, token_file, environ, transport)
        assert checks[0].code == code and SECRET not in checks[0].message
    assert sent == []


# ------------------------------------------------------------------ S16-T05 sanitized export


def test_export_contains_only_allowlisted_facts(tmp_path):
    marker_dir = tmp_path / f"path-{SECRET}"
    marker_dir.mkdir()
    data = marker_dir / "data"
    data.mkdir()
    host = "synthetic-host-marker.invalid"
    config = marker_dir / "devices.toml"
    config.write_text(
        "schema_version = 1\n"
        f'[[devices]]\nid = "secretid"\nname = "Name {SECRET}"\nbase_url = "http://{host}:8080"\n',
        encoding="utf-8",
    )
    router = Router()
    planted = make_info(
        name=f"Info {SECRET}",
        mac="00005e0053ff",
        ip="192.0.2.77",
        wifi={"bssid": "00:00:5E:00:53:FF", "ssid": f"ssid-{SECRET}", "rssi": -40},
        leds={"count": 90},
    )
    router.device(host, info=planted, state=make_state())
    token_path = marker_dir / "token"
    token_path.write_text(TOKEN, encoding="utf-8")
    report = diagnose(
        config,
        data,
        router,
        environ={},
        endpoint=f"http://endpoint-{SECRET}.invalid/mcp",
        http_token_file=str(token_path),
        endpoint_transport=httpx.MockTransport(lambda request: httpx.Response(401)),
    )
    exported = doctor.export(report)
    text = json.dumps(exported)
    for forbidden in (
        SECRET,
        "secretid",
        host,
        "8080",
        "192.0.2.77",
        "00005e0053ff",
        "00:00:5E:00:53:FF",
        "bssid",
        "ssid",
        TOKEN,
        str(tmp_path),
        "token",
        "http",
        "message",
    ):
        assert forbidden not in text, forbidden
    assert exported["devices"] == [
        {
            "device": "devices[0]",
            "firmware": {
                "ver": "16.0.1",
                "vid": 2510010,
                "arch": "esp32",
                "tier": "tested",
                "minimum_supported": "16.0.0",
            },
            "unknown_capabilities": sorted(
                ["max_segments", "device_wide_color", "segment_color_capability"]
            ),
        }
    ]
    assert exported["schema_version"] == 1 and exported["command"] == "doctor"
    assert set(exported["runtime"]) == {
        "package_version",
        "build_kind",
        "python_version",
        "python_tier",
        "platform_tier",
    }
    for check in exported["checks"]:
        assert set(check) <= {"category", "status", "code", "device", "protocol_version"}
    assert {"category": "endpoint", "status": "failed", "code": "ENDPOINT_CREDENTIAL_REJECTED"} in (
        exported["checks"]
    )


def test_console_export_and_exit_codes(tmp_path, capsys):
    config, data = layout(tmp_path)
    argv = ["doctor", "--config", str(config), "--data-dir", str(data)]
    assert cli.main([*argv, "--export"]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["export"] is True and exported["ok"] is True
    assert cli.main([*argv, "--format", "json"]) == 0
    full = json.loads(capsys.readouterr().out)
    assert {c["code"] for c in full["checks"]} >= {"CONFIG_VALID", "DEVICES_NONE"}
    assert cli.main(["doctor", "--config", str(tmp_path / "absent.toml")]) == 1
    text = capsys.readouterr().out
    assert "CONFIG_NOT_FOUND" in text and "action:" in text and str(tmp_path) not in text


# ------------------------------------------------------------------ S16-T08 OPS-04


def test_every_ops04_condition_maps_to_a_doctor_result_with_an_action(tmp_path, monkeypatch):
    observed: dict[str, set[str]] = {}

    def scenario(name: str, report: doctor.Report) -> None:
        observed[name] = {c.code for c in report.checks if c.status in ("failed", "warning")}

    base = tmp_path / "bad"
    base.mkdir()
    bad = write_config(base, extra="unknown = 1\n")
    scenario("bad configuration", diagnose(bad, base, offline=True))

    for name, info, state in [
        ("unsupported firmware", make_info(ver="0.15.1"), make_state()),
        ("offline device", httpx.ConnectError("synthetic"), httpx.ConnectError("synthetic")),
        ("invalid response", {"no": "version"}, make_state()),
    ]:
        directory = tmp_path / name.replace(" ", "-")
        directory.mkdir()
        config, data = layout(directory, DESK)
        router = Router()
        router.device(DESK, info=info, state=state)
        scenario(name, diagnose(config, data, router))

    directory = tmp_path / "storage"
    directory.mkdir()
    config, data = layout(directory)
    with monkeypatch.context() as patched:
        patched.setattr(setup.os, "access", lambda *args: False)
        scenario("unavailable backup storage", diagnose(config, data, offline=True))

    assert set(observed) == set(doctor.OPS04_CONDITIONS)
    for condition, expected in doctor.OPS04_CONDITIONS.items():
        found = observed[condition] & set(expected)
        assert found, condition
        assert all(doctor.ACTIONS[code] for code in found)


def test_serve_prints_one_backups_advisory_and_still_starts(tmp_path, monkeypatch, capsys):
    config, data = layout(tmp_path)
    served: list[str] = []
    monkeypatch.setattr(setup.os, "access", lambda *args: False)
    monkeypatch.setattr(cli.anyio, "run", lambda function, *args: served.append(function.__name__))
    assert cli.main(["--config", str(config), "--data-dir", str(data)]) == 0
    out, err = capsys.readouterr()
    assert served == ["serve"] and out == ""
    assert err.count("\n") == 1 and err.strip() == cli.BACKUPS_ADVISORY
    assert str(tmp_path) not in err and list(data.iterdir()) == []


def test_serve_is_silent_when_backups_are_writable(tmp_path, monkeypatch, capsys):
    config, data = layout(tmp_path)
    monkeypatch.setattr(cli.anyio, "run", lambda *args: None)
    assert cli.main(["--config", str(config), "--data-dir", str(data)]) == 0
    assert capsys.readouterr() == ("", "")


# ------------------------------------------------------------------ review round 1 (M1, N2, N3)


@pytest.fixture
def backups_eacces(monkeypatch):
    """Model POSIX EACCES on ``<data-dir>/backups``: a data directory that cannot be searched."""
    import errno
    import pathlib

    original = pathlib.Path.stat

    def stat(self, *args, **kwargs):
        if self.name == "backups":
            raise PermissionError(errno.EACCES, "Permission denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "stat", stat)


def test_unsearchable_data_dir_still_serves_with_the_advisory(
    tmp_path, monkeypatch, capsys, backups_eacces
):
    config, data = layout(tmp_path)
    served: list[str] = []
    monkeypatch.setattr(cli.anyio, "run", lambda function, *args: served.append(function.__name__))
    assert cli.main(["--config", str(config), "--data-dir", str(data)]) == 0
    out, err = capsys.readouterr()
    assert served == ["serve"] and out == "" and err.strip() == cli.BACKUPS_ADVISORY


def test_unsearchable_data_dir_is_reported_not_crashed(tmp_path, capsys, backups_eacces):
    config, data = layout(tmp_path)
    argv = ["--config", str(config), "--data-dir", str(data), "--format", "json"]
    assert cli.main(["doctor", *argv]) == 1
    report = json.loads(capsys.readouterr().out)
    assert {"category": "storage", "code": "BACKUPS_NOT_WRITABLE"} in [
        {"category": c["category"], "code": c["code"]} for c in report["checks"]
    ]
    assert cli.main(["config", "validate", *argv, "--check-backups"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert [p["code"] for p in result["problems"]] == ["BACKUPS_NOT_WRITABLE"]


def test_inaccessible_data_dir_maps_to_the_documented_code(tmp_path, monkeypatch, capsys):
    import errno
    import pathlib

    config, data = layout(tmp_path)
    original = pathlib.Path.stat

    def stat(self, *args, **kwargs):
        if self.name == "data":
            raise PermissionError(errno.EACCES, "Permission denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "stat", stat)
    report = diagnose(config, data, offline=True)
    assert codes(report, "storage") == ["DATA_DIR_NOT_FOUND"]
    argv = ["config", "validate", "--config", str(config), "--data-dir", str(data)]
    assert cli.main([*argv, "--format", "json"]) == 1
    assert [p["code"] for p in json.loads(capsys.readouterr().out)["problems"]] == [
        "DATA_DIR_NOT_FOUND"
    ]


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="real POSIX permission bits; root bypasses them",
)
def test_real_unsearchable_data_dir(tmp_path, monkeypatch, capsys):
    config, data = layout(tmp_path)
    data.chmod(0o600)
    try:
        monkeypatch.setattr(cli.anyio, "run", lambda *args: None)
        assert cli.main(["--config", str(config), "--data-dir", str(data)]) == 0
        assert capsys.readouterr().err.strip() == cli.BACKUPS_ADVISORY
        report = diagnose(config, data, offline=True)
        assert "BACKUPS_NOT_WRITABLE" in codes(report, "storage") and report.exit_code == 1
        argv = ["config", "validate", "--config", str(config), "--data-dir", str(data)]
        assert cli.main([*argv, "--check-backups"]) == 1
        assert "not writable" in capsys.readouterr().out
    finally:
        data.chmod(0o700)


@pytest.mark.anyio
@pytest.mark.parametrize("version", ["2025-11-25\x1b[31m", "x" * 40, "../../etc"])
async def test_endpoint_protocol_version_must_be_a_date(version):
    body = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": version}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    checks = await doctor.endpoint_checks(
        "http://127.0.0.1:9/mcp", None, {"WLED_MCP_HTTP_TOKEN": TOKEN}, httpx.MockTransport(handler)
    )
    assert [(c.code, c.facts) for c in checks] == [("ENDPOINT_PROTOCOL_ERROR", {})]
    assert version not in checks[0].message


def test_export_and_format_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["doctor", "--export", "--format", "json"])
    assert caught.value.code == 2 and capsys.readouterr().out == ""
