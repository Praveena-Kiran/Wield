"""
A studio's launch list: the apps, files, folders and websites it opens in
one go ("Launch all"). Users add and remove items in Coding Studio and in
every custom studio (Gaming Studio included); the list is saved with the
studio.

An item is a small dict:

    {"kind": "app" | "file" | "folder" | "website",
     "target": "code" | "C:\\path\\to\\thing" | "github.com",
     "label": "VS Code"}

Coding Studio keeps its list as the steps of "coding_flow" in flows.json
(so older versions keep working); to_flow_steps / from_flow_steps convert.
"""

import os
import platform
import subprocess
import webbrowser

from backend.automation.app_launcher import AppLaunchError, launch_app


KINDS = ("app", "file", "folder", "website")

KIND_LABELS = {
    "app": "App",
    "file": "File",
    "folder": "Folder",
    "website": "Website",
}

KIND_ICONS = {
    "app": "💻",
    "file": "📄",
    "folder": "📁",
    "website": "🌐",
}


class LaunchError(Exception):
    pass


# ---------------------------------------------------------------------
# ITEMS
# ---------------------------------------------------------------------

def default_label(kind, target):
    """A readable name when the user doesn't give one."""

    target = (target or "").strip()

    if kind == "website":
        name = target.split("://", 1)[-1].split("/", 1)[0]
        return name[4:] if name.startswith("www.") else name

    if kind in ("file", "folder", "app") and ("\\" in target or "/" in target):
        # Split on both separators: a Windows path typed anywhere.
        name = target.rstrip("\\/").replace("\\", "/").rsplit("/", 1)[-1] or target
        if kind == "app" and name.lower().endswith(".exe"):
            name = name[:-4]
        return name

    return target


def make_item(kind, target, label=""):
    """A clean item, or ValueError with a message for the user."""

    kind = (kind or "").strip().lower()
    target = (target or "").strip().strip('"').strip()
    label = (label or "").strip()

    if kind not in KINDS:
        raise ValueError("Choose what to open: an app, file, folder or website.")

    if not target:
        raise ValueError({
            "app": "Type an app name, like code or chrome, or browse to its .exe.",
            "file": "Browse to the file to open.",
            "folder": "Browse to the folder to open.",
            "website": "Type a web address, like github.com.",
        }[kind])

    if kind == "website" and " " in target:
        raise ValueError("A web address can't contain spaces.")

    return {"kind": kind, "target": target, "label": label or default_label(kind, target)}


def clean_items(items):
    """Valid items from stored data; anything broken is skipped."""

    result = []

    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            result.append(make_item(item.get("kind"), item.get("target"), item.get("label")))
        except ValueError:
            continue

    return result


# ---------------------------------------------------------------------
# FLOW STEPS (Coding Studio)
# ---------------------------------------------------------------------

def from_flow_steps(steps):
    """flows.json steps -> items (steps that aren't launchable are skipped)."""

    items = []

    for step in steps or []:

        if not isinstance(step, dict):
            continue

        if step.get("type") == "website":
            kind, target = "website", step.get("url")
        elif step.get("type") == "launch":
            kind, target = step.get("kind") or "app", step.get("target")
        else:
            continue

        try:
            items.append(make_item(kind, target, step.get("label")))
        except ValueError:
            continue

    return items


def to_flow_steps(items):
    steps = []
    for item in clean_items(items):
        if item["kind"] == "website":
            steps.append({"type": "website", "url": item["target"], "label": item["label"]})
        else:
            steps.append({
                "type": "launch",
                "kind": item["kind"],
                "target": item["target"],
                "label": item["label"],
            })
    return steps


# ---------------------------------------------------------------------
# LAUNCHING
# ---------------------------------------------------------------------

def _open_path(path):

    if not os.path.exists(path):
        raise LaunchError(f"Couldn't find {path}. It may have been moved or deleted.")

    system = platform.system()

    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def launch_item(item, app_aliases=None):
    """Open one item; raises LaunchError with a friendly message."""

    kind, target = item["kind"], item["target"]

    if kind == "website":
        url = target if "://" in target else "https://" + target
        if not webbrowser.open(url):
            raise LaunchError(f"Couldn't open {url} in your browser.")
        return

    if kind in ("file", "folder"):
        path = os.path.expandvars(os.path.expanduser(target))
        if kind == "folder" and os.path.exists(path) and not os.path.isdir(path):
            raise LaunchError(f"{target} is a file, not a folder.")
        _open_path(path)
        return

    try:
        launch_app(target, app_aliases)
    except AppLaunchError as e:
        raise LaunchError(str(e)) from e


def launch_all(items, app_aliases=None, launch=launch_item):
    """
    Open every item; one that fails doesn't stop the rest.
    Returns a list of "label: reason" strings for the ones that failed.
    """

    failures = []

    for item in clean_items(items):
        try:
            launch(item, app_aliases)
        except Exception as e:  # noqa: BLE001 - report and carry on
            failures.append(f"{item['label']}: {e}")

    return failures
