"""Exercise shared role synchronization without models, network or LAN devices."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_agents


class SyncAgentsTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / ".agent-runs" / "sync-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "agents").mkdir()
        for stem in sync_agents.SOURCE_STEMS:
            self.write_source(stem, "A synthetic role", f"Read AGENTS.md.\nWork on {stem}.\n")

    def write_source(self, stem, description, body):
        text = (
            "+++\n"
            f"name = {json.dumps('wled_' + stem)}\n"
            f"description = {json.dumps(description, ensure_ascii=False)}\n"
            "+++\n" + body
        )
        (self.root / "agents" / f"{stem}.md").write_bytes(text.encode("utf-8"))

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }

    def test_native_content_roundtrips_with_escaping_and_delimiters(self):
        description = 'Quoted "role" \\ Unicode: ä 🦉\nline\tend\x85\u2028\u2029'
        body = 'First line\n---\n+++\n""" \\ ${synthetic} ä 🦉\n\nLast line\n'
        self.write_source("reviewer", description, body)
        sync_agents.sync(self.root)
        codex = tomllib.loads(
            (self.root / ".codex/agents/wled_reviewer.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(codex, {
            "name": "wled_reviewer", "description": description, "developer_instructions": body
        })
        claude = (self.root / ".claude/agents/wled_reviewer.md").read_bytes().decode("utf-8")
        self.assertTrue(claude.startswith("---\n"))
        header, actual_body = claude[4:].split("\n---\n", 1)
        # Renderer emits a deliberately restricted YAML subset: JSON-quoted
        # scalar values, which can be independently decoded with stdlib JSON.
        metadata = {
            key: json.loads(value.strip())
            for line in header.splitlines() if not line.startswith("#")
            for key, value in [line.split(":", 1)]
        }
        self.assertEqual(metadata, {"name": "wled_reviewer", "description": description})
        self.assertEqual(actual_body, body)
        self.assertIn("DO NOT EDIT", header)

    def test_crlf_source_normalizes_to_lf_without_changing_content(self):
        path = self.root / "agents/reviewer.md"
        original = path.read_bytes()
        path.write_bytes(original.replace(b"\n", b"\r\n"))
        sync_agents.sync(self.root)
        expected_body = "Read AGENTS.md.\nWork on reviewer.\n"
        self.assertEqual(sync_agents.load_roles(self.root)[3].instructions, expected_body)
        self.assertNotIn(b"\r\n", (self.root / ".claude/agents/wled_reviewer.md").read_bytes())
        self.assertEqual(sync_agents.sync(self.root, check=True), [])

    def test_regeneration_is_byte_identical_and_does_not_rewrite_files(self):
        self.assertTrue(sync_agents.sync(self.root))
        before = self.snapshot()
        self.assertEqual(sync_agents.sync(self.root), [])
        self.assertEqual(sync_agents.sync(self.root, check=True), [])
        self.assertEqual(self.snapshot(), before)

    def test_check_missing_output_does_not_create_directories(self):
        before = self.snapshot()
        self.assertTrue(sync_agents.sync(self.root, check=True))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / ".claude").exists())

    def test_source_and_adapter_drift_are_read_only_and_repairable(self):
        sync_agents.sync(self.root)
        self.write_source("reviewer", "Updated description", "Changed\nprompt.\n")
        generated = self.root / ".claude/agents/wled_completion.md"
        generated.write_bytes(b"manual drift\n")
        before = self.snapshot()
        drift = sync_agents.sync(self.root, check=True)
        self.assertIn(".codex/agents/wled_reviewer.toml", drift)
        self.assertIn(".claude/agents/wled_completion.md", drift)
        self.assertEqual(self.snapshot(), before)
        sync_agents.sync(self.root)
        self.assertEqual(sync_agents.sync(self.root, check=True), [])

    def test_invalid_last_source_never_partially_updates_adapters(self):
        sync_agents.sync(self.root)
        bad_inputs = (
            '+++\nname = "wled_completion"\n+++\nBody\n',
            '+++\nname = "wled_completion"\nname = "duplicate"\ndescription = "x"\n+++\nBody\n',
            '+++\nname = "../../escape"\ndescription = "x"\n+++\nBody\n',
            '+++\nname = "wled_reviewer"\ndescription = "duplicate identity"\n+++\nBody\n',
            '+++\nname = "wled_completion"\ndescription = "x"\nmodel = "forced"\n+++\nBody\n',
            '+++\nname = "wled_completion"\ndescription = 12\n+++\nBody\n',
            '+++\nname = "wled_completion"\ndescription = "x"\n+++\n  \n',
            'not a role file\n',
        )
        for bad in bad_inputs:
            with self.subTest(bad=bad):
                self.write_source("coordinator", "Earlier valid change", "A new prompt\n")
                (self.root / "agents/completion.md").write_bytes(bad.encode("utf-8"))
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    sync_agents.sync(self.root)
                self.assertEqual(self.snapshot(), before)

    def test_missing_or_unexpected_source_is_rejected_and_preserved(self):
        unexpected = self.root / "agents/unrelated.md"
        unexpected.write_bytes(b"Do not overwrite this document.\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "unexpected"):
            sync_agents.sync(self.root)
        self.assertEqual(self.snapshot(), before)
        unexpected.unlink()
        (self.root / "agents/completion.md").unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "missing"):
            sync_agents.sync(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_unrelated_files_are_preserved(self):
        files = ("agents/README.md", "agents/private.txt", ".codex/agents/other.toml",
                 ".claude/agents/other.md", "elsewhere.txt")
        for relative in files:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"unrelated\n")
        sync_agents.sync(self.root)
        for relative in files:
            self.assertEqual((self.root / relative).read_bytes(), b"unrelated\n")

    def test_invalid_output_path_is_found_before_any_write(self):
        collision = self.root / ".claude/agents/wled_completion.md"
        collision.mkdir(parents=True)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "not a file"):
            sync_agents.sync(self.root)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / ".codex").exists())

    def test_write_failure_is_reported_without_claiming_batch_atomicity(self):
        real_replace = sync_agents.os.replace
        calls = []

        def replace_once(source, destination):
            calls.append(destination)
            if len(calls) == 2:
                raise OSError("synthetic disk failure")
            return real_replace(source, destination)

        with patch.object(sync_agents.os, "replace", side_effect=replace_once):
            with self.assertRaisesRegex(OSError, "synthetic disk failure"):
                sync_agents.sync(self.root)
        self.assertTrue(calls[0].is_file())  # Earlier file may already be replaced.
        self.assertFalse(calls[1].exists())
        self.assertEqual(list((self.root / ".claude/agents").iterdir()), [])
        sync_agents.sync(self.root)
        self.assertEqual(sync_agents.sync(self.root, check=True), [])

    def test_output_parent_file_collision_is_rejected_before_writes(self):
        parent = self.root / ".claude"
        parent.write_bytes(b"unrelated parent collision\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "parent is not a directory"):
            sync_agents.sync(self.root)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / ".codex").exists())

    def test_cli_drift_and_failure_exit_nonzero(self):
        output = io.StringIO()
        with patch.object(sync_agents, "sync", return_value=["adapter"]):
            with redirect_stdout(output):
                self.assertEqual(sync_agents.main(["--check"]), 1)
        self.assertIn("drift", output.getvalue())
        with patch.object(sync_agents, "sync", side_effect=OSError("synthetic failure")):
            with redirect_stderr(output):
                self.assertEqual(sync_agents.main([]), 1)
        self.assertIn("failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
