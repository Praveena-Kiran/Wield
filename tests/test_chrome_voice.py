"""Chrome by voice: new tab, reload, find, bookmark... and opening sites."""

import json
import os
import unittest

from backend.automation.browse_media import BrowseMediaController, NotInBrowser, PROFILE_ACTIONS
from backend.automation.controllers.desktop_input import VK, DesktopInput
from backend.paths import DEFAULT_CONFIG_DIR


class FakeApi:
    def __init__(self, foreground):
        self.foreground = foreground
        self.keys = []

    def foreground_process(self):
        return self.foreground

    def send_keys(self, codes):
        self.keys.append(list(codes))


def defaults():
    with open(os.path.join(DEFAULT_CONFIG_DIR, "profiles", "browse.json"), encoding="utf-8") as f:
        return json.load(f)["gesture_map"]


class ChromeVoiceTests(unittest.TestCase):

    def press(self, command, app="chrome.exe"):
        api = FakeApi(app)
        BrowseMediaController(DesktopInput(api)).execute(command)
        names = {v: k for k, v in VK.items()}
        return ["+".join(names[c] for c in combo) for combo in api.keys]

    def test_browser_shortcuts(self):
        self.assertEqual(self.press("new_tab"), ["ctrl+t"])
        self.assertEqual(self.press("reload"), ["ctrl+r"])
        self.assertEqual(self.press("find"), ["ctrl+f"])
        self.assertEqual(self.press("bookmark"), ["ctrl+d"])
        self.assertEqual(self.press("downloads"), ["ctrl+j"])
        self.assertEqual(self.press("new_window"), ["ctrl+n"])

    def test_only_into_a_browser(self):
        with self.assertRaises(NotInBrowser):
            self.press("reload", app="winword.exe")

    def test_sites_open_in_the_browser_from_anywhere(self):
        name, action, url = PROFILE_ACTIONS["browse_open_youtube"]
        self.assertEqual((action, url), ("Open Website", "https://www.youtube.com"))
        for key in ("gmail", "google", "maps", "whatsapp", "netflix"):
            self.assertEqual(PROFILE_ACTIONS[f"browse_open_{key}"][1], "Open Website")

    def test_default_phrases(self):
        m = defaults()
        for phrase, action in [("new tab", "browse_new_tab"), ("reload", "browse_reload"),
                               ("refresh", "browse_reload"), ("find on page", "browse_find"),
                               ("open youtube", "browse_open_youtube"), ("open gmail", "browse_open_gmail")]:
            self.assertEqual(m["🎤 " + phrase], action, phrase)

    def test_phrases_are_allowed_and_unique(self):
        from backend.voice.commands import check_phrase
        phrases = [t[2:] for t in defaults() if t.startswith("🎤 ")]
        self.assertEqual(len(phrases), len(set(phrases)))
        for phrase in phrases:
            ok, message = check_phrase(phrase)
            self.assertTrue(ok, f"{phrase}: {message}")


if __name__ == "__main__":
    unittest.main()
