"""``wled-mcp config init|add-device|validate`` (issue #16: S16-T02, -T03, -T07, -T09).

Everything runs in ``tmp_path`` with synthetic values; no command contacts a device or
the network (a socket guard enforces it for validate).
"""

import json
import os
import shutil
import socket
import stat
import tomllib
from pathlib import Path

import pytest

from scripts import check_coverage
from wled_mcp import cli, setup
from wled_mcp.config import ConfigurationError, load_config

ROOT = Path(__file__).resolve().parents[1]
SECRET = "synthetic-secret-marker"
# The oldest retained release configuration (tests/test_upgrade_compat.py layout).
RETAINED = min((ROOT / "tests" / "fixtures" / "compat").glob("*/config.toml"))
EXAMPLES = [
    ROOT / "examples" / "bootstrap.toml",
    ROOT / "examples" / "devices.example.toml",
    ROOT / "examples" / "h01-h02.devices.example.toml",
    RETAINED,
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("WLED_MCP_"):
            monkeypatch.delenv(name)


def run(capsys, *argv: str) -> tuple[int, str, str]:
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:  # argparse usage errors
        code = int(exc.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def snapshot(directory: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(directory)): p.read_bytes() if p.is_file() else b"<dir>"
        for p in sorted(directory.rglob("*"))
    }


def init(capsys, config: Path, *extra: str) -> tuple[int, str, str]:
    return run(capsys, "config", "init", "--config", str(config), *extra)


def add(capsys, config: Path, device_id: str, name: str, url: str, *extra: str):
    return run(
        capsys,
        "config",
        "add-device",
        "--config",
        str(config),
        "--device-id",
        device_id,
        "--device-name",
        name,
        "--base-url",
        url,
        *extra,
    )


# ------------------------------------------------------------------ S16-T02 config writes


def test_init_writes_only_the_selected_file_and_validates(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    code, out, err = init(
        capsys,
        config,
        "--device-id",
        "desk",
        "--device-name",
        "Desk",
        "--base-url",
        "http://192.0.2.10",
    )
    assert code == 0 and err == ""
    assert sorted(p.name for p in tmp_path.iterdir()) == ["devices.toml"]  # no data/backups dir
    assert "192.0.2.10" not in out
    loaded = load_config(str(config), str(tmp_path), {})
    assert [(d.id, d.name, d.base_url) for d in loaded.devices] == [
        ("desk", "Desk", "http://192.0.2.10")
    ]
    if os.name != "nt":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600


def test_init_without_device_writes_an_empty_inventory(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    code, out, _ = init(capsys, config, "--format", "json")
    assert code == 0
    result = json.loads(out)
    assert result == {
        "schema_version": 1,
        "command": "config init",
        "ok": True,
        "written": True,
        "replaced": False,
        "device_count": 0,
    }
    assert load_config(str(config), str(tmp_path), {}).devices == ()


def test_init_refuses_existing_target_without_force(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    config.write_bytes(b"# keep me\nschema_version = 1\ndevices = []\n")
    before = snapshot(tmp_path)
    code, out, _ = init(capsys, config)
    assert code == 1 and "--force" in out
    assert snapshot(tmp_path) == before
    code, _, _ = init(capsys, config, "--force")
    assert code == 0
    assert b"keep me" not in config.read_bytes()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["devices.toml"]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--device-id", "desk"], 2),  # device options only together
        (["--device-id", "desk", "--device-name", "D", "--base-url", "ftp://x"], 1),
        (["--device-id", "Desk!", "--device-name", "D", "--base-url", "http://x.invalid"], 1),
    ],
)
def test_init_refuses_incomplete_or_invalid_device_values(tmp_path, capsys, argv, expected):
    code, _, _ = init(capsys, tmp_path / "devices.toml", *argv)
    assert code == expected
    assert list(tmp_path.iterdir()) == []


def test_init_refuses_missing_parent_relative_path_and_missing_option(tmp_path, capsys):
    assert init(capsys, tmp_path / "absent" / "devices.toml")[0] == 1
    assert init(capsys, Path("relative.toml"))[0] == 1
    code, out, err = run(capsys, "config", "init")
    assert code == 2 and out == "" and "--config" in err
    assert list(tmp_path.iterdir()) == []


def test_environment_path_is_used_like_the_server(tmp_path, capsys, monkeypatch):
    config = tmp_path / "env.toml"
    monkeypatch.setenv("WLED_MCP_CONFIG", str(config))
    assert run(capsys, "config", "init")[0] == 0
    assert run(capsys, "config", "validate")[0] == 0


def symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")


def test_symlink_targets_are_refused(tmp_path, capsys):
    real = tmp_path / "real.toml"
    real.write_bytes(b"schema_version = 1\ndevices = []\n")
    link = tmp_path / "link.toml"
    symlink_or_skip(link, real)
    before = snapshot(tmp_path)
    assert init(capsys, link, "--force")[0] == 1
    assert add(capsys, link, "desk", "Desk", "http://192.0.2.10")[0] == 1
    assert snapshot(tmp_path) == before


def retained_copy(tmp_path: Path) -> Path:
    config = tmp_path / "config.toml"
    shutil.copyfile(RETAINED, config)
    return config


def test_add_device_appends_and_keeps_every_original_byte(tmp_path, capsys):
    config = retained_copy(tmp_path)
    original = config.read_bytes()
    code, out, err = add(capsys, config, "lamp", "Example lamp", "http://192.0.2.20:8080")
    assert code == 0 and err == ""
    assert "devices[2]" in out and "192.0.2.20" not in out
    updated = config.read_bytes()
    assert updated.startswith(original)
    devices = load_config(str(config), str(tmp_path), {}).devices
    assert [d.id for d in devices] == ["desk", "shelf", "lamp"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]  # no temp file left


def test_add_device_after_empty_init_replaces_the_empty_array(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    assert init(capsys, config)[0] == 0
    header = config.read_text(encoding="utf-8").replace("devices = []\n", "")
    assert add(capsys, config, "desk", "Desk", "http://192.0.2.10")[0] == 0
    text = config.read_text(encoding="utf-8")
    assert text.startswith(header)
    assert "devices = []" not in text
    assert [d.id for d in load_config(str(config), str(tmp_path), {}).devices] == ["desk"]


@pytest.mark.parametrize(
    ("device_id", "url", "code"),
    [
        ("desk", "http://192.0.2.99", "DUPLICATE_ID"),
        ("other", "http://WLED-DESK.example.invalid/", "DUPLICATE_URL"),
        ("other", "http://wled-desk.example.invalid:80", "DUPLICATE_URL"),
        ("other", f"http://user:{SECRET}@x.invalid", "CONFIG_INVALID"),
        ("other", f"http://{SECRET}.invalid/path", "CONFIG_INVALID"),
        ("Bad ID", "http://192.0.2.99", "CONFIG_INVALID"),
    ],
)
def test_add_device_refusals_leave_the_file_byte_identical(tmp_path, capsys, device_id, url, code):
    config = retained_copy(tmp_path)
    before = snapshot(tmp_path)
    exit_code, out, err = add(capsys, config, device_id, "Example", url, "--format", "json")
    assert exit_code == 1
    result = json.loads(out)
    assert result["ok"] is False and result["written"] is False
    assert [p["code"] for p in result["problems"]] == [code]
    assert SECRET not in out + err
    assert snapshot(tmp_path) == before
    if code == "CONFIG_INVALID" and "Bad" not in device_id:
        assert "devices[2].base_url: invalid" in result["problems"][0]["message"]


def test_add_device_refuses_result_over_64_kib(tmp_path, capsys):
    config = retained_copy(tmp_path)
    with config.open("ab") as stream:
        stream.write(b"#" + b"x" * (65536 - config.stat().st_size - 40) + b"\n")
    assert config.stat().st_size <= 65536
    before = snapshot(tmp_path)
    code, out, _ = add(capsys, config, "lamp", "Example lamp", "http://192.0.2.20")
    assert code == 1 and "64 KiB" in out
    assert snapshot(tmp_path) == before


def test_add_device_refuses_invalid_existing_configuration(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    config.write_text(f'schema_version = 1\ndevices = []\nx = "{SECRET}"\n', encoding="utf-8")
    before = snapshot(tmp_path)
    code, out, err = add(capsys, config, "desk", "Desk", "http://192.0.2.10")
    assert code == 1 and SECRET not in out + err
    assert snapshot(tmp_path) == before


def test_add_device_aborts_when_the_file_changes_before_replace(tmp_path, capsys, monkeypatch):
    config = retained_copy(tmp_path)
    original_append = setup.append_device

    def racing_append(text: str, block: str) -> str:
        config.write_bytes(config.read_bytes() + b"# edited concurrently\n")
        return original_append(text, block)

    monkeypatch.setattr(setup, "append_device", racing_append)
    code, out, _ = add(capsys, config, "lamp", "Example lamp", "http://192.0.2.20")
    assert code == 1 and "changed" in out
    assert config.read_bytes() == RETAINED.read_bytes() + b"# edited concurrently\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]


def test_failed_replace_leaves_target_and_no_temporary_file(tmp_path, capsys, monkeypatch):
    config = retained_copy(tmp_path)
    before = snapshot(tmp_path)

    def failing_replace(*args: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(setup.os, "replace", failing_replace)
    code, out, err = add(capsys, config, "lamp", "Example lamp", "http://192.0.2.20")
    assert code == 1 and "left unchanged" in out and "synthetic" not in out + err
    assert snapshot(tmp_path) == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_add_device_keeps_the_existing_file_mode(tmp_path, capsys):
    config = retained_copy(tmp_path)
    config.chmod(0o640)
    assert add(capsys, config, "lamp", "Example lamp", "http://192.0.2.20")[0] == 0
    assert stat.S_IMODE(config.stat().st_mode) == 0o640


@pytest.mark.parametrize(
    "name",
    ['Quote " inside', "Back\\slash \\n literal", "Ünïcödé Lampe 💡", '\'single\' and """triple'],
)
def test_names_round_trip_through_toml_escaping(tmp_path, capsys, name):
    config = retained_copy(tmp_path)
    assert add(capsys, config, "lamp", name, "http://192.0.2.20")[0] == 0
    assert load_config(str(config), str(tmp_path), {}).devices[-1].name == name


@pytest.mark.parametrize("value", ["\t\n\r\b\f", "\x00\x1f\x7f", '"\\', "plain"])
def test_toml_string_escapes_control_characters(value):
    assert tomllib.loads(f"v = {setup.toml_string(value)}")["v"] == value


# ------------------------------------------------------------------ S16-T03 compatibility


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_shipped_and_retained_configurations_validate_unchanged(path, capsys):
    before = path.read_bytes()
    code, out, _ = run(capsys, "config", "validate", "--config", str(path), "--format", "json")
    assert code == 0, out
    assert json.loads(out)["problems"] == []
    assert path.read_bytes() == before


def test_newer_schema_version_is_named_and_the_file_untouched(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    config.write_bytes(b"schema_version = 2\ndevices = []\n")
    code, out, _ = run(capsys, "config", "validate", "--config", str(config))
    assert code == 1
    assert "schema_version 2" in out and "reads schema_version 1" in out
    assert config.read_bytes() == b"schema_version = 2\ndevices = []\n"


# ------------------------------------------------------------------ S16-T07 validate


@pytest.fixture
def no_network(monkeypatch):
    class Forbidden(socket.socket):
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("config commands must not open sockets")

    monkeypatch.setattr(socket, "socket", Forbidden)


@pytest.mark.parametrize(
    "content",
    [
        'schema_version = 1\n[[devices]]\nid = "a"\nname = "A"\nbase_url = "http://a.invalid"\n'
        f'[[devices]]\nid = "b"\nname = "B"\nbase_url = "http://u:{SECRET}@b.invalid"\n',
        f'schema_version = 1\ndevices = []\nsecret = "{SECRET}"\n',
        f'schema_version = "{SECRET}',
    ],
)
def test_validate_reports_the_startup_message(tmp_path, capsys, no_network, content):
    config = tmp_path / "devices.toml"
    config.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError) as startup:
        load_config(str(config), str(tmp_path), {})
    code, out, err = run(capsys, "config", "validate", "--config", str(config), "--format", "json")
    assert code == 1 and err == ""
    assert json.loads(out)["problems"] == [
        {"code": "CONFIG_INVALID", "message": str(startup.value)}
    ]
    assert SECRET not in out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["devices.toml"]


def test_validate_checks_data_dir_and_backups_without_creating(
    tmp_path, capsys, no_network, monkeypatch
):
    config = retained_copy(tmp_path)
    data = tmp_path / "data"
    code, out, _ = run(
        capsys, "config", "validate", "--config", str(config), "--data-dir", str(data)
    )
    assert code == 1 and "data directory" in out
    data.mkdir()
    argv = ["config", "validate", "--config", str(config), "--data-dir", str(data)]
    assert run(capsys, *argv, "--check-backups")[0] == 0
    monkeypatch.setattr(setup.os, "access", lambda *args: False)
    code, out, _ = run(capsys, *argv, "--check-backups", "--format", "json")
    assert code == 1
    assert json.loads(out)["backups_writable"] is False
    assert list(data.iterdir()) == []
    assert run(capsys, "config", "validate", "--config", str(config), "--check-backups")[0] == 2


# ------------------------------------------------------------------ S16-T09 console shape


def test_parser_exposes_the_subcommands_to_the_coverage_check():
    commands = check_coverage.cli_commands()
    assert {
        ("config",),
        ("config", "init"),
        ("config", "add-device"),
        ("config", "validate"),
        ("doctor",),
    } <= commands


@pytest.mark.parametrize(
    "argv",
    [
        ["--config", "/x.toml", "doctor"],
        ["--transport", "stdio", "config", "validate"],
        ["config"],
        ["config", "migrate"],
        ["doctor", "--transport", "stdio"],
        ["config", "init", "--token", SECRET],
    ],
)
def test_usage_errors_exit_2_with_the_safe_message(capsys, argv):
    code, out, err = run(capsys, *argv)
    assert code == 2 and out == ""
    assert err == "Invalid command-line arguments. Use --help for supported options.\n"


def test_unexpected_failure_exits_3_without_traceback(tmp_path, capsys, monkeypatch):
    def broken(*args: object) -> None:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(setup, "validate_document", broken)
    code, out, err = run(capsys, "config", "validate", "--config", str(retained_copy(tmp_path)))
    assert code == 3 and out == ""
    assert "internal failure" in err and SECRET not in err and "Traceback" not in err


# ------------------------------------------------------------------ S16-T01 fresh user


def test_fresh_user_setup_validate_serve_both_transports_and_doctor(tmp_path):
    """Installed console only, stdin closed, every path inside ``tmp_path``, no source edit.

    The controller is the synthetic loopback ``FakeWLED``; it records POSTs, and none
    may occur.
    """
    import subprocess

    import anyio
    import httpx2 as httpx
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters
    from mcp.client.streamable_http import streamable_http_client

    from tests.test_http_cli import (
        CONSOLE,
        TOKEN,
        FakeWLED,
        clean_env,
        console,
        free_port,
        wait_ready,
    )

    wled = FakeWLED()
    try:
        config, data = tmp_path / "devices.toml", tmp_path / "data"
        data.mkdir()
        env = clean_env()

        def console_run(*argv: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(CONSOLE), *argv],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=tmp_path,
                env=env,
            )

        created = console_run(
            "config",
            "init",
            "--config",
            str(config),
            "--device-id",
            "desk",
            "--device-name",
            "Desk",
            "--base-url",
            f"http://127.0.0.1:{wled.port}",
        )
        assert created.returncode == 0, created.stderr
        valid = console_run("config", "validate", "--config", str(config), "--data-dir", str(data))
        assert valid.returncode == 0 and "1 device(s)" in valid.stdout
        checked = console_run(
            "doctor", "--config", str(config), "--data-dir", str(data), "--format", "json"
        )
        assert checked.returncode == 0, checked.stdout
        assert "DEVICE_REACHABLE" in checked.stdout

        serve_args = ["--config", str(config), "--data-dir", str(data)]

        async def read_state(client: Client) -> None:
            result = await client.call_tool("wled_get_state", {"device_id": "desk"})
            assert not result.is_error
            assert result.structured_content["data"]["firmware"]["version"] == "16.0.1"

        async def over_stdio() -> None:
            params = StdioServerParameters(
                command=str(CONSOLE), args=serve_args, cwd=tmp_path, env=env
            )
            with anyio.fail_after(30):
                async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
                    await read_state(client)

        anyio.run(over_stdio)

        port = free_port()
        http_args = ["--transport", "streamable-http", "--port", str(port)]
        http_args += ["--allowed-host", f"127.0.0.1:{port}"]
        with console(config, data, *http_args, env=clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)) as (
            process,
            lines,
        ):
            wait_ready(lines, port)

            async def over_http() -> None:
                with anyio.fail_after(30):
                    async with httpx.AsyncClient(
                        headers={"Authorization": f"Bearer {TOKEN}"}
                    ) as http:
                        transport = streamable_http_client(
                            f"http://127.0.0.1:{port}/mcp",
                            http_client=http,
                            terminate_on_close=False,
                        )
                        async with Client(transport, mode="legacy") as client:
                            await read_state(client)

            anyio.run(over_http)
            endpoint = subprocess.run(
                [str(CONSOLE), "doctor", "--offline", "--endpoint", f"http://127.0.0.1:{port}"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=tmp_path,
                env=clean_env(WLED_MCP_HTTP_TOKEN=TOKEN),
            )
            assert "ENDPOINT_OK" in endpoint.stdout
            process.terminate()
        assert wled.posts == []
        assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "devices.toml"]
        assert list(data.iterdir()) == []
    finally:
        wled.close()


# ------------------------------------------------------------------ review round 1 (S1, S2, N1)


def test_directory_fsync_failure_after_replace_reports_written(tmp_path, capsys, monkeypatch):
    config = retained_copy(tmp_path)

    def failing(directory: Path) -> None:
        raise OSError("synthetic directory fsync failure")

    monkeypatch.setattr(setup, "_fsync_directory", failing)
    code, out, err = add(
        capsys, config, "lamp", "Example lamp", "http://192.0.2.20", "--format", "json"
    )
    assert code == 0 and json.loads(out)["written"] is True
    assert [d.id for d in load_config(str(config), str(tmp_path), {}).devices][-1] == "lamp"


def test_validate_io_failure_is_a_check_failure_not_a_write_failure(tmp_path, capsys, monkeypatch):
    config = retained_copy(tmp_path)

    def failing(path: Path) -> tuple[bytes, object]:
        raise OSError("synthetic")

    monkeypatch.setattr(setup, "_read_regular", failing)
    code, out, _ = run(capsys, "config", "validate", "--config", str(config), "--format", "json")
    result = json.loads(out)
    assert code == 1 and "written" not in result
    assert [p["code"] for p in result["problems"]] == ["CHECK_FAILED"]


def test_surrogate_in_device_value_is_an_input_error(tmp_path, capsys):
    config = retained_copy(tmp_path)
    before = snapshot(tmp_path)
    code, out, _ = add(
        capsys, config, "lamp", "Bad \udcff name", "http://192.0.2.20", "--format", "json"
    )
    result = json.loads(out)
    assert code == 1 and result["written"] is False
    assert [p["code"] for p in result["problems"]] == ["INVALID_TEXT"]
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "argv",
    [
        ["config", "validate", "--conf", "/x.toml"],
        ["config", "init", "--conf", "/x.toml"],
        ["config", "add-device", "--device-i", "x"],
        ["doctor", "--off"],
    ],
)
def test_subcommand_options_cannot_be_abbreviated(capsys, argv):
    code, out, err = run(capsys, *argv)
    assert code == 2 and out == ""


# ------------------------------------------------------------------ PR B carried nits


def test_init_names_a_missing_parent(tmp_path, capsys):
    code, out, _ = init(capsys, tmp_path / "absent" / "devices.toml", "--format", "json")
    assert code == 1 and json.loads(out)["problems"][0]["code"] == "PARENT_MISSING"


def test_init_reports_an_unwritable_parent_accurately(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(setup.os, "access", lambda path, mode: False)
    code, out, _ = init(capsys, tmp_path / "devices.toml", "--format", "json")
    (problem,) = json.loads(out)["problems"]
    assert code == 1 and problem["code"] == "PARENT_INACCESSIBLE"
    assert "does not exist" not in problem["message"]
    assert list(tmp_path.iterdir()) == []


def test_init_reports_an_uninspectable_parent_accurately(tmp_path, capsys, monkeypatch):
    real_stat = Path.stat

    def denied(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        if self == tmp_path:
            raise PermissionError(13, "denied")
        return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", denied)
    code, out, _ = init(capsys, tmp_path / "devices.toml", "--format", "json")
    (problem,) = json.loads(out)["problems"]
    assert code == 1 and problem["code"] == "PARENT_INACCESSIBLE"
    assert "does not exist" not in problem["message"]


def test_add_device_hints_at_an_inline_devices_array(tmp_path, capsys):
    config = tmp_path / "devices.toml"
    config.write_bytes(
        b"schema_version = 1\n"
        b'devices = [{ id = "desk", name = "Desk", base_url = "http://192.0.2.10" }]\n'
    )
    before = snapshot(tmp_path)
    code, out, _ = add(capsys, config, "shelf", "Shelf", "http://192.0.2.11", "--format", "json")
    (problem,) = json.loads(out)["problems"]
    assert code == 1 and problem["code"] == "INLINE_DEVICES_ARRAY"
    assert "[[devices]]" in problem["message"]
    assert snapshot(tmp_path) == before
