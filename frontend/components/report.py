"""
"Email us about it": opens a filled-in email (backend/report.py), shows
the log file so it's easy to attach, and copies the address in case no
email app opens.
"""

import os
import platform
import subprocess

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication

from backend.report import SUPPORT_EMAIL, mailto_url


def report_problem(error=None):
    """Open the email and the log's folder. Returns the address."""

    QDesktopServices.openUrl(QUrl(mailto_url(error), QUrl.ParsingMode.TolerantMode))
    _show_log()
    try:
        QGuiApplication.clipboard().setText(SUPPORT_EMAIL)
    except Exception:  # noqa: BLE001
        pass
    return SUPPORT_EMAIL


def _show_log():
    """Open the folder with wield.log selected (so it can be dragged in)."""

    try:
        from backend.app_log import log_path
        path = log_path()
        if not os.path.exists(path):
            open(path, "a").close()
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
    except Exception:  # noqa: BLE001 - the email still opens
        pass
