"""
Settings page: accessibility options for gesture recognition, and where
Wield keeps its data. Changes save immediately and apply the next time a
studio starts listening.
"""

import os
import platform
import subprocess

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from frontend.pages.studio_page import StudioPage
from frontend.styles.theme import (
    OVERLAY_1,
    BORDER,
    ON_PRIMARY,
    PRIMARY,
    PRIMARY_MUTED,
    PRIMARY_HOVER,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
    SURFACE,
    SURFACE_HOVER,
    TEXT_MUTED,
)
from frontend.styles import theme as theme_module
from backend.paths import APP_DIR, user_data_dir
from backend.settings.settings_manager import SettingsManager
from backend.settings import gesture_settings
from backend.settings.gesture_settings import ARM_TIMEOUT_CHOICES, HOLD_TIME_CHOICES
from backend.app_info import APP_NAME
from backend.voice import model as voice_model

CHEVRON = os.path.join(APP_DIR, "frontend", "styles", "icons", "chevron-down.svg").replace("\\", "/")



class _ModelDownloader(QObject):
    """Downloads the speech model off the UI thread."""

    progress = Signal(int, int)
    done = Signal(str)        # "" on success, else the error message

    @Slot()
    def run(self):
        try:
            voice_model.download_model(
                progress=lambda done, total: self.progress.emit(done, total)
            )
        except Exception as e:
            self.done.emit(str(e) or "The download failed.")
            return
        self.done.emit("")


