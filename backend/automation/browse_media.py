"""
Browse & Media Studio: scroll, control videos and music, and manage
browser tabs with gestures, motions or voice.

Its profile (backend/config/profiles/browse.json) maps triggers to these
action codes, just like Presentation Studio. PROFILE_ACTIONS gives each a
name and the event it becomes: (name, action, value).

    "Scroll"   handled live by the gesture worker while the pose is held
               (backend/gestures/scroll.py), never as a one-off event
    "Wheel"    one scroll up or down (voice, a motion or a pose): works in
               any app, like turning the mouse wheel a few notches
    "Browser"  keys for the browser in front (YouTube's K / J / L / arrows);
               refused when anything else is in front, so letters are never
               typed into another app
    "Media"    Windows media and volume keys: work in the background and in
               any player (Spotify, VLC, a browser tab)
    "VolumeHold"  like "Scroll", but moving the held hand changes the volume

Closing tabs by name or website ("close all YouTube tabs") would need a
browser extension; it's a possible follow-up.
"""

from backend.automation.controllers.desktop_input import WHEEL_DELTA, DesktopInput


PROFILE_NAME = "browse"

SCROLL = "browse_scroll"

# In the order shown in the studio.
ACTIONS = [
    SCROLL,
    "browse_scroll_up",
    "browse_scroll_down",
    "browse_video_play_pause",
    "browse_video_forward",
    "browse_video_back",
    "browse_video_forward_5",
    "browse_video_back_5",
    "browse_media_play_pause",
    "browse_media_next",
    "browse_media_previous",
    "browse_volume_up",
    "browse_volume_down",
    "browse_volume_mute",
    "browse_volume_hold",
    "browse_tab_close",
    "browse_tab_reopen",
    "browse_tab_next",
    "browse_tab_previous",
]

# How the studio groups its actions: (key, title, icon, where it works, actions).
SECTIONS = [
    ("scroll", "Scroll", "↕",
     "Any app: a web page, a PDF, Word. Scrolls what's under your mouse pointer.",
     [SCROLL, "browse_scroll_up", "browse_scroll_down"]),
    ("video", "Videos", "▶",
     "YouTube and most video sites, in the browser in front.",
     ["browse_video_play_pause", "browse_video_forward", "browse_video_back",
      "browse_video_forward_5", "browse_video_back_5"]),
    ("music", "Music & volume", "♫",
     "Spotify, VLC, a video in a tab: any player, even in the background.",
     ["browse_media_play_pause", "browse_media_next", "browse_media_previous",
      "browse_volume_up", "browse_volume_down", "browse_volume_mute",
      "browse_volume_hold"]),
    ("tabs", "Browser tabs", "⧉",
     "Chrome, Edge, Firefox or Brave in front. Closing needs a one-second hold.",
     ["browse_tab_close", "browse_tab_reopen", "browse_tab_next", "browse_tab_previous"]),
]

PROFILE_ACTIONS = {
    SCROLL: ("Scroll (hold and move your hand)", "Scroll", "hold"),
    "browse_scroll_up": ("Scroll up", "Wheel", "scroll_up"),
    "browse_scroll_down": ("Scroll down", "Wheel", "scroll_down"),
    "browse_video_play_pause": ("Play / pause video", "Browser", "video_play_pause"),
    "browse_video_forward": ("Video forward 10 s", "Browser", "video_forward_10"),
    "browse_video_back": ("Video back 10 s", "Browser", "video_back_10"),
    "browse_video_forward_5": ("Video forward 5 s", "Browser", "video_forward_5"),
    "browse_video_back_5": ("Video back 5 s", "Browser", "video_back_5"),
    "browse_media_play_pause": ("Play / pause music (any app)", "Media", "play_pause"),
    "browse_media_next": ("Next track", "Media", "next"),
    "browse_media_previous": ("Previous track", "Media", "previous"),
    "browse_volume_up": ("Volume up", "Media", "volume_up"),
    "browse_volume_down": ("Volume down", "Media", "volume_down"),
    "browse_volume_mute": ("Mute / unmute", "Media", "mute"),
    "browse_volume_hold": ("Volume (hold and move your hand)", "VolumeHold", "hold"),
    "browse_tab_close": ("Close tab (hold)", "Browser", "tab_close"),
    "browse_tab_reopen": ("Reopen closed tab", "Browser", "tab_reopen"),
    "browse_tab_next": ("Next tab", "Browser", "tab_next"),
    "browse_tab_previous": ("Previous tab", "Browser", "tab_previous"),
}

