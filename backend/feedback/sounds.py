"""
Soft sound cues, so people know what Wield did without looking at it
(e.g. while a slideshow fills the screen, or for people with low vision).

    armed     rising two-note chime   Wield is now listening for a command
    action    single short note       an action ran
    disarmed  falling two-note chime  Wield stopped listening
    error     low note                something didn't work

The tones are generated once as small WAV files in the user's data
folder (no audio assets to ship) and played asynchronously with
Windows' built-in winsound. On other systems they are silently skipped.
"""

import math
import os
import struct
import time
import wave

from backend.paths import user_data_dir

SAMPLE_RATE = 22050
VOLUME = 0.07          # very quiet: a gentle "tink", never a beep
ATTACK = 0.008         # seconds to reach full volume (no click)
GAP = 0.03             # seconds between two notes

# Version of the sounds: part of the file names, so new sounds replace
# the files made by an older Wield.
SOUND_VERSION = 2

# name -> [(frequency Hz, seconds), ...]. Lower, rounder notes than a
# beep; each one rings out and fades like a small bell.
CUES = {
    "armed": [(523.25, 0.16), (659.25, 0.26)],      # C5 then E5, rising
    "action": [(587.33, 0.20)],                     # one soft D5
    "disarmed": [(659.25, 0.16), (523.25, 0.26)],   # E5 then C5, falling
    "error": [(293.66, 0.30)],                      # a low, soft D4
}

MIN_GAP = 0.12  # seconds between two plays of the same cue


def tone_frames(notes, rate=SAMPLE_RATE, volume=VOLUME, attack=ATTACK):
    """
    16-bit mono PCM bytes for a list of (frequency, seconds) notes: a soft
    bell-like tone (the note plus a quieter octave above), a quick gentle
    attack and a long fade to silence.
    """
    frames = bytearray()
    attack_n = max(1, int(attack * rate))
    for frequency, seconds in notes:
        n = int(seconds * rate)
        for i in range(n):
            t = i / rate
            rise = min(1.0, i / attack_n)
            decay = math.exp(-5.0 * t / seconds)          # rings out
            tail = min(1.0, (n - 1 - i) / attack_n)        # no click at the end
            tone = (math.sin(2 * math.pi * frequency * t)
                    + 0.25 * math.sin(2 * math.pi * 2 * frequency * t)) / 1.25
            frames += struct.pack("<h", int(volume * rise * decay * tail * tone * 32767))
        frames += b"\x00\x00" * int(GAP * rate)
    return bytes(frames)


def write_wav(path, notes):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(tone_frames(notes))


def _winsound_player(path):
    import winsound
    winsound.PlaySound(
        path,
        winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
    )


def default_player():
    try:
        import winsound  # noqa: F401  (Windows only)
    except ImportError:
        return None
    return _winsound_player


class SoundCues:

    def __init__(self, folder=None, player="default", clock=time.monotonic):
        self.folder = folder or os.path.join(user_data_dir(), "sounds")
        self.player = default_player() if player == "default" else player
        self.enabled = True
        self._clock = clock
        self._last = {}

    def path(self, cue):
        return os.path.join(self.folder, f"{cue}-v{SOUND_VERSION}.wav")

    def ensure_files(self):
        os.makedirs(self.folder, exist_ok=True)
        for cue, notes in CUES.items():
            old = os.path.join(self.folder, f"{cue}.wav")      # an older Wield's
            if os.path.exists(old):
                try:
                    os.remove(old)
                except OSError:
                    pass
            if not os.path.exists(self.path(cue)):
                write_wav(self.path(cue), notes)

    def play(self, cue):
        """Play a cue if sounds are on. Never raises."""
        if not self.enabled or self.player is None or cue not in CUES:
            return False

        now = self._clock()
        if now - self._last.get(cue, -1e9) < MIN_GAP:
            return False
        self._last[cue] = now

        try:
            self.ensure_files()
            self.player(self.path(cue))
            return True
        except Exception as e:
            print(f"⚠ Could not play sound '{cue}': {e}")
            return False
