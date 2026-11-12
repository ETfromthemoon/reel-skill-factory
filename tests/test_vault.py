import tempfile
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
            state = {"ABC123": {"status": "published", "pr": "https://github.com/example/repo/pull/1"}}
            html = render_vault(state, root / "jobs", root)
            self.assertIn("Revisar &lt;script&gt;", html)
            self.assertIn("Borrador listo", html)
            self.assertNotIn("<script>", html)
            self.assertIn("Por qué se creó", html)
            self.assertIn("Qué enseñaba el video", html)
            self.assertIn("Enseña &lt;script&gt;", html)
            self.assertIn("Contraste y adaptaciones", html)
            self.assertIn("Evidencia del video (1)", html)
            self.assertIn("https://github.com/example/repo/pull/1", html)
            self.assertTrue(write_vault(state, root / "jobs", root).is_file())

    def test_ignores_invalid_job_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            html = render_vault({"../outside": {"status": "published"}}, root / "jobs", root)
            self.assertNotIn("../outside", html)

    def test_interactive_vault_shows_review_gate_and_escapes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "jobs" / "ABC123" / "evaluations" / "trial" / "report.json"
            report.parent.mkdir(parents=True)
            report.write_text('{"status":"review","judgment":{"verdict":"review",'
                              '"summary":"<script>","gaps":["Sin navegador"]}}', encoding="utf-8")
            html = render_vault({"ABC123": {"status": "published"}}, root / "jobs", root,
                                token="local-token")
            self.assertIn("Probar en entorno aislado", html)
            self.assertIn("Revisé la prueba", html)
            self.assertIn("Sin navegador", html)
            self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
