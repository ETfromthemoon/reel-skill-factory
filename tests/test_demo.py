import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_skill_factory import demo


class DemoTests(unittest.TestCase):
    def test_creates_versioned_private_demo_and_reviews_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "private" / "SKILL.md"
            skill.parent.mkdir()
            skill.write_text("---\nname: example\n---\nApply the lesson.\n", encoding="utf-8")
            job = root / "local-state" / "jobs" / "ABC123"
            generated = {"scenario": "Diseña una tarjeta de café con precio y botón.",
                         "expected": "Debe mostrar jerarquía, precio y botón legible.",
                         "sample_output_md": "Una tarjeta concreta con precio visible y botón destacado.",
                         "preview_html": "<html><body><h1>Café</h1></body></html>",
                         "checklist": ["Jerarquía"], "limitations": ["Sin navegador"]}
            review = {"verdict": "pass", "summary": "Cubre el caso", "evidence": ["Precio visible"], "gaps": []}
            result = {"description": "Aplica la lección", "source_map": {"thesis": "Enseña jerarquía visual",
                      "lessons": [{"id": "L1", "point": "Precio visible"}]}}
            with patch.object(demo, "_model_json", side_effect=[generated, review]) as model:
                path = demo.create_demo(skill, job, result)
            self.assertEqual(model.call_count, 2)
            self.assertTrue(all(call.kwargs["search"] is False for call in model.call_args_list))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["revision"], demo.skill_revision(skill))
            self.assertEqual(demo.read_demo(job, saved["revision"])["preview_html"], generated["preview_html"])
            skill.write_text("Changed", encoding="utf-8")
            self.assertIsNone(demo.read_demo(job, demo.skill_revision(skill)))

    def test_pass_with_gaps_is_downgraded_to_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "SKILL.md"
            skill.write_text("A skill", encoding="utf-8")
            generated = {"scenario": "Create a concrete example task.",
                         "expected": "Show one specific observable result.",
                         "sample_output_md": "A complete example result with enough detail.",
                         "preview_html": "", "checklist": [], "limitations": []}
            review = {"verdict": "pass", "summary": "Some criteria are unverified",
                      "evidence": [], "gaps": ["Browser not checked"]}
            with patch.object(demo, "_model_json", side_effect=[generated, review]):
                path = demo.create_demo(skill, root / "job", {})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["judgment"]["verdict"], "review")

    def test_active_html_is_not_exposed_as_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "SKILL.md"
            skill.write_text("A skill", encoding="utf-8")
            generated = {"scenario": "Create a specific example task.",
                         "expected": "Show one observable result in the output.",
                         "sample_output_md": "A specific result with enough detail to judge.",
                         "preview_html": "<html><body><script>alert(1)</script></body></html>",
                         "checklist": [], "limitations": []}
            review = {"verdict": "review", "summary": "Preview omitted", "evidence": [], "gaps": ["No preview"]}
            with patch.object(demo, "_model_json", side_effect=[generated, review]):
                path = demo.create_demo(skill, root / "job", {})
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["preview_html"], "")
            self.assertIn("se omitió", saved["limitations"][-1])


if __name__ == "__main__":
    unittest.main()
