"""
Voice commands: spoken phrases as triggers, like gestures and motions.

A voice trigger is stored as "🎤 <phrase>", e.g. "🎤 next slide", so it
can sit in a studio's events and in Gesture Studio next to 👍 and swipes.

Recognition is offline (see voice_worker.py) and restricted to a small
grammar: the studio's phrases, optionally preceded by the wake phrase.
Restricting the vocabulary is what makes it reliable; the wake phrase is
what stops words in a talk ("...the next slide shows...") from acting.

VoiceCommandMatcher holds the rules and has no audio or Qt code, so it
is fully testable:

    wake word on:   "hey wield next slide"         -> runs "🎤 next slide"
                    "hey wield" ... "next slide"   -> runs (within window)
                    "next slide"                   -> ignored (no wake word)
    wake word off:  "next slide"                   -> runs

A phrase can hold a number: the word "number" in it stands for one, e.g.
"go to page number" matches "go to page twelve" (and the event gets 12).
"""

import re
import time
from dataclasses import dataclass
from typing import Optional

VOICE_PREFIX = "🎤 "

WAKE_PHRASE = "hey wield"
# Spoken variants recognised as the wake phrase. ("Wield" alone is short and
# easy to say on its own; "hey" helps the recogniser lock onto it.)
WAKE_VARIANTS = ("hey wield", "okay wield", "ok wield", "wield")

DEFAULT_PHRASES = [
    "next slide",
    "previous slide",
    "go back",
    "start presentation",
    "end presentation",
]

# After the wake phrase alone, how long to wait for the command.
DEFAULT_WAKE_WINDOW = 5.0

# Per-word confidence (0-1) below which an utterance is ignored.
DEFAULT_MIN_CONFIDENCE = 0.55

UNKNOWN = "[unk]"

