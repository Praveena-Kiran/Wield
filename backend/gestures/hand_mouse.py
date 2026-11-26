"""
The hand mouse: move the pointer with your hand, pinch to click.

    mouse = HandMouse()
    ops = mouse.update(image_landmarks, now)
    # [("move", x, y), ("click",), ("right_click",), ("scroll", "up"|"down"), ("exit",)]
    # x, y: 0..1 across the screen

- Your hand moves the pointer: it follows the point between your thumb
  tip and index fingertip, smoothed (One-Euro filter), and on screen it
  glides between camera frames (pointer_glide.py).
- A small box of the camera image covers the whole screen. It's centred
  on where your hand is when the hand mouse turns on, and if your hand
  drifts past its edge the box follows (see REACH).
- One pinch (thumb + index) = one click. While your fingers close for
  the pinch the pointer holds still, so the click lands where you aimed.
- Pinch thumb + middle finger: right-click.
- ☝️ Point up / 👇 point down and hold: scroll up / down (the pointer
  stays put meanwhile).
- Hold a fist for a second (or say "Hey Wield, mouse off"): leave mouse mode.
"""

import math

from backend.fog import OneEuroFilter, finger_states
from backend.gestures.pointing import pointing

THUMB_TIP, INDEX_TIP, MIDDLE_TIP = 4, 8, 12
WRIST, MIDDLE_KNUCKLE = 0, 9

# Camera area (image coordinates, 0..1) that maps to the whole screen,
# for to_screen() and a fixed region.
REGION = (0.18, 0.12, 0.82, 0.68)

# Reach: the width and height of the camera area that covers the screen.
# Smaller = less hand movement (a little less precise).
REACH = {
    "short": (0.26, 0.24),
    "medium": (0.36, 0.32),
    "long": (0.60, 0.52),
}
DEFAULT_REACH = "medium"

PINCH_ON = 0.28      # pinched: tips closer than this × hand size
PINCH_OFF = 0.40     # released: further than this (hysteresis)
FREEZE_SECONDS = 0.25   # (kept for older code/tests: a pinch holds the pointer)
# Fingers closing for a pinch: below this (× hand size) the pointer holds
# still, so the click lands where you were pointing.
AIM_LOCK = 0.45
# Point up / down this long before it scrolls (passing through the pose
# on the way to another doesn't).
POINT_SCROLL_AFTER = 0.25
MIN_MOVE = 0.0005    # of the screen: smaller moves aren't sent (the glide smooths the rest)
EXIT_FIST_SECONDS = 1.0


def _xy(point):
    return (point.x, point.y) if hasattr(point, "x") else (point[0], point[1])


def _distance(a, b):
    (ax, ay), (bx, by) = _xy(a), _xy(b)
    return math.hypot(ax - bx, ay - by)


def to_screen(x, y, region=REGION):
    """Image point -> 0..1 screen point (clamped)."""
    x0, y0, x1, y1 = region
    sx = (x - x0) / (x1 - x0)
    sy = (y - y0) / (y1 - y0)
    return min(max(sx, 0.0), 1.0), min(max(sy, 0.0), 1.0)


def centred_region(x, y, reach=DEFAULT_REACH):
    """The screen's camera area, centred on (x, y) and kept inside the image."""
    w, h = REACH.get(reach, REACH[DEFAULT_REACH])
    x0 = min(max(x - w / 2, 0.0), 1.0 - w)
    y0 = min(max(y - h / 2, 0.0), 1.0 - h)
    return (x0, y0, x0 + w, y0 + h)


def follow(region, x, y):
    """Slide the area so (x, y) is inside it: past an edge, the area comes
    along (the pointer stays at the screen's edge), so you never have to
    reach further than the area is wide."""
    x0, y0, x1, y1 = region
    dx = min(x - x0, 0.0) + max(x - x1, 0.0)
    dy = min(y - y0, 0.0) + max(y - y1, 0.0)
    if not dx and not dy:
        return region
    w, h = x1 - x0, y1 - y0
    x0 = min(max(x0 + dx, 0.0), 1.0 - w)
    y0 = min(max(y0 + dy, 0.0), 1.0 - h)
    return (x0, y0, x0 + w, y0 + h)


