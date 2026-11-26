"""
Wield's six hand signs: each one means the same kind of thing in every
app, so there are six things to learn instead of a list per studio.
Anything else is said out loud ("Hey Wield, help" lists it all).

A new studio or app fits in by deciding what each sign does there; it
never needs new signs. tests/test_hand_signs.py checks that the built-in
studios keep to these meanings.

    SIGNS   (gesture, emoji, name, meaning, examples)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HandSign:
    gesture: str          # how it's stored in a studio, e.g. "👍 Thumbs Up"
    emoji: str
    name: str
    meaning: str
    examples: str


SIGNS = [
    HandSign("✋ Open Palm", "✋", "Open hand", "Wake Wield up",
             "When Wield is waiting in the background"),
    HandSign("👍 Thumbs Up", "👍", "Thumbs up", "Go / play",
             "Next slide · play or pause a video"),
    HandSign("👎 Thumbs Down", "👎", "Thumbs down", "Go back",
             "Previous slide · back a web page"),
    HandSign("Swipe right", "👉", "Swipe left or right", "Forward or back",
             "Change slides · skip 10 seconds in a video"),
    HandSign("☝️ Pointing Up", "☝️", "Point up or down", "Scroll",
             "Hold it to keep scrolling a page, PDF or document"),
    HandSign("✊ Fist", "✊", "Hold a fist", "Stop or close",
             "End a slideshow · close a browser tab"),
]

# The action each sign should lead to in each built-in studio (None: the
# sign isn't used there). Swipe left is Swipe right's partner.
EXPECTED = {
    "presentation": {
        "✋ Open Palm": "ACTIVATE",
        "👍 Thumbs Up": "presentation_next",
        "👎 Thumbs Down": "presentation_previous",
        "Swipe right": "presentation_next",
        "Swipe left": "presentation_previous",
        "✊ Fist": "presentation_end",
        # Not one of the six, kept for starting the slideshow.
        "✌️ Peace": "presentation_start",
    },
    "browse": {
        "✋ Open Palm": None,
        "👍 Thumbs Up": "browse_video_play_pause",
        "👎 Thumbs Down": "browse_page_back",
        "Swipe right": "browse_video_forward",
        "Swipe left": "browse_video_back",
        "☝️ Pointing Up": "browse_point_up",
        "👇 Pointing Down": "browse_point_down",
        "✊ Fist": "browse_tab_close",
    },
}

# Every other built-in gesture is left free in the built-in studios, so
# people only meet the six.
OTHER_BUILT_IN_GESTURES = ("✌️ Peace",)
