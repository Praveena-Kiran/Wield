import math
import unittest

import random

from backend.fog import OneEuroFilter, PenState, PointSmoother, fingertip, hand_mode


def hand(extended):
    """Synthetic landmarks: wrist at the bottom, fingers pointing up.
    `extended` = set of finger names that are out."""
    pts = [(0.5, 0.9)] + [(0.5, 0.8)] * 20
    bases = {"index": (0.42, 5, 6, 7, 8), "middle": (0.48, 9, 10, 11, 12),
             "ring": (0.54, 13, 14, 15, 16), "pinky": (0.60, 17, 18, 19, 20)}
    for name, (x, mcp, pip, dip, tip) in bases.items():
        pts[mcp] = (x, 0.7)
        pts[pip] = (x, 0.6)
        if name in extended:
            pts[dip], pts[tip] = (x, 0.5), (x, 0.4)
        else:  # curled back down towards the palm
            pts[dip], pts[tip] = (x, 0.65), (x, 0.72)
    pts[4] = (0.35, 0.75)
    return [(x, y, 0.0) for x, y in pts]


class HandModeTests(unittest.TestCase):

    def test_modes(self):
        self.assertEqual(hand_mode(hand({"index"})), "write")
        self.assertEqual(hand_mode(hand(set())), "pause")
        self.assertEqual(hand_mode(hand({"index", "middle", "ring", "pinky"})), "wipe")
        self.assertIsNone(hand_mode(hand({"index", "middle"})))   # peace sign
        self.assertIsNone(hand_mode(None))

    def test_write_is_forgiving(self):
        # Ring or pinky a little out still writes; a peace sign doesn't.
        self.assertEqual(hand_mode(hand({"index", "pinky"})), "write")
        self.assertEqual(hand_mode(hand({"index", "ring"})), "write")
        self.assertIsNone(hand_mode(hand({"index", "ring", "pinky"})))

    def test_fingertip(self):
        self.assertEqual(fingertip(hand({"index"}))[:2], (0.42, 0.4))
        self.assertIsNone(fingertip(None))


class SmoothingTests(unittest.TestCase):

    def test_one_euro_removes_jitter_from_a_still_finger(self):
        random.seed(3)
        f = OneEuroFilter()
        raw, out = [], []
        for i in range(120):
            x = 0.5 + random.uniform(-0.01, 0.01)
            raw.append(x)
            out.append(f(x, i / 30))
        spread = lambda v: max(v[30:]) - min(v[30:])
        self.assertLess(spread(out), spread(raw) / 2)

    def test_one_euro_keeps_up_with_a_fast_move(self):
        f = OneEuroFilter()
        for i in range(30):
            y = f(i * 0.02, i / 30)      # 0.6 of the screen per second
        self.assertGreater(y, 0.58 - 0.06)

    def test_point_smoother_resets_after_a_pause(self):
        s = PointSmoother()
        s((0.1, 0.1), 0.0)
        self.assertEqual(s((0.9, 0.9), 2.0), (0.9, 0.9))


class PenStateTests(unittest.TestCase):

    def test_needs_two_frames_to_start(self):
        pen = PenState()
        self.assertIsNone(pen.update("write", 0.00))
        self.assertEqual(pen.update("write", 0.03), "write")

    def test_survives_short_dropouts_and_flickers(self):
        pen = PenState()
        pen.update("write", 0.00)
        pen.update("write", 0.03)
        self.assertEqual(pen.update(None, 0.20), "write")      # hand lost briefly
        self.assertEqual(pen.update("write", 0.25), "write")
        self.assertEqual(pen.update("pause", 0.30), "write")   # one odd frame
        self.assertEqual(pen.update("pause", 0.50), "pause")   # really lifted
        self.assertFalse(pen.down)


if __name__ == "__main__":
    unittest.main()
