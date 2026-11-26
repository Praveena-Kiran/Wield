"""The six hand signs mean the same kind of thing in every built-in studio."""

import json
import os
import unittest

from backend.hand_signs import EXPECTED, OTHER_BUILT_IN_GESTURES, SIGNS
from backend.paths import DEFAULT_CONFIG_DIR


def defaults(profile):
    with open(os.path.join(DEFAULT_CONFIG_DIR, "profiles", f"{profile}.json"), encoding="utf-8") as f:
        return json.load(f)["gesture_map"]


class HandSignTests(unittest.TestCase):

    def test_six_signs(self):
        self.assertEqual(len(SIGNS), 6)
        self.assertEqual(len({s.gesture for s in SIGNS}), 6)

    def test_built_in_studios_keep_to_the_meanings(self):
        for profile, expected in EXPECTED.items():
            gesture_map = defaults(profile)
            for gesture, action in expected.items():
                self.assertEqual(gesture_map.get(gesture), action, f"{profile}: {gesture}")

    def test_no_other_gestures_to_learn(self):
        # ✌️ only starts a slideshow (Presentation Studio, as before).
        used = set(defaults("browse"))
        for gesture in OTHER_BUILT_IN_GESTURES:
            self.assertNotIn(gesture, used)

    def test_the_wake_sign_does_nothing_else_once_awake(self):
        # ✋ wakes Wield in hands-free mode, so Browse & Media mustn't use it.
        self.assertNotIn("✋ Open Palm", defaults("browse"))


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class HomeCardTests(unittest.TestCase):

    def test_home_shows_the_six(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import tempfile
        os.environ.setdefault("WIELD_DATA_DIR", tempfile.mkdtemp())
        app = QApplication.instance() or QApplication([])
        from frontend.pages.home import HomePage
        page = HomePage()
        self.assertEqual(len(page.hand_sign_tiles), 6)
        self.assertIn("Go / play", page.hand_sign_tiles[1].accessibleName())
        page.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
