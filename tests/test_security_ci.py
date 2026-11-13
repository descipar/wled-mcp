"""Security checks stay active and unprivileged when pull-request content is untrusted."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.load((ROOT / ".github" / "workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_ci_and_publish_actions_are_immutable_and_checkout_drops_credentials():
    for name in ("ci.yml", "publish.yml", "codeql.yml"):
        document = workflow(name)
        assert "pull_request_target" not in document["on"]
        for job in document["jobs"].values():
            for step in job["steps"]:
                if "uses" not in step:
                    continue
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"])
                if step["uses"].startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] == "false"


def test_security_scan_is_not_skipped_by_docs_gate_or_granted_write_tokens():
    ci = workflow("ci.yml")
    job = ci["jobs"]["security-lint"]
    assert ci["permissions"] == {"contents": "read"}
    assert "permissions" not in job and "if" not in job
    scan = next(step for step in job["steps"] if "--select S" in step.get("run", ""))
    assert "if" not in scan and "--ignore S101" in scan["run"]
    assert "--no-install-project" in str(job["steps"])
    codeql = workflow("codeql.yml")
    assert {"push", "pull_request", "schedule"} <= set(codeql["on"])
    assert codeql["jobs"]["analyze"]["permissions"] == {
        "contents": "read",
        "security-events": "write",
    }
    assert not any("run" in step for step in codeql["jobs"]["analyze"]["steps"])
    assert codeql["jobs"]["analyze"]["steps"][1]["with"]["build-mode"] == "none"


def test_dependency_updates_cover_lock_and_action_pins_without_auto_merge():
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text())
    assert {update["package-ecosystem"] for update in config["updates"]} == {
        "uv",
        "github-actions",
    }
    assert all(update["schedule"]["interval"] == "weekly" for update in config["updates"])
