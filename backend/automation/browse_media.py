"""
Browse & Media Studio: scroll, control videos and music, and manage
browser tabs with gestures, motions or voice.

Its profile (backend/config/profiles/browse.json) maps triggers to these
action codes, just like Presentation Studio. PROFILE_ACTIONS gives each a
name and the event it becomes: (name, action, value).

    "Scroll"   handled live by the gesture worker while the pose is held
               (backend/gestures/scroll.py), never as a one-off event
"""

from backend.automation.controllers.desktop_input import DesktopInput


PROFILE_NAME = "browse"

SCROLL = "browse_scroll"

# In the order shown in the studio.
ACTIONS = [
    SCROLL,
]

PROFILE_ACTIONS = {
    SCROLL: ("Scroll (hold and move your hand)", "Scroll", "hold"),
}

# Actions that only run after the pose is held this many seconds.
HOLD_SECONDS = {}


class NotInBrowser(RuntimeError):
    """A browser-only action while another app is in front."""


class BrowseMediaController:
    """Runs the studio's one-off actions (video, media keys, tabs)."""

    COMMANDS = {}

    def __init__(self, desktop_input=None):
        self.input = desktop_input or DesktopInput()

    def execute(self, command):
        spec = self.COMMANDS.get(command)
        if spec is None:
            raise ValueError(f'Unknown command "{command}".')
        raise ValueError(f'"{command}" isn\'t available yet.')
