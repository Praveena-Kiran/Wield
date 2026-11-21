import os
import tempfile
import unittest
from unittest import mock

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:  # CI's unit-test job installs only the standard library
    HAVE_QT = False


class FogSettingsTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"WIELD_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_defaults_and_bad_values(self):
        from backend.settings import gesture_settings as G
        self.assertEqual(G.load()["fog_colour"], "white")
        G.save("fog_colour", "black")
        self.assertEqual(G.load()["fog_colour"], "black")
        G.save("fog_colour", "purple")
        self.assertEqual(G.load()["fog_colour"], "white")

    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_window_uses_contrasting_ink(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from backend.settings import gesture_settings as G
        from frontend.components.fog_window import FogWindow

        window = FogWindow()
        try:
            light_ink = window.style["ink"].lightness()
            G.save("fog_colour", "black")
            window.apply_settings()
            self.assertEqual(window.fog_colour, "black")
            self.assertGreater(window.style["ink"].lightness(), light_ink)
            self.assertLess(window.style["fog"].lightness(), 60)

            medium = window.stroke_width
            G.save("fog_stroke", "thick")
            window.apply_settings()
            self.assertGreater(window.stroke_width, medium)
            G.save("fog_stroke", "huge")
            window.apply_settings()
            self.assertEqual(window.stroke, "medium")
        finally:
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
