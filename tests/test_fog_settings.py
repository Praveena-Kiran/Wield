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


    @unittest.skipUnless(HAVE_QT, "PySide6 not installed")
    def test_jump_then_off_the_edge_does_not_crash(self):
        # A friend's report: the finger jumped (tracking glitch) and the
        # fresh start point was off the edge -> drawLine(None, None).
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QPointF
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from frontend.components import fog_window
        from frontend.components.fog_window import FogWindow

        window = FogWindow()
        try:
            points = iter([QPointF(10, 10), QPointF(400, 300), None])   # pen down on frame 2
            window._to_mask = lambda p: next(points)

            class Passthrough:
                def __call__(self, p, now):
                    return p

                def reset(self):
                    pass

            window._smoother = Passthrough()
            with mock.patch.object(fog_window, "hand_mode", lambda lm: "write"), \
                    mock.patch.object(fog_window, "fingertip", lambda lm: (0.5, 0.5)):
                for i in range(3):
                    window.handle_hand(object(), now=i * 0.05)    # pen down, a line, a jump
            self.assertEqual(window._stroke, [])                   # nothing drawn off the edge
            window._add_point(None)                                # and never with no point
        finally:
            window.deleteLater()

if __name__ == "__main__":
    unittest.main()
