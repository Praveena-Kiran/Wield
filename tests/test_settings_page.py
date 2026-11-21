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
class SettingsPageTests(unittest.TestCase):

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
        from frontend.pages.settings_page import SettingsPage
        self.page = SettingsPage()
        self.page.resize(900, 2400)
        self.page.show()
        self.app.processEvents()

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_every_visible_dropdown_has_options_and_works(self):
        from PySide6.QtWidgets import QComboBox
        self.page.require_arm.setChecked(True)
        self.app.processEvents()
        combos = [c for c in self.page.findChildren(QComboBox) if c.isVisible()]
        self.assertTrue(combos)
        for combo in combos:
            with self.subTest(combo=combo.accessibleName()):
                self.assertGreater(combo.count(), 0)
                self.assertTrue(combo.isEnabled())

    def test_activation_options_only_show_when_switched_on(self):
        self.assertFalse(self.page.arm_gesture_row.isVisible())
        self.page.require_arm.setChecked(True)
        self.assertTrue(self.page.arm_gesture_row.isVisible())
        self.assertTrue(self.page.arm_timeout_row.isVisible())

    def test_choice_pills_save(self):
        from backend.settings import gesture_settings
        buttons = self.page.hold_time.group.buttons()
        buttons[2].click()
        self.assertEqual(gesture_settings.load()["hold_time"], buttons[2].property("choice"))
        self.page.fog_stroke.group.buttons()[2].click()
        self.assertEqual(gesture_settings.load()["fog_stroke"], "thick")


if __name__ == "__main__":
    unittest.main()
