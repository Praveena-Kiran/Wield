import os
import tempfile
import unittest
from unittest import mock

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_QT = False


class FakeSettings:
    def __init__(self, seen=None):
        self.values = {"tour_seen_version": seen} if seen else {}

    def get_setting(self, key):
        return self.values.get(key)

    def set_setting(self, key, value):
        self.values[key] = value


class WhatsNewTests(unittest.TestCase):

    def test_tour_after_install_and_after_every_update(self):
        from backend import whats_new
        from backend.app_info import VERSION
        self.assertEqual(whats_new.tour_due(FakeSettings()), "first")
        self.assertEqual(whats_new.tour_due(FakeSettings("1.0.0")), "update")
        settings = FakeSettings("1.0.0")
        whats_new.mark_seen(settings)
        self.assertEqual(settings.values["tour_seen_version"], VERSION)
        self.assertIsNone(whats_new.tour_due(settings))

    def test_this_version_has_notes(self):
        from backend import whats_new
        self.assertTrue(whats_new.notes())


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class TourWidgetTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
        from frontend.components import tour as tour_module
        tour_module.SETTLE_MS = 0
        self.window = QWidget()
        self.window.resize(900, 600)
        layout = QVBoxLayout(self.window)
        self.button = QPushButton("Target")
        layout.addWidget(self.button)
        self.window.show()
        self.app.processEvents()
        self.prepared = []

        from frontend.components.tour import Tour, TourStep
        self.tour = Tour(self.window, [
            TourStep("Welcome", "Hi", prepare=lambda: self.prepared.append(0)),
            TourStep("A button", "This one", target=lambda: self.button,
                     prepare=lambda: self.prepared.append(1)),
            TourStep("Done", "Bye"),
        ])
        self.results = []
        self.tour.finished.connect(self.results.append)

    def tearDown(self):
        self.window.deleteLater()
        self.app.processEvents()

    def settle(self):
        for _ in range(3):
            self.app.processEvents()

    def test_steps_light_up_their_target(self):
        self.tour.start()
        self.settle()
        self.assertIsNone(self.tour.hole)                # the welcome is centred
        self.tour.next()
        self.settle()
        self.assertTrue(self.tour.hole.contains(self.button.geometry().center()))
        self.assertEqual(self.tour.card.title.text(), "A button")
        self.assertEqual(self.prepared, [0, 1])

    def test_back_next_and_done(self):
        self.tour.start()
        self.settle()
        self.assertFalse(self.tour.card.back.isVisible())
        self.tour.next(); self.settle()
        self.tour.back(); self.settle()
        self.assertEqual(self.tour.index, 0)
        self.tour.next(); self.tour.next(); self.settle()
        self.assertEqual(self.tour.card.next.text(), "Done")
        self.tour.next()
        self.assertEqual(self.results, [True])

    def test_escape_skips(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.tour.start()
        self.settle()
        QTest.keyClick(self.tour, Qt.Key_Escape)
        self.assertEqual(self.results, [False])


if __name__ == "__main__":
    unittest.main()
