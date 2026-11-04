"""Validate repository agent definitions without launching models or network calls."""

from pathlib import Path
import re
import sys
import tomllib


def check(root: Path) -> list[str]:
    errors: list[str] = []
    expected = {
        "wled_coordinator", "wled_requirements", "wled_implementer", "wled_reviewer"
    }
    found: set[str] = set()
    agent_dir = root / ".codex" / "agents"
    for path in sorted(agent_dir.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if set(data) != {"name", "description", "developer_instructions"}:
            errors.append(f"{path.name}: use only the three supported identity/instruction fields")
        for key in ("name", "description", "developer_instructions"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                errors.append(f"{path.name}: missing nonempty {key}")
        name = data.get("name")
        if isinstance(name, str):
            if name in found:
                errors.append(f"{path.name}: duplicate role {name}")
            found.add(name)
            if path.stem != name:
                errors.append(f"{path.name}: filename must match role name")
        instructions = data.get("developer_instructions")
        for token in ("AGENTS.md", "docs/AGENT-WORKFLOW.md"):
            if not isinstance(instructions, str) or token not in instructions:
                errors.append(f"{path.name}: missing workflow reference {token}")
    if found != expected:
        errors.append("agent role set does not match the four documented roles")
    try:
        config = tomllib.loads((root / ".codex/config.toml").read_text(encoding="utf-8"))
        agents = config.get("agents")
        if (
            config != {"agents": {"enabled": True, "max_concurrent_threads_per_session": 3}}
            or not isinstance(agents, dict)
            or type(agents.get("enabled")) is not bool
            or type(agents.get("max_concurrent_threads_per_session")) is not int
        ):
            errors.append("project config must only enable agents and cap child concurrency at three")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"project config: {exc}")
    required = [
        root / "docs/AGENT-WORKFLOW.md",
        root / "docs/agent-workflow/packet.template.md",
        root / "docs/agent-workflow/implementation.template.md",
        root / "docs/agent-workflow/review.template.md",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing {path.relative_to(root)}")
            continue
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).is_file():
                errors.append(f"{path.name}: missing local reference {local}")
    return errors


if __name__ == "__main__":
    failures = check(Path(__file__).resolve().parents[1])
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    if failures:
        raise SystemExit(1)
    print("Agent setup valid: four roles, inherited session settings, workflow references present.")
    print("Static validation only; no model, network, product or hardware run performed.")
