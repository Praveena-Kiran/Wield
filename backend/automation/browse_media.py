"""
Browse & Media Studio: scroll, control videos and music, and manage
browser tabs with gestures, motions or voice.

Its profile (backend/config/profiles/browse.json) maps triggers to these
action codes, just like Presentation Studio. PROFILE_ACTIONS gives each a
name and the event it becomes: (name, action, value).

    "Scroll"   handled live by the gesture worker while the pose is held
    "ScrollPoint"  likewise: ☝️ / 👇 scroll up / down while held
               (backend/gestures/scroll.py), never as a one-off event
    "Wheel"    one scroll up or down (voice, a motion or a pose): works in
               any app, like turning the mouse wheel a few notches
    "Browser"  keys for the browser in front (YouTube's K / J / L / arrows);
               refused when anything else is in front, so letters are never
               typed into another app
    "Media"    Windows media and volume keys: work in the background and in
               any player (Spotify, VLC, a browser tab)
    "VolumeHold"  like "Scroll", but moving the held hand changes the volume
    "Mouse"    hand mouse on / off (the gesture worker moves the pointer)
    "Click"    a click where the pointer is
    "System"   Windows itself, whatever is in front: switch app (Alt+Tab),
               show the desktop (Win+D), lock the computer

Closing tabs by name or website ("close all YouTube tabs") would need a
browser extension; it's a possible follow-up.
"""

from backend.automation.controllers.desktop_input import WHEEL_DELTA, DesktopInput, is_browser


PROFILE_NAME = "browse"

SCROLL = "browse_scroll"

# In the order shown in the studio.
ACTIONS = [
    "browse_point_up",
    "browse_point_down",
    SCROLL,
    "browse_scroll_up",
    "browse_scroll_down",
    "browse_go_to_page",
    "browse_zoom_in",
    "browse_zoom_out",
    "browse_zoom_reset",
    "browse_video_play_pause",
    "browse_video_forward",
    "browse_video_back",
    "browse_video_forward_5",
    "browse_video_back_5",
    "browse_video_fullscreen",
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
    "browse_page_back",
    "browse_page_forward",
    "browse_mouse_on",
    "browse_mouse_off",
    "browse_click",
    "browse_double_click",
    "browse_right_click",
    "browse_app_switch",
    "browse_desktop",
    "browse_lock",
]

# How the studio groups its actions: (key, title, icon, where it works, actions).
SECTIONS = [
    ("scroll", "Scroll & zoom", "↕",
     "Any app: a web page, a PDF, Word. Works on what's under your mouse pointer.",
     ["browse_point_up", "browse_point_down", SCROLL,
      "browse_scroll_up", "browse_scroll_down", "browse_go_to_page",
      "browse_zoom_in", "browse_zoom_out", "browse_zoom_reset"]),
    ("video", "Videos", "▶",
     "YouTube and most video sites, in the browser in front.",
     ["browse_video_play_pause", "browse_video_forward", "browse_video_back",
      "browse_video_forward_5", "browse_video_back_5", "browse_video_fullscreen"]),
    ("music", "Music & volume", "♫",
     "Spotify, VLC, a video in a tab: any player, even in the background.",
     ["browse_media_play_pause", "browse_media_next", "browse_media_previous",
      "browse_volume_up", "browse_volume_down", "browse_volume_mute",
      "browse_volume_hold"]),
    ("tabs", "Browser tabs & pages", "⧉",
     "Chrome, Edge, Firefox or Brave in front. Closing a tab needs a one-second hold.",
     ["browse_tab_close", "browse_tab_reopen", "browse_tab_next", "browse_tab_previous",
      "browse_page_back", "browse_page_forward"]),
    ("mouse", "Hand mouse", "➚",
     "Any app. Point to move the pointer, pinch thumb and index to click "
     "(pinch and move to drag), thumb and middle finger to right-click, "
     "hold a fist for a second to stop.",
     ["browse_mouse_on", "browse_mouse_off", "browse_click",
      "browse_double_click", "browse_right_click"]),
    ("windows", "Windows", "⊞",
     "Any time: switch apps, show the desktop, lock the computer (hold to lock).",
     ["browse_app_switch", "browse_desktop", "browse_lock"]),
]

