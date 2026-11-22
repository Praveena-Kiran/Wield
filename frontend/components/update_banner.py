"""
The "a new version is available" strip under the title bar, and the
background thread that asks GitHub (backend/updates.py).

    banner = UpdateBanner()
    banner.show_update({"version": "1.2.0", "url": ..., "notes": ...})

Download opens the release page in the browser (updating stays manual:
download, close Wield, replace the folder; settings are kept in the data
folder). "Not now" hides it until the next version.
"""

import webbrowser

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from backend.app_info import APP_NAME
from frontend.styles.theme import (
    BORDER,
    ON_PRIMARY,
    PRIMARY,
    PRIMARY_HOVER,
    PRIMARY_MUTED,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
)


class UpdateChecker(QObject):
    """Runs backend.updates.check off the UI thread."""

    found = Signal(object)        # the release dict, or None

    def __init__(self, force=False):
        super().__init__()
        self.force = force

    @Slot()
    def run(self):
        try:
            from backend.settings.settings_manager import SettingsManager
            from backend import updates
            result = updates.check(SettingsManager(), force=self.force)
        except Exception:  # noqa: BLE001 - never bother the user about this
            result = None
        self.found.emit(result)


class UpdateBanner(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UpdateBanner")
        self.release = None
        self.setStyleSheet(f"""
            QFrame#UpdateBanner {{
                background: {PRIMARY_MUTED};
                border-bottom: 1px solid {BORDER};
            }}
            QLabel {{ background: transparent; border: none; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 14, 8)
        layout.setSpacing(12)

        self.text = QLabel()
        self.text.setStyleSheet(f"color: {PRIMARY_TEXT}; font-size: 13px; font-weight: 600;")
        layout.addWidget(self.text)

        self.detail = QLabel("Your settings and gestures carry over.")
        self.detail.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        layout.addWidget(self.detail, 1)

        self.download = QPushButton("Download")
        self.download.setCursor(Qt.PointingHandCursor)
        self.download.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY}; color: {ON_PRIMARY}; border: none;
                border-radius: 14px; padding: 0 16px; min-height: 28px;
                font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {PRIMARY_HOVER}; }}
        """)
        self.download.clicked.connect(self._open)
        layout.addWidget(self.download)

        self.later = QPushButton("Not now")
        self.later.setCursor(Qt.PointingHandCursor)
        self.later.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {SECONDARY_TEXT}; border: none;
                padding: 0 10px; min-height: 28px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ color: {PRIMARY_TEXT}; }}
        """)
        self.later.clicked.connect(self.skip)
        layout.addWidget(self.later)

        self.hide()

    def show_update(self, release):
        if not release:
            return
        self.release = release
        self.text.setText(f"{APP_NAME} {release['version']} is available.")
        if release.get("notes"):
            self.setToolTip("What's new:\n\n" + release["notes"])
        self.show()

    def _open(self):
        if self.release:
            webbrowser.open(self.release["url"])

    def skip(self):
        """Hide, and don't mention this version again."""
        if self.release:
            try:
                from backend.settings.settings_manager import SettingsManager
                SettingsManager().set_setting("update_skipped", self.release["version"])
            except Exception:  # noqa: BLE001
                pass
        self.hide()
