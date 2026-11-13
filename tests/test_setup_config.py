import json
import tempfile
import unittest
from pathlib import Path

from reel_skill_factory.core import WorkflowError, load_config
from reel_skill_factory.setup_config import configure


class SetupConfigTests(unittest.TestCase):
    def test_configures_private_inbox_and_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inbox = root / "inbox"
            inbox.mkdir()
            config = root / "config.local.json"
            configure(config, inbox)
            self.assertEqual(load_config(config).inbox_dir, inbox.resolve())
            original = config.read_bytes()
            configure(config, inbox)
            self.assertEqual(config.read_bytes(), original)
            other = root / "other"
            other.mkdir()
            with self.assertRaises(WorkflowError):
                configure(config, other)
            self.assertEqual(config.read_bytes(), original)

    def test_missing_folder_does_not_create_config(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.local.json"
            with self.assertRaises(WorkflowError):
                configure(config, Path(temp) / "missing")
            self.assertFalse(config.exists())


if __name__ == "__main__":
    unittest.main()
