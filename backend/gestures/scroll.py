"""
Scrolling by holding a pose (by default ✌️ two fingers) and moving the hand
up or down, like a joystick:

- When the pose starts, the hand's height is the "centre".
- Move the hand above it to scroll up, below it to scroll down; back to the
  centre (a small dead zone) to stop. Holding keeps scrolling.
- With "hand height sets speed" on, the further from the centre, the
  faster; off, any height outside the dead zone scrolls at one steady speed.

    scroller = ScrollController(speed="medium", height_sets_speed=True)
    wheel = scroller.update(active=True, y=0.42, now=t)   # wheel units this frame

The hand height goes through the same One-Euro filter as the fog writing
(backend/fog.py), so tracking jitter doesn't make the page shudder.
Wheel units are Windows' (120 = one notch); positive scrolls up.
"""

from backend.fog import OneEuroFilter
from backend.automation.controllers.desktop_input import WHEEL_DELTA


SPEEDS = {"slow": 0.6, "medium": 1.0, "fast": 1.7}
DEFAULT_SPEED = "medium"

DEAD_ZONE = 0.035        # of the image height: small wobbles don't scroll
FULL_SPEED_AT = 0.22     # this far from the centre = full speed
MIN_NOTCHES_PER_SECOND = 2.0
MAX_NOTCHES_PER_SECOND = 22.0
STEADY_NOTCHES_PER_SECOND = 8.0
MIN_SEND = 20            # don't send tiny wheel events (some apps ignore them)


class ScrollController:

    def __init__(self, speed=DEFAULT_SPEED, height_sets_speed=True):
        self.speed = SPEEDS.get(speed, 1.0)
        self.height_sets_speed = height_sets_speed
        self._filter = OneEuroFilter(min_cutoff=0.8, beta=2.0)
        self.reset()

    def reset(self):
        self.active = False
        self.centre = None
        self._last_t = None
        self._pending = 0.0
        self._filter.reset()

    def rate(self, offset):
        """Notches per second for an offset (centre - hand y; + is up)."""

        distance = abs(offset) - DEAD_ZONE
        if distance <= 0:
            return 0.0

        if self.height_sets_speed:
            amount = min(distance / (FULL_SPEED_AT - DEAD_ZONE), 1.0)
            rate = MIN_NOTCHES_PER_SECOND + amount * (MAX_NOTCHES_PER_SECOND - MIN_NOTCHES_PER_SECOND)
        else:
            rate = STEADY_NOTCHES_PER_SECOND

        rate *= self.speed
        return rate if offset > 0 else -rate

    def update(self, active, y, now):
        """
        One camera frame. `active`: the scroll pose is held; `y`: hand
        height in 0..1 image coordinates (0 = top). Returns the wheel
        amount to send now (0 = nothing).
        """

        if not active or y is None:
            if self.active:
                self.reset()
            return 0

        y = self._filter(y, now)

        if not self.active:
            self.active = True
            self.centre = y
            self._last_t = now
            return 0

        dt = max(0.0, min(now - self._last_t, 0.2))   # a stalled frame doesn't jump
        self._last_t = now

        self._pending += self.rate(self.centre - y) * WHEEL_DELTA * dt

        if abs(self._pending) < MIN_SEND:
            return 0

        amount = int(self._pending)
        self._pending -= amount
        return amount

    @property
    def direction(self):
        """'up', 'down' or None, for the status line."""
        if not self.active or self.centre is None or self._filter._x is None:
            return None
        offset = self.centre - self._filter._x
        if abs(offset) <= DEAD_ZONE:
            return None
        return "up" if offset > 0 else "down"
