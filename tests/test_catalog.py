import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


class CatalogTests(unittest.TestCase):
    def test_every_published_skill_has_matching_frontmatter(self):
        if not SKILLS.exists():
            return
        for folder in SKILLS.iterdir():
            if not folder.is_dir():
                continue
            with self.subTest(skill=folder.name):
                content = (folder / "SKILL.md").read_text(encoding="utf-8")
                match = re.match(r"\A---\nname: ([a-z0-9-]+)\ndescription: (.+)\n---\n", content)
                self.assertIsNotNone(match)
                self.assertEqual(match.group(1), folder.name)
                self.assertGreater(len(match.group(2)), 20)


if __name__ == "__main__":
    unittest.main()
