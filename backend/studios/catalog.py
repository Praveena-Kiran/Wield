"""
Which studios Wield always has, and which are optional.

    CORE        Presentation, Browse & Media and Gesture Studio: always
                there, can't be removed
    optional    the other studios Wield comes with (Coding, Gaming): can
                be removed, and brought back from Settings
    your own    studios you made: can be removed (for good)

    removable(title)      -> bool
    remove(title)         -> True if it was removed
    missing_optional()    -> titles of optional studios that were removed
    restore_optional()    -> titles brought back
"""

import json
import os

from backend.paths import DEFAULT_CONFIG_DIR, user_config_path

CORE = ("Presentation Studio", "Browse & Media Studio", "Gesture Studio")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            studios = json.load(f)
    except (OSError, ValueError):
        return []
    return [s for s in studios if isinstance(s, dict) and s.get("title")] if isinstance(studios, list) else []


def _write(studios):
    with open(user_config_path("studios.json"), "w", encoding="utf-8") as f:
        json.dump(studios, f, indent=4, ensure_ascii=False)


def default_studios():
    """The studios Wield comes with, in order."""
    return _read(os.path.join(DEFAULT_CONFIG_DIR, "studios.json"))


def user_studios():
    return _read(user_config_path("studios.json"))


def is_core(title):
    return (title or "").strip().lower() in {c.lower() for c in CORE}


def is_optional(title):
    """One of the studios Wield comes with, but not a core one."""
    titles = {s["title"].lower() for s in default_studios()}
    return not is_core(title) and (title or "").strip().lower() in titles


def removable(title):
    return not is_core(title)


def remove(title):
    """Remove a studio by title. Core studios are never removed."""

    if not removable(title):
        return False

    studios = user_studios()
    kept = [s for s in studios if s["title"].strip().lower() != title.strip().lower()]
    if len(kept) == len(studios):
        return False

    _write(kept)
    return True


def missing_optional():
    have = {s["title"].lower() for s in user_studios()}
    return [s["title"] for s in default_studios()
            if not is_core(s["title"]) and s["title"].lower() not in have]


def restore_optional():
    """Put removed optional studios back where they were in the defaults."""

    studios = user_studios()
    have = {s["title"].lower() for s in studios}
    restored = []

    defaults = default_studios()
    for i, studio in enumerate(defaults):
        if is_core(studio["title"]) or studio["title"].lower() in have:
            continue
        # After the default that came before it, if the user still has it.
        index = len(studios)
        for previous in reversed(defaults[:i]):
            match = next((j for j, s in enumerate(studios)
                          if s["title"].lower() == previous["title"].lower()), None)
            if match is not None:
                index = match + 1
                break
        studios.insert(index, dict(studio))
        have.add(studio["title"].lower())
        restored.append(studio["title"])

    if restored:
        _write(studios)
    return restored