PROFILE_ACTIONS = {
    "browse_point_up": ("Scroll up (point up and hold)", "ScrollPoint", "up"),
    "browse_point_down": ("Scroll down (point down and hold)", "ScrollPoint", "down"),
    SCROLL: ("Scroll (hold and move your hand)", "Scroll", "hold"),
    "browse_scroll_up": ("Scroll up", "Wheel", "scroll_up"),
    "browse_scroll_down": ("Scroll down", "Wheel", "scroll_down"),
    "browse_go_to_page": ("Go to page (Word, PDFs)", "Document", "go_to_page"),
    "browse_zoom_in": ("Zoom in", "Wheel", "zoom_in"),
    "browse_zoom_out": ("Zoom out", "Wheel", "zoom_out"),
    "browse_zoom_reset": ("Reset zoom (browser)", "Browser", "zoom_reset"),
    "browse_video_play_pause": ("Play / pause video", "Browser", "video_play_pause"),
    "browse_video_forward": ("Video forward 10 s", "Browser", "video_forward_10"),
    "browse_video_back": ("Video back 10 s", "Browser", "video_back_10"),
    "browse_video_forward_5": ("Video forward 5 s", "Browser", "video_forward_5"),
    "browse_video_back_5": ("Video back 5 s", "Browser", "video_back_5"),
    "browse_video_fullscreen": ("Video full screen on / off", "Browser", "video_fullscreen"),
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
    "browse_page_back": ("Back a page", "Browser", "page_back"),
    "browse_page_forward": ("Forward a page", "Browser", "page_forward"),
    "browse_mouse_on": ("Hand mouse on", "Mouse", "on"),
    "browse_mouse_off": ("Hand mouse off", "Mouse", "off"),
    "browse_click": ("Click", "Click", "left"),
    "browse_double_click": ("Double-click", "Click", "double"),
    "browse_right_click": ("Right-click", "Click", "right"),
    "browse_app_switch": ("Switch to the last app", "System", "app_switch"),
    "browse_desktop": ("Show the desktop", "System", "show_desktop"),
    "browse_lock": ("Lock the computer (hold)", "System", "lock"),
}

# Actions that only run after the pose is held this many seconds, with a
# bar filling up on screen (backend/gestures/hold.py). Closing a tab must
# never happen by accident.
HOLD_SECONDS = {
    "browse_tab_close": 1.0,
    "browse_lock": 1.0,
}

# value -> ("keys", [keys for the browser in front]) or ("media", media key)
COMMANDS = {
    # One scroll, in any app (the page under the mouse pointer).
    "scroll_up": ("wheel", 1),
    "scroll_down": ("wheel", -1),
    # Zoom with Ctrl + wheel: the same in browsers, PDF readers and Word.
    "zoom_in": ("zoom", 1),
    "zoom_out": ("zoom", -1),
    "zoom_reset": ("keys", ["ctrl", "0"]),
    # "Go to page twelve": Word and PDF readers' own Go To box.
    "go_to_page": ("page", None),
    # YouTube (and most web players): K play/pause, J/L 10 s, arrows 5 s.
    "video_play_pause": ("keys", ["k"]),
    "video_forward_10": ("keys", ["l"]),
    "video_back_10": ("keys", ["j"]),
    "video_forward_5": ("keys", ["right"]),
    "video_back_5": ("keys", ["left"]),
    "video_fullscreen": ("keys", ["f"]),
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
    "page_back": ("keys", ["alt", "left"]),
    "page_forward": ("keys", ["alt", "right"]),
    # Mouse clicks where the pointer is (voice, while using the hand mouse).
    "left": ("click", "left"),
    "double": ("click", "double"),
    "right": ("click", "right"),
    # Windows itself: any app in front.
    "app_switch": ("system_keys", ["alt", "tab"]),
    "show_desktop": ("system_keys", ["win", "d"]),
    "lock": ("lock", None),
}


# Mouse-wheel notches for one "scroll up / down" at each speed.
WHEEL_NOTCHES = {"slow": 3, "medium": 5, "fast": 8}


# Built-in gestures from earlier versions that the six hand signs replaced
# (backend/hand_signs.py). Still set to these = never changed by the user,
# so they're swapped for the new defaults once.
OLD_DEFAULTS = {
    "✌️ Peace": "browse_scroll",
    "☝️ Pointing Up": "browse_tab_next",
    "✋ Open Palm": "browse_tab_reopen",
    "👎 Thumbs Down": "browse_tab_previous",
}
DEFAULTS_VERSION = 2


def update_old_defaults(profile_manager):
    """
    Move a profile saved by an older Wield to the new built-in gestures,
    keeping anything the user chose themselves. Runs once per profile.
    Returns the gestures it took off.
    """

    profile = getattr(profile_manager, "current_profile", None)
    if profile is None or profile.get("defaults_version", 1) >= DEFAULTS_VERSION:
        return []

    current = profile_manager.get_gesture_map()
    removed = [g for g, action in OLD_DEFAULTS.items() if current.get(g) == action]
    for gesture in removed:
        del current[gesture]
    profile["defaults_version"] = DEFAULTS_VERSION
    profile_manager.save_profile()
    return removed


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

    update_old_defaults(profile_manager)

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


