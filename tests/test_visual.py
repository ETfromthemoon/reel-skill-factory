import unittest

from reel_skill_factory.visual import _coverage_cues


class CoverageCueTests(unittest.TestCase):
    def test_short_numbered_video_keeps_dense_coverage(self):
        cues = _coverage_cues(15, 48)
        self.assertGreaterEqual(len(cues), 30)
        self.assertLessEqual(len(cues), 48)
        self.assertTrue({0.0, 1.0, 2.0}.issubset(cues))
        self.assertGreater(cues[-1], 14)

    def test_longer_video_stays_bounded_and_covers_the_end(self):
        cues = _coverage_cues(60, 48)
        self.assertLessEqual(len(cues), 48)
        self.assertGreaterEqual(len(cues), 30)
        self.assertGreater(cues[-1], 58)


if __name__ == "__main__":
    unittest.main()