class HandMouse:

    def __init__(self, region=None, reach=DEFAULT_REACH):
        self.fixed_region = region          # None: centred on your hand
        self.reach = reach
        # Steadier when you hold still (lower cutoff), still quick when you
        # sweep across the screen (beta).
        # Steady when you hold still, still quick when you sweep across.
        self.fx = OneEuroFilter(min_cutoff=0.5, beta=3.0)
        self.fy = OneEuroFilter(min_cutoff=0.5, beta=3.0)
        self.reset()

    def reset(self):
        self.region = self.fixed_region
        self.fx.reset()
        self.fy.reset()
        self.left_down = False          # never held: a pinch is a click
        self._pinched = False
        self._pinch_since = None
        self._right_pinched = False
        self._point_since = None
        self._point_dir = None
        self._last_sent = None
        self._fist_since = None

    def _release(self):
        self._pinched = False
        self._pinch_since = None
        return []

    def update(self, landmarks, now):

        if not landmarks or len(landmarks) < 21:
            self._release()
            self._fist_since = None
            self._point_since = None
            return []

        ops = []
        size = _distance(landmarks[WRIST], landmarks[MIDDLE_KNUCKLE]) or 1e-6
        left_ratio = _distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / size
        right_ratio = _distance(landmarks[THUMB_TIP], landmarks[MIDDLE_TIP]) / size

        # Leave mouse mode: a fist held for a second (not a pinch: curled
        # fingers with the thumb on the index).
        states = finger_states(landmarks)
        if states and not any(states.values()) and left_ratio >= PINCH_OFF:
            if self._fist_since is None:
                self._fist_since = now
            elif now - self._fist_since >= EXIT_FIST_SECONDS:
                self._fist_since = None
                return [("exit",)]
            return []
        self._fist_since = None

        # Point up / down: scroll while held (the pointer stays put).
        direction = pointing(landmarks) if left_ratio >= PINCH_OFF else None
        if direction:
            if self._point_dir != direction:
                self._point_dir, self._point_since = direction, now
            if now - self._point_since >= POINT_SCROLL_AFTER:
                return [("scroll", direction)]
            return []
        self._point_dir = self._point_since = None

        # One pinch, one click (with hysteresis, so a pinch isn't two).
        if not self._pinched and left_ratio < PINCH_ON:
            self._pinched = True
            self._pinch_since = now
            ops.append(("click",))
        elif self._pinched and left_ratio > PINCH_OFF:
            self._pinched = False

        # Right click: thumb + middle pinch, once per pinch.
        if not self._pinched and not self._right_pinched and right_ratio < PINCH_ON:
            self._right_pinched = True
            ops.append(("right_click",))
        elif self._right_pinched and right_ratio > PINCH_OFF:
            self._right_pinched = False

        # Pointer: between thumb and index tips, smoothed.
        (tx, ty), (ix, iy) = _xy(landmarks[THUMB_TIP]), _xy(landmarks[INDEX_TIP])
        px, py = (tx + ix) / 2, (ty + iy) / 2
        if self.region is None:
            self.region = centred_region(px, py, self.reach)
        elif self.fixed_region is None:
            self.region = follow(self.region, px, py)
        sx, sy = to_screen(px, py, self.region)
        sx, sy = self.fx(sx, now), self.fy(sy, now)

        # Hold still while a pinch is on its way or held, so clicks land
        # where you aimed.
        aiming = min(left_ratio, right_ratio) < AIM_LOCK
        if not (aiming or self._pinched or self._right_pinched):
            last = self._last_sent
            if last is None or abs(sx - last[0]) + abs(sy - last[1]) >= MIN_MOVE:
                self._last_sent = (sx, sy)
                ops.insert(0, ("move", sx, sy))

        return ops
