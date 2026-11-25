"""
Actions that need a deliberate, held pose (e.g. closing a browser tab:
hold ✊ for about a second). Ordinary actions fire as soon as a pose is
recognised; these only fire after the pose has been held for the whole
time, and report their progress so a bar can fill up on screen.

    holds = HoldTracker(events)              # events with "hold_seconds"
    for name, progress, event in holds.update(pose, now):
        ...  # progress 0..1 for the bar; `event` is set when it fires

Letting go before the end cancels it (progress 0). After firing, the pose
must be released before it can fire again.
"""


class HoldTracker:

    def __init__(self, events):
        # trigger -> event (only events that need holding)
        self.events = {
            event["gesture"]: event
            for event in events or []
            if event.get("hold_seconds") and event.get("gesture")
        }
        self._pose = None
        self._since = 0.0
        self._fired = False
        self._last_progress = 0.0

    def __contains__(self, pose):
        return pose in self.events

    def update(self, pose, now):
        """
        Feed this frame's pose (or None). Returns a list of
        (event name, progress, event-to-run-or-None) updates.
        """

        updates = []

        if pose != self._pose:
            # Let go (or changed pose) before the end: cancel the bar.
            if self._pose in self.events and not self._fired and self._last_progress > 0:
                updates.append((self.events[self._pose]["name"], 0.0, None))
            self._pose = pose
            self._since = now
            self._fired = False
            self._last_progress = 0.0

        event = self.events.get(pose)
        if event is None or self._fired:
            return updates

        progress = min((now - self._since) / float(event["hold_seconds"]), 1.0)
        self._last_progress = progress

        if progress >= 1.0:
            self._fired = True
            updates.append((event["name"], 1.0, event))
        else:
            updates.append((event["name"], progress, None))

        return updates
