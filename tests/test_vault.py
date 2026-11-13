import tempfile
import hashlib
import json
import unittest
from pathlib import Path

from reel_skill_factory.vault import render_vault, write_vault


class VaultTests(unittest.TestCase):
    def test_renders_skill_and_escapes_video_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "jobs" / "ABC123"
            job.mkdir(parents=True)
            (job / "result.json").write_text(
                '{"title":"Revisar <script>","description":"Diseñar tarjetas",'
                '"instructions_md":"No ejecutar <script>","analysis":"Visto en [00:02]",'
                '"source_map":{"thesis":"Enseña <script>","lessons":'
                '[{"id":"L1","point":"Corregir la tarjeta","basis":"explicit"}]},'
                '"fidelity_review":{"verdict":"pass","summary":"Cubre L1",'
                '"issues":[],"editorial_additions":["Comprobar contraste"]},'
                '"evidence":[{"timestamp":"[00:02]","modality":"visual",'
                '"finding":"Una tarjeta"}]}', encoding="utf-8")
            state = {"ABC123": {"status": "draft", "draft_path": "C:/private/ABC123/SKILL.md"}}
            html = render_vault(state, root / "jobs", root)
            self.assertIn("Revisar &lt;script&gt;", html)
            self.assertIn("Borrador privado", html)
            self.assertNotIn("<script>", html)
            self.assertIn("Por qué se creó", html)
            self.assertIn("Qué enseñaba el video", html)
            self.assertIn("Enseña &lt;script&gt;", html)
            self.assertIn("Contraste y adaptaciones", html)
            self.assertIn("Evidencia del video (1)", html)
            self.assertIn("C:/private/ABC123/SKILL.md", html)
            self.assertNotIn("github.com", html)
            self.assertTrue(write_vault(state, root / "jobs", root).is_file())

    def test_ignores_invalid_job_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            html = render_vault({"../outside": {"status": "draft"}}, root / "jobs", root)
            self.assertNotIn("../outside", html)

    def test_interactive_vault_shows_local_first_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "jobs" / "ABC123"
            job.mkdir(parents=True)
            frame = job / "first.jpg"
            frame.write_bytes(b"test")
            (job / "visual.json").write_text(json.dumps({"frames": [{"image": str(frame)}]}), encoding="utf-8")
            html = render_vault({"ABC123": {"status": "draft"}}, root / "jobs", root, token="test")
            self.assertIn('src="/frame/ABC123"', html)

    def test_interactive_vault_shows_review_gate_and_escapes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "jobs" / "ABC123" / "evaluations" / "trial" / "report.json"
            report.parent.mkdir(parents=True)
            skill = root / "private" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("A skill\n", encoding="utf-8")
            revision = hashlib.sha256(skill.read_text(encoding="utf-8").encode()).hexdigest()
            report.write_text('{"status":"review","revision":"' + revision + '","judgment":{"verdict":"review",'
                              '"summary":"<script>","gaps":["Sin navegador"]}}', encoding="utf-8")
            html = render_vault({"ABC123": {"status": "draft", "draft_path": str(skill)}}, root / "jobs", root,
                                token="local-token")
            self.assertIn("Probar este borrador", html)
            self.assertIn("Cómo probar una skill, paso a paso", html)
            self.assertIn("Confirmo que revisé el resultado y los vacíos", html)
            self.assertIn("Sin navegador", html)
            self.assertIn("La prueba no creó archivos", html)
            self.assertNotIn('http-equiv="refresh"', html)
            self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
