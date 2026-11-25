import os
import tempfile
import unittest
from unittest import mock

from backend import cheat_sheet

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_QT = False


class SheetTests(unittest.TestCase):

    def test_groups_by_section_with_gestures_first(self):
        gesture_map = {
            "🎤 scroll down": "browse_scroll_down",
            "Swipe down": "browse_scroll_down",
            "👍 Thumbs Up": "browse_video_play_pause",
        }
        sections = cheat_sheet.sheet(gesture_map, cheat_sheet.BROWSE_SECTIONS, wake=True)
        titles = [title for title, _ in sections]
        self.assertEqual(titles, ["Scroll & zoom", "Videos"])     # empty ones left out
        rows = dict(sections[0][1])
        self.assertEqual(rows["Scroll down"], ["Swipe down", "“Hey Wield, scroll down”"])

    def test_phrases_without_wake_word(self):
        self.assertEqual(cheat_sheet.label("🎤 next slide", wake=False), "“next slide”")
        self.assertEqual(cheat_sheet.label("✋ Open Palm"), "✋ Open Palm")

    def test_presentation_and_custom(self):
        sections = cheat_sheet.sheet({"👍 Thumbs Up": "presentation_next"},
                                     cheat_sheet.PRESENTATION_SECTIONS)
        self.assertEqual(sections, [("Slides", [("Next slide", ["👍 Thumbs Up"])])])
        custom = cheat_sheet.sheet_for_events(
            [{"name": "Open notes", "gesture": "☝️ Pointing Up"}, {"name": "No trigger"}],
            "Study Studio")
        self.assertEqual(custom, [("Study Studio", [("Open notes", ["☝️ Pointing Up"])])])

    def test_help_phrases_are_valid(self):
        from backend.voice.commands import check_phrase, phrase_of
        for event in cheat_sheet.HELP_EVENTS:
            self.assertTrue(check_phrase(phrase_of(event["gesture"]))[0], event["gesture"])


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class CheatSheetWidgetTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_toggle_shows_then_hides(self):
        from frontend.components.cheat_sheet import CheatSheet
        sheet = CheatSheet()
        try:
            sheet.toggle("What you can do", [("Videos", [("Play", ["👍 Thumbs Up"])])], "note")
            self.assertTrue(sheet.isVisible())
            sheet.toggle("What you can do", [], "")
            self.assertFalse(sheet.isVisible())

            sheet.toggle("What you can do", [], "")
            sheet.close_button.click()                      # the ✕ button
            self.assertFalse(sheet.isVisible())

            from PySide6.QtCore import QPoint, Qt
            from PySide6.QtTest import QTest
            sheet.toggle("What you can do", [], "")
            QTest.mouseClick(sheet, Qt.LeftButton, pos=QPoint(40, 40))   # anywhere
            self.assertFalse(sheet.isVisible())
        finally:
            sheet.deleteLater()


if __name__ == "__main__":
    unittest.main()