class SettingsPage(StudioPage):

    # A theme was picked: the main window switches to it straight away.
    theme_chosen = Signal(str)

    # "See history" (the list of what Wield did, which used to have its
    # own place in the sidebar).
    history_requested = Signal()

    # The display name changed (greeting and sidebar update).
    name_changed = Signal()

    # "Show welcome again" (About section).
    welcome_requested = Signal()

    # Hands-free mode switched on or off.
    hands_free_changed = Signal(bool)

    # Optional studios brought back (Home should show them).
    studios_restored = Signal()

    # "Take the tour" (About section).
    tour_requested = Signal()

    # "Check for updates now" (About section); the main window answers
    # with show_update_result().
    update_check_requested = Signal()

    def __init__(self, parent=None):

        super().__init__(
            title="Settings",
            subtitle=f"Change how {APP_NAME} looks, listens and sees your hand.",
            parent=parent,
        )

        self.settings = gesture_settings.load()

        self.setStyleSheet(self.styleSheet() + f"""
            QComboBox {{
                background: {SURFACE}; color: {PRIMARY_TEXT};
                border: 1px solid {BORDER}; border-radius: 17px;
                padding: 0 14px; min-height: 34px; min-width: 220px;
            }}
            QComboBox:hover {{ border: 1px solid {PRIMARY}; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: center right;
                width: 28px; border: none; background: transparent;
            }}
            QComboBox::down-arrow {{ image: url({CHEVRON}); width: 12px; height: 12px; }}
            QComboBox QAbstractItemView {{
                background-color: {SURFACE}; color: {PRIMARY_TEXT};
                border: 1px solid {BORDER}; border-radius: 12px;
                padding: 6px; outline: 0;
                selection-background-color: {PRIMARY_MUTED};
                selection-color: {PRIMARY_TEXT};
            }}
            QWidget#SettingsRow {{ background: transparent; }}
            QCheckBox {{ color: {PRIMARY_TEXT}; font-size: 14px; spacing: 10px; background: transparent; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px; border-radius: 5px;
                border: 1px solid {BORDER}; background: {SURFACE};
            }}
            QCheckBox::indicator:checked {{ background: {PRIMARY}; border: 1px solid {PRIMARY}; }}
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{
                height: 6px; border-radius: 3px; background: {SURFACE_HOVER};
            }}
            QSlider::sub-page:horizontal {{
                height: 6px; border-radius: 3px; background: {PRIMARY};
            }}
            QSlider::handle:horizontal {{
                width: 18px; height: 18px; margin: -6px 0;
                border-radius: 9px; background: white;
            }}
        """)

        self._build_you()

        self._build_appearance()

        self._build_hands_free()

        self._build_window()

        self._section("How easily Wield sees your hand")

        # Sensitivity -------------------------------------------------

        self.sensitivity = QSlider(Qt.Horizontal)
        self.sensitivity.setRange(0, 100)
        self.sensitivity.setSingleStep(5)
        self.sensitivity.setPageStep(10)
        self.sensitivity.setValue(self.settings["sensitivity"])
        self.sensitivity.setAccessibleName("Matching sensitivity")
        self.sensitivity.valueChanged.connect(self._on_sensitivity)

        slider_row = QHBoxLayout()
        slider_row.addWidget(self._muted("Strict"))
        slider_row.addWidget(self.sensitivity, 1)
        slider_row.addWidget(self._muted("Forgiving"))

        self._row(
            "How exact your hand needs to be",
            "Slide towards Forgiving if Wield misses your hand signs, for "
            "example if your hands shake. Slide towards Strict if it reacts "
            "when you didn't mean it to.",
            slider_row,
        )

        # Hold time ---------------------------------------------------

        self.hold_time = self._choices(
            "hold_time",
            [(seconds, "No wait" if seconds == 0 else f"{seconds:g} sec")
             for seconds in HOLD_TIME_CHOICES],
            "Hold time",
        )

        self._row(
            "How long to hold a hand sign",
            "Wield waits this long before it acts, so a quick wave doesn't "
            "do anything by mistake. Swipes don't wait.",
            self.hold_time,
        )

        self._section("Wake-up hand sign")

        # Activation --------------------------------------------------

        self.require_arm = QCheckBox("Wait for a wake-up hand sign first")
        self.require_arm.setChecked(self.settings["require_arm"])
        self.require_arm.toggled.connect(self._on_require_arm)

        self._row(
            None,
            "Wield ignores your hands until you show this sign. Handy if you "
            "talk with your hands on video calls.",
            self.require_arm,
        )

        # These two only matter with the checkbox on, so they are shown
        # only then (a greyed-out dropdown looked like an empty one).
        self.arm_gesture = QComboBox()
        self.arm_gesture.setAccessibleName("Activation gesture")
        self._fill_gestures()
        self.arm_gesture.currentIndexChanged.connect(
            lambda: self._save("arm_gesture", self.arm_gesture.currentData())
        )

        self.arm_gesture_row = self._row(
            "Wake-up sign", "Show this to wake Wield up.", self.arm_gesture
        )

        self.arm_timeout = self._choices(
            "arm_timeout",
            [(seconds, f"{seconds} sec") for seconds in ARM_TIMEOUT_CHOICES],
            "Switch off after",
        )

        self.arm_timeout_row = self._row(
            "Go back to sleep after",
            "If you don't use a hand sign for this long, Wield stops "
            "watching until you wake it again.",
            self.arm_timeout,
        )

        self._on_require_arm(self.settings["require_arm"], save=False)

        self._section("Sounds and messages")

        self.sound_feedback = QCheckBox("Play a soft sound when Wield does something")
        self.sound_feedback.setChecked(self.settings["sound_feedback"])
        self.sound_feedback.toggled.connect(
            lambda checked: self._save("sound_feedback", bool(checked))
        )
        self._row(
            None,
            "So you know it worked without looking at the screen.",
            self.sound_feedback,
        )

        self.feedback_overlay = QCheckBox("Show a small message when Wield does something")
        self.feedback_overlay.setChecked(self.settings["feedback_overlay"])
        self.feedback_overlay.toggled.connect(
            lambda checked: self._save("feedback_overlay", bool(checked))
        )
        self._row(
            None,
            "For example \u201c\U0001F44D \u2192 Next slide\u201d at the bottom of "
            "your screen. It also shows over slideshows, and you can click "
            "through it.",
            self.feedback_overlay,
        )

        self._build_voice()

        self._build_studios()

        self._section("Your information")

        self._row(
            "History",
            "A list of everything Wield did for you, like opening a studio "
            "or moving to the next slide.",
            self._small_button("See history", self.history_requested.emit),
        )

        data_button = QPushButton("Show me where")
        data_button.setCursor(Qt.PointingHandCursor)
        data_button.setStyleSheet(f"""
            QPushButton {{
                background: {OVERLAY_1}; color: {PRIMARY_TEXT};
                border: 1px solid {BORDER}; border-radius: 10px;
                padding: 9px 16px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
        """)
        data_button.clicked.connect(self._open_data_folder)

        self._row(
            "Kept only on this computer",
            "Your studios, settings and the hand signs you taught Wield are "
            "saved here, and nowhere else.",
            data_button,
        )

        self._build_about()

        self.content_layout.addStretch()

    # -----------------------------------------------------
    # ABOUT
    # -----------------------------------------------------

    def _small_button(self, text, handler):
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(f"""
            QPushButton {{
                background: {OVERLAY_1}; color: {PRIMARY_TEXT};
                border: 1px solid {BORDER}; border-radius: 10px;
                padding: 9px 16px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
        """)
        button.clicked.connect(handler)
        return button

    def _build_about(self):

        from backend.app_info import APP_NAME, VERSION

        self._section("Help and updates")

        self._row(
            f"{APP_NAME} {VERSION}",
            "Wield never records your camera or your voice, and nothing is "
            "sent over the internet.",
            QWidget(),
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(self._small_button("Show the log", self._open_log))
        buttons.addWidget(self._small_button("Tell us about a problem", self._report_problem))
        buttons.addWidget(self._small_button("Take the tour", self.tour_requested.emit))
        buttons.addWidget(self._small_button("Start the welcome again", self.welcome_requested.emit))
        buttons.addStretch()

        self._row(
            None,
            "Something not working? \u201cTell us about a problem\u201d opens a "
            "short form on the web. The log is a list of what Wield did, "
            "which helps us find the problem.",
            buttons,
        )

        # Updates ------------------------------------------------------

        self.update_auto = QCheckBox("Tell me when a new version is out")
        self.update_auto.setChecked(SettingsManager().get_setting("update_check") is not False)
        self.update_auto.toggled.connect(
            lambda checked: SettingsManager().set_setting("update_check", bool(checked))
        )

        update_row = QHBoxLayout()
        update_row.setSpacing(12)
        update_row.addWidget(self.update_auto)
        self.update_now = self._small_button("Check now", self._check_updates_now)
        update_row.addWidget(self.update_now)
        self.update_result = QLabel("")
        self.update_result.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 13px; background: transparent;"
        )
        update_row.addWidget(self.update_result)
        update_row.addStretch()

        self._row(
            "Updates",
            f"Once a day, {APP_NAME} checks if there's a newer version and "
            "tells you. Nothing about you is sent.",
            update_row,
        )

    def _check_updates_now(self):
        self.update_now.setEnabled(False)
        self.update_result.setText("Checking…")
        self.update_check_requested.emit()

    def show_update_result(self, release):
        from backend.app_info import VERSION
        self.update_now.setEnabled(True)
        if release:
            self.update_result.setText(
                f"{APP_NAME} {release['version']} is available: use Download at the top."
            )
        else:
            self.update_result.setText(
                f"You have the newest version ({VERSION}). (Or the internet couldn't be reached.)"
            )

    def _open_log(self):
        from backend.app_log import log_path
        path = log_path()
        if not os.path.exists(path):
            open(path, "a").close()
        self._open_path(path)

    def _report_problem(self):
        from urllib.parse import urlencode
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from backend.app_info import APP_NAME, ISSUES_URL, VERSION

        body = (
            "**What happened?**\n\n\n"
            "**What did you expect?**\n\n\n"
            f"---\n{APP_NAME} {VERSION} on {platform.system()} {platform.release()}\n"
            "(Settings → About → Open log, and attach wield.log if you can.)"
        )
        QDesktopServices.openUrl(QUrl(ISSUES_URL + "?" + urlencode({"body": body})))

    # -----------------------------------------------------
    # YOU
    # -----------------------------------------------------

    def _build_you(self):

        from backend.settings.user import display_name

        self._section("You")

        self.name_input = QLineEdit(display_name())
        self.name_input.setPlaceholderText("Your name")
        self.name_input.setAccessibleName("Your name")
        self.name_input.setMaxLength(40)
        self.name_input.setFixedWidth(280)
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {SURFACE}; color: {PRIMARY_TEXT};
                border: 1px solid {BORDER}; border-radius: 8px;
                padding: 8px 10px; font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {PRIMARY}; }}
        """)
        self.name_input.editingFinished.connect(self._on_name)

        self._row("Your name", "So Wield can say hello to you.", self.name_input)

    def _on_name(self):
        from backend.settings.user import set_display_name
        set_display_name(self.name_input.text())
        self.notify("Saved.")
        self.name_changed.emit()

    # -----------------------------------------------------
    # APPEARANCE
    # -----------------------------------------------------

    def _build_appearance(self):

        self._section("How Wield looks")

        row = QHBoxLayout()
        row.setSpacing(12)

        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)

        saved = SettingsManager().get_setting(theme_module.SETTING_KEY) or theme_module.DEFAULT_THEME

        for name, palette in theme_module.THEMES.items():

            button = QPushButton(palette["label"])
            button.setCheckable(True)
            button.setChecked(name == saved)
            button.setCursor(Qt.PointingHandCursor)
            button.setAccessibleName(f"{palette['label']} theme")
            button.setFixedSize(132, 84)
            # Each swatch is drawn in its own theme's colours.
            button.setStyleSheet(f"""
                QPushButton {{
                    background: {palette['BG_DARK']};
                    color: {palette['PRIMARY_TEXT']};
                    border: 2px solid {palette['BORDER']};
                    border-radius: 14px;
                    font-size: 13px; font-weight: 600;
                    padding-top: 34px;
                }}
                QPushButton:hover {{ border: 2px solid {palette['PRIMARY_HOVER']}; }}
                QPushButton:checked {{ border: 2px solid {palette['PRIMARY']}; }}
            """)

            dot = QLabel(button)
            dot.setGeometry(14, 14, 22, 22)
            dot.setStyleSheet(
                f"background: {palette['PRIMARY']}; border-radius: 11px; border: none;"
            )
            surface = QLabel(button)
            surface.setGeometry(42, 14, 76, 22)
            surface.setStyleSheet(
                f"background: {palette['SURFACE']}; border-radius: 7px; "
                f"border: 1px solid {palette['BORDER']};"
            )

            button.clicked.connect(lambda checked=False, n=name: self._on_theme(n))
            self.theme_group.addButton(button)
            row.addWidget(button)

        row.addStretch()

        box = self._row(
            "Theme",
            "Pick the colours you like. Galaxy and Jungle add a picture behind everything.",
            row,
        )


    # -----------------------------------------------------
    # HANDS-FREE MODE
    # -----------------------------------------------------

    def _build_hands_free(self):

        self._section("Use Wield in any app")

        self.hands_free = QCheckBox("Keep Wield ready in the background")
        self.hands_free.setChecked(self.settings["hands_free"])
        self.hands_free.toggled.connect(self._on_hands_free)
        self._row(
            None,
            f"You don't need to open Wield first. Show "
            f"{self.settings['arm_gesture']} to the camera, or say "
            "“Hey Wield, wake up”, and your hand signs work in any app: slides "
            "in PowerPoint, and videos, music and web pages everywhere else. "
            "Your camera stays on while this is ticked.",
            self.hands_free,
        )

        self.hands_free_timeout = self._choices(
            "hands_free_timeout",
            [(seconds, f"{seconds} sec") for seconds in gesture_settings.HANDS_FREE_TIMEOUTS],
            "Sleep after",
        )
        self._row("Go back to sleep after", None, self.hands_free_timeout)

    def _on_hands_free(self, checked):
        self._save("hands_free", bool(checked))
        self.hands_free_changed.emit(bool(checked))
        self.notify(
            "Wield is ready. Show your wake-up sign to use it."
            if checked else "Wield is no longer waiting in the background."
        )

    # -----------------------------------------------------
    # STUDIOS (bring back optional ones)
    # -----------------------------------------------------

    def _build_studios(self):

        from backend.studios import catalog

        self._section("Studios")

        row = QHBoxLayout()
        row.setSpacing(12)
        self.restore_studios = self._small_button(
            "Bring them back", self._restore_studios
        )
        row.addWidget(self.restore_studios)
        self.studios_note = QLabel("")
        self.studios_note.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 13px; background: transparent;"
        )
        row.addWidget(self.studios_note)
        row.addStretch()

        self._row(
            "Studios that come with Wield",
            "Removed a studio from Home by mistake? Bring it back here. "
            "(Presentation, Browse & Media and Gesture Studio can't be removed.)",
            row,
        )
        self._refresh_studios_note()

    def _refresh_studios_note(self):
        from backend.studios import catalog
        missing = catalog.missing_optional()
        self.restore_studios.setEnabled(bool(missing))
        self.studios_note.setText(
            f"Removed: {', '.join(missing)}" if missing else "All of them are on Home."
        )

    def _restore_studios(self):
        from backend.studios import catalog
        restored = catalog.restore_optional()
        self._refresh_studios_note()
        if restored:
            self.notify(f"Brought back {', '.join(restored)}.")
            self.studios_restored.emit()

    # -----------------------------------------------------
    # YOUR WINDOW (the fog on Home)
    # -----------------------------------------------------

    def _build_window(self):

        self._section("The misty window on Home")

        self.fog_colour = self._choices(
            "fog_colour",
            [("white", "White"), ("black", "Black")],
            "Fog colour",
        )
        self._row(
            "Mist colour",
            "On Home you can write on a misty window with your finger. Pick "
            "white or black mist.",
            self.fog_colour,
        )

        self.fog_stroke = self._choices(
            "fog_stroke",
            [("thin", "Thin"), ("medium", "Medium"), ("thick", "Thick")],
            "Pen size",
        )
        self._row(
            "Pen size",
            "How thick your writing is. Thick is easier to read.",
            self.fog_stroke,
        )

    def _choices(self, key, options, accessible_name):
        """A row of pill buttons, one per option; saves `key` when clicked."""

        row = QHBoxLayout()
        row.setSpacing(8)

        group = QButtonGroup(self)
        group.setExclusive(True)

        for value, label in options:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(self.settings.get(key) == value)
            button.setCursor(Qt.PointingHandCursor)
            button.setAccessibleName(f"{accessible_name}: {label}")
            button.setProperty("choice", value)
            button.setStyleSheet(f"""
                QPushButton {{
                    background: {SURFACE}; color: {PRIMARY_TEXT};
                    border: 1px solid {BORDER}; border-radius: 17px;
                    padding: 0 18px; min-height: 34px;
                    font-size: 13px; font-weight: 600;
                }}
                QPushButton:hover {{ border: 1px solid {PRIMARY}; }}
                QPushButton:checked {{
                    background: {PRIMARY}; color: {ON_PRIMARY};
                    border: 1px solid {PRIMARY};
                }}
            """)
            button.clicked.connect(lambda checked=False, v=value: self._save(key, v))
            group.addButton(button)
            row.addWidget(button)

        row.addStretch()
        row.group = group
        return row

    def _on_theme(self, name):
        self.theme_chosen.emit(name)

    # -----------------------------------------------------
    # LAYOUT HELPERS
    # -----------------------------------------------------

    # -----------------------------------------------------
    # VOICE COMMANDS
    # -----------------------------------------------------

    def _build_voice(self):

        self._section("Talking to Wield")

        self.voice_enabled = QCheckBox("Let me talk to Wield")
        self.voice_enabled.setChecked(self.settings["voice_enabled"])
        self.voice_enabled.toggled.connect(self._on_voice_enabled)
        self._row(
            None,
            "Say what you want instead of using your hands, like "
            "\u201cHey Wield, next slide\u201d. Your voice never leaves this "
            "computer and is never recorded.",
            self.voice_enabled,
        )

        self.voice_wake_word = QCheckBox("Only listen after I say \u201cHey Wield\u201d")
        self.voice_wake_word.setChecked(self.settings["voice_wake_word"])
        self.voice_wake_word.toggled.connect(
            lambda checked: self._save("voice_wake_word", bool(checked))
        )
        self._row(
            None,
            "Best left on, so normal talking doesn't do anything by mistake.",
            self.voice_wake_word,
        )

        self.voice_model_status = QLabel()
        self.voice_model_status.setWordWrap(True)
        self.voice_model_status.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 13px; border: none; background: transparent;"
        )

        self.voice_download = self._small_button(
            f"Download it ({voice_model.MODEL_SIZE_MB} MB)",
            self._download_voice_model,
        )

        model_row = QHBoxLayout()
        model_row.addWidget(self.voice_download)
        model_row.addWidget(self.voice_model_status, 1)
        self._row("Voice pack", None, model_row)

        self._download_thread = None
        self._refresh_voice_status()

    def _on_voice_enabled(self, checked):
        self._save("voice_enabled", bool(checked))
        self._refresh_voice_status()

    def _refresh_voice_status(self, message=None):
        ready = voice_model.model_ready()
        available = voice_model.vosk_available()
        downloading = self._download_thread is not None

        self.voice_download.setVisible(available and not ready)
        self.voice_download.setEnabled(not downloading)

        if message:
            text = message
        elif not available:
            text = ("Voice commands need two extra packages: "
                    "pip install vosk sounddevice")
        elif ready:
            text = "\u2713 Ready. Talking works even without internet."
        else:
            text = "Wield needs this once to understand your voice."
        self.voice_model_status.setText(text)

    def _download_voice_model(self):
        if self._download_thread is not None:
            return

        self._download_thread = QThread(self)
        self._downloader = _ModelDownloader()
        self._downloader.moveToThread(self._download_thread)
        self._download_thread.started.connect(self._downloader.run)
        self._downloader.progress.connect(self._on_download_progress)
        self._downloader.done.connect(self._on_download_done)
        self._download_thread.start()
        self._refresh_voice_status("Downloading\u2026")

    @Slot(int, int)
    def _on_download_progress(self, done, total):
        if total:
            self.voice_model_status.setText(
                f"Downloading\u2026 {done * 100 // total}% "
                f"({done // 1_000_000} of {total // 1_000_000} MB)"
            )

    @Slot(str)
    def _on_download_done(self, error):
        thread = self._download_thread
        self._download_thread = None
        if thread is not None:
            thread.quit()
            thread.wait(5000)
        self._refresh_voice_status(
            f"\u26a0 Download failed: {error}" if error else None
        )

    def _section(self, title):
        label = QLabel(title)
        label.setStyleSheet(f"""
            color: {PRIMARY_TEXT}; font-size: 17px; font-weight: 700;
            margin-top: 8px; border: none; background: transparent;
        """)
        self.content_layout.addWidget(label)

    def _muted(self, text):
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; border: none; background: transparent;"
        )
        return label

    def _row(self, title, description, control):

        box = QWidget()
        box.setObjectName("SettingsRow")
        box.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(6)

        if title:
            heading = QLabel(title)
            heading.setStyleSheet(
                f"color: {PRIMARY_TEXT}; font-size: 14px; font-weight: 600; "
                "border: none; background: transparent;"
            )
            layout.addWidget(heading)

        if description:
            text = QLabel(description)
            text.setWordWrap(True)
            text.setStyleSheet(
                f"color: {SECONDARY_TEXT}; font-size: 13px; border: none; "
                "background: transparent;"
            )
            layout.addWidget(text)

        if isinstance(control, QHBoxLayout):
            layout.addLayout(control)
        else:
            layout.addWidget(control, 0, Qt.AlignLeft)

        self.content_layout.addWidget(box)

        return box

    @staticmethod
    def _select(combo, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _fill_gestures(self):

        from backend.gestures.custom_gestures import CustomGestureStore
        from backend.gestures.google_gesture_recognizer import BUILTIN_GESTURE_NAMES
        from backend.gestures.motions import BUILTIN_MOTION_NAMES, MotionStore

        names = (
            list(BUILTIN_GESTURE_NAMES)
            + CustomGestureStore().names()
            + list(BUILTIN_MOTION_NAMES)
            + MotionStore().names()
        )

        self.arm_gesture.blockSignals(True)
        self.arm_gesture.clear()

        for name in names:
            self.arm_gesture.addItem(name, name)

        current = self.settings["arm_gesture"]
        if self.arm_gesture.findData(current) < 0:
            self.arm_gesture.addItem(f"{current} (not found)", current)

        self._select(self.arm_gesture, current)
        self.arm_gesture.blockSignals(False)

    # -----------------------------------------------------
    # CHANGES
    # -----------------------------------------------------

    def _save(self, key, value):
        gesture_settings.save(key, value)
        self.settings[key] = value
        if key.startswith("fog_"):
            self.notify("Saved. You'll see it on your window on Home.")
        else:
            self.notify("Saved. You'll notice it next time you press Start.")

    def _on_sensitivity(self, value):
        self._save("sensitivity", int(value))

    def _on_require_arm(self, checked, save=True):
        if save:
            self._save("require_arm", bool(checked))
        self.arm_gesture_row.setVisible(checked)
        self.arm_timeout_row.setVisible(checked)

    def _open_data_folder(self):
        self._open_path(user_data_dir())

    def _open_path(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def showEvent(self, event):
        # Pick up gestures recorded since the page was built, and studios
        # removed on Home since.
        self._fill_gestures()
        self._refresh_studios_note()
        super().showEvent(event)
