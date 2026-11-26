"""The hand mouse glides between camera frames instead of hopping."""

import unittest

from backend.gestures.pointer_glide import PointerGlide


def run(glide, seconds, start=0.0, hz=120):
    positions = []
    for i in range(int(seconds * hz)):
        p = glide.step(start + i / hz)
        if p is not None:
            positions.append(p)
    return positions


class GlideTests(unittest.TestCase):

    def test_first_position_is_immediate(self):
        g = PointerGlide()
        g.aim(0.3, 0.4)
        self.assertEqual(g.step(0.0), (0.3, 0.4))      # sent straight away
        self.assertIsNone(g.step(0.01))

    def test_moves_in_many_small_steps_and_arrives(self):
        g = PointerGlide()
        g.aim(0.0, 0.0)
        g.step(0.0)
        g.aim(0.4, 0.0)                         # one camera frame's jump
        positions = run(g, 0.45, start=0.0)
        xs = [x for x, _ in positions]
        self.assertGreater(len(xs), 10)          # lots of small moves, not one hop
        self.assertEqual(xs, sorted(xs))         # always forwards, no overshoot
        self.assertLess(max(b - a for a, b in zip(xs, xs[1:])), 0.1)
        self.assertAlmostEqual(xs[-1], 0.4, places=3)

    def test_quick_to_follow(self):
        g = PointerGlide()
        g.aim(0.0, 0.0)
        g.step(0.0)
        g.aim(1.0, 0.0)
        run(g, 0.15)                             # 150 ms later: nearly there
        self.assertGreater(g.current[0], 0.9)

    def test_still_hand_sends_nothing(self):
        g = PointerGlide()
        g.aim(0.5, 0.5)
        run(g, 0.2)
        self.assertEqual(run(g, 0.2, start=1.0), [])

    def test_settle_jumps_to_where_you_aimed(self):
        g = PointerGlide()
        g.aim(0.0, 0.0)
        g.step(0.0)
        g.aim(0.6, 0.2)
        g.step(0.01)
        self.assertEqual(g.settle(), (0.6, 0.2))

    def test_a_pause_does_not_leap(self):
        g = PointerGlide()
        g.aim(0.0, 0.0)
        g.step(0.0)
        g.aim(1.0, 0.0)
        g.step(5.0)                              # the timer stalled for seconds
        self.assertLess(g.current[0], 0.9)


if __name__ == "__main__":
    unittest.main()
