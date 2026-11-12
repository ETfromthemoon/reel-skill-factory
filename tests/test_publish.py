import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from reel_skill_factory.core import Config, WorkflowError, publish


class PublishRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(Path("."), "owner/repo", "main", "base", 60)
        self.source = "https://www.instagram.com/reel/ABC123/"
        self.result = {"title": "Una skill", "slug": "una-skill", "description": "Descripción",
                       "instructions_md": "Instrucciones", "analysis": "Análisis",
                       "evidence": [], "technical_sources": []}

    def test_closed_pr_is_not_reported_as_published(self):
        def fake_run(command, **kwargs):
            if command[:3] == ["gh", "pr", "list"]:
                return json.dumps([{"url": "https://github.com/owner/repo/pull/1", "state": "CLOSED"}])
            return ""

        with patch("reel_skill_factory.core.subprocess.run", return_value=SimpleNamespace(returncode=0)), \
             patch("reel_skill_factory.core.run", side_effect=fake_run) as run:
            with self.assertRaisesRegex(WorkflowError, "PR cerrado"):
                publish(self.config, self.source, "ABC123", self.result)
        self.assertFalse(any(call.args[0][:3] == ["gh", "pr", "create"] for call in run.call_args_list))

    def test_pushed_branch_without_pr_can_recover_if_contents_match(self):
        def fake_run(command, **kwargs):
            if command[:3] == ["gh", "pr", "list"]:
                return "[]"
            if command[:2] == ["git", "show"]:
                return f"# Análisis de origen\n\nFuente: {self.source}\n"
            if command[:3] == ["git", "diff", "--name-only"]:
                return "sources/ABC123.md\nskills/una-skill/SKILL.md"
            if command[:3] == ["gh", "pr", "view"]:
                return json.dumps({"url": "https://github.com/owner/repo/pull/2",
                                   "state": "OPEN", "isDraft": True})
            return ""

        with patch("reel_skill_factory.core.subprocess.run", return_value=SimpleNamespace(returncode=0)), \
             patch("reel_skill_factory.core.run", side_effect=fake_run) as run:
            url = publish(self.config, self.source, "ABC123", self.result)
        self.assertEqual(url, "https://github.com/owner/repo/pull/2")
        self.assertTrue(any(call.args[0][:3] == ["gh", "pr", "create"] for call in run.call_args_list))

    def test_pushed_branch_with_unrelated_files_is_not_reused(self):
        def fake_run(command, **kwargs):
            if command[:3] == ["gh", "pr", "list"]:
                return "[]"
            if command[:2] == ["git", "show"]:
                return f"Fuente: {self.source}\n"
            if command[:3] == ["git", "diff", "--name-only"]:
                return "sources/ABC123.md\nskills/una-skill/SKILL.md\nsecret.txt"
            return ""

        with patch("reel_skill_factory.core.subprocess.run", return_value=SimpleNamespace(returncode=0)), \
             patch("reel_skill_factory.core.run", side_effect=fake_run):
            with self.assertRaisesRegex(WorkflowError, "no coincide"):
                publish(self.config, self.source, "ABC123", self.result)

    def test_refresh_rejects_non_draft_open_pr(self):
        def fake_run(command, **kwargs):
            if command[:3] == ["gh", "pr", "list"]:
                return json.dumps([{"url": "https://github.com/owner/repo/pull/1", "state": "OPEN"}])
            if command[:3] == ["gh", "pr", "view"]:
                return json.dumps({"state": "OPEN", "isDraft": False, "files": []})
            return ""

        with patch("reel_skill_factory.core.subprocess.run", return_value=SimpleNamespace(returncode=0)), \
             patch("reel_skill_factory.core.run", side_effect=fake_run) as run:
            with self.assertRaisesRegex(WorkflowError, "borrador abierto"):
                publish(self.config, self.source, "ABC123", self.result, update_draft=True)
        self.assertFalse(any(call.args[0][:2] == ["git", "push"] for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
