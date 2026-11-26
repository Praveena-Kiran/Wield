"""☝️ / 👇 pointing: reading the finger, scrolling while held, and moving
older Browse & Media profiles over to it."""

import unittest

from backend.gestures.pointing import pointing
from backend.gestures.scroll import POINT_NOTCHES_PER_SECOND, ScrollController


def hand(direction="down", index_straight=True, others_curled=True):
    """21 (x, y) points: wrist at the middle, the index finger up or down."""
    sign = 1 if direction == "down" else -1
    wrist = (0.5, 0.5)
    pts = [wrist] + [(0.5, 0.5)] * 20

    def at(dx, dy):
        return (0.5 + dx, 0.5 + sign * dy)

    # Index: knuckle, two joints, tip in a line (or bent back).
    pts[5], pts[6] = at(0.0, 0.08), at(0.0, 0.12)
    if index_straight:
        pts[7], pts[8] = at(0.0, 0.16), at(0.0, 0.20)
    else:
        pts[7], pts[8] = at(0.03, 0.10), at(0.03, 0.07)
    # Middle, ring, little: joints out from the wrist, tips curled back in
    # (or sticking out).
    for joint, tip, dx in ((10, 12, 0.02), (14, 16, 0.04), (18, 20, 0.06)):
        pts[joint] = at(dx, 0.09)
        pts[tip] = at(dx, 0.13 if not others_curled else 0.05)
    return pts


class PointingTests(unittest.TestCase):

    def test_up_and_down(self):
        self.assertEqual(pointing(hand("down")), "down")
        self.assertEqual(pointing(hand("up")), "up")

    def test_not_pointing(self):
        self.assertIsNone(pointing(hand("down", index_straight=False)))
        self.assertIsNone(pointing(hand("down", others_curled=False)))   # open hand
        self.assertIsNone(pointing(None))
        self.assertIsNone(pointing([(0, 0)] * 5))

    def test_sideways_is_not_up_or_down(self):
        pts = hand("down")
        sideways = [(0.5 + (y - 0.5), 0.5 + (x - 0.5)) for x, y in pts]   # turned 90°
        self.assertIsNone(pointing(sideways))


class PointScrollTests(unittest.TestCase):

    def run_for(self, scroller, direction, seconds, start=0.0, fps=30):
        total = 0
        for i in range(int(seconds * fps)):
            total += scroller.update(True, None, start + i / fps, direction=direction)
        return total

    def test_scrolls_the_way_you_point(self):
        s = ScrollController()
        self.assertLess(self.run_for(s, "down", 1.0), 0)
        s = ScrollController()
        self.assertGreater(self.run_for(s, "up", 1.0), 0)
        self.assertEqual(s.direction, "up")

    def test_speeds_up_the_longer_you_hold(self):
        s = ScrollController()
        self.assertGreater(s.point_rate(3.0), s.point_rate(0.5))
        self.assertAlmostEqual(s.point_rate(0.0), POINT_NOTCHES_PER_SECOND)

    def test_letting_go_stops(self):
        s = ScrollController()
        self.run_for(s, "down", 0.5)
        self.assertEqual(s.update(False, None, 1.0, direction="down"), 0)
        self.assertIsNone(s.direction)


class OlderProfileTests(unittest.TestCase):

    class Profile:
        def __init__(self, gesture_map, version=None):
            self.current_profile = {"name": "Browse & Media", "gesture_map": gesture_map}
            if version:
                self.current_profile["defaults_version"] = version
            self.saved = 0

        def get_gesture_map(self):
            return self.current_profile["gesture_map"]

        def save_profile(self):
            self.saved += 1

    def test_untouched_old_defaults_move_to_pointing(self):
        from backend.automation.browse_media import add_missing_defaults
        p = self.Profile({
            "✌️ Peace": "browse_scroll",
            "☝️ Pointing Up": "browse_tab_next",
            "✋ Open Palm": "browse_tab_reopen",
            "👎 Thumbs Down": "browse_tab_previous",
            "✊ Fist": "browse_tab_close",
        })
        add_missing_defaults(p)
        m = p.get_gesture_map()
        self.assertEqual(m["☝️ Pointing Up"], "browse_point_up")
        self.assertEqual(m["👇 Pointing Down"], "browse_point_down")
        self.assertEqual(m["👎 Thumbs Down"], "browse_page_back")
        self.assertNotIn("✌️ Peace", m)
        self.assertNotIn("✋ Open Palm", m)
        self.assertEqual(m["✊ Fist"], "browse_tab_close")

    def test_your_own_choices_are_kept_and_it_runs_once(self):
        from backend.automation.browse_media import add_missing_defaults
        p = self.Profile({"✌️ Peace": "browse_video_play_pause"})     # changed by the user
        add_missing_defaults(p)
        self.assertEqual(p.get_gesture_map()["✌️ Peace"], "browse_video_play_pause")
        self.assertEqual(p.current_profile["defaults_version"], 2)

        # Later, the user sets ☝️ to next tab themselves: left alone.
        p.get_gesture_map()["☝️ Pointing Up"] = "browse_tab_next"
        add_missing_defaults(p)
        self.assertEqual(p.get_gesture_map()["☝️ Pointing Up"], "browse_tab_next")


if __name__ == "__main__":
    unittest.main()
