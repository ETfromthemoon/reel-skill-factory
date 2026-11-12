import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reel_skill_factory.core import (
    WorkflowError, find_reel_url, generate, load_config, normalize_reel_url,
    skill_markdown, source_markdown, validate_fidelity, validate_generation,
    validate_source_map,
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
            data = {"inbox_dir": temp}
            path.write_text(json.dumps(data), encoding="utf-8")
            config = load_config(path)
            self.assertFalse(config.library_dir.is_relative_to(Path(temp)))
            self.assertIsNone(config.review_whisper_model)
            data["repository"] = "owner/old-public-repo"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "GitHub ya no se usa"):
                load_config(path)
            data.pop("repository")
            data["review_whisper_model"] = "small"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_config(path).review_whisper_model, "small")
            data["review_whisper_model"] = "invalid"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(WorkflowError):
                load_config(path)
            data["review_whisper_model"] = "small"
            data["library_dir"] = str(Path(temp) / "library")
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "fuera del repositorio y de la carpeta"):
                load_config(path)
            data.pop("library_dir")
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
            source_map = {"thesis": "El video enseña a reconocer un error visual en una interfaz.",
                          "audience": "Diseñadores", "format": "demonstration", "promised_count": None,
                          "lessons": [{"id": "L1", "point": "Reconocer el error visual", "basis": "explicit",
                                       "evidence": self.result["evidence"]}],
                          "gaps": [], "unproven_claims": [], "editorial_needs": []}
            review = {"verdict": "pass", "covered_ids": ["L1"], "issues": [],
                      "editorial_additions": [], "summary": "La skill conserva la enseñanza."}

            def fake_run(command, **kwargs):
                output = Path(command[command.index("--output-last-message") + 1])
                value = (source_map if output.name == "source-map.json" else
                         review if output.name == "fidelity.json" else self.result)
                output.write_text(json.dumps(value), encoding="utf-8")
                if output.name != "fidelity.json":
                    self.assertEqual(command[command.index("--image") + 1], str(frame))
                    self.assertEqual(command[-2:], ["--image", str(frame)])
                    self.assertIn('"ocr_text": "Error visual"', kwargs["input_text"])
                    self.assertIn('"task_intent": "Transformar interfaces"', kwargs["input_text"])

            with patch("reel_skill_factory.core.run", side_effect=fake_run):
                generated = generate("video de prueba", {"transcripcion": "",
                                     "duracion_seg": 5}, workdir, visual=visual,
                                     task_intent="Transformar interfaces")
                self.assertEqual(generated["status"], "skillable")
                self.assertEqual(generated["source_map"]["lessons"][0]["id"], "L1")

    def test_source_map_rejects_missing_evidence_and_unexplained_list_gap(self):
        source_map = {"thesis": "El video enseña dos pasos para probar una solución.",
                      "format": "list", "promised_count": 2,
                      "lessons": [{"id": "L1", "point": "Definir el problema", "basis": "explicit",
                                   "evidence": self.result["evidence"]}],
                      "gaps": [], "unproven_claims": [], "editorial_needs": []}
        with self.assertRaisesRegex(WorkflowError, "incompleta"):
            validate_source_map(source_map, self.transcript, None)
        source_map["gaps"] = ["Falta el segundo elemento"]
        validate_source_map(source_map, self.transcript, None)
        source_map["lessons"][0]["evidence"][0]["timestamp"] = "[00:59]"
        with self.assertRaisesRegex(WorkflowError, "ausente"):
            validate_source_map(source_map, self.transcript, None)

    def test_fidelity_downgrades_pass_with_missing_lessons(self):
        source_map = {"lessons": [{"id": "L1"}, {"id": "L2"}]}
        review = {"verdict": "pass", "covered_ids": ["L1"], "issues": [],
                  "editorial_additions": [], "summary": "Incompleta"}
        validate_fidelity(review, source_map)
        self.assertEqual(review["verdict"], "review")
        self.assertIn("L2", review["issues"][0])

    def test_failed_fidelity_gets_one_revision_before_publication(self):
        source_map = {"thesis": "El video enseña a definir el problema y luego probar una solución.",
                      "audience": "Equipos", "format": "sequence", "promised_count": 2,
                      "lessons": [
                          {"id": "L1", "point": "Definir el problema", "basis": "explicit",
                           "evidence": self.result["evidence"]},
                          {"id": "L2", "point": "Probar una solución", "basis": "explicit",
                           "evidence": [{"timestamp": "[00:05]", "modality": "audio",
                                         "finding": "Prueba la solución"}]}],
                      "gaps": [], "unproven_claims": [], "editorial_needs": []}
        first_review = {"verdict": "review", "covered_ids": ["L1"],
                        "issues": ["Falta probar la solución"], "editorial_additions": [],
                        "summary": "Falta una enseñanza."}
        final_review = {"verdict": "pass", "covered_ids": ["L1", "L2"],
                        "issues": [], "editorial_additions": [],
                        "summary": "Las dos enseñanzas están presentes."}
        with tempfile.TemporaryDirectory() as temp, \
             patch("reel_skill_factory.core._model_json", side_effect=[
                 source_map, self.result.copy(), first_review, self.result.copy(), final_review]) as model:
            generated = generate("video de prueba", {"transcripcion": self.transcript,
                                 "duracion_seg": 6}, Path(temp))
        self.assertEqual(generated["status"], "skillable")
        self.assertEqual(generated["fidelity_review"]["verdict"], "pass")
        self.assertEqual([call.args[2] for call in model.call_args_list],
                         ["source-map.json", "generation.json", "fidelity.json",
                          "revision.json", "fidelity-revision.json"])

    def test_persistent_fidelity_issue_requires_review(self):
        source_map = {"thesis": "El video enseña a definir un problema antes de probarlo.",
                      "audience": "Equipos", "format": "sequence", "promised_count": None,
                      "lessons": [{"id": "L1", "point": "Definir el problema", "basis": "explicit",
                                   "evidence": self.result["evidence"]}],
                      "gaps": [], "unproven_claims": [], "editorial_needs": []}
        review = {"verdict": "review", "covered_ids": ["L1"],
                  "issues": ["La skill altera el método"], "editorial_additions": [],
                  "summary": "La skill altera el método principal."}
        with tempfile.TemporaryDirectory() as temp, \
             patch("reel_skill_factory.core._model_json", side_effect=[
                 source_map, self.result.copy(), review.copy(), self.result.copy(), review.copy()]):
            generated = generate("video de prueba", {"transcripcion": self.transcript,
                                 "duracion_seg": 6}, Path(temp))
        self.assertEqual((generated["status"], generated["review_reason"]),
                         ("needs_review", "missing_context"))


if __name__ == "__main__":
    unittest.main()
