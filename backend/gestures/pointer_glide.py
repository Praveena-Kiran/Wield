"""
Makes the hand mouse glide instead of hop.

The camera gives a new hand position only 24-30 times a second, so moving
the pointer straight there jumps from spot to spot. Instead the hand sets
a target, and a fast timer (about 120 times a second) eases the pointer
towards it: smooth, and only a few hundredths of a second behind.

    glide = PointerGlide()
    glide.aim(x, y)                 # new hand position (0..1 of the screen)
    pos = glide.step(now)           # where the pointer goes now, or None
"""

import math

# How quickly the pointer catches up: after TIME_CONSTANT seconds it has
# gone about 63% of the way, after 3x that 95%.
TIME_CONSTANT = 0.035
# Close enough: snap to the target (and stop sending moves).
SNAP = 0.0004
MAX_STEP_SECONDS = 0.05      # after a pause, don't leap in one go


class PointerGlide:

    def __init__(self, time_constant=TIME_CONSTANT):
        self.time_constant = time_constant
        self.reset()

    def reset(self):
        self.current = None
        self.target = None
        self._last = None
        self._jump = False           # the first position still to be sent

    def aim(self, x, y):
        self.target = (x, y)
        if self.current is None:            # first position: go straight there
            self.current = (x, y)
            self._jump = True

    def step(self, now):
        """Move towards the target. Returns the new (x, y), or None if
        there's nothing to do (no target, or already there)."""

        if self.target is None or self.current is None:
            self._last = now
            return None

        dt = 0.0 if self._last is None else min(max(now - self._last, 0.0), MAX_STEP_SECONDS)
        self._last = now

        if self._jump:
            self._jump = False
            return self.current

        (cx, cy), (tx, ty) = self.current, self.target
        if abs(tx - cx) + abs(ty - cy) <= SNAP:
            if self.current == self.target:
                return None
            self.current = self.target
            return self.current

        follow = 1.0 - math.exp(-dt / self.time_constant) if dt > 0 else 0.0
        if follow <= 0:
            return None
        self.current = (cx + (tx - cx) * follow, cy + (ty - cy) * follow)
        return self.current

    def settle(self):
        """Jump to the target now (before a click, so it lands where aimed)."""
        if self.target is not None:
            self.current = self.target
        return self.current
