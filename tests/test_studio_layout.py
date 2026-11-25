"""The studios' shared pieces: sections that open and close, and toasts."""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("WIELD_DATA_DIR", tempfile.mkdtemp())

try:
    from PySide6.QtWidgets import QApplication, QWidget
except ImportError:  # CI's tests job has no Qt
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class CollapsibleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_accordion_keeps_one_section_open(self):
        from frontend.components.collapsible import Accordion, CollapsibleSection
        accordion = Accordion()
        a = accordion.add("a", CollapsibleSection("A", "1", "first"))
        b = accordion.add("b", CollapsibleSection("B", "2"))
        self.assertFalse(a.is_open() or b.is_open())

        accordion.toggle("a")
        self.assertTrue(a.is_open())
        b.head.click()                       # clicking the header works too
        self.assertTrue(b.is_open())
        self.assertFalse(a.is_open())
        self.assertEqual(accordion.open_key(), "b")
        accordion.toggle("b")
        self.assertIsNone(accordion.open_key())
        self.assertEqual(a.summary.text(), "first")


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class ToastTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_one_toast_per_window_replaced_by_the_next(self):
        from frontend.components.toast import toast
        window = QWidget()
        window.resize(800, 600)
        child = QWidget(window)
        window.show()
        first = toast(child, "Saved.")
        second = toast(window, "Couldn't save.", "error")
        self.assertIs(first, second)
        self.assertEqual(second.text.text(), "Couldn't save.")
        self.assertTrue(second.isVisible())
        # At the bottom, in the middle.
        self.assertGreater(second.y(), 600 // 2)
        self.assertIsNone(toast(child, ""))

    def test_studio_pages_notify_instead_of_a_status_line(self):
        from frontend.pages.studio_page import StudioPage
        page = StudioPage("T", "S")
        page.show()
        self.assertTrue(page.status_label.isHidden())
        page.notify("Saved.")
        self.assertTrue(page._wield_toast.isVisible())


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class GestureStudioTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sections_open_one_at_a_time_and_say_what_is_there(self):
        from frontend.pages.gesture_page import GesturePage
        page = GesturePage()
        self.assertIn("None yet", page.section_frames["gesture"].summary.text())
        page.toggle_section("gesture")
        page.toggle_section("motion")
        self.assertFalse(page.section_frames["gesture"].is_open())
        self.assertTrue(page.section_frames["motion"].is_open())


if __name__ == "__main__":
    unittest.main()
