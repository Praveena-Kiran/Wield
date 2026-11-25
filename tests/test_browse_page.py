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

    def test_sections_cover_every_action_once(self):
        from backend.automation import browse_media
        self.assertEqual(list(self.page.editors), [s[0] for s in browse_media.SECTIONS])
        shown = [a for e in self.page.editors.values() for a in e.rows]
        self.assertEqual(sorted(shown), sorted(browse_media.ACTIONS))

    def test_scroll_section_has_voice_motion_and_pose(self):
        rows = self.page.editors["scroll"].rows
        self.assertIn("✌️ Peace", rows["browse_scroll"].triggers)
        self.assertIn("🎤 scroll down", rows["browse_scroll_down"].triggers)
        self.assertIn("Swipe up", rows["browse_scroll_up"].triggers)

    def _scrolled_to(self, editor, action):
        from PySide6.QtWidgets import QPushButton, QScrollArea
        self.page.resize(1060, 700)
        self.page.show()
        key = next(k for k, e in self.page.editors.items() if e is editor)
        self.page.toggle_section(key)
        self.app.processEvents()
        area = [a for a in self.page.findChildren(QScrollArea) if a.objectName() == "ContentScroll"][0]
        add = editor.rows[action].findChild(QPushButton, "AddTrigger")
        area.ensureWidgetVisible(add)
        self.app.processEvents()
        add.setFocus()
        self.app.processEvents()
        return area.verticalScrollBar()

    def test_adding_a_trigger_does_not_move_the_page(self):
        editor = self.page.editors["tabs"]
        bar = self._scrolled_to(editor, "browse_page_forward")
        before = bar.value()
        self.assertGreater(before, 0)
        editor.assign("Swipe up", "browse_page_forward")
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(bar.value(), before)

    def test_removing_a_trigger_does_not_move_the_page(self):
        editor = self.page.editors["tabs"]
        bar = self._scrolled_to(editor, "browse_tab_next")
        before = bar.value()
        editor.remove_trigger("☝️ Pointing Up")
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(bar.value(), before)

    def test_sections_start_closed_and_open_one_at_a_time(self):
        bodies = {k: v[1] for k, v in self.page.sections.items()}
        self.page.show()
        self.assertFalse(any(b.isVisible() for b in bodies.values()))
        self.page.toggle_section("video")
        self.assertTrue(bodies["video"].isVisible())
        self.page.toggle_section("music")
        self.assertTrue(bodies["music"].isVisible())
        self.assertFalse(bodies["video"].isVisible())
        self.page.toggle_section("music")
        self.assertFalse(bodies["music"].isVisible())

    def test_summaries_say_what_each_section_does(self):
        summary = self.page.sections["video"][3].text()
        self.assertIn("👍 play / pause video", summary)
        self.page.editors["video"].assign("☝️ Pointing Up", "browse_video_fullscreen")
        self.assertIn("☝️", self.page.sections["video"][3].text())

    def test_empty_actions_are_tucked_away(self):
        editor = self.page.editors["video"]
        self.page.show()
        self.page.toggle_section("video")
        self.assertFalse(editor.rows["browse_video_back_5"].isVisible())   # nothing assigned
        self.assertTrue(editor.rows["browse_video_back"].isVisible())
        self.assertIn("2 more", editor.more_button.text())
        editor.more_button.click()
        self.app.processEvents()
        self.assertTrue(editor.rows["browse_video_back_5"].isVisible())

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
