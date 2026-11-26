"""“Hey Wield, go to page twelve”: numbers in phrases, and the jump itself."""

import unittest

from backend.automation.browse_media import (
    BrowseMediaController,
    NotInDocument,
    PROFILE_ACTIONS,
)
from backend.automation.controllers.desktop_input import VK, DesktopInput
from backend.voice.commands import (
    VoiceCommandMatcher,
    expand_numbers,
    grammar,
    match_number,
    number_words,
    parse_number,
)


class NumberWordsTests(unittest.TestCase):

    def test_round_trip(self):
        for n in (1, 7, 12, 19, 20, 21, 40, 99, 100, 105, 120, 123, 300, 999):
            self.assertEqual(parse_number(number_words(n)), n, n)
        self.assertEqual(number_words(123), "one hundred twenty three")

    def test_spoken_variants_and_nonsense(self):
        self.assertEqual(parse_number("one hundred and five"), 105)
        self.assertEqual(parse_number("twenty"), 20)
        for text in ("", "page", "zero", "hundred", "twelve banana"):
            self.assertIsNone(parse_number(text), text)

    def test_expand_and_match(self):
        said = expand_numbers("go to page number", maximum=3)
        self.assertEqual(said, ["go to page one", "go to page two", "go to page three"])
        self.assertEqual(expand_numbers("next slide"), ["next slide"])
        self.assertEqual(match_number("go to page number", "go to page forty two"), 42)
        self.assertEqual(match_number("page number please", "page nine please"), 9)
        self.assertIsNone(match_number("go to page number", "go to slide four"))
        self.assertIsNone(match_number("next slide", "next slide"))

    def test_grammar_has_every_page(self):
        words = grammar(["go to page number", "next slide"])
        self.assertIn("go to page one", words)
        self.assertIn("hey wield go to page three hundred", words)
        self.assertNotIn("go to page number", words)
        self.assertIn("next slide", words)


class MatcherTests(unittest.TestCase):

    def test_number_reaches_the_event(self):
        matcher = VoiceCommandMatcher(["go to page number", "next slide"])
        event = matcher.process("hey wield go to page twelve")
        self.assertEqual(event.kind, "command")
        self.assertEqual(event.trigger, "🎤 go to page number")
        self.assertEqual(event.number, 12)

        plain = matcher.process("hey wield next slide")
        self.assertIsNone(plain.number)

    def test_still_needs_the_wake_word(self):
        matcher = VoiceCommandMatcher(["go to page number"])
        self.assertEqual(matcher.process("go to page twelve").kind, "ignored")


class FakeApi:
    def __init__(self, foreground):
        self.foreground = foreground
        self.keys = []

    def foreground_process(self):
        return self.foreground

    def send_keys(self, codes):
        self.keys.append(list(codes))


class FakeInput(DesktopInput):
    """Keys go to FakeApi; the clipboard is a string."""

    def __init__(self, foreground, address=""):
        super().__init__(FakeApi(foreground))
        self.clipboard = "something you copied"
        self.address = address

    def press(self, keys):
        super().press(keys)
        if keys == ["ctrl", "c"]:
            self.clipboard = self.address

    def clipboard_text(self):
        return self.clipboard

    def set_clipboard_text(self, text):
        self.clipboard = text


def typed(keys):
    """[[ctrl, g], [1], [2]] -> readable strings."""
    names = {v: k for k, v in VK.items()}
    return ["+".join(names[c] for c in combo) for combo in keys]


class GoToPageTests(unittest.TestCase):

    def run_in(self, app, number, address=""):
        inp = FakeInput(app, address)
        BrowseMediaController(inp, sleep=lambda s: None).execute("go_to_page", number=number)
        return inp, typed(inp.api.keys)

    def test_word(self):
        _, keys = self.run_in("winword.exe", 12)
        self.assertEqual(keys, ["ctrl+g", "ctrl+a", "1", "2", "enter", "esc"])

    def test_pdf_readers(self):
        _, keys = self.run_in("acrord32.exe", 7)
        self.assertEqual(keys, ["ctrl+shift+n", "ctrl+a", "7", "enter"])
        _, keys = self.run_in("sumatrapdf.exe", 30)
        self.assertEqual(keys[0], "ctrl+g")

    def test_pdf_in_the_browser_keeps_your_clipboard(self):
        inp, keys = self.run_in("msedge.exe", 5, "file:///C:/notes/lecture.pdf#page=2")
        self.assertEqual(keys, ["ctrl+l", "ctrl+c", "ctrl+v", "enter"])
        self.assertEqual(inp.clipboard, "something you copied")

    def test_a_web_page_is_not_a_pdf(self):
        with self.assertRaises(NotInDocument):
            self.run_in("chrome.exe", 5, "https://www.youtube.com/watch?v=x")

    def test_other_apps_and_missing_numbers(self):
        with self.assertRaises(NotInDocument):
            self.run_in("notepad.exe", 3)
        with self.assertRaises(ValueError):
            self.run_in("winword.exe", None)

    def test_in_the_studio_with_a_default_phrase(self):
        import json
        import os
        from backend.paths import DEFAULT_CONFIG_DIR
        self.assertIn("browse_go_to_page", PROFILE_ACTIONS)
        with open(os.path.join(DEFAULT_CONFIG_DIR, "profiles", "browse.json"), encoding="utf-8") as f:
            defaults = json.load(f)["gesture_map"]
        self.assertEqual(defaults["🎤 go to page number"], "browse_go_to_page")


if __name__ == "__main__":
    unittest.main()
