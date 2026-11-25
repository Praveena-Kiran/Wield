from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFrame,
    QVBoxLayout,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
)

from frontend.pages.studio_page import StudioPage
from frontend.components.collapsible import Accordion, CollapsibleSection
from frontend.components.toast import toast
from frontend.components.gesture_recorder_dialog import GestureRecorderDialog
from frontend.components.gesture_test_dialog import GestureTestDialog
from frontend.components.motion_recorder_dialog import MotionRecorderDialog
from backend.gestures.motions import BUILTIN_MOTION_NAMES, FINGERTIP, MotionStore
from frontend.styles.theme import (
    ON_PRIMARY,
    OVERLAY_1,
    OVERLAY_2,
    OVERLAY_BORDER,
    TEXT_STRONG,
    BG_DARK,
    SURFACE,
    SURFACE_HOVER,
    BORDER,
    PRIMARY,
    PRIMARY_HOVER,
    PRIMARY_PRESSED,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
    TEXT_MUTED,
    ERROR,
)
from backend.profile_manager import ProfileManager
from backend.automation.events import friendly_action
from backend.gestures.custom_gestures import CustomGestureStore
from backend.gestures.google_gesture_recognizer import BUILTIN_GESTURE_NAMES
from backend.app_info import APP_NAME


class GesturePage(StudioPage):

    # The pointer to where presentation gestures are chosen now.
    open_presentation_studio = Signal()

    def __init__(self, parent=None):

        super().__init__(
            title="Gesture Studio",
            subtitle="Record and test your own gestures and motions.",
            parent=parent,
        )

        # -----------------------------------------
        # Profile
        # -----------------------------------------

        self.profile_manager = ProfileManager()
        self.profile_manager.load("presentation")

        self.gesture_map = (
            self.profile_manager.get_gesture_map()
        )

        # -----------------------------------------
        # Available actions
        # -----------------------------------------

        self.available_actions = [
            "ACTIVATE",
            "presentation_start",
            "presentation_end",
            "presentation_next",
            "presentation_previous",
        ]

        # -----------------------------------------
        # Supported gestures
        # -----------------------------------------

        self.builtin_gestures = list(BUILTIN_GESTURE_NAMES)

        # The user's own recorded gestures
        self.custom_store = CustomGestureStore()

        # The user's own recorded motions
        self.motion_store = MotionStore()

        # -----------------------------------------
        # Store UI labels
        # -----------------------------------------



        # -----------------------------------------
        # Intro
        # -----------------------------------------

        # Like the studios: a bar at the top with what you can do now,
        # then sections that open.
        bar = QFrame()
        bar.setObjectName("Card")
        bar.setStyleSheet(f"""
            QFrame#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; }}
            QFrame#Card QLabel {{ background: transparent; border: none; }}
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 16, 20, 16)
        bar_layout.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(4)
        intro = QLabel(
            "Record poses and movements that are comfortable for you, then "
            "use them in any studio."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 13px;")
        text.addWidget(intro)

        # Presentation gestures used to be edited here; they now live in
        # Presentation Studio, where people present. A pointer, not a copy.
        pointer = QPushButton("Choose your presentation gestures in Presentation Studio  \u2192")
        pointer.setCursor(Qt.PointingHandCursor)
        pointer.setAccessibleName("Open Presentation Studio")
        pointer.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; color: {PRIMARY};
                font-size: 12px; font-weight: 600; text-align: left; padding: 2px 0;
            }}
            QPushButton:hover {{ color: {PRIMARY_HOVER}; }}
        """)
        pointer.clicked.connect(self.open_presentation_studio.emit)
        text.addWidget(pointer, 0, Qt.AlignLeft)
        bar_layout.addLayout(text, 1)

        test_button = QPushButton("\u25B6  Test gestures && motions")
        test_button.setCursor(Qt.PointingHandCursor)
        test_button.setAccessibleName("Test gestures with the camera")
        test_button.setStyleSheet(f"""
            QPushButton {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: none;
                border-radius: 18px; padding: 0 20px; min-height: 36px;
                font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: {PRIMARY_HOVER}; }}
        """)
        test_button.clicked.connect(self.test_gestures)
        self.test_button = test_button
        bar_layout.addWidget(test_button, 0, Qt.AlignVCenter)

        self.content_layout.addWidget(bar)

        # -----------------------------------------
        # Custom gestures
        # -----------------------------------------

        self._build_custom_section()

        self.content_layout.addStretch()

    # ==================================================
    # AVAILABLE GESTURES (built-in + custom)
    # ==================================================

    @property
    def available_gestures(self):

        return (
            self.builtin_gestures
            + list(BUILTIN_MOTION_NAMES)
            + self.custom_store.names()
            + self.motion_store.names()
        )

    # ==================================================
    # CUSTOM GESTURES SECTION
    # ==================================================

    # The two kinds of user-recorded triggers shown on this page.
    SECTIONS = {
        "gesture": {
            "title": "Your gestures",
            "info": "Record any hand pose that's comfortable for you, "
                    "then use it for your slides in Presentation Studio or in a studio's events.",
            "button": "+ Record Custom Gesture",
            "empty": "No custom gestures yet.",
            "noun": "gesture",
            "icon": "✋",
        },
        "motion": {
            "title": "Your motions",
            "info": "Swipe left, right, up and down are built in. Record "
                    "your own movements, like a wave or a circle.",
            "button": "+ Record Custom Motion",
            "empty": "No custom motions yet.",
            "noun": "motion",
            "icon": "〰",
        },
    }

    def _store(self, kind):
        return self.custom_store if kind == "gesture" else self.motion_store

    def _entries(self, kind):
        store = self._store(kind)
        return store.gestures if kind == "gesture" else store.motions

    def _build_custom_section(self):

        self.section_lists = {}
        self.section_frames = {}
        self.accordion = Accordion()

        for kind in ("gesture", "motion"):
            self._build_section(kind)

        self.refresh_custom_list()

    def _build_section(self, kind):
        """
        "Your gestures" / "Your motions": sections that open and close,
        like the studios'. Closed, they say how many you've recorded.
        """

        config = self.SECTIONS[kind]
        section = CollapsibleSection(config["title"], config["icon"])
        section.setProperty("section", kind)
        self.accordion.add(kind, section)
        self.section_frames[kind] = section

        info = QLabel(config["info"])
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        section.body_layout.addWidget(info)

        list_layout = QVBoxLayout()
        list_layout.setSpacing(8)
        section.body_layout.addLayout(list_layout)
        self.section_lists[kind] = list_layout

        if kind == "gesture":
            # Older code refers to this name.
            self.custom_list_layout = list_layout

        record_button = QPushButton(config["button"])
        record_button.setCursor(Qt.PointingHandCursor)
        record_button.setStyleSheet(f"""
            QPushButton {{
                background: {OVERLAY_1};
                color: {PRIMARY_TEXT};
                border: 1px solid {PRIMARY};
                border-radius: 17px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background: {SURFACE_HOVER};
            }}
        """)
        record_button.clicked.connect(
            self.record_custom_gesture
            if kind == "gesture"
            else self.record_custom_motion
        )
        section.body_layout.addWidget(record_button, 0, Qt.AlignLeft)

        self.content_layout.addWidget(section)

    def toggle_section(self, kind):
        self.accordion.toggle(kind)

    def _update_summary(self, kind):
        names = [entry["name"] for entry in self._entries(kind)]
        noun = self.SECTIONS[kind]["noun"]
        if not names:
            text = f"None yet. Open to record your first {noun}."
        else:
            shown = ", ".join(names[:4]) + ("…" if len(names) > 4 else "")
            text = f"{len(names)} {noun}{'' if len(names) == 1 else 's'}: {shown}"
        self.section_frames[kind].set_summary(text)

    def refresh_custom_list(self):

        for kind, list_layout in self.section_lists.items():

            while list_layout.count():

                widget = list_layout.takeAt(0).widget()

                if widget:
                    widget.deleteLater()

            self._store(kind).load()

            entries = self._entries(kind)
            self._update_summary(kind)

            if not entries:

                empty = QLabel(self.SECTIONS[kind]["empty"])

                empty.setStyleSheet(f"""
                    color: {TEXT_MUTED};
                    font-size: 13px;
                    border: none;
                    background: transparent;
                """)

                list_layout.addWidget(empty)

                continue

            for entry in entries:
                self.create_custom_card(entry, kind)

    def create_custom_card(self, entry, kind="gesture"):

        name = entry["name"]

        card = QFrame()

        card.setStyleSheet(f"""
            QFrame {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """)

        layout = QHBoxLayout(card)

        layout.setContentsMargins(18, 14, 18, 14)

        name_label = QLabel(name)

        name_label.setStyleSheet(f"""
            color: {PRIMARY_TEXT};
            font-size: 15px;
            font-weight: 600;
            border: none;
            background: transparent;
        """)

        action = self.gesture_map.get(name)

        detail = f"→  {friendly_action(action)}" if action else "Not assigned yet"

        if kind == "motion":
            if entry.get("point") == FINGERTIP:
                detail += "   ·   follows your fingertip"
            else:
                detail += "   ·   follows your whole hand"

        detail_label = QLabel(detail)

        detail_label.setStyleSheet(f"""
            color: {SECONDARY_TEXT};
            font-size: 14px;
            border: none;
            background: transparent;
        """)

        delete_button = QPushButton("Delete")

        delete_button.setCursor(Qt.PointingHandCursor)

        delete_button.setAccessibleName(
            f"Delete {self.SECTIONS[kind]['noun']} {name}"
        )

        delete_button.setStyleSheet(f"""
            QPushButton {{
                background: {OVERLAY_1};
                color: {ERROR};
                border: none;
                border-radius: 8px;
                padding: 7px 14px;
            }}

            QPushButton:hover {{
                background: rgba(239, 68, 68, 0.12);
            }}
        """)

        delete_button.clicked.connect(
            lambda checked=False, n=name, k=kind:
            self.delete_custom(k, n)
        )

        layout.addWidget(name_label)
        layout.addStretch()
        layout.addWidget(detail_label)
        layout.addStretch()
        layout.addWidget(delete_button)

        self.section_lists[kind].addWidget(card)

    def test_gestures(self):

        dialog = GestureTestDialog(
            gesture_map=self.gesture_map,
            store=self.custom_store,
            parent=self,
        )

        dialog.exec()

    def _taken_names(self):
        """Names a new gesture or motion can't use."""
        return (
            self.builtin_gestures
            + list(BUILTIN_MOTION_NAMES)
            + self.custom_store.names()
            + self.motion_store.names()
        )

    def record_custom_gesture(self):

        taken = [
            n for n in self._taken_names()
            if n not in self.custom_store.names()  # re-recording is allowed
        ]

        dialog = GestureRecorderDialog(
            taken,
            store=self.custom_store,
            parent=self,
        )

        self._after_recording(dialog)

    def record_custom_motion(self):

        taken = [
            n for n in self._taken_names()
            if n not in self.motion_store.names()
        ]

        dialog = MotionRecorderDialog(
            taken_names=taken,
            store=self.motion_store,
            parent=self,
        )

        self._after_recording(dialog)

    def _after_recording(self, dialog):

        if dialog.exec() and dialog.saved_name:

            self.refresh_custom_list()

            toast(self, f'Saved "{dialog.saved_name}". Pick it for an action in any studio.')

    def delete_custom_gesture(self, name):
        self.delete_custom("gesture", name)

    def delete_custom(self, kind, name):

        noun = self.SECTIONS[kind]["noun"]

        assigned = name in self.gesture_map

        message = f'Delete your "{name}" {noun}?'

        if assigned:
            message += "\n\nIts action assignment will be removed too."

        answer = QMessageBox.question(
            self,
            f"Delete {noun.title()}",
            message,
        )

        if answer != QMessageBox.Yes:
            return

        self._store(kind).delete(name)

        if assigned:
            self.profile_manager.remove_gesture(name)
            self.refresh_gesture_list()

        self.refresh_custom_list()

    # ==================================================
    # ACTIONS AND TRIGGERS
    # ==================================================

    def refresh_gesture_list(self):

        # Re-read from disk: Presentation Studio (and first-time voice
        # defaults) edit the same profile, and saving a stale copy from
        # here would undo those changes.
        self.profile_manager.load("presentation")

        self.gesture_map = self.profile_manager.get_gesture_map()

        # Custom gesture/motion cards show their assigned action.
        if hasattr(self, "section_lists"):
            self.refresh_custom_list()


