"""
Browse & Media Studio: scroll, control videos and music, and manage
browser tabs without touching the mouse.

Like Presentation Studio, every action's gestures, motions and voice
phrases can be changed (the same trigger editor), and the camera only
turns on with "Start". It keeps running while you switch to your browser,
Word or a PDF, because that's where the gestures are used.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from backend.automation import browse_media
from backend.profile_manager import ProfileManager
from backend.settings import gesture_settings
from frontend.components.trigger_editor import ActionTriggerEditor
from frontend.pages.studio_page import StudioPage
from frontend.styles.theme import (
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
    TEXT_MUTED,
)


def _recorded_names():
    try:
        from backend.gestures.custom_gestures import CustomGestureStore
        gestures = CustomGestureStore().names()
    except Exception:
        gestures = []
    try:
        from backend.gestures.motions import MotionStore
        motions = MotionStore().names()
    except Exception:
        motions = []
    return gestures, motions


class BrowsePage(StudioPage):

    TITLE = "Browse & Media Studio"

    # Turn the camera (+ mic) on or off; MainWindow answers with set_listening().
    listening_requested = Signal(bool)

    # Gestures changed: a running camera should reload them.
    bindings_changed = Signal()

    # "Record your own" link.
    open_gesture_studio = Signal()

    def __init__(self, parent=None):

        super().__init__(
            self.TITLE,
            "Scroll pages, control videos and music, and switch browser tabs "
            "with your hands or voice.",
            parent,
        )

        self.listening = False
        self.profile = ProfileManager()
        self.profile.load(browse_media.PROFILE_NAME)
        # Profiles saved before an action existed get its default triggers.
        browse_media.add_missing_defaults(self.profile)
        self.settings = gesture_settings.load()

        self.setStyleSheet(self.styleSheet() + f"""
            QFrame#Card {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
            QFrame#Card QLabel {{ background: transparent; border: none; }}
            QCheckBox {{ color: {PRIMARY_TEXT}; font-size: 13px; spacing: 10px; background: transparent; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px; border-radius: 5px;
                border: 1px solid {BORDER}; background: {SURFACE};
            }}
            QCheckBox::indicator:checked {{ background: {PRIMARY}; border: 1px solid {PRIMARY}; }}
        """)

        self.content_layout.addWidget(self._build_session())
        self.content_layout.addWidget(self._build_scrolling())
        self.content_layout.addWidget(self._build_controls())
        self.content_layout.addStretch()

        self.status_label.hide()
        self.set_listening(False)

    # ---------------------------------------------------------
    # Layout
    # ---------------------------------------------------------

    def _card(self):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        return frame, layout

    def _label(self, text, color=PRIMARY_TEXT, size=13, weight=400):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {weight};")
        return label

    def _button(self, text, primary=False):
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        if primary:
            style = f"""
                QPushButton {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: none;
                    border-radius: 18px; padding: 0 20px; min-height: 36px;
                    font-size: 13px; font-weight: 700; }}
                QPushButton:hover {{ background: {PRIMARY_HOVER}; }}
            """
        else:
            style = f"""
                QPushButton {{ background: {OVERLAY_1}; color: {PRIMARY_TEXT};
                    border: 1px solid {BORDER}; border-radius: 18px; padding: 0 18px;
                    min-height: 36px; font-size: 13px; font-weight: 600; }}
                QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
            """
        button.setStyleSheet(style)
        return button

    def _build_session(self):
        frame, layout = self._card()

        row = QHBoxLayout()
        row.setSpacing(12)
        self.camera_pill = QLabel()
        row.addWidget(self.camera_pill)
        self.status = self._label("", SECONDARY_TEXT, 13)
        row.addWidget(self.status, 1)
        self.start_button = self._button("▶  Start", primary=True)
        self.start_button.clicked.connect(lambda: self.listening_requested.emit(not self.listening))
        row.addWidget(self.start_button)
        layout.addLayout(row)

        layout.addWidget(self._label(
            "Start, then switch to your browser, a PDF or Word. Wield keeps "
            "watching in the background; it only types browser shortcuts "
            "when a browser (Chrome, Edge, Firefox or Brave) is in front.",
            TEXT_MUTED, 12,
        ))
        return frame

    def _build_scrolling(self):
        frame, layout = self._card()
        layout.addWidget(self._label("Scrolling", PRIMARY_TEXT, 16, 700))
        layout.addWidget(self._label(
            "Hold your scroll pose (✌️ by default) and move your hand up or "
            "down from where you started: above scrolls up, below scrolls "
            "down, back to the middle stops. Keep holding to keep scrolling.",
            SECONDARY_TEXT, 13,
        ))

        speeds = QHBoxLayout()
        speeds.setSpacing(8)
        speeds.addWidget(self._label("Speed", SECONDARY_TEXT, 12))
        self.speed_group = QButtonGroup(self)
        for value in gesture_settings.SCROLL_SPEEDS:
            button = QPushButton(value.title())
            button.setCheckable(True)
            button.setChecked(self.settings["browse_scroll_speed"] == value)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("choice", value)
            button.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {SECONDARY_TEXT};
                    border: 1px solid {BORDER}; border-radius: 15px;
                    padding: 0 14px; min-height: 30px; font-size: 12px; font-weight: 600; }}
                QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
                QPushButton:checked {{ background: {OVERLAY_2}; color: {PRIMARY_TEXT};
                    border: 1px solid {PRIMARY}; }}
            """)
            button.clicked.connect(lambda checked=False, v=value: self._save("browse_scroll_speed", v))
            self.speed_group.addButton(button)
            speeds.addWidget(button)
        speeds.addSpacing(16)

        self.by_height = QCheckBox("Hand height sets the speed (further = faster)")
        self.by_height.setChecked(self.settings["browse_scroll_by_height"])
        self.by_height.toggled.connect(lambda on: self._save("browse_scroll_by_height", bool(on)))
        speeds.addWidget(self.by_height)
        speeds.addStretch()
        layout.addLayout(speeds)
        return frame

    def _build_controls(self):
        frame, layout = self._card()
        layout.addWidget(self._label("Your gestures", PRIMARY_TEXT, 16, 700))
        layout.addWidget(self._label(
            "Change any of them: add a gesture, a motion or a voice phrase, or "
            "remove one with ✕.", TEXT_MUTED, 12,
        ))

        names = _recorded_names
        self.editor = ActionTriggerEditor(
            self.profile,
            list(browse_media.ACTIONS),
            custom_gestures=lambda: names()[0],
            custom_motions=lambda: names()[1],
        )
        self.editor.changed.connect(self.bindings_changed.emit)
        layout.addWidget(self.editor)

        record = QPushButton("Record your own gesture or motion in Gesture Studio  →")
        record.setCursor(Qt.PointingHandCursor)
        record.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {PRIMARY};
                font-size: 12px; font-weight: 600; text-align: left; padding: 4px 2px; }}
            QPushButton:hover {{ color: {PRIMARY_HOVER}; }}
        """)
        record.clicked.connect(self.open_gesture_studio.emit)
        layout.addWidget(record, 0, Qt.AlignLeft)
        return frame

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    def refresh_bindings(self):
        self.profile.load(browse_media.PROFILE_NAME)
        self.editor.refresh()

    def _save(self, key, value):
        gesture_settings.save(key, value)
        self.settings[key] = value
        self.bindings_changed.emit()        # the camera picks up the new speed

    def set_listening(self, state):
        """False (off), "starting" or True (on)."""
        self.listening = state is not False
        voice = gesture_settings.load()["voice_enabled"]
        devices = "Camera & mic" if voice else "Camera"

        if state is True:
            text, colour = f"●  {devices} on", ERROR
            hint = "Listening. Switch to your browser or document."
        elif state == "starting":
            text, colour, hint = "●  Starting camera…", SECONDARY_TEXT, ""
        else:
            text, colour = f"○  {devices} off", TEXT_MUTED
            hint = "Press Start when you're ready."

        self.camera_pill.setText(text)
        self.camera_pill.setStyleSheet(f"""
            color: {colour}; font-size: 13px; font-weight: 700;
            background: {OVERLAY_1}; border: 1px solid {BORDER};
            border-radius: 15px; padding: 5px 14px;
        """)
        self.start_button.setText("■  Stop" if self.listening else "▶  Start")
        self.set_status(hint, SECONDARY_TEXT)

    def set_status(self, text, colour=SUCCESS):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {colour}; font-size: 13px; font-weight: 500;")
