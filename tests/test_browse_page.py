import os
import tempfile
import unittest
from unittest import mock

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class BrowsePageTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"WIELD_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        from frontend.pages.browse_page import BrowsePage
        self.page = BrowsePage()

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_four_sections_cover_every_action_once(self):
        from backend.automation import browse_media
        self.assertEqual(list(self.page.editors), ["scroll", "video", "music", "tabs"])
        shown = [a for e in self.page.editors.values() for a in e.rows]
        self.assertEqual(sorted(shown), sorted(browse_media.ACTIONS))

    def test_scroll_section_has_voice_motion_and_pose(self):
        rows = self.page.editors["scroll"].rows
        self.assertIn("✌️ Peace", rows["browse_scroll"].triggers)
        self.assertIn("🎤 scroll down", rows["browse_scroll_down"].triggers)
        self.assertIn("Swipe up", rows["browse_scroll_up"].triggers)

    def test_moving_a_trigger_between_sections_updates_both(self):
        changes = []
        self.page.bindings_changed.connect(lambda: changes.append(1))
        self.page.editors["music"].assign("👍 Thumbs Up", "browse_media_play_pause")
        self.assertIn("👍 Thumbs Up", self.page.editors["music"].rows["browse_media_play_pause"].triggers)
        self.assertNotIn("👍 Thumbs Up",
                         self.page.editors["video"].rows["browse_video_play_pause"].triggers)
        self.assertTrue(changes)


if __name__ == "__main__":
    unittest.main()
