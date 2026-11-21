"""
The editable launch list used by Coding Studio and custom studios:
apps, files, folders and websites that open together with "Launch all".

    widget = LaunchListWidget(title, description)
    widget.set_items(items)
    widget.changed.connect(save)        # called with the new list

See backend/automation/launch_items.py for the item format.
"""

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.automation.launch_items import (
    KIND_ICONS,
    KIND_LABELS,
    KINDS,
    clean_items,
    launch_all,
    make_item,
)
from backend.paths import user_config_path
from frontend.styles.theme import (
    BG_DARK,
    BORDER,
    ERROR,
    ON_PRIMARY,
    OVERLAY_1,
    OVERLAY_2,
    PRIMARY,
    PRIMARY_HOVER,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
    SUCCESS,
    SURFACE,
    SURFACE_HOVER,
    TEXT_MUTED,
)


def _app_aliases():
    try:
        with open(user_config_path("apps.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


PRIMARY_BUTTON = f"""
    QPushButton {{
        background: {PRIMARY}; color: {ON_PRIMARY}; border: none;
        border-radius: 17px; padding: 0 18px; min-height: 34px;
        font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {PRIMARY_HOVER}; }}
    QPushButton:disabled {{ background: {OVERLAY_2}; color: {TEXT_MUTED}; }}
"""

SECONDARY_BUTTON = f"""
    QPushButton {{
        background: {OVERLAY_1}; color: {PRIMARY_TEXT};
        border: 1px solid {BORDER}; border-radius: 17px;
        padding: 0 16px; min-height: 34px; font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
"""


class LaunchListWidget(QFrame):

    changed = Signal(list)

    def __init__(self, title="Launch list", description="", parent=None):

        super().__init__(parent)
        self.setObjectName("LaunchList")
        self.setStyleSheet(f"""
            QFrame#LaunchList {{
                background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px;
            }}
            QLabel {{ background: transparent; border: none; }}
            QPushButton#RemoveItem {{
                background: transparent; color: {SECONDARY_TEXT};
                border: none; border-radius: 15px; font-size: 13px;
                padding: 0; margin: 0; min-width: 30px; min-height: 30px;
            }}
            QPushButton#RemoveItem:hover {{ background: {OVERLAY_2}; color: {ERROR}; }}
        """)

        self._items = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(2)

        heading = QLabel(title)
        heading.setStyleSheet(f"color: {PRIMARY_TEXT}; font-size: 15px; font-weight: 700;")
        text.addWidget(heading)

        if description:
            sub = QLabel(description)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
            text.addWidget(sub)

        header.addLayout(text, 1)

        self.add_button = QPushButton("+ Add")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setAccessibleName(f"Add to {title}")
        self.add_button.setStyleSheet(SECONDARY_BUTTON)
        self.add_button.clicked.connect(self._ask_for_item)
        header.addWidget(self.add_button, 0, Qt.AlignTop)

        self.launch_button = QPushButton("▶  Launch all")
        self.launch_button.setCursor(Qt.PointingHandCursor)
        self.launch_button.setStyleSheet(PRIMARY_BUTTON)
        self.launch_button.clicked.connect(self.launch)
        header.addWidget(self.launch_button, 0, Qt.AlignTop)

        layout.addLayout(header)

        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        layout.addLayout(self.rows)

        self.empty = QLabel(
            "Nothing here yet. Add the apps, files, folders and websites "
            "you open for this, then launch them all at once."
        )
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; padding: 6px 2px;")
        layout.addWidget(self.empty)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)

        self._refresh()

    # -----------------------------------------------------
    # ITEMS
    # -----------------------------------------------------

    def items(self):
        return [dict(item) for item in self._items]

    def set_items(self, items):
        self._items = clean_items(items)
        self._refresh()

    def add_item(self, item):
        self._items.append(item)
        self._refresh()
        self.changed.emit(self.items())
        self._show_status(f"Added {item['label']}.", SUCCESS)

    def remove_item(self, index):
        if 0 <= index < len(self._items):
            removed = self._items.pop(index)
            self._refresh()
            self.changed.emit(self.items())
            self._show_status(f"Removed {removed['label']}.", SECONDARY_TEXT)

    def _ask_for_item(self):
        dialog = AddLaunchItemDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.item:
            self.add_item(dialog.item)

    def _refresh(self):

        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()

        for index, item in enumerate(self._items):
            self.rows.addWidget(self._row(index, item))

        self.empty.setVisible(not self._items)
        self.launch_button.setEnabled(bool(self._items))

    def _row(self, index, item):

        row = QFrame()
        row.setObjectName("LaunchRow")
        row.setStyleSheet(f"""
            QFrame#LaunchRow {{ background: {SURFACE_HOVER}; border-radius: 12px; }}
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 8, 8)
        layout.setSpacing(12)

        icon = QLabel(KIND_ICONS[item["kind"]])
        icon.setStyleSheet("font-size: 16px;")
        layout.addWidget(icon)

        name = QLabel(item["label"])
        name.setStyleSheet(f"color: {PRIMARY_TEXT}; font-size: 13px; font-weight: 600;")
        layout.addWidget(name)

        detail = QLabel(f"{KIND_LABELS[item['kind']]} · {item['target']}")
        detail.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        detail.setToolTip(item["target"])
        detail.setMinimumWidth(40)
        layout.addWidget(detail, 1)

        remove = QPushButton("✕")
        remove.setFixedSize(30, 30)
        remove.setCursor(Qt.PointingHandCursor)
        remove.setToolTip(f"Remove {item['label']}")
        remove.setAccessibleName(f"Remove {item['label']}")
        remove.setObjectName("RemoveItem")
        remove.clicked.connect(lambda checked=False, i=index: self.remove_item(i))
        layout.addWidget(remove)

        return row

    # -----------------------------------------------------
    # LAUNCHING
    # -----------------------------------------------------

    def launch(self):

        if not self._items:
            return

        failures = launch_all(self._items, _app_aliases())

        if not failures:
            self._show_status(f"Opened {len(self._items)} item(s).", SUCCESS)
        else:
            self._show_status(
                f"{len(failures)} of {len(self._items)} didn't open. " + " · ".join(failures),
                ERROR,
            )

        return failures

    def _show_status(self, text, colour):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {colour}; font-size: 12px;")
        self.status.show()


class AddLaunchItemDialog(QDialog):
    """Pick what to open: an app, file, folder or website."""

    def __init__(self, parent=None):

        super().__init__(parent)
        self.setWindowTitle("Add to launch list")
        self.setMinimumWidth(460)
        self.item = None
        self.kind = "app"

        self.setStyleSheet(f"""
            QDialog {{ background: {SURFACE}; }}
            QLabel {{ color: {PRIMARY_TEXT}; background: transparent; }}
            QLineEdit {{
                background: {BG_DARK}; color: {PRIMARY_TEXT};
                border: 1px solid {BORDER}; border-radius: 10px;
                padding: 8px 12px; font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid {PRIMARY}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("What do you want to open?")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {PRIMARY_TEXT};")
        layout.addWidget(title)

        kinds = QHBoxLayout()
        kinds.setSpacing(8)
        self.kind_group = QButtonGroup(self)
        for kind in KINDS:
            button = QPushButton(f"{KIND_ICONS[kind]}  {KIND_LABELS[kind]}")
            button.setCheckable(True)
            button.setChecked(kind == self.kind)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("kind", kind)
            button.setStyleSheet(f"""
                QPushButton {{
                    background: {OVERLAY_1}; color: {PRIMARY_TEXT};
                    border: 1px solid {BORDER}; border-radius: 16px;
                    padding: 0 14px; min-height: 32px; font-size: 13px; font-weight: 600;
                }}
                QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
                QPushButton:checked {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: 1px solid {PRIMARY}; }}
            """)
            button.clicked.connect(lambda checked=False, k=kind: self.set_kind(k))
            self.kind_group.addButton(button)
            kinds.addWidget(button)
        kinds.addStretch()
        layout.addLayout(kinds)

        self.target_label = QLabel()
        self.target_label.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        layout.addWidget(self.target_label)

        target_row = QHBoxLayout()
        self.target = QLineEdit()
        self.target.setAccessibleName("What to open")
        target_row.addWidget(self.target, 1)
        self.browse = QPushButton("Browse…")
        self.browse.setCursor(Qt.PointingHandCursor)
        self.browse.setStyleSheet(SECONDARY_BUTTON)
        self.browse.clicked.connect(self._browse)
        target_row.addWidget(self.browse)
        layout.addLayout(target_row)

        name_label = QLabel("Name (optional)")
        name_label.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        layout.addWidget(name_label)
        self.label = QLineEdit()
        self.label.setAccessibleName("Name")
        self.label.setPlaceholderText("Shown in the list")
        layout.addWidget(self.label)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
        self.error.hide()
        layout.addWidget(self.error)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(SECONDARY_BUTTON)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        add = QPushButton("Add")
        add.setCursor(Qt.PointingHandCursor)
        add.setDefault(True)
        add.setStyleSheet(PRIMARY_BUTTON)
        add.clicked.connect(self.accept_item)
        buttons.addWidget(add)
        layout.addLayout(buttons)

        self.set_kind(self.kind)

    HINTS = {
        "app": ("App name or .exe", "e.g. code, chrome, steam, or browse to the .exe"),
        "file": ("File", "Browse to a file, e.g. your notes or a project"),
        "folder": ("Folder", "Browse to a folder, e.g. your projects or downloads"),
        "website": ("Web address", "e.g. github.com or https://chat.openai.com"),
    }

    def set_kind(self, kind):
        self.kind = kind
        for button in self.kind_group.buttons():
            button.setChecked(button.property("kind") == kind)
        label, placeholder = self.HINTS[kind]
        self.target_label.setText(label)
        self.target.setPlaceholderText(placeholder)
        self.browse.setVisible(kind != "website")
        self.error.hide()

    def _browse(self):
        if self.kind == "folder":
            path = QFileDialog.getExistingDirectory(self, "Choose a folder")
        elif self.kind == "app":
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose an app", "", "Apps (*.exe *.lnk *.bat *.cmd);;All files (*)"
            )
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose a file")
        if path:
            self.target.setText(path)

    def accept_item(self):
        try:
            self.item = make_item(self.kind, self.target.text(), self.label.text())
        except ValueError as e:
            self.error.setText(str(e))
            self.error.show()
            return
        self.accept()
