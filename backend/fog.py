"""
Logic behind the foggy window on Home: which "pen" the hand is holding, and
where the saved note lives. The drawing itself is in
frontend/components/fog_window.py.

Hand modes (from MediaPipe image landmarks, no extra model):
    write  index finger out, middle finger curled (the ring or pinky may
           be a little out; new users rarely curl them fully)  -> writes
    pause  every finger curled (fist)                        -> moves freely
    wipe   every finger out (open palm)                      -> held, clears
    None   anything else / no hand

Smoother writing:
    PointSmoother  a One-Euro filter on the fingertip: strong smoothing
                   when the finger moves slowly (kills jitter), little when
                   it moves fast (no lag)
    PenState       forgiving pen-down / pen-up: a stroke starts after two
                   "write" frames in a row, and survives short tracking
                   drop-outs or a frame or two of a different pose
"""

import math
import os

from backend.paths import user_data_dir


NOTE_FILENAME = "fog_note.png"

WRIST = 0
FINGERS = {               # tip, middle joint (PIP)
    "index": (8, 6),
    "middle": (12, 10),
    "ring": (16, 14),
    "pinky": (20, 18),
}

# A finger is "out" when its tip is this much further from the wrist than
# its middle joint (as a fraction of the joint's distance).
EXTENDED_RATIO = 1.12


def _xy(lm):
    return (lm.x, lm.y) if hasattr(lm, "x") else (lm[0], lm[1])


def finger_states(landmarks):
    """{"index": True/False, ...} for 21 landmarks, or None."""

    if landmarks is None or len(landmarks) < 21:
        return None

    wx, wy = _xy(landmarks[WRIST])
    states = {}

    for name, (tip, pip) in FINGERS.items():
        tx, ty = _xy(landmarks[tip])
        px, py = _xy(landmarks[pip])
        tip_d = math.hypot(tx - wx, ty - wy)
        pip_d = math.hypot(px - wx, py - wy)
        states[name] = pip_d > 0 and tip_d > pip_d * EXTENDED_RATIO

    return states


def hand_mode(landmarks):
    """'write', 'pause', 'wipe' or None."""

    states = finger_states(landmarks)

    if states is None:
        return None

    others = [states["middle"], states["ring"], states["pinky"]]

    # Forgiving: the middle finger must be curled (so a peace sign is not
    # writing), but one of ring / pinky may be a little out.
    if states["index"] and not states["middle"] and not (states["ring"] and states["pinky"]):
        return "write"

    if not states["index"] and not any(others):
        return "pause"

    if states["index"] and all(others):
        return "wipe"

    return None


def fingertip(landmarks):
    """(x, y) of the index fingertip in 0..1 image coordinates, or None."""

    if landmarks is None or len(landmarks) < 21:
        return None

    return _xy(landmarks[8])


def note_path():
    return os.path.join(user_data_dir(), NOTE_FILENAME)


# ---------------------------------------------------------------------
# SMOOTHING
# ---------------------------------------------------------------------

class OneEuroFilter:
    """
    The One-Euro filter (Casiez et al., 2012) for one value. Its cut-off
    frequency rises with speed: slow, jittery movement is smoothed a lot,
    fast movement hardly at all, so it stays responsive.
    """

    def __init__(self, min_cutoff=0.8, beta=2.0, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self):
        self._x = None
        self._dx = 0.0
        self._t = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):

        if self._x is None or self._t is None or t <= self._t:
            self._x, self._t = x, t
            return x

        dt = t - self._t
        dx = (x - self._x) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        self._dx = a_d * dx + (1 - a_d) * self._dx

        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        a = self._alpha(cutoff, dt)
        self._x = a * x + (1 - a) * self._x
        self._t = t
        return self._x


class PointSmoother:
    """One-Euro filtering of an (x, y) point in 0..1 image coordinates."""

    # Forget the past after this long without a point (a new stroke).
    RESET_AFTER = 0.5

    def __init__(self, **kwargs):
        self.fx = OneEuroFilter(**kwargs)
        self.fy = OneEuroFilter(**kwargs)
        self._last_t = None

    def reset(self):
        self.fx.reset()
        self.fy.reset()
        self._last_t = None

    def __call__(self, point, t):
        if self._last_t is not None and t - self._last_t > self.RESET_AFTER:
            self.reset()
        self._last_t = t
        return (self.fx(point[0], t), self.fy(point[1], t))


class PenState:
    """
    Turns per-frame hand modes into a steadier pen.

        update(raw_mode, now) -> the mode to act on

    - The pen goes down after WRITE_ON_FRAMES "write" frames in a row, so
      passing through the pose on the way to another doesn't leave a dot.
    - Once down, it stays down through a missing hand for up to
      DROPOUT_SECONDS and through another pose for up to LIFT_SECONDS,
      so a flicker in tracking doesn't break a word into pieces.
    """

    WRITE_ON_FRAMES = 2
    LIFT_SECONDS = 0.15
    DROPOUT_SECONDS = 0.3

    def __init__(self):
        self.down = False
        self._write_frames = 0
        self._last_write = None

    def reset(self):
        self.__init__()

    def update(self, raw, now):

        if raw == "write":
            self._write_frames += 1
            self._last_write = now
            if self.down or self._write_frames >= self.WRITE_ON_FRAMES:
                self.down = True
            return "write" if self.down else None

        self._write_frames = 0

        if self.down and self._last_write is not None:
            grace = self.DROPOUT_SECONDS if raw is None else self.LIFT_SECONDS
            if now - self._last_write <= grace:
                return "write"

        self.down = False
        return raw
