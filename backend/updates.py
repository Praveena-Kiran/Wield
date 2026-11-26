"""
Checks GitHub for a newer Wield release, so people hear about updates.

    latest = fetch_latest()            # {"version", "url", "notes"} or None
    if is_newer(latest["version"], VERSION): ...

It only asks GitHub's public "latest release" API for this repository,
with a generic user agent and nothing about the user, when Wield starts and
every few hours while Wield runs (see due()). No internet or any error
simply means "no update found", and it tries again soon.
Updating stays manual: the app offers a Download button that opens the
release page.

Settings (settings.json):
    update_check          bool   check automatically (default on)
    update_last_check     float  when we last asked (epoch seconds)
    update_skipped        str    a version the user said "not now" to
    update_notified       str    the version a Windows notification was shown for
"""

import json
import re
import time
import urllib.request

from backend.app_info import REPO_URL, VERSION

API_URL = REPO_URL.replace("https://github.com/", "https://api.github.com/repos/") + "/releases/latest"
RELEASES_URL = REPO_URL + "/releases/latest"
# Wield often runs for days (in the tray), so it looks again every few
# hours, not just when it starts.
CHECK_EVERY_SECONDS = 4 * 60 * 60
TIMEOUT_SECONDS = 6


def parse_version(text):
    """'v1.2.0' / '1.2' / '1.2.0-beta' -> (1, 2, 0), or None."""

    match = re.match(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(text or ""))
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def is_newer(candidate, current=VERSION):
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b


def due(last_check, now=None):
    """True if it's been CHECK_EVERY_SECONDS since the last check (or there wasn't one)."""
    now = time.time() if now is None else now
    try:
        return now - float(last_check or 0) >= CHECK_EVERY_SECONDS
    except (TypeError, ValueError):
        return True


def _download(url):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Wield-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_latest(download=_download):
    """
    The latest published release as {"version", "url", "notes"}, or None
    when it can't be found (offline, rate-limited, no releases, ...).
    Drafts and pre-releases are never returned by GitHub's /latest.
    """

    try:
        data = download(API_URL)
    except Exception:  # noqa: BLE001 - offline etc. is not an error for the user
        return None

    if not isinstance(data, dict):
        return None

    version = str(data.get("tag_name") or "").lstrip("vV")
    if parse_version(version) is None:
        return None

    notes = str(data.get("body") or "").strip()
    return {
        "version": version,
        "url": data.get("html_url") or RELEASES_URL,
        "notes": notes[:600],
    }


def check(settings, now=None, download=_download, force=False):
    """
    The update to tell the user about, or None.

    `settings` is a SettingsManager-like object (get_setting / set_setting).
    Respects the on/off switch, the once-a-day limit and a skipped version,
    unless `force` (the "Check now" button).
    """

    now = time.time() if now is None else now

    if not force:
        if settings.get_setting("update_check") is False:
            return None
        if not due(settings.get_setting("update_last_check"), now):
            return None

    latest = fetch_latest(download)
    if latest is None:
        # Offline or GitHub busy: not a real check, so try again next time
        # instead of waiting hours.
        return None
    settings.set_setting("update_last_check", now)

    if not is_newer(latest["version"]):
        return None

    if not force and settings.get_setting("update_skipped") == latest["version"]:
        return None

    return latest


def should_notify(settings, release):
    """Show a Windows notification for this release? Once per version."""
    return bool(release) and settings.get_setting("update_notified") != release["version"]


def mark_notified(settings, release):
    settings.set_setting("update_notified", release["version"])