class NotInDocument(RuntimeError):
    """"Go to page" while no Word document or PDF is in front."""


# App in front -> the keys that open its "go to page" box. The box takes
# the page number, Enter goes there; Word's stays open, so Esc closes it.
GO_TO_PAGE = {
    "winword.exe": (["ctrl", "g"], True),
    "acrobat.exe": (["ctrl", "shift", "n"], False),
    "acrord32.exe": (["ctrl", "shift", "n"], False),
    "sumatrapdf.exe": (["ctrl", "g"], False),
}

DIALOG_WAIT = 0.35      # seconds for a dialog to open / the address bar to copy


class BrowseMediaController:
    """Runs the studio's one-off actions (video, media keys, tabs)."""

    def __init__(self, desktop_input=None, speed=None, sleep=None):
        import time
        self.input = desktop_input or DesktopInput()
        self.speed = speed          # None: read from Settings each time
        self.sleep = sleep or time.sleep

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

    def execute(self, command, number=None):

        spec = COMMANDS.get(command)
        if spec is None:
            raise ValueError(f'Unknown command "{command}".')

        kind, what = spec

        if kind == "page":
            self.go_to_page(number)
            return

        if kind == "wheel":
            self.input.scroll(what * self.wheel_notches() * WHEEL_DELTA)
            return

        if kind == "click":
            if what == "double":
                self.input.click("left", double=True)
            else:
                self.input.click(what)
            return

        if kind == "zoom":
            self.input.zoom(what)
            return

        if kind == "system_keys":
            self.input.press(what)
            return

        if kind == "lock":
            self.input.lock()
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


    def go_to_page(self, number):
        """Jump to a page in Word, Adobe Reader / Acrobat, SumatraPDF or a
        PDF open in the browser."""

        try:
            number = int(number)
        except (TypeError, ValueError):
            number = 0
        if number < 1:
            raise ValueError("Say the page number, like “go to page twelve”.")

        app = self.input.foreground_process()
        if app in GO_TO_PAGE:
            keys, close_after = GO_TO_PAGE[app]
            self.input.press(keys)
            self.sleep(DIALOG_WAIT)
            self.input.press(["ctrl", "a"])          # replace what's in the box
            self.input.type_digits(number)
            self.input.press(["enter"])
            if close_after:
                self.sleep(DIALOG_WAIT)
                self.input.press(["esc"])
            return

        if is_browser(app):
            self._browser_pdf_page(number)
            return

        raise NotInDocument("Open a Word document or a PDF first, then say the page.")

    def _browser_pdf_page(self, number):
        """A PDF in Chrome / Edge / Firefox: its address + #page=N."""

        saved = self.input.clipboard_text()
        try:
            self.input.press(["ctrl", "l"])
            self.input.press(["ctrl", "c"])
            self.sleep(DIALOG_WAIT)
            address = self.input.clipboard_text().strip()
            base = address.split("#", 1)[0]
            if not base.split("?", 1)[0].lower().endswith(".pdf"):
                self.input.press(["esc"])
                raise NotInDocument("This tab isn't a PDF. Open a PDF or a Word document first.")
            self.input.set_clipboard_text(f"{base}#page={number}")
            self.input.press(["ctrl", "v"])
            self.input.press(["enter"])
            self.sleep(DIALOG_WAIT)
        finally:
            self.input.set_clipboard_text(saved)


def _short_trigger(trigger):
    """👍 Thumbs Up -> 👍; Swipe up stays; a phrase -> “phrase”."""
    from backend.voice.commands import example_phrase, is_voice_trigger, phrase_of
    if is_voice_trigger(trigger):
        return f"“{example_phrase(phrase_of(trigger))}”"
    first = trigger.split(" ", 1)[0]
    return first if first and not first[0].isalnum() else trigger


def section_summary(gesture_map, actions, limit=5):
    """
    One line saying what a section does right now, e.g.
    "✌️ scroll · Swipe up scroll up · “zoom in”" (phrases speak for themselves).
    """
    from backend.voice.commands import is_voice_trigger

    items = []
    for action in actions:
        triggers = [t for t, a in (gesture_map or {}).items() if a == action]
        if not triggers:
            continue
        trigger = sorted(triggers, key=is_voice_trigger)[0]
        short = _short_trigger(trigger)
        if is_voice_trigger(trigger):
            items.append(short)
        else:
            name = PROFILE_ACTIONS[action][0].split(" (")[0].lower()
            items.append(f"{short} {name}")
        if len(items) >= limit:
            break
    return " · ".join(items) if items else "Nothing set up yet"
