"""The hand mouse: pointer, pinch clicks, drags, right-click and leaving."""

import unittest

from backend.automation.controllers.desktop_input import DesktopInput
from backend.gestures.hand_mouse import (
    EXIT_FIST_SECONDS,
    FREEZE_SECONDS,
    HandMouse,
    to_screen,
)


def hand(cx=0.5, cy=0.4, pinch=False, right=False, fist=False):
    """Synthetic image landmarks around (cx, cy); a hand ~0.2 tall."""
    pts = [(cx, cy + 0.2)] + [(cx, cy + 0.1)] * 20
    fingers = {"index": (-0.06, 5, 6, 7, 8), "middle": (-0.02, 9, 10, 11, 12),
               "ring": (0.02, 13, 14, 15, 16), "pinky": (0.06, 17, 18, 19, 20)}
    for name, (dx, mcp, pip, dip, tip) in fingers.items():
        x = cx + dx
        pts[mcp] = (x, cy + 0.1)
        pts[pip] = (x, cy + 0.0)
        if fist:
            pts[dip], pts[tip] = (x, cy + 0.05), (x, cy + 0.08)
        else:
            pts[dip], pts[tip] = (x, cy - 0.05), (x, cy - 0.1)
    thumb = (cx - 0.12, cy)
    if pinch:
        thumb = pts[8]
    elif right:
        thumb = pts[12]
    elif fist:
        thumb = (cx + 0.02, cy + 0.03)
    pts[4] = thumb
    return [(x, y, 0.0) for x, y in pts]


class HandMouseTests(unittest.TestCase):

    def frames(self, mouse, hands, start=0.0, fps=30):
        ops = []
        for i, h in enumerate(hands):
            ops += mouse.update(h, start + i / fps)
        return ops

    def test_region_maps_to_the_whole_screen(self):
        self.assertEqual(to_screen(0.0, 0.0), (0.0, 0.0))
        self.assertEqual(to_screen(1.0, 1.0), (1.0, 1.0))
        x, y = to_screen(0.5, 0.4)
        self.assertAlmostEqual(x, 0.5)

    def test_moving_the_hand_moves_the_pointer(self):
        ops = self.frames(HandMouse(), [hand(0.3 + i * 0.01, 0.4) for i in range(30)])
        moves = [op for op in ops if op[0] == "move"]
        self.assertGreater(len(moves), 5)
        self.assertGreater(moves[-1][1], moves[0][1])
        self.assertFalse(any(op[0] != "move" for op in ops))

    def test_a_still_hand_sends_nothing_new(self):
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 30)
        self.assertEqual(self.frames(mouse, [hand()] * 10, start=1.0), [])

    def test_quick_pinch_is_a_click_and_the_pointer_stays_put(self):
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 20)
        # Pinch while the hand drifts a little: the pointer shouldn't follow.
        ops = self.frames(mouse, [hand(0.5 + i * 0.004, pinch=True) for i in range(5)], start=1.0)
        self.assertEqual(ops[0], ("left_down",))
        self.assertFalse(any(op[0] == "move" for op in ops))
        ops = self.frames(mouse, [hand()] * 2, start=1.2)
        self.assertIn(("left_up",), ops)

    def test_pinch_and_move_drags(self):
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 10)
        ops = self.frames(mouse, [hand(0.5 + i * 0.01, pinch=True) for i in range(30)], start=1.0)
        self.assertEqual(ops[0], ("left_down",))
        moves_after_freeze = [op for op in ops if op[0] == "move"]
        self.assertTrue(moves_after_freeze)
        self.assertNotIn(("left_up",), ops)                  # still holding
        self.assertGreater(30 / 30, FREEZE_SECONDS)

    def test_right_click_once_per_pinch(self):
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 5)
        ops = self.frames(mouse, [hand(right=True)] * 10, start=1.0)
        self.assertEqual(ops.count(("right_click",)), 1)

    def test_losing_the_hand_releases_the_button(self):
        mouse = HandMouse()
        self.frames(mouse, [hand(pinch=True)] * 3)
        self.assertEqual(mouse.update(None, 1.0), [("left_up",)])
        self.assertEqual(mouse.update(None, 1.1), [])

    def test_holding_a_fist_leaves_mouse_mode(self):
        mouse = HandMouse()
        frames = int(EXIT_FIST_SECONDS * 30) + 3
        ops = self.frames(mouse, [hand(fist=True)] * frames)
        self.assertIn(("exit",), ops)


class MouseInputTests(unittest.TestCase):

    def test_clicks_and_moves(self):
        calls = []

        class Api:
            def send_move(self, x, y):
                calls.append(("move", x, y))

            def send_button(self, button, down):
                calls.append((button, down))

        inp = DesktopInput(Api())
        inp.move_to(0.25, 0.75)
        inp.click("right")
        inp.click("left", double=True)
        self.assertEqual(calls, [
            ("move", 0.25, 0.75),
            ("right", True), ("right", False),
            ("left", True), ("left", False), ("left", True), ("left", False),
        ])
        with self.assertRaises(ValueError):
            inp.button("middle", True)

    def test_voice_clicks_through_the_controller(self):
        from backend.automation.browse_media import BrowseMediaController
        calls = []

        class Api:
            def send_button(self, button, down):
                calls.append((button, down))

        c = BrowseMediaController(DesktopInput(Api()))
        c.execute("right")
        c.execute("double")
        self.assertEqual(calls[0:2], [("right", True), ("right", False)])
        self.assertEqual(len(calls), 6)


if __name__ == "__main__":
    unittest.main()