# Actions that only run after the pose is held this many seconds, with a
# bar filling up on screen (backend/gestures/hold.py). Closing a tab must
# never happen by accident.
HOLD_SECONDS = {
    "browse_tab_close": 1.0,
}

# value -> ("keys", [keys for the browser in front]) or ("media", media key)
COMMANDS = {
    # One scroll, in any app (the page under the mouse pointer).
    "scroll_up": ("wheel", 1),
    "scroll_down": ("wheel", -1),
    # YouTube (and most web players): K play/pause, J/L 10 s, arrows 5 s.
    "video_play_pause": ("keys", ["k"]),
    "video_forward_10": ("keys", ["l"]),
    "video_back_10": ("keys", ["j"]),
    "video_forward_5": ("keys", ["right"]),
    "video_back_5": ("keys", ["left"]),
    # Windows media keys.
    "play_pause": ("media", "play_pause"),
    "next": ("media", "next"),
    "previous": ("media", "previous"),
    "mute": ("media", "mute"),
    # Volume keys, a few steps at a time (each step is about 2%).
    "volume_up": ("volume", 5),
    "volume_down": ("volume", -5),
    # Tabs (every major browser).
    "tab_close": ("keys", ["ctrl", "w"]),
    "tab_reopen": ("keys", ["ctrl", "shift", "t"]),
    "tab_next": ("keys", ["ctrl", "tab"]),
    "tab_previous": ("keys", ["ctrl", "shift", "tab"]),
}


# Mouse-wheel notches for one "scroll up / down" at each speed.
WHEEL_NOTCHES = {"slow": 3, "medium": 5, "fast": 8}


def add_missing_defaults(profile_manager):
    """
    Give an existing profile the default triggers of actions added since it
    was saved (only for actions with no trigger at all, and only triggers
    that aren't used for something else). Returns what was added.
    """

    import json
    import os
    from backend.paths import DEFAULT_CONFIG_DIR

    try:
        with open(os.path.join(DEFAULT_CONFIG_DIR, "profiles", f"{PROFILE_NAME}.json"),
                  encoding="utf-8") as f:
            defaults = json.load(f)["gesture_map"]
    except (OSError, ValueError, KeyError):
        return []

    current = profile_manager.get_gesture_map()
    used_actions = set(current.values())
    added = []

    for trigger, action in defaults.items():
        if action not in used_actions and trigger not in current:
            current[trigger] = action
            added.append(trigger)

    if added:
        profile_manager.save_profile()

    return added


class NotInBrowser(RuntimeError):
    """A browser-only action while another app is in front."""


class BrowseMediaController:
    """Runs the studio's one-off actions (video, media keys, tabs)."""

    def __init__(self, desktop_input=None, speed=None):
        self.input = desktop_input or DesktopInput()
        self.speed = speed          # None: read from Settings each time

    def wheel_notches(self):
        """How far one "scroll up / down" goes, from the studio's speed."""
        speed = self.speed
        if speed is None:
            try:
                from backend.settings import gesture_settings
                speed = gesture_settings.load()["browse_scroll_speed"]
            except Exception:
                speed = "medium"
        return WHEEL_NOTCHES.get(speed, WHEEL_NOTCHES["medium"])

    def execute(self, command):

        spec = COMMANDS.get(command)
        if spec is None:
            raise ValueError(f'Unknown command "{command}".')

        kind, what = spec

        if kind == "wheel":
            self.input.scroll(what * self.wheel_notches() * WHEEL_DELTA)
            return

        if kind == "volume":
            self.input.volume(what)
            return

        if kind == "media":
            self.input.media(what)
            return

        # Browser keys: only into a browser, never into Word or a chat box.
        if not self.input.browser_in_front():
            raise NotInBrowser(
                "Bring your browser to the front first (Chrome, Edge, Firefox or Brave)."
            )

        self.input.press(what)
