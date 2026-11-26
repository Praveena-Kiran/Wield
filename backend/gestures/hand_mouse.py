"""
The hand mouse: move the pointer with your hand, pinch to click.

    mouse = HandMouse()
    ops = mouse.update(image_landmarks, now)
    # [("move", x, y), ("left_down",), ("left_up",), ("right_click",), ("exit",)]
    # x, y: 0..1 across the screen

- The pointer follows the point between your thumb tip and index fingertip.
  That point barely moves when you pinch them together, so clicking
  doesn't knock the pointer off the button (a fingertip would).
- A box in the middle of the camera image covers the whole screen, so
  small hand movements reach every corner.
- The position goes through a One-Euro filter (as the fog writing and
  scrolling do): steady when you aim, quick when you sweep across. On
  screen, the pointer glides between camera frames (pointer_glide.py).
- Pinch thumb + index: left button down; let go: up. A quick pinch is a
  click, two are a double-click, pinch-and-move drags. For the first
  moment of a pinch the pointer stays put, so a click lands where you aimed.
- Pinch thumb + middle finger: right-click.
- Hold a fist for a second (or say "Hey Wield, mouse off"): leave mouse mode.
- Hand lost: any held button is released, so nothing stays dragged.
"""

import math

from backend.fog import OneEuroFilter, finger_states

THUMB_TIP, INDEX_TIP, MIDDLE_TIP = 4, 8, 12
WRIST, MIDDLE_KNUCKLE = 0, 9

# Camera area (image coordinates, 0..1) that maps to the whole screen.
REGION = (0.18, 0.12, 0.82, 0.68)

PINCH_ON = 0.28      # pinched: tips closer than this × hand size
PINCH_OFF = 0.40     # released: further than this (hysteresis)
FREEZE_SECONDS = 0.25
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


class HandMouse:

    def __init__(self, region=REGION):
        self.region = region
        # Steadier when you hold still (lower cutoff), still quick when you
        # sweep across the screen (beta).
        self.fx = OneEuroFilter(min_cutoff=0.7, beta=3.0)
        self.fy = OneEuroFilter(min_cutoff=0.7, beta=3.0)
        self.reset()

    def reset(self):
        self.fx.reset()
        self.fy.reset()
        self.left_down = False
        self._pinch_since = None
        self._right_pinched = False
        self._last_sent = None
        self._fist_since = None

    def _release(self):
        ops = [("left_up",)] if self.left_down else []
        self.left_down = False
        self._pinch_since = None
        return ops

    def update(self, landmarks, now):

        if not landmarks or len(landmarks) < 21:
            # Hand lost: never leave a button held down.
            ops = self._release()
            self._fist_since = None
            return ops

        ops = []
        size = _distance(landmarks[WRIST], landmarks[MIDDLE_KNUCKLE]) or 1e-6
        left_ratio = _distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / size

        # Leave mouse mode: a fist held for a second. Not while pinching
        # (curled fingers + thumb on the index is a pinch, not a fist).
        states = finger_states(landmarks)
        if states and not any(states.values()) and left_ratio >= PINCH_OFF and not self.left_down:
            if self._fist_since is None:
                self._fist_since = now
            elif now - self._fist_since >= EXIT_FIST_SECONDS:
                self._fist_since = None
                return self._release() + [("exit",)]
            return self._release()
        self._fist_since = None

        # Left button: thumb + index pinch (with hysteresis).
        if not self.left_down and left_ratio < PINCH_ON:
            self.left_down = True
            self._pinch_since = now
            ops.append(("left_down",))
        elif self.left_down and left_ratio > PINCH_OFF:
            ops += self._release()

        # Right click: thumb + middle pinch, once per pinch.
        right_ratio = _distance(landmarks[THUMB_TIP], landmarks[MIDDLE_TIP]) / size
        if not self.left_down and not self._right_pinched and right_ratio < PINCH_ON:
            self._right_pinched = True
            ops.append(("right_click",))
        elif self._right_pinched and right_ratio > PINCH_OFF:
            self._right_pinched = False

        # Pointer: between thumb and index tips, smoothed.
        (tx, ty), (ix, iy) = _xy(landmarks[THUMB_TIP]), _xy(landmarks[INDEX_TIP])
        sx, sy = to_screen((tx + ix) / 2, (ty + iy) / 2, self.region)
        sx, sy = self.fx(sx, now), self.fy(sy, now)

        frozen = self._pinch_since is not None and now - self._pinch_since < FREEZE_SECONDS
        if not frozen and not self._right_pinched:
            last = self._last_sent
            if last is None or abs(sx - last[0]) + abs(sy - last[1]) >= MIN_MOVE:
                self._last_sent = (sx, sy)
                ops.insert(0, ("move", sx, sy))

        return ops
