import hashlib
import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


worker = importlib.import_module("reel_skill_factory.__main__")


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / "inbox"
        self.inbox.mkdir()
        self.state = self.root / "results.json"
        self.config = SimpleNamespace(inbox_dir=self.inbox, whisper_model="base")

    def test_local_video_uses_file_and_hash_without_publishing_file_path(self):
        video = self.inbox / "mi-video.mp4"
        video.write_bytes(b"video de prueba")
        old = time.time() - 60
        os.utime(video, (old, old))
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        result = {"status": "skillable", "title": "Prueba", "slug": "prueba"}
        with patch.object(worker, "STATE_PATH", self.state), \
             patch.object(worker, "load_config", return_value=self.config), \
             patch.object(worker, "transcribe", return_value={"transcripcion": "[00:01] Prueba"}) as transcribe, \
             patch.object(worker, "generate", return_value=result) as generate, \
             patch.object(worker, "publish", return_value="https://github.com/test/pull/1") as publish:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (0, 0))

        self.assertEqual(transcribe.call_count, 1)
        self.assertEqual(transcribe.call_args.args[0], str(video))
        self.assertEqual(generate.call_args.kwargs["source_type"], "local_video")
        source = publish.call_args.args[1]
        self.assertIn(digest, source)
        self.assertNotIn(str(video), source)
        self.assertEqual(publish.call_args.args[2], f"video-{digest[:16]}")
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved[f"video-{digest[:16]}"]["status"], "published")

    def test_new_video_waits_for_drive_sync(self):
        (self.inbox / "nuevo.mov").write_bytes(b"video")
        with patch.object(worker, "STATE_PATH", self.state), \
             patch.object(worker, "load_config", return_value=self.config), \
             patch.object(worker, "transcribe") as transcribe:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (0, 0))
        transcribe.assert_not_called()

    def test_text_link_still_uses_reel_url(self):
        (self.inbox / "reel.txt").write_text("https://www.instagram.com/reel/ABC123/", encoding="utf-8")
        result = {"status": "not_skillable", "analysis": "Video de prueba sin método reutilizable"}
        with patch.object(worker, "STATE_PATH", self.state), \
             patch.object(worker, "load_config", return_value=self.config), \
             patch.object(worker, "transcribe", return_value={"transcripcion": "[00:01] Prueba"}) as transcribe, \
             patch.object(worker, "generate", return_value=result) as generate:
            self.assertEqual(worker.process_inbox(self.root / "config.json"), (1, 0))
        self.assertEqual(transcribe.call_args.args[0], "https://www.instagram.com/reel/ABC123/")
        self.assertEqual(generate.call_args.kwargs["source_type"], "reel_url")


if __name__ == "__main__":
    unittest.main()
