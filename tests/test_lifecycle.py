import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_skill_factory import lifecycle
from reel_skill_factory.core import Config, WorkflowError
from reel_skill_factory.library import save_draft


class PrivateLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = Config(self.root, "base", 60, library_dir=self.root / "private")
        self.job = self.root / "jobs" / "ABC123"
        self.draft = self.config.library_dir / "drafts" / "ABC123"
        self.draft.mkdir(parents=True)
        self.skill = "---\nname: example\ndescription: A useful sample skill\n---\n\nDo the task.\n"
        (self.draft / "SKILL.md").write_text(self.skill, encoding="utf-8")
        (self.draft / "source.md").write_text("Source summary", encoding="utf-8")
        (self.draft / "metadata.json").write_text('{"slug":"example"}', encoding="utf-8")

    def test_evaluation_is_bound_to_local_skill_hash(self):
        def fake_run(command, **kwargs):
            if command[:2] == ["codex", "exec"]:
                workdir = Path(command[command.index("--cd") + 1])
                (workdir / "index.html").write_text("<h1>Done</h1>", encoding="utf-8")
                Path(command[command.index("--output-last-message") + 1]).write_text("Done", encoding="utf-8")
            return ""

        with patch.object(lifecycle, "_job", return_value=(self.job, self.draft)), \
             patch.object(lifecycle, "_judge", return_value={"verdict": "pass", "gaps": []}), \
             patch.object(lifecycle, "_codex_env", return_value={}), \
             patch.object(lifecycle, "run", side_effect=fake_run):
            report_path = lifecycle.evaluate(self.config, "ABC123", "A" * 30, "B" * 30)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["revision"], hashlib.sha256(self.skill.encode()).hexdigest())
        self.assertEqual(report["files"], {"index.html": "<h1>Done</h1>"})

    def test_activation_requires_review_of_current_hash(self):
        with patch.object(lifecycle, "_job", return_value=(self.job, self.draft)):
            with self.assertRaisesRegex(WorkflowError, "prueba terminada"):
                lifecycle.activate(self.config, "ABC123", targets=[self.root / "agent"])
        self.assertFalse((self.config.library_dir / "approved").exists())

    def test_activation_approves_locally_and_installs_without_github(self):
        report = self.job / "evaluations" / "trial" / "report.json"
        lifecycle._write_json(report, {"status": "review", "revision": hashlib.sha256(self.skill.encode()).hexdigest(),
                                       "judgment": {"verdict": "pass"}})
        target_root = self.root / "agent"
        with patch.object(lifecycle, "_job", return_value=(self.job, self.draft)), \
             patch.object(lifecycle, "run") as command:
            installed = lifecycle.activate(self.config, "ABC123", targets=[target_root])
        command.assert_not_called()
        self.assertEqual(installed[0].read_text(encoding="utf-8"), self.skill)
        self.assertEqual((self.config.library_dir / "approved" / "example" / "SKILL.md").read_text(encoding="utf-8"), self.skill)
        self.assertNotIn("pr", json.loads((self.job / "activation.json").read_text(encoding="utf-8")))

    def test_sync_uses_private_catalog_and_preserves_local_edits(self):
        approved = self.config.library_dir / "approved" / "example"
        approved.mkdir(parents=True)
        source = approved / "SKILL.md"
        source.write_text(self.skill, encoding="utf-8")
        target_root = self.root / "agent"
        installed = lifecycle.sync_approved(library_dir=self.config.library_dir, targets=[target_root])
        self.assertEqual(installed[0].read_text(encoding="utf-8"), self.skill)
        source.write_text(self.skill + "More\n", encoding="utf-8")
        lifecycle.sync_approved(library_dir=self.config.library_dir, targets=[target_root])
        self.assertIn("More", installed[0].read_text(encoding="utf-8"))
        installed[0].write_text("My edits", encoding="utf-8")
        with self.assertRaisesRegex(WorkflowError, "modificada"):
            lifecycle.sync_approved(library_dir=self.config.library_dir, targets=[target_root])

    def test_save_draft_never_writes_to_shared_checkout(self):
        result = {"slug": "example", "title": "Example", "description": "A useful sample skill",
                  "instructions_md": "Do the task.", "analysis": "A detailed analysis of the source.",
                  "evidence": [], "technical_sources": []}
        fresh = save_draft(self.config, "NEW123", "source", result)
        self.assertTrue(fresh.is_file())
        self.assertTrue((fresh.parent / "source.md").is_file())
        self.assertTrue((fresh.parent / "metadata.json").is_file())
        with self.assertRaisesRegex(WorkflowError, "borrador distinto"):
            save_draft(self.config, "ABC123", "source", result)
        new_path = save_draft(self.config, "ABC123", "source", result, update=True)
        self.assertTrue(new_path.is_relative_to(self.config.library_dir))
        self.assertFalse(new_path.is_relative_to(Path(__file__).resolve().parent.parent))


if __name__ == "__main__":
    unittest.main()
