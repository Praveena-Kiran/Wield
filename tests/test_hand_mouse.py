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

    def test_starts_in_the_middle_wherever_your_hand_is(self):
        from backend.gestures.hand_mouse import centred_region
        for x, y in ((0.3, 0.6), (0.7, 0.3)):
            mouse = HandMouse()
            ops = mouse.update(hand(x, y), 0.0)
            move = [op for op in ops if op[0] == "move"][0]
            self.assertAlmostEqual(move[1], 0.5, delta=0.05)
            self.assertAlmostEqual(move[2], 0.5, delta=0.05)
        # Near the camera's edge the area stays inside the picture.
        x0, y0, x1, y1 = centred_region(0.02, 0.98)
        self.assertGreaterEqual(x0, 0.0)
        self.assertLessEqual(y1, 1.0)

    def test_short_reach_needs_less_movement(self):
        from backend.gestures.hand_mouse import REACH
        self.assertLess(REACH["short"][0], REACH["medium"][0])
        self.assertLess(REACH["medium"][0], REACH["long"][0])
        def across(reach):
            mouse = HandMouse(reach=reach)
            mouse.update(hand(0.5, 0.5), 0.0)
            ops = self.frames(mouse, [hand(0.5 + 0.1, 0.5)] * 30, start=0.1)
            return [op for op in ops if op[0] == "move"][-1][1]
        self.assertGreater(across("short"), across("long"))

    def test_past_the_edge_the_area_follows(self):
        from backend.gestures.hand_mouse import follow
        region = (0.3, 0.3, 0.6, 0.6)
        self.assertEqual(follow(region, 0.4, 0.4), region)
        moved = follow(region, 0.7, 0.4)                  # 0.1 past the right edge
        self.assertAlmostEqual(moved[2], 0.7)
        self.assertAlmostEqual(moved[2] - moved[0], 0.3)  # same size
        # ...so coming back left moves the pointer straight away.
        mouse = HandMouse(reach="short")
        mouse.update(hand(0.5, 0.5), 0.0)
        self.frames(mouse, [hand(0.9, 0.5)] * 20, start=0.1)
        ops = self.frames(mouse, [hand(0.85, 0.5)] * 20, start=1.0)
        self.assertLess([op for op in ops if op[0] == "move"][-1][1], 0.95)

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

    def test_one_pinch_is_one_click_and_the_pointer_stays_put(self):
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 20)
        # Pinch while the hand drifts a little: the pointer shouldn't follow.
        ops = self.frames(mouse, [hand(0.5 + i * 0.004, pinch=True) for i in range(15)], start=1.0)
        self.assertEqual(ops.count(("click",)), 1)           # held: still one click
        self.assertFalse(any(op[0] == "move" for op in ops))
        self.assertNotIn(("left_down",), ops)                # no accidental drags
        self.frames(mouse, [hand()] * 5, start=1.6)          # let go...
        ops = self.frames(mouse, [hand(pinch=True)] * 3, start=2.0)
        self.assertEqual(ops.count(("click",)), 1)           # ...and pinch again: a second click

    def test_pointer_holds_still_while_fingers_close(self):
        from backend.gestures.hand_mouse import AIM_LOCK
        self.assertGreater(AIM_LOCK, 0.28)                   # before the pinch counts

    def test_right_click_once_per_pinch(self):
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 5)
        ops = self.frames(mouse, [hand(right=True)] * 10, start=1.0)
        self.assertEqual(ops.count(("right_click",)), 1)

    def test_losing_the_hand_is_quiet_and_never_holds_a_button(self):
        mouse = HandMouse()
        self.frames(mouse, [hand(pinch=True)] * 3)
        self.assertEqual(mouse.update(None, 1.0), [])
        self.assertFalse(mouse.left_down)

    def test_thumbs_scroll_and_the_pointer_stays_put(self):
        from tests.test_pointing import thumbs
        mouse = HandMouse()
        self.frames(mouse, [hand()] * 10)
        down = self.frames(mouse, [thumbs("down")] * 20, start=1.0)
        self.assertIn(("scroll", "down"), down)
        self.assertFalse(any(op[0] in ("move", "click", "exit") for op in down))
        up = self.frames(mouse, [thumbs("up")] * 40, start=2.0)   # held > a fist's second
        self.assertIn(("scroll", "up"), up)
        self.assertNotIn(("exit",), up)                           # a thumbs-up isn't a fist
        # MediaPipe's own label works too.
        mouse2 = HandMouse()
        ops = self.frames_with(mouse2, [hand()] * 15, "👍 Thumbs Up")
        self.assertIn(("scroll", "up"), ops)
        # A quick pass through the pose doesn't scroll.
        self.assertNotIn(("scroll", "down"), self.frames(HandMouse(), [thumbs("down")] * 3))

    def test_pointing_moves_the_pointer_and_never_scrolls(self):
        from tests.test_pointing import hand as pointing_hand
        mouse = HandMouse()
        ops = []
        for i in range(30):
            pts = [(x + i * 0.004, y) for x, y in pointing_hand("up")]
            ops += mouse.update(pts, i / 30)
        self.assertFalse(any(op[0] == "scroll" for op in ops))
        moves = [op for op in ops if op[0] == "move"]
        self.assertGreater(moves[-1][1], moves[0][1])

    def frames_with(self, mouse, hands, gesture, start=0.0, fps=30):
        ops = []
        for i, h in enumerate(hands):
            ops += mouse.update(h, start + i / fps, gesture)
        return ops

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
