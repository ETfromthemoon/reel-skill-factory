import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname
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
            generated = {"proof_kind": "interface_static", "motion_stages": [],
                         "scenario": "Diseña una tarjeta de café con precio y botón.",
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
            generated = {"proof_kind": "document", "motion_stages": [],
                         "scenario": "Create a concrete example task.",
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
            generated = {"proof_kind": "interface_static", "motion_stages": [],
                         "scenario": "Create a specific example task.",
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

    def test_motion_requires_observed_frames_and_cannot_pass_without_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "SKILL.md"
            skill.write_text("Animate the transition", encoding="utf-8")
            generated = {"proof_kind": "interface_static", "scenario": "Rediseña un panel con movimiento.",
                         "expected": "El panel cambia de estado en tres momentos observables.",
                         "sample_output_md": "Panel con entrada, desplazamiento y estado final.",
                         "preview_html": "<html><style>@keyframes enter{to{opacity:1}}</style><body>Panel</body></html>",
                         "motion_stages": ["Inicio", "Desarrollo", "Final"],
                         "checklist": ["Entrada"], "limitations": []}
            review = {"verdict": "pass", "summary": "Parecería completo", "evidence": [], "gaps": []}
            result = {"source_map": {"thesis": "Movimiento de paneles", "lessons": []}}
            with patch.object(demo, "_model_json", side_effect=[generated, review]), \
                 patch.object(demo, "_capture_motion", return_value=([], "Sin capturas")):
                path = demo.create_demo(skill, root / "job", result)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["proof_kind"], "interface_motion")
            self.assertEqual(saved["judgment"]["verdict"], "review")
            self.assertIn("Sin capturas", saved["judgment"]["gaps"])

    def test_motion_review_retries_once_with_observed_gaps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "SKILL.md"
            skill.write_text("Animate the view", encoding="utf-8")
            generated = {"proof_kind": "interface_motion", "scenario": "Transforma un panel entre vistas.",
                         "expected": "Tres estados de navegación y composición observables.",
                         "sample_output_md": "Vista inicial, transición y vista final terminada.",
                         "preview_html": "<html><style>@keyframes enter{to{opacity:1}}</style><body>Panel</body></html>",
                         "motion_stages": ["Inicio", "Cambio", "Final"], "checklist": [], "limitations": []}
            first = {"verdict": "review", "summary": "Falta la vista final", "gaps": ["No aparece final"],
                     "evidence": []}
            second = {"verdict": "pass", "summary": "Cambio visible", "gaps": [], "evidence": ["Tres estados"]}

            def shots(_html, workdir):
                paths = [workdir / f"shot-{index}.png" for index in range(3)]
                for index, path in enumerate(paths):
                    path.write_bytes(b"PNG" + bytes([index]))
                return paths, None

            with patch.object(demo, "_model_json", side_effect=[generated.copy(), first, generated.copy(), second]) as model, \
                 patch.object(demo, "_capture_motion", side_effect=shots):
                path = demo.create_demo(skill, root / "job", {"source_map": {"thesis": "Movimiento"}})
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(model.call_count, 4)
            self.assertEqual(model.call_args_list[2].args[4]["prior_demo_feedback"]["gaps"], ["No aparece final"])
            self.assertEqual(saved["judgment"]["verdict"], "pass")

    def test_motion_capture_freezes_css_timeline_at_three_instants(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = []

            def fake_run(command, **_kwargs):
                page = Path(url2pathname(urlparse(command[-1]).path))
                pages.append(page.read_text(encoding="utf-8"))
                shot = Path(next(arg.removeprefix("--screenshot=") for arg in command
                                 if arg.startswith("--screenshot=")))
                shot.write_bytes(bytes([len(pages)]) * 1200)

            html = "<html><head><style>@keyframes enter{to{opacity:1}}</style></head><body>Test</body></html>"
            with patch.object(demo, "_browser", return_value=Path("browser")), \
                 patch.object(demo, "run", side_effect=fake_run):
                shots, error = demo._capture_motion(html, root)
            self.assertIsNone(error)
            self.assertEqual(len(shots), 3)
            for milliseconds, page in zip(demo.FRAME_TIMES, pages):
                self.assertIn(f"animation-delay:-{milliseconds}ms!important", page)
                self.assertIn("default-src 'none'", page)


if __name__ == "__main__":
    unittest.main()
