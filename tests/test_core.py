import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_skill_factory.core import (
    WorkflowError, find_reel_url, generate, load_config, normalize_reel_url,
    skill_markdown, source_markdown, validate_generation,
)


class UrlTests(unittest.TestCase):
    def test_share_url_is_canonical_and_drops_tracking(self):
        url, code = find_reel_url(
            "Mira esto: https://www.instagram.com/reel/ABC_123-/?igsh=secret123"
        )
        self.assertEqual(url, "https://www.instagram.com/reel/ABC_123-/")
        self.assertEqual(code, "ABC_123-")

    def test_external_host_and_non_reel_are_rejected(self):
        for value in (
            "https://instagram.com.evil.test/reel/ABC/",
            "https://instagram.com/p/ABC/",
            "http://instagram.com/reel/ABC/",
        ):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                normalize_reel_url(value)


class ConfigTests(unittest.TestCase):
    def test_valid_config_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            data = {"inbox_dir": temp, "repository": "owner/repo", "base_branch": "main"}
            path.write_text(json.dumps(data), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config.repository, "owner/repo")
            self.assertIsNone(config.review_whisper_model)
            data["review_whisper_model"] = "small"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_config(path).review_whisper_model, "small")
            data["review_whisper_model"] = "invalid"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                load_config(path)
            data["review_whisper_model"] = "small"
            data["inbox_dir"] = str(Path(temp) / "missing")
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                load_config(path)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.transcript = "[00:01] Primero define el problema.\n[00:05] Después prueba la solución."
        self.result = {
            "status": "skillable",
            "review_reason": "none",
            "title": "Resolver problemas",
            "slug": "resolver-problemas",
            "description": "Aplica un método para definir y probar soluciones a problemas.",
            "instructions_md": "# Resolver problemas\n\n" + "Define el problema, formula una prueba y evalúa el resultado. " * 3,
            "analysis": "El video propone definir el problema y después probar una solución. Es un método repetible.",
            "evidence": [{"timestamp": "[00:01]", "modality": "audio",
                          "finding": "Define el problema primero"}],
            "technical_sources": [],
        }

    def test_skillable_generation_builds_valid_frontmatter(self):
        validate_generation(self.result, self.transcript)
        markdown = skill_markdown(self.result["slug"], self.result)
        self.assertTrue(markdown.startswith("---\nname: resolver-problemas\ndescription:"))

    def test_fabricated_timestamp_is_rejected(self):
        self.result["evidence"][0]["timestamp"] = "[00:59]"
        with self.assertRaises(WorkflowError):
            validate_generation(self.result, self.transcript)

    def test_bare_timestamp_is_normalized_only_when_present(self):
        self.result["evidence"][0]["timestamp"] = "00:01"
        validate_generation(self.result, self.transcript)
        self.assertEqual(self.result["evidence"][0]["timestamp"], "[00:01]")

    def test_caption_only_is_not_treated_as_skill(self):
        self.result["status"] = "not_skillable"
        self.result["evidence"] = []
        self.result["instructions_md"] = ""
        validate_generation(self.result, "")

    def test_review_reason_matches_status(self):
        self.result["status"] = "needs_review"
        with self.assertRaises(WorkflowError):
            validate_generation(self.result, self.transcript)
        self.result["review_reason"] = "transcription"
        validate_generation(self.result, self.transcript)

    def test_visual_only_evidence_requires_a_real_frame(self):
        self.result["evidence"] = [{"timestamp": "[00:02]", "modality": "visual",
                                     "finding": "La pantalla muestra un criterio"}]
        visual = {"frames": [{"timestamp": "[00:02]"}]}
        validate_generation(self.result, "", visual)
        self.assertIn("(visual)", source_markdown("Fuente de prueba", self.result))
        visual["frames"][0]["timestamp"] = "[00:03]"
        with self.assertRaises(WorkflowError):
            validate_generation(self.result, "", visual)

    def test_generate_attaches_watch_frames_to_codex(self):
        with tempfile.TemporaryDirectory() as temp:
            workdir = Path(temp)
            frame = workdir / "frame.jpg"
            frame.write_bytes(b"imagen de prueba")
            visual = {"frames": [{"timestamp": "[00:02]", "ocr_text": "Error visual",
                                  "image": str(frame)}]}
            self.result["evidence"] = [{"timestamp": "[00:02]", "modality": "visual",
                                        "finding": "Error visual visible"}]

            def fake_run(command, **kwargs):
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text(json.dumps(self.result), encoding="utf-8")
                self.assertEqual(command[command.index("--image") + 1], str(frame))
                self.assertEqual(command[-2:], ["--image", str(frame)])
                self.assertIn('"ocr_text": "Error visual"', kwargs["input_text"])

            with patch("reel_skill_factory.core.run", side_effect=fake_run):
                self.assertEqual(generate("video de prueba", {"transcripcion": "",
                                 "duracion_seg": 5}, workdir, visual=visual)["status"], "skillable")


if __name__ == "__main__":
    unittest.main()
