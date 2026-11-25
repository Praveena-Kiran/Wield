"""
Browse & Media Studio: scroll, control videos and music, and manage
browser tabs with gestures, motions or voice.

Its profile (backend/config/profiles/browse.json) maps triggers to these
action codes, just like Presentation Studio. PROFILE_ACTIONS gives each a
name and the event it becomes: (name, action, value).

    "Scroll"   handled live by the gesture worker while the pose is held
               (backend/gestures/scroll.py), never as a one-off event
    "Browser"  keys for the browser in front (YouTube's K / J / L / arrows);
               refused when anything else is in front, so letters are never
               typed into another app
    "Media"    Windows media keys: work in the background and in any player
               (Spotify, VLC, a browser tab)

Closing tabs by name or website ("close all YouTube tabs") would need a
browser extension; it's a possible follow-up.
"""

from backend.automation.controllers.desktop_input import DesktopInput


PROFILE_NAME = "browse"

SCROLL = "browse_scroll"

# In the order shown in the studio.
ACTIONS = [
    SCROLL,
    "browse_video_play_pause",
    "browse_video_forward",
    "browse_video_back",
    "browse_video_forward_5",
    "browse_video_back_5",
    "browse_media_play_pause",
    "browse_media_next",
    "browse_media_previous",
    "browse_tab_close",
    "browse_tab_reopen",
    "browse_tab_next",
    "browse_tab_previous",
]

PROFILE_ACTIONS = {
    SCROLL: ("Scroll (hold and move your hand)", "Scroll", "hold"),
    "browse_video_play_pause": ("Play / pause video", "Browser", "video_play_pause"),
    "browse_video_forward": ("Video forward 10 s", "Browser", "video_forward_10"),
    "browse_video_back": ("Video back 10 s", "Browser", "video_back_10"),
    "browse_video_forward_5": ("Video forward 5 s", "Browser", "video_forward_5"),
    "browse_video_back_5": ("Video back 5 s", "Browser", "video_back_5"),
    "browse_media_play_pause": ("Play / pause music (any app)", "Media", "play_pause"),
    "browse_media_next": ("Next track", "Media", "next"),
    "browse_media_previous": ("Previous track", "Media", "previous"),
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
    # Tabs (every major browser).
    "tab_close": ("keys", ["ctrl", "w"]),
    "tab_reopen": ("keys", ["ctrl", "shift", "t"]),
    "tab_next": ("keys", ["ctrl", "tab"]),
    "tab_previous": ("keys", ["ctrl", "shift", "tab"]),
}


class NotInBrowser(RuntimeError):
    """A browser-only action while another app is in front."""


class BrowseMediaController:
    """Runs the studio's one-off actions (video, media keys, tabs)."""

    def __init__(self, desktop_input=None):
        self.input = desktop_input or DesktopInput()

    def execute(self, command):

        spec = COMMANDS.get(command)
        if spec is None:
            raise ValueError(f'Unknown command "{command}".')

        kind, what = spec

        if kind == "media":
            self.input.media(what)
            return

        # Browser keys: only into a browser, never into Word or a chat box.
        if not self.input.browser_in_front():
            raise NotInBrowser(
                "Bring your browser to the front first (Chrome, Edge, Firefox or Brave)."
            )

        self.input.press(what)
