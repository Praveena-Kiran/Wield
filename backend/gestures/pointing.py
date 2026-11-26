"""
Which way the index finger points, from MediaPipe's 21 hand points.

MediaPipe's gesture model knows "Pointing_Up" but not pointing down, so
both are worked out here from the points themselves:

    pointing(landmarks) -> "up", "down" or None

Pointing means: the index finger is straight, the middle, ring and little
fingers are curled in, and the index finger is closer to vertical than to
horizontal. Points are image coordinates (x, y in 0..1, y downwards),
either MediaPipe landmarks (.x / .y) or (x, y) pairs.
"""

import math

WRIST = 0
INDEX = (5, 6, 7, 8)                  # knuckle, middle joints, tip
CURLED = ((10, 12), (14, 16), (18, 20))   # (middle joint, tip) of the other fingers

STRAIGHT = 0.85        # tip-to-knuckle vs the finger's length along its joints
VERTICAL = 0.6         # of the finger's length that must be up / down
CURLED_RATIO = 1.1     # a curled tip is no further from the wrist than this x its joint


def _xy(point):
    if hasattr(point, "x"):
        return point.x, point.y
    return point[0], point[1]


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def pointing(landmarks):
    if not landmarks or len(landmarks) < 21:
        return None
    p = [_xy(point) for point in landmarks]

    knuckle, joint1, joint2, tip = (p[i] for i in INDEX)
    along = _dist(knuckle, joint1) + _dist(joint1, joint2) + _dist(joint2, tip)
    reach = _dist(knuckle, tip)
    if along <= 0 or reach / along < STRAIGHT:
        return None                                   # index finger bent

    wrist = p[WRIST]
    for joint, finger_tip in CURLED:
        if _dist(p[finger_tip], wrist) > _dist(p[joint], wrist) * CURLED_RATIO:
            return None                               # another finger is out

    rise = tip[1] - knuckle[1]                        # + = the tip is lower
    if rise >= VERTICAL * reach:
        return "down"
    if -rise >= VERTICAL * reach:
        return "up"
    return None
