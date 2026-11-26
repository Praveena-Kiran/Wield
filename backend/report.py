"""
Reporting a problem by email (no GitHub account needed).

    url = mailto_url(error="TypeError: ...")     # opens the user's email app

The email is filled in with what helps fix things: the Wield and Windows
versions and, after a crash, the error. People are asked to attach their
log (backend/app_log.py), which never contains anything they said.
"""

import platform
from urllib.parse import quote

from backend.app_info import APP_NAME, VERSION

SUPPORT_EMAIL = "hipraveenakiran@gmail.com"

# Windows can drop very long mailto links: keep the error short.
MAX_ERROR = 600


def subject(error=None):
    return f"{APP_NAME} {VERSION}: {'it hit a problem' if error else 'a problem'}"


def body(error=None):
    lines = [
        "Hi! Something isn't working in Wield.",
        "",
        "What happened?",
        "",
        "",
        "What were you doing just before?",
        "",
        "",
        "(If you can, please attach the file wield.log: Wield has opened",
        "the folder it's in. Just drag it into this email.)",
        "",
        "---",
        f"{APP_NAME} {VERSION} on {platform.system()} {platform.release()}",
    ]
    if error:
        text = str(error).strip()
        if len(text) > MAX_ERROR:
            text = text[:MAX_ERROR] + "…"
        lines += ["Error:", text]
    return "\n".join(lines)


def mailto_url(error=None, to=SUPPORT_EMAIL):
    return (
        f"mailto:{to}?subject={quote(subject(error))}"
        f"&body={quote(body(error))}"
    )
