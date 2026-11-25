"""
What's new in each version, and whether this version's tour has been seen.

The tour (frontend/components/tour.py) runs once after installing, and
again after every update, starting with these notes. Settings > About >
Take the tour runs it any time.
"""

from backend.app_info import VERSION
from backend.settings.settings_manager import SettingsManager

SEEN_KEY = "tour_seen_version"

NOTES = {
    "1.3.0": [
        "<b>Hands-free mode</b>: Wield watches in the background; ✋ or “Hey Wield, wake up” and your gestures work in any app.",
        "<b>Hand mouse</b>: “Hey Wield, mouse mode”, then point to move and pinch to click.",
        "<b>What can I do?</b>: “Hey Wield, help” shows every gesture and phrase on screen.",
        "<b>A tidier Browse &amp; Media Studio</b>, and studios you can remove and bring back.",
    ],
    "1.2.0": [
        "<b>Browse &amp; Media Studio</b>: scroll, videos, music, volume, tabs and windows by gesture or voice.",
    ],
    "1.1.0": [
        "A warmer look, white or black fog, pen sizes and smoother writing.",
        "Editable Coding and Gaming Studios, and update notifications.",
    ],
}


def notes(version=VERSION):
    return NOTES.get(version, [])


def seen_version(settings=None):
    try:
        return (settings or SettingsManager()).get_setting(SEEN_KEY)
    except Exception:
        return None


def tour_due(settings=None):
    """'first' (never seen), 'update' (an older version's), or None."""
    seen = seen_version(settings)
    if not seen:
        return "first"
    if seen != VERSION:
        return "update"
    return None


def mark_seen(settings=None):
    try:
        (settings or SettingsManager()).set_setting(SEEN_KEY, VERSION)
    except Exception:
        pass
