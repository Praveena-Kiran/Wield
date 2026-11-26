"""
Which way the index finger points, from MediaPipe's 21 hand points.

MediaPipe's gesture model knows "Pointing_Up" but not pointing down, so
both are worked out here from the points themselves:

    pointing(landmarks) -> "up", "down" or None
    thumb(landmarks)    -> "up", "down" or None   (👍 / 👎)

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


THUMB = (2, 3, 4)                       # thumb knuckle, joint, tip
FINGER_JOINTS = ((6, 8), (10, 12), (14, 16), (18, 20))
THUMB_CLEAR = 0.2      # how far past the fingers (x hand size) the thumb tip sticks out


def thumb(landmarks):
    """
    👍 / 👎: the four fingers curled into the palm and the thumb sticking
    out straight up or down (a fist has the thumb folded across instead).
    """
    if not landmarks or len(landmarks) < 21:
        return None
    p = [_xy(point) for point in landmarks]
    wrist = p[WRIST]

    for joint, tip in FINGER_JOINTS:
        if _dist(p[tip], wrist) > _dist(p[joint], wrist) * CURLED_RATIO:
            return None                               # a finger is out

    knuckle, joint, tip = (p[i] for i in THUMB)
    along = _dist(knuckle, joint) + _dist(joint, tip)
    reach = _dist(knuckle, tip)
    if along <= 0 or reach / along < STRAIGHT:
        return None                                   # thumb bent over

    rise = tip[1] - knuckle[1]
    if abs(rise) < VERTICAL * reach:
        return None                                   # sideways

    # The thumb must stick out past the curled fingers. In a fist it lies
    # across them instead, inside the hand.
    fingers_y = [p[i][1] for i in range(5, 21)]
    margin = THUMB_CLEAR * (_dist(wrist, p[9]) or 1e-6)
    if rise < 0 and tip[1] < min(fingers_y) - margin:
        return "up"
    if rise > 0 and tip[1] > max(fingers_y) + margin:
        return "down"
    return None