# "go to page number": the word "number" is a slot for 1..MAX_NUMBER.
NUMBER_SLOT = "number"
MAX_NUMBER = 300

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def number_words(n):
    """12 -> "twelve", 123 -> "one hundred twenty three" (1-999)."""
    if not 0 < n < 1000:
        raise ValueError(n)
    words = []
    if n >= 100:
        words += [_ONES[n // 100], "hundred"]
        n %= 100
    if n >= 20:
        words.append(_TENS[n // 10])
        n %= 10
    if n:
        words.append(_ONES[n])
    return " ".join(words)


def parse_number(text):
    """"one hundred and twenty three" -> 123; None if it isn't a number."""
    words = [w for w in (text or "").split() if w != "and"]
    if not words:
        return None
    total, seen = 0, False
    for word in words:
        if word in _ONES[1:]:
            total += _ONES.index(word)
        elif word in _TENS[2:]:
            total += 10 * _TENS.index(word)
        elif word == "hundred" and 0 < total < 10:
            total *= 100
        else:
            return None
        seen = True
    return total if seen and total > 0 else None


def example_phrase(phrase, example=12):
    """How to show a phrase to people: "go to page number" -> "go to page 12"."""
    words = normalize_phrase(phrase).split()
    return " ".join(str(example) if w == NUMBER_SLOT else w for w in words)


def has_number(phrase):
    return NUMBER_SLOT in normalize_phrase(phrase).split()


def expand_numbers(phrase, maximum=MAX_NUMBER):
    """Every way to say a phrase with a number slot ("go to page one" ...)."""
    phrase = normalize_phrase(phrase)
    if not has_number(phrase):
        return [phrase]
    return [phrase.replace(NUMBER_SLOT, number_words(n), 1) for n in range(1, maximum + 1)]


def match_number(phrase, text):
    """The number in text if it's phrase with the slot filled in, else None."""
    words = normalize_phrase(phrase).split()
    if NUMBER_SLOT not in words:
        return None
    i = words.index(NUMBER_SLOT)
    before, after = " ".join(words[:i]), " ".join(words[i + 1:])
    if before and not (text == before or text.startswith(before + " ")):
        return None
    middle = text[len(before):].strip()
    if after:
        if not (middle == after or middle.endswith(" " + after)):
            return None
        middle = middle[: len(middle) - len(after)].strip()
    return parse_number(middle)


def normalize_phrase(text):
    """Lower-case words only: "Next Slide!" -> "next slide"."""
    words = re.findall(r"[a-z']+", (text or "").lower())
    return " ".join(words)


def is_voice_trigger(name):
    return isinstance(name, str) and name.startswith(VOICE_PREFIX)


def voice_trigger(phrase):
    return VOICE_PREFIX + normalize_phrase(phrase)


def phrase_of(trigger):
    return normalize_phrase(trigger[len(VOICE_PREFIX):]) if is_voice_trigger(trigger) else None


def check_phrase(phrase, existing=()):
    """(ok, message) for a phrase the user typed."""
    phrase = normalize_phrase(phrase)
    if not phrase:
        return False, "Type a few words to say, e.g. “next slide”."
    words = phrase.split()
    if len(words) > 5:
        return False, "Keep it short: five words or fewer."
    if len(words) == 1 and len(words[0]) < 4:
        return False, "That's very short and easy to mishear. Try two words."
    if phrase in {normalize_phrase(w) for w in WAKE_VARIANTS}:
        return False, "That's the wake phrase. Pick something else."
    if phrase in {normalize_phrase(p) for p in existing}:
        return False, "That phrase is already used."
    return True, ""


def grammar(phrases, wake_word=True):
    """
    The phrases the recogniser may return. Anything else comes back as
    [unk], so ordinary speech doesn't get forced into a command.
    """
    phrases = sorted({
        said for p in phrases if normalize_phrase(p) for said in expand_numbers(p)
    })
    allowed = set(phrases)
    if wake_word:
        for wake in WAKE_VARIANTS:
            allowed.add(wake)
            for phrase in phrases:
                allowed.add(f"{wake} {phrase}")
    return sorted(allowed) + [UNKNOWN]


@dataclass
class VoiceEvent:
    kind: str                     # "armed" | "command" | "ignored"
    trigger: Optional[str] = None
    text: str = ""
    reason: str = ""
    number: Optional[int] = None        # "go to page twelve" -> 12


class VoiceCommandMatcher:

    def __init__(
        self,
        phrases,
        wake_word=True,
        wake_window=DEFAULT_WAKE_WINDOW,
        min_confidence=DEFAULT_MIN_CONFIDENCE,
        clock=time.monotonic,
    ):
        self.phrases = {normalize_phrase(p) for p in phrases if normalize_phrase(p)}
        self.wake_word = wake_word
        self.wake_window = wake_window
        self.min_confidence = min_confidence
        self._clock = clock
        self._armed_until = 0.0

    @property
    def armed(self):
        return self._clock() < self._armed_until

    def _split_wake(self, text):
        """(had_wake_phrase, rest)."""
        for wake in sorted(WAKE_VARIANTS, key=len, reverse=True):
            if text == wake:
                return True, ""
            if text.startswith(wake + " "):
                return True, text[len(wake) + 1:]
        return False, text

    def process(self, text, confidence=1.0):
        """
        Feed one recognised utterance (and its average word confidence).
        Returns a VoiceEvent, or None for silence / unknown speech.
        """
        text = normalize_phrase(text.replace(UNKNOWN, " ") if text else "")
        if not text:
            return None

        if confidence < self.min_confidence:
            return VoiceEvent("ignored", text=text, reason=f"unsure ({confidence:.2f})")

        woke, rest = self._split_wake(text)

        if woke and not rest:
            if not self.wake_word:
                return VoiceEvent("ignored", text=text, reason="just the wake phrase")
            self._armed_until = self._clock() + self.wake_window
            return VoiceEvent("armed", text=text)

        number = None
        phrase = rest
        if rest not in self.phrases:
            for candidate in self.phrases:
                number = match_number(candidate, rest)
                if number is not None:
                    phrase = candidate
                    break
            else:
                return VoiceEvent("ignored", text=text, reason="not a command")

        if self.wake_word and not woke:
            if not self.armed:
                return VoiceEvent(
                    "ignored", text=text, reason=f'say "{WAKE_PHRASE}" first'
                )

        self._armed_until = 0.0
        return VoiceEvent("command", trigger=VOICE_PREFIX + phrase, text=text, number=number)


def average_confidence(result):
    """Average word confidence from a Vosk result dict (1.0 if absent)."""
    words = result.get("result") or []
    if not words:
        return 1.0
    return sum(w.get("conf", 1.0) for w in words) / len(words)
