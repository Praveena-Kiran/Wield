"""
Scrolling by holding a pose (any you pick, e.g. ✌️ two fingers) and moving the hand
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

Or point the way to go (☝️ up / 👇 down): while the pose is held the page
scrolls that way at a steady speed, a little faster the longer you hold:

    wheel = scroller.update(active=True, y=None, now=t, direction="down")
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

# Pointing: steady speed, rising to POINT_BOOST x after holding a while.
POINT_NOTCHES_PER_SECOND = 7.0
POINT_BOOST = 2.2
POINT_BOOST_AFTER = 1.2    # seconds held before it speeds up
POINT_BOOST_OVER = 1.5     # seconds to reach full speed


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
        self.pointing = None         # "up" / "down" while pointing
        self._started = None

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

    def point_rate(self, held):
        """Notches per second after pointing for `held` seconds."""
        boost = min(max(held - POINT_BOOST_AFTER, 0.0) / POINT_BOOST_OVER, 1.0)
        return POINT_NOTCHES_PER_SECOND * self.speed * (1.0 + (POINT_BOOST - 1.0) * boost)

    def update(self, active, y, now, direction=None):
        """
        One camera frame. `active`: the scroll pose is held; `y`: hand
        height in 0..1 image coordinates (0 = top). With `direction`
        ("up" / "down", a pointing pose) the height doesn't matter.
        Returns the wheel amount to send now (0 = nothing).
        """

        if direction is not None:
            return self._point(active, direction, now)

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

    def _point(self, active, direction, now):
        if not active:
            if self.active:
                self.reset()
            return 0
        if not self.active or self.pointing != direction:
            self.reset()
            self.active = True
            self.pointing = direction
            self._started = self._last_t = now
            return 0

        dt = max(0.0, min(now - self._last_t, 0.2))
        self._last_t = now
        rate = self.point_rate(now - self._started)
        self._pending += (rate if direction == "up" else -rate) * WHEEL_DELTA * dt
        if abs(self._pending) < MIN_SEND:
            return 0
        amount = int(self._pending)
        self._pending -= amount
        return amount

    @property
    def direction(self):
        """'up', 'down' or None, for the status line."""
        if self.pointing is not None:
            return self.pointing if self.active else None
        if not self.active or self.centre is None or self._filter._x is None:
            return None
        offset = self.centre - self._filter._x
        if abs(offset) <= DEAD_ZONE:
            return None
        return "up" if offset > 0 else "down"
