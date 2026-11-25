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
    QSizePolicy,
    QWidget,
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

    # "What can I do?" (the cheat sheet shown over any app).
    help_requested = Signal()

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
            QFrame#Section {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
            QFrame#Section[open="true"] {{ border: 1px solid {PRIMARY}; }}
            QFrame#Section QLabel {{ background: transparent; border: none; }}
            QWidget#SectionBody {{ background: transparent; }}
            QPushButton#SectionHead {{
                background: transparent; border: none; border-radius: 16px; text-align: left;
            }}
            QPushButton#SectionHead:hover {{ background: {OVERLAY_1}; }}
            QPushButton#SettingsLink {{
                background: transparent; border: none; color: {SECONDARY_TEXT};
                font-size: 12px; font-weight: 600; padding: 2px 0;
            }}
            QPushButton#SettingsLink:hover {{ color: {PRIMARY}; }}
            QFrame#Section QLabel#SectionBadge, QFrame#Card QLabel#SectionBadge {{
                background: {OVERLAY_2}; color: {PRIMARY}; border-radius: 19px;
                font-size: 17px; font-weight: 700;
            }}
        """)

        self.editors = {}
        self.sections = {}

        self.content_layout.addWidget(self._build_session())
        for section in browse_media.SECTIONS:
            self.content_layout.addWidget(self._build_section(*section))
        self.content_layout.addWidget(self._record_link(), 0, Qt.AlignLeft)
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
        help_button = self._button("What can I do?")
        help_button.setToolTip("Show your gestures and phrases on screen. Or say “Hey Wield, help”.")
        help_button.clicked.connect(self.help_requested.emit)
        row.addWidget(help_button)
        self.start_button = self._button("▶  Start", primary=True)
        self.start_button.clicked.connect(lambda: self.listening_requested.emit(not self.listening))
        row.addWidget(self.start_button)
        layout.addLayout(row)

        return frame

    def _scroll_options(self):
        """Speed pills and the hand-height switch (Scroll section)."""

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._label("Speed", SECONDARY_TEXT, 12))
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
            row.addWidget(button)
        row.addSpacing(16)

        self.by_height = QCheckBox("Hold-and-move: further from the start = faster")
        self.by_height.setChecked(self.settings["browse_scroll_by_height"])
        self.by_height.toggled.connect(lambda on: self._save("browse_scroll_by_height", bool(on)))
        row.addWidget(self.by_height)
        row.addStretch()
        return row

    def _build_section(self, key, title, icon, where, actions):
        """
        A section that opens and closes: closed, one line says what it does
        now; open, its actions in compact rows (empty ones tucked away).
        Only one section is open at a time.
        """

        frame = QFrame()
        frame.setObjectName("Section")
        frame.setProperty("section", key)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header: the whole line is the button.
        head = QPushButton()
        head.setObjectName("SectionHead")
        head.setCursor(Qt.PointingHandCursor)
        head.setAccessibleName(f"{title}: show or hide")
        head.setMinimumHeight(64)
        line = QHBoxLayout(head)
        line.setContentsMargins(16, 10, 18, 10)
        line.setSpacing(14)

        badge = QLabel(icon)
        badge.setObjectName("SectionBadge")
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignCenter)
        line.addWidget(badge)

        name = QLabel(title)
        name.setFixedWidth(190)
        name.setStyleSheet(f"color: {PRIMARY_TEXT}; font-size: 15px; font-weight: 700;")
        line.addWidget(name)

        summary = QLabel()
        summary.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        line.addWidget(summary, 1)

        chevron = QLabel("▸")
        chevron.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 14px;")
        line.addWidget(chevron)
        for label in (badge, name, summary, chevron):
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        outer.addWidget(head)

        # Body: where it works, (scroll settings), the actions.
        body = QWidget()
        body.setObjectName("SectionBody")
        inner = QVBoxLayout(body)
        inner.setContentsMargins(68, 0, 18, 14)
        inner.setSpacing(8)
        inner.addWidget(self._label(where, TEXT_MUTED, 12))

        if key == "scroll":
            settings_link = QPushButton("⚙  Scroll speed")
            settings_link.setObjectName("SettingsLink")
            settings_link.setCursor(Qt.PointingHandCursor)
            options = QWidget()
            options.setLayout(self._scroll_options())
            options.hide()
            settings_link.clicked.connect(lambda: options.setVisible(not options.isVisible()))
            inner.addWidget(settings_link, 0, Qt.AlignLeft)
            inner.addWidget(options)
            self.scroll_options = options

        names = _recorded_names
        editor = ActionTriggerEditor(
            self.profile,
            list(actions),
            custom_gestures=lambda: names()[0],
            custom_motions=lambda: names()[1],
            compact=True,
            hide_empty=True,
        )
        editor.changed.connect(lambda k=key: self._on_triggers_changed(k))
        self.editors[key] = editor
        inner.addWidget(editor)
        body.hide()
        outer.addWidget(body)

        self.sections[key] = (frame, body, chevron, summary, actions)
        head.clicked.connect(lambda checked=False, k=key: self.toggle_section(k))
        self._update_summary(key)
        return frame

    def toggle_section(self, key):
        """Open a section (closing the others), or close it if it's open."""
        opening = not self.sections[key][1].isVisible()
        for other, (frame, body, chevron, _summary, _actions) in self.sections.items():
            open_now = opening and other == key
            body.setVisible(open_now)
            chevron.setText("▾" if open_now else "▸")
            frame.setProperty("open", open_now)
            frame.style().unpolish(frame)
            frame.style().polish(frame)

    def _update_summary(self, key):
        _frame, _body, _chevron, summary, actions = self.sections[key]
        text = browse_media.section_summary(self.profile.get_gesture_map(), actions)
        summary.setText(text)
        summary.setToolTip(text)

    def _record_link(self):
        record = QPushButton("Record your own gesture or motion in Gesture Studio  →")
        record.setCursor(Qt.PointingHandCursor)
        record.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {PRIMARY};
                font-size: 12px; font-weight: 600; text-align: left; padding: 4px 2px; }}
            QPushButton:hover {{ color: {PRIMARY_HOVER}; }}
        """)
        record.clicked.connect(self.open_gesture_studio.emit)
        return record

    def _on_triggers_changed(self, key):
        # A trigger can move between sections (e.g. 👍 from videos to
        # music): show the change everywhere, then reload the camera.
        for other, editor in self.editors.items():
            if other != key:
                editor.refresh()
        for section in self.sections:
            self._update_summary(section)
        self.bindings_changed.emit()

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    def refresh_bindings(self):
        self.profile.load(browse_media.PROFILE_NAME)
        for editor in self.editors.values():
            editor.refresh()
        for section in self.sections:
            self._update_summary(section)

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
