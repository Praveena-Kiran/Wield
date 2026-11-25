"""
Who else needs the webcam right now (Home's foggy window, the gesture
recorder and tester). Only one thing can use a webcam at a time, so
hands-free mode steps aside while any of these has it, and comes back
when they're done.

    claims.take(owner)      # before opening the camera (UI thread)
    claims.give_back(owner) # after closing it
    claims.subscribe(fn)    # fn(in_use: bool), called on every change
"""

_owners = set()
_listeners = []


def take(owner):
    _owners.add(id(owner))
    _notify()


def give_back(owner):
    if id(owner) in _owners:
        _owners.discard(id(owner))
        _notify()


def in_use():
    return bool(_owners)


def subscribe(listener):
    _listeners.append(listener)


def _notify():
    for listener in list(_listeners):
        try:
            listener(in_use())
        except Exception as e:  # noqa: BLE001 - a listener mustn't break the camera
            print(f"⚠ Camera claim listener failed: {e}")
