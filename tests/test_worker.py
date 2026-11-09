import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from reel_skill_factory import worker
from reel_skill_factory.core import WorkflowError
from reel_skill_factory.worker import ProcessOptions


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / "inbox"
        self.inbox.mkdir()
        self.state_dir = self.root / ".local-state"
        self.state = self.state_dir / "results.json"
        self.jobs = self.state_dir / "jobs"
        self.config = SimpleNamespace(inbox_dir=self.inbox, whisper_model="base",
                                      review_whisper_model=None)
        for name, value in (("STATE_DIR", self.state_dir), ("STATE_PATH", self.state),
                            ("JOBS_DIR", self.jobs)):
            patcher = patch.object(worker, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(worker, "load_config", return_value=self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.frame = self.root / "frame.jpg"
        self.frame.write_bytes(b"frame de prueba")
        self.visual = {"frames": [{"timestamp": "[00:00]", "seconds": 0,
                                    "image": str(self.frame), "ocr_text": "Tema"}],
                       "has_audio": True, "duration_seconds": 15,
                       "media_path": None, "captions": None}
        patcher = patch.object(worker, "inspect_video", return_value=self.visual)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_old(self, name: str, content: bytes) -> Path:
        path = self.inbox / name
        path.write_bytes(content)
        old = time.time() - 60
        os.utime(path, (old, old))
        return path

    @staticmethod
    def transcript(text: str = "[00:01] Primero define el problema.") -> dict:
        return {"transcripcion": text, "duracion_seg": 15, "n_segmentos": 1,
                "fuente": "whisper (base)"}

    @staticmethod
    def result(status: str, reason: str = "none") -> dict:
        return {"status": status, "review_reason": reason,
                "analysis": "El video propone un método que requiere revisar algunas palabras del audio."}

    def test_local_video_uses_file_and_hash_without_publishing_file_path(self):
        video = self.make_old("mi-video.mp4", b"video de prueba")
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        with patch.object(worker, "transcribe", return_value=self.transcript()) as transcribe, \
             patch.object(worker, "generate", return_value=self.result("skillable")) as generate, \
             patch.object(worker, "publish", return_value="https://github.com/test/pull/1") as publish:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (0, 0))

        self.assertEqual(transcribe.call_count, 1)
        self.assertEqual(transcribe.call_args.args[0], str(video))
        self.assertEqual(generate.call_args.kwargs["source_type"], "local_video")
        self.assertIs(generate.call_args.kwargs["visual"], self.visual)
        source = publish.call_args.args[1]
        self.assertIn(digest, source)
        self.assertNotIn(str(video), source)
        item_id = f"video-{digest[:16]}"
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved[item_id]["status"], "published")
        self.assertTrue((self.jobs / item_id / "transcript.txt").is_file())

    def test_new_video_waits_for_drive_sync(self):
        (self.inbox / "nuevo.mov").write_bytes(b"video")
        with patch.object(worker, "transcribe") as transcribe:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (0, 0))
        transcribe.assert_not_called()

    def test_text_link_still_uses_reel_url(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        with patch.object(worker, "transcribe", return_value=self.transcript()) as transcribe, \
             patch.object(worker, "generate", return_value=self.result("not_skillable")) as generate:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
        self.assertEqual(transcribe.call_args.args[0], "https://www.instagram.com/reel/ABC123/")
        self.assertEqual(generate.call_args.kwargs["source_type"], "reel_url")

    def test_silent_video_uses_visual_evidence_without_transcribing(self):
        self.make_old("silencio.mp4", b"video de prueba")
        self.visual["has_audio"] = False
        with patch.object(worker, "transcribe") as transcribe, \
             patch.object(worker, "generate", return_value=self.result("not_skillable")) as generate:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
        transcribe.assert_not_called()
        self.assertEqual(generate.call_args.args[1]["transcripcion"], "")

    def test_watch_captions_avoid_second_download_and_transcription(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        self.visual["captions"] = self.transcript()
        with patch.object(worker, "transcribe") as transcribe, \
             patch.object(worker, "generate", return_value=self.result("not_skillable")) as generate:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
        transcribe.assert_not_called()
        self.assertEqual(generate.call_args.args[1], self.visual["captions"])

    def test_transcription_review_tries_small_and_publishes_only_clear_result(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        self.config.review_whisper_model = "small"
        first = self.transcript("[00:01] Palabras dudosas.")
        second = self.transcript("[00:01] Define el problema y verifica la solución.")
        with patch.object(worker, "transcribe", side_effect=[first, second]) as transcribe, \
             patch.object(worker, "generate", side_effect=[
                 self.result("needs_review", "transcription"), self.result("skillable")]), \
             patch.object(worker, "publish", return_value="https://github.com/test/pull/2") as publish:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
        self.assertEqual([call.args[1] for call in transcribe.call_args_list], ["base", "small"])
        self.assertEqual(publish.call_count, 1)
        saved = json.loads(self.state.read_text(encoding="utf-8"))["ABC123"]
        self.assertEqual((saved["status"], saved["model"]), ("published", "small"))
        self.assertIn("Define el problema", (self.jobs / "ABC123" / "transcript.txt").read_text())
        self.assertEqual(len(list((self.jobs / "ABC123" / "attempts").iterdir())), 2)

    def test_fallback_disagreement_stays_in_review(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        self.config.review_whisper_model = "small"
        with patch.object(worker, "transcribe", side_effect=[self.transcript(), self.transcript()]), \
             patch.object(worker, "generate", side_effect=[
                 self.result("needs_review", "transcription"), self.result("not_skillable")]), \
             patch.object(worker, "publish") as publish:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
        publish.assert_not_called()
        saved = json.loads(self.state.read_text(encoding="utf-8"))["ABC123"]
        self.assertEqual((saved["status"], saved["model"]), ("needs_review", "base"))

    def test_retry_can_use_corrected_saved_transcript_without_downloading_again(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        with patch.object(worker, "transcribe", return_value=self.transcript()) as transcribe, \
             patch.object(worker, "generate", side_effect=[
                 self.result("needs_review", "transcription"), self.result("skillable")]), \
             patch.object(worker, "publish", return_value="https://github.com/test/pull/3"):
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
            editable = self.jobs / "ABC123" / "transcript.txt"
            editable.write_text("[00:01] Primero define el problema con precisión.\n", encoding="utf-8")
            options = ProcessOptions(target_id="ABC123", use_saved_transcript=True)
            self.assertEqual(worker.process_inbox(self.root / "config.json", options), (1, 0))
        self.assertEqual(transcribe.call_count, 1)
        saved = json.loads(self.state.read_text(encoding="utf-8"))["ABC123"]
        self.assertEqual((saved["status"], saved["model"]), ("published", "edited"))

    def test_failed_retry_keeps_previous_review_result(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        self.state_dir.mkdir()
        self.state.write_text(json.dumps({"ABC123": {"status": "needs_review", "analysis": "Anterior"}}),
                              encoding="utf-8")
        options = ProcessOptions(target_id="ABC123", use_saved_transcript=True)
        self.assertEqual(worker.process_inbox(self.root / "config.json", options), (0, 1))
        saved = json.loads(self.state.read_text(encoding="utf-8"))["ABC123"]
        self.assertEqual(saved["status"], "needs_review")
        self.assertIn("No hay una transcripción guardada", saved["retry_error"])

    def test_targeted_retry_ignores_other_invalid_files(self):
        self.make_old("invalid.txt", b"no reel here")
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        self.state_dir.mkdir()
        self.state.write_text(json.dumps({"ABC123": {"status": "needs_review"}}), encoding="utf-8")
        with patch.object(worker, "transcribe", return_value=self.transcript()), \
             patch.object(worker, "generate", return_value=self.result("needs_review", "other")):
            self.assertEqual(worker.process_inbox(
                self.root / "config.json", ProcessOptions(target_id="ABC123")), (1, 0))
        self.assertNotIn("invalid.txt", json.loads(self.state.read_text(encoding="utf-8")))

    def test_worker_lock_rejects_second_process(self):
        with worker.worker_lock(), self.assertRaises(WorkflowError):
            with worker.worker_lock():
                pass

    def test_scheduled_pass_skips_when_manual_retry_holds_lock(self):
        self.make_old("reel.txt", b"https://www.instagram.com/reel/ABC123/")
        with worker.worker_lock(), patch.object(worker, "transcribe") as transcribe:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (0, 0))
        transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
