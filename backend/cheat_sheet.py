"""
"What can I do?": the gestures, motions and phrases that work right now,
grouped the way the studio groups them. Shown by "Hey Wield, help" over
any app (frontend/components/cheat_sheet.py draws it).

    sheet(gesture_map, sections)  ->  [(section title, [(action name, [triggers])])]
"""

from backend.automation import browse_media
from backend.automation.events import friendly_action
from backend.voice.commands import is_voice_trigger, phrase_of

PRESENTATION_SECTIONS = [
    ("Slides", ["presentation_start", "presentation_next",
                "presentation_previous", "presentation_end"]),
]

BROWSE_SECTIONS = [(title, actions) for _key, title, _icon, _where, actions in browse_media.SECTIONS]

# Always available by voice (see GestureWorker.voice_events).
HELP_EVENTS = [
    {"name": "What can I do?", "gesture": "🎤 help", "action": "Help", "value": "show"},
    {"name": "What can I do?", "gesture": "🎤 what can i say", "action": "Help", "value": "show"},
    {"name": "What can I do?", "gesture": "🎤 show gestures", "action": "Help", "value": "show"},
]


def label(trigger, wake=True):
    """How a trigger reads on the sheet: 👍 Thumbs Up, Swipe left, “Hey Wield, …”."""
    if is_voice_trigger(trigger):
        phrase = phrase_of(trigger)
        return f"“Hey Wield, {phrase}”" if wake else f"“{phrase}”"
    return trigger


def sheet(gesture_map, sections, wake=True):
    """Sections with their actions and triggers; actions with none are left out."""

    by_action = {}
    for trigger, action in (gesture_map or {}).items():
        by_action.setdefault(action, []).append(trigger)

    result = []
    for title, actions in sections:
        rows = []
        for action in actions:
            triggers = by_action.get(action)
            if not triggers:
                continue
            # Gestures and motions first, then phrases.
            triggers = sorted(triggers, key=is_voice_trigger)
            rows.append((friendly_action(action), [label(t, wake) for t in triggers]))
        if rows:
            result.append((title, rows))
    return result


def sheet_for_events(events, title="This studio", wake=True):
    """A custom studio's events as one section."""
    rows = {}
    for event in events or []:
        trigger = event.get("gesture")
        if trigger:
            rows.setdefault(event.get("name") or "Event", []).append(label(trigger, wake))
    return [(title, list(rows.items()))] if rows else []
