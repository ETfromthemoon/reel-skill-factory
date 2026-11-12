import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_skill_factory.core import Config, WorkflowError
from reel_skill_factory import lifecycle


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.jobs = self.root / "jobs"
        self.config = Config(self.root, "owner/repo", "main", "base", 60)
        self.item = "ABC123"
        self.record = {"status": "published", "pr": "https://github.com/owner/repo/pull/1"}
        self.details = {"state": "OPEN", "isDraft": True, "headRefOid": "a" * 40,
                        "statusCheckRollup": [{"conclusion": "SUCCESS"}]}
        self.skill_path = "skills/example/SKILL.md"

    def test_evaluate_records_artifacts_and_judgment_for_exact_revision(self):
        def fake_run(command, **kwargs):
            if command[:2] == ["codex", "exec"]:
                workdir = Path(command[command.index("--cd") + 1])
                (workdir / "index.html").write_text("<h1>Done</h1>", encoding="utf-8")
                Path(command[command.index("--output-last-message") + 1]).write_text("Terminado", encoding="utf-8")
            return ""

        with patch.object(lifecycle, "_job", return_value=(self.record, self.jobs / self.item)), \
             patch.object(lifecycle, "_pr", return_value=(self.details, self.skill_path, self.record["pr"])), \
             patch.object(lifecycle, "_skill_at", return_value="---\nname: example\n---\nUse this skill\n"), \
             patch.object(lifecycle, "_judge", return_value={"verdict": "pass", "gaps": []}), \
             patch.object(lifecycle, "_codex_env", return_value={}), \
             patch.object(lifecycle, "run", side_effect=fake_run):
            report_path = lifecycle.evaluate(self.config, self.item, "A" * 30, "B" * 30)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["revision"], "a" * 40)
        self.assertEqual(report["files"], {"index.html": "<h1>Done</h1>"})
        self.assertEqual(report["judgment"]["verdict"], "pass")
        self.assertEqual(report["status"], "review")

    def test_activate_rejects_unreviewed_commit_before_mutation(self):
        with patch.object(lifecycle, "_job", return_value=(self.record, self.jobs / self.item)), \
             patch.object(lifecycle, "_pr", return_value=(self.details, self.skill_path, self.record["pr"])), \
             patch.object(lifecycle, "run") as run:
            with self.assertRaisesRegex(WorkflowError, "prueba terminada"):
                lifecycle.activate(self.config, self.item)
        run.assert_not_called()

    def test_activate_rejects_existing_different_skill_before_merge(self):
        job = self.jobs / self.item
        report = job / "evaluations" / "attempt" / "report.json"
        lifecycle._write_json(report, {"status": "review", "revision": "a" * 40,
                                       "judgment": {"verdict": "pass"}})
        target_root = self.root / "installed"
        target = target_root / "example" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("Existing user content", encoding="utf-8")
        with patch.object(lifecycle, "_job", return_value=(self.record, job)), \
             patch.object(lifecycle, "_pr", return_value=(self.details, self.skill_path, self.record["pr"])), \
             patch.object(lifecycle, "_skill_at", return_value="New content"), \
             patch.object(lifecycle, "run") as run:
            with self.assertRaisesRegex(WorkflowError, "skill distinta"):
                lifecycle.activate(self.config, self.item, targets=[target_root])
        run.assert_not_called()
        self.assertEqual(target.read_text(encoding="utf-8"), "Existing user content")

    def test_activate_installs_only_verified_merged_content(self):
        job = self.jobs / self.item
        report = job / "evaluations" / "attempt" / "report.json"
        lifecycle._write_json(report, {"status": "review", "revision": "a" * 40,
                                       "judgment": {"verdict": "pass"}})
        target_root = self.root / "installed"
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            if command[:3] == ["gh", "pr", "view"]:
                return json.dumps({"state": "MERGED", "mergeCommit": {"oid": "b" * 40}})
            return ""

        with patch.object(lifecycle, "_job", return_value=(self.record, job)), \
             patch.object(lifecycle, "_pr", return_value=(self.details, self.skill_path, self.record["pr"])), \
             patch.object(lifecycle, "_skill_at", return_value="Verified skill\n") as source, \
             patch.object(lifecycle, "run", side_effect=fake_run):
            installed = lifecycle.activate(self.config, self.item, targets=[target_root])
        self.assertEqual(installed, [target_root / "example" / "SKILL.md"])
        self.assertEqual(installed[0].read_text(encoding="utf-8"), "Verified skill\n")
        self.assertEqual(source.call_count, 2)
        self.assertTrue(any(cmd[:3] == ["gh", "pr", "merge"] for cmd in commands))
        self.assertEqual(json.loads((job / "activation.json").read_text(encoding="utf-8"))["merge_commit"], "b" * 40)


if __name__ == "__main__":
    unittest.main()
