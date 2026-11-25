"""Hands-free mode: wake gesture, studios that follow the app in front."""

import os
import tempfile
import unittest
from unittest import mock

from backend.camera import claims

try:
    import cv2  # noqa: F401
    import PySide6  # noqa: F401
    HAVE_WORKER = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_WORKER = False


class ClaimTests(unittest.TestCase):

    def test_take_and_give_back(self):
        seen = []
        claims.subscribe(seen.append)
        owner = object()
        claims.take(owner)
        self.assertTrue(claims.in_use())
        claims.give_back(owner)
        claims.give_back(owner)            # twice is harmless
        self.assertFalse(claims.in_use())
        self.assertEqual(seen[-2:], [True, False])


class StudioChoiceTests(unittest.TestCase):

    def test_powerpoint_gets_presentation_everything_else_browse(self):
        if not HAVE_WORKER:
            self.skipTest("cv2 / PySide6 not installed")
        from backend.gestures.gesture_worker import studio_for_app
        self.assertEqual(studio_for_app("POWERPNT.EXE"), "presentation")
        for app in ("chrome.exe", "winword.exe", "", None):
            self.assertEqual(studio_for_app(app), "browse")


@unittest.skipUnless(HAVE_WORKER, "cv2 / PySide6 not installed")
class AutoWorkerTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"WIELD_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

        from backend.gestures.gesture_worker import GestureWorker
        self.app = "chrome.exe"
        self.worker = GestureWorker("auto", foreground=lambda: self.app)
        self.ran = []
        self.studios = []
        self.worker.custom_event_detected.connect(lambda e: self.ran.append(e["name"]))
        self.worker.studio_changed.connect(self.studios.append)

    def test_needs_waking_and_sleeps_again(self):
        w = self.worker
        self.assertTrue(w.require_arm)
        self.assertEqual(w.arm_timeout, 30)
        w._check_studio(0.0)
        w._trigger("👍 Thumbs Up")                 # asleep: nothing runs
        self.assertEqual(self.ran, [])
        w._trigger(w.arm_gesture)                  # wake
        self.assertTrue(w.armed)
        w._trigger("👍 Thumbs Up")
        self.assertEqual(self.ran, ["Play / pause video"])
        w._armed_until = 0                         # time passes
        w._check_arm_timeout()
        self.assertFalse(w.armed)

    def test_gestures_follow_the_app_in_front(self):
        w = self.worker
        w._check_studio(0.0)
        self.assertEqual(self.studios, ["browse"])
        self.assertIn("✌️ Peace", w.scroll_poses)

        self.app = "POWERPNT.EXE"
        w._check_studio(0.1)                       # too soon: no change
        w._check_studio(1.0)
        self.assertEqual(self.studios, ["browse", "presentation"])
        w._set_armed(True)
        w._trigger("👍 Thumbs Up")
        self.assertEqual(self.ran, ["Next slide"])
        self.assertEqual(w.scroll_poses, {})

    def test_voice_covers_both_studios_and_wake_words(self):
        phrases = {e["gesture"] for e in self.worker.voice_events}
        self.assertIn("🎤 next slide", phrases)
        self.assertIn("🎤 scroll down", phrases)
        self.assertIn("🎤 wake up", phrases)
        self.assertIn("🎤 go to sleep", phrases)


if __name__ == "__main__":
    unittest.main()
