"""
Wield — Premium Desktop Workspace Operating System

Main application window.
"""

import sys
import datetime
import time
import os

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QDialog,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QFile,
    QTextStream,
    QObject,
    QProcess,
    QThread,
    QTimer,
)

from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap

from frontend.components.title_bar import TitleBar
from frontend.components.sidebar import AppSidebar
from frontend.components.feedback_overlay import Feedback

from frontend.pages.home import HomePage
from frontend.pages.presentation_page import PresentationPage
from frontend.pages.coding_page import CodingPage
from frontend.pages.browse_page import BrowsePage
from backend.camera import claims as camera_claims
from backend.automation.controllers.desktop_input import DesktopInput, InputUnavailable
from frontend.pages.gesture_page import GesturePage
from frontend.pages.custom_page import CustomPage
from frontend.pages.settings_page import SettingsPage
from frontend.pages.activity_page import ActivityPage
from frontend.pages.notifications_page import NotificationsPage
from frontend.components.suggestion_dialog import SuggestionDialog
from frontend.components.welcome_dialog import WelcomeDialog, needs_welcome
from backend import startup
from backend.routines import (
    ActivityLog,
    RoutineStore,
    due_routines,
    suggest_routines,
)
from backend.settings.settings_manager import SettingsManager
from frontend.styles.theme import (
    ON_PRIMARY,
    BG_DARK,
    SURFACE,
    BORDER,
    PRIMARY,
    PRIMARY_HOVER,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
)

from backend.gestures.gesture_worker import GestureWorker
from backend.automation.events import events_for_gesture, gesture_of
from backend.settings import gesture_settings
from backend.voice.commands import is_voice_trigger, phrase_of
from backend.voice.model import model_ready, vosk_available
from backend.automation.action_manager import ActionManager
from frontend.styles.theme import BG_DARK, ERROR, PRIMARY, global_stylesheet
from frontend.components.backdrop import BackdropWidget
from backend.paths import APP_DIR
from backend import app_log
from backend.app_info import VERSION
from frontend.components.update_banner import UpdateBanner, UpdateChecker
from backend.app_info import APP_NAME


# =============================================================
# ROOT PATH
# =============================================================

sys.path.insert(
    0,
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


class _CameraClaims(QObject):
    """Carries webcam claim changes (from any thread) to the UI thread."""
    changed = Signal(bool)


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            APP_NAME
        )

        # =====================================================
        # WINDOW
        # =====================================================

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
        )

        screen = (
            QApplication
            .primaryScreen()
            .availableGeometry()
        )

        width = int(
            screen.width() * 0.85
        )

        height = int(
            screen.height() * 0.85
        )

        self.setMinimumSize(
            1100,
            700
        )

        self.resize(
            width,
            height
        )

        self._center_on_screen()

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            False
        )

        # Scoped to the window: an unscoped rule here would cascade to
        # every widget and hide the theme's backdrop.
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {BG_DARK}; }}"
        )

        # =====================================================
        # ROOT (paints the theme background: plain, stars or leaves)
        # =====================================================

        root = BackdropWidget()

        self.setCentralWidget(
            root
        )

        root_layout = QVBoxLayout(
            root
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        root_layout.setSpacing(
            0
        )

        # =====================================================
        # TITLE BAR
        # =====================================================

        self.title_bar = TitleBar(
            self
        )

        root_layout.addWidget(
            self.title_bar
        )

        # "A new version is available" (hidden until a check finds one).
        self.update_banner = UpdateBanner()

        root_layout.addWidget(
            self.update_banner
        )

        # =====================================================
        # BODY
        # =====================================================

        body = QHBoxLayout()

        body.setContentsMargins(
            0,
            0,
            0,
            0
        )

        body.setSpacing(
            0
        )

        # =====================================================
        # SIDEBAR
        # =====================================================

        self.sidebar = AppSidebar()

        body.addWidget(
            self.sidebar
        )

        # =====================================================
        # STACK
        # =====================================================

        self.stack = QStackedWidget()

        # =====================================================
        # PAGES
        # =====================================================

        self.home_page = HomePage()

        self.presentation_page = (
            PresentationPage()
        )

        self.coding_page = (
            CodingPage()
        )

        self.gesture_page = (
            GesturePage()
        )

        self.browse_page = BrowsePage()

        self.custom_page = (
            CustomPage()
        )

        self.settings_page = SettingsPage()

        self.activity_page = ActivityPage()

        self.notifications_page = NotificationsPage()

        # =====================================================
        # ADD PAGES
        # =====================================================

        self.stack.addWidget(
            self.home_page
        )

        self.stack.addWidget(
            self.settings_page
        )

        self.stack.addWidget(
            self.activity_page
        )

        self.stack.addWidget(
            self.notifications_page
        )

        self.stack.addWidget(
            self.presentation_page
        )

        self.stack.addWidget(
            self.coding_page
        )

        self.stack.addWidget(
            self.gesture_page
        )

        self.stack.addWidget(
            self.browse_page
        )

        self.stack.addWidget(
            self.custom_page
        )

        body.addWidget(
            self.stack,
            1
        )

        # =====================================================
        # GESTURE SYSTEM
        # =====================================================

        self.gesture_thread = None

        self.gesture_worker = None

        # Which studio page started the gesture worker ("custom",
        # "presentation", ...) and its name, for status messages.
        self.gesture_context = None

        self.gesture_studio_name = ""

        self._last_event_run = {}

        # Stopped camera threads that are still shutting down.
        self._retiring_threads = []

        # Sounds + always-on-top note for what gestures/voice just did.
        self.feedback = Feedback(self)

        # Spoken commands, running alongside the camera (see _start_voice).
        self.voice_worker = None
        self.voice_thread = None
        self._voice_events = []
        self._voice_note = ""

        self.action_manager = (
            ActionManager()
        )

        # =====================================================
        # HOME → BUILT-IN STUDIO
        # =====================================================

        self.home_page.studio_selected.connect(
            self.open_live_workspace
        )

        # =====================================================
        # HOME → CREATE STUDIO
        # =====================================================

        self.home_page.create_studio_requested.connect(
            self.create_custom_studio
        )

        # =====================================================
        # HOME → CUSTOM STUDIO EXECUTION
        # =====================================================

        self.home_page.launch_all_events_requested.connect(
            self.launch_all_events
        )

        self.home_page.launch_specific_event_requested.connect(
            self.launch_specific_event
        )

        # =====================================================
        # CUSTOM → HOME
        # =====================================================

        self.custom_page.back_requested.connect(
            self.go_home
        )

        # =====================================================
        # CUSTOM → SAVE
        # =====================================================

        self.custom_page.studio_saved.connect(
            self.refresh_home
        )

        # =====================================================
        # CUSTOM → GESTURE CONTROL
        # =====================================================

        self.custom_page.gesture_control_started.connect(
            self.start_custom_gesture_control
        )

        self.custom_page.gesture_control_stopped.connect(
            self.stop_gesture_worker
        )

        # =====================================================
        # PRESENTATION → HOME
        # =====================================================

        self.presentation_page.back_requested.connect(
            self.go_home
        )

        # Gestures / phrases edited on the Presentation Studio page: keep
        # Gesture Studio in sync and reload the running camera and voice
        # (debounced, so several quick edits restart them once).
        self._bindings_restart = QTimer(self)
        self._bindings_restart.setSingleShot(True)
        self._bindings_restart.setInterval(700)
        self._bindings_restart.timeout.connect(self._apply_presentation_bindings)

        self.presentation_page.bindings_changed.connect(
            self._on_presentation_bindings_changed
        )

        self.presentation_page.open_gesture_studio.connect(
            lambda: self.open_live_workspace("Gesture Studio")
        )

        self.gesture_page.open_presentation_studio.connect(
            lambda: self.open_live_workspace("Presentation Studio")
        )

        # Browse & Media Studio
        self.browse_page.back_requested.connect(self.go_home)
        self.browse_page.listening_requested.connect(self.set_browse_listening)
        self.browse_page.bindings_changed.connect(self._on_browse_bindings_changed)
        self.browse_page.open_gesture_studio.connect(
            lambda: self.open_live_workspace("Gesture Studio")
        )
        self.browse_page.help_requested.connect(
            lambda: self.show_cheat_sheet("browse")
        )
        self.desktop_input = DesktopInput()

        # Hands-free mode: always watching in the background (Settings).
        self._camera_claims = _CameraClaims()
        self._camera_claims.changed.connect(self._on_camera_claims)
        camera_claims.subscribe(self._camera_claims.changed.emit)
        self.settings_page.hands_free_changed.connect(self.set_hands_free)
        self.settings_page.studios_restored.connect(self.home_page.refresh_studios)
        self.settings_page.tour_requested.connect(lambda: self.start_tour("full"))
        self.home_page.studio_removed.connect(self._on_studio_removed)
        self._scroll_error_shown = False
        self._browse_restart = QTimer(self)
        self._browse_restart.setSingleShot(True)
        self._browse_restart.setInterval(700)
        self._browse_restart.timeout.connect(self._apply_browse_bindings)

        self.presentation_page.listening_requested.connect(
            self.set_presentation_listening
        )

        # =====================================================
        # CODING → HOME
        # =====================================================

        self.coding_page.back_requested.connect(
            self.go_home
        )

        # =====================================================
        # GESTURE → HOME
        # =====================================================

        self.gesture_page.back_requested.connect(
            self.go_home
        )

        self.settings_page.back_requested.connect(
            self.go_home
        )

        self.settings_page.restart_requested.connect(
            self.restart_app
        )

        self.activity_page.back_requested.connect(
            self.go_home
        )

        self.notifications_page.back_requested.connect(
            self.go_home
        )

        self.notifications_page.changed.connect(
            self._refresh_suggestion
        )

        self.notifications_page.suggestion_accepted.connect(
            self._after_accept
        )

        self.home_page.history_requested.connect(
            lambda: self._on_sidebar("history")
        )

        self.settings_page.name_changed.connect(
            self._on_name_changed
        )

        self.settings_page.welcome_requested.connect(
            self.show_welcome
        )

        self.settings_page.update_check_requested.connect(
            lambda: self.check_for_updates(force=True)
        )

        # =====================================================
        # ROUTINES
        # =====================================================

        self._setup_routines()

        # =====================================================
        # SYSTEM TRAY
        # =====================================================

        self._setup_tray()

        # =====================================================
        # SIDEBAR NAVIGATION
        # =====================================================

        self.sidebar.item_selected.connect(
            self._on_sidebar
        )

        # =====================================================
        # FINISH ROOT LAYOUT
        # =====================================================

        root_layout.addLayout(
            body,
            1
        )

        self.showNormal()

    # =============================================================
    # CENTER WINDOW
    # =============================================================

    def _center_on_screen(
        self
    ):

        screen = (
            QApplication
            .primaryScreen()
            .availableGeometry()
        )

        x = (
            screen.x()
            + (
                screen.width()
                - self.width()
            ) // 2
        )

        y = (
            screen.y()
            + (
                screen.height()
                - self.height()
            ) // 2
        )

        self.move(
            x,
            y
        )

    # =============================================================
    # SIDEBAR
    # =============================================================

    def _on_sidebar(
        self,
        item_id
    ):

        if item_id == "settings":
            self.stop_gesture_worker()
            self.stack.setCurrentWidget(self.settings_page)

        elif item_id == "history":
            self.stop_gesture_worker()
            self.sidebar.set_active("history")
            self.stack.setCurrentWidget(self.activity_page)

        elif item_id == "notifications":
            self.stop_gesture_worker()
            self.sidebar.set_active("notifications")
            self.stack.setCurrentWidget(self.notifications_page)

        elif item_id == "studios":
            # Studios live on Home: go there and scroll to the list.
            self.go_home()
            self.sidebar.set_active("studios")
            self.home_page.show_studios()

        else:
            self.go_home()
            self.home_page.show_top()

    # =============================================================
    # GO HOME
    # =============================================================

    def go_home(
        self
    ):

        print(
            "🏠 Returning to dashboard..."
        )

        self.stop_gesture_worker()

        self.sidebar.set_active("home")

        self.home_page.refresh_studios()

        self._refresh_suggestion()

        self.stack.setCurrentWidget(
            self.home_page
        )

    # =============================================================
    # REFRESH HOME
    # =============================================================

    def refresh_home(
        self
    ):

        print(
            "🔄 Refreshing dashboard..."
        )

        self.home_page.refresh_studios()

    # =============================================================
    # CREATE CUSTOM STUDIO
    # =============================================================

    def create_custom_studio(
        self
    ):

        print(
            "🛠 Creating Custom Studio"
        )

        # =====================================================
        # DIALOG
        # =====================================================

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Create Studio"
        )

        dialog.setMinimumWidth(
            400
        )

        dialog.setStyleSheet(f"""
            QDialog {{
                background: {SURFACE};
                border: 1px solid {BORDER};
            }}

            QLabel {{
                color: {PRIMARY_TEXT};
                font-size: 13px;
            }}

            QLineEdit {{
                background: {BG_DARK};
                color: {PRIMARY_TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 10px;
            }}

            QLineEdit:focus {{
                border: 1px solid {PRIMARY};
            }}

            QDialogButtonBox QPushButton {{
                background: {PRIMARY};
                color: {ON_PRIMARY};
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }}

            QDialogButtonBox QPushButton:hover {{
                background: {PRIMARY_HOVER};
            }}
        """)

        layout = QVBoxLayout(
            dialog
        )

        layout.setContentsMargins(
            24,
            24,
            24,
            24
        )

        layout.setSpacing(
            12
        )

        layout.addWidget(
            QLabel(
                "Studio Name"
            )
        )

        name_input = QLineEdit()

        name_input.setPlaceholderText(
            "e.g. Gaming Studio"
        )

        layout.addWidget(
            name_input
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )

        buttons.accepted.connect(
            dialog.accept
        )

        buttons.rejected.connect(
            dialog.reject
        )

        layout.addWidget(
            buttons
        )

        # =====================================================
        # SHOW DIALOG
        # =====================================================

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):

            return

        name = (
            name_input
            .text()
            .strip()
        )

        if not name:

            return

        # =====================================================
        # CREATE STUDIO
        # =====================================================

        self.custom_page.start_new_studio(
            name
        )

        # =====================================================
        # OPEN CUSTOM EDITOR
        # =====================================================

        self.stack.setCurrentWidget(
            self.custom_page
        )

    # =============================================================
    # STUDIO NAVIGATION
    # =============================================================

    def open_live_workspace(
        self,
        studio_name
    ):

        print(
            "CLICKED:",
            studio_name
        )

        # Gesture Studio is a settings area, not something to automate.
        if studio_name != "Gesture Studio":
            self._record("studio", studio_name, studio=studio_name)

        # =====================================================
        # PRESENTATION
        # =====================================================

        if studio_name == "Presentation Studio":

            # Gestures may have changed in Gesture Studio meanwhile.
            self.presentation_page.refresh_bindings()

            self.stack.setCurrentWidget(
                self.presentation_page
            )

            # The camera and microphone stay off until the user starts the
            # presentation (or turns them on): opening a page shouldn't.
            if self.gesture_context not in ("presentation", "auto"):
                self.stop_gesture_worker()
                self.presentation_page.set_listening(False)

        # =====================================================
        # CODING
        # =====================================================

        elif studio_name == BrowsePage.TITLE:

            self.browse_page.refresh_bindings()

            self.stack.setCurrentWidget(
                self.browse_page
            )

        elif studio_name == "Coding Studio":

            self.stack.setCurrentWidget(
                self.coding_page
            )

        # =====================================================
        # GESTURE
        # =====================================================

        elif studio_name == "Gesture Studio":

            # Show the latest saved gestures (Presentation Studio edits them too).
            self.gesture_page.refresh_gesture_list()

            self.stack.setCurrentWidget(
                self.gesture_page
            )

        # =====================================================
        # CUSTOM STUDIO
        # =====================================================

        else:

            if self.custom_page.load_studio(
                studio_name
            ):

                print(
                    f"🛠 Editing custom studio: "
                    f"{studio_name}"
                )

                self.stack.setCurrentWidget(
                    self.custom_page
                )

            else:

                print(
                    f"⚠ No workspace configured for: "
                    f"{studio_name}"
                )

    # =============================================================
    # LAUNCH ALL CUSTOM EVENTS
    # =============================================================

    def launch_all_events(self, studio_name):
        print(f"🚀 Launching ALL events: {studio_name}")

        self._record("launch", studio_name, studio=studio_name)

        studios = self.home_page.load_studios()

        studio = next(
            (
                s for s in studios
                if isinstance(s, dict)
                and s.get("title") == studio_name
            ),
            None
        )

        if not studio:
            print(f"❌ Could not find studio: {studio_name}")
            return

        events = studio.get("events", [])

        if not events:
            print("⚠️ This studio has no events.")
            return

        for event in events:
            try:
                self.action_manager.flow_manager.execute_custom_event(
                    event
                )
            except Exception as e:
                print(f"❌ Event failed: {e}")

    # =============================================================
    # LAUNCH SPECIFIC CUSTOM EVENT
    # =============================================================

    def launch_specific_event(
        self,
        studio_name,
        event
    ):

        event_name = (
            event.get(
                "name",
                "Unnamed Event"
            )
            if isinstance(event, dict)
            else "Invalid Event"
        )

        if isinstance(event, dict):
            self._record("event", event_name, studio=studio_name, event=event)

        print(
            ""
        )

        print(
            "========================================"
        )

        print(
            f"🎯 LAUNCHING EVENT: {event_name}"
        )

        print(
            f"📁 STUDIO: {studio_name}"
        )

        print(
            "========================================"
        )

        if not isinstance(
            event,
            dict
        ):

            print(
                "❌ Invalid event."
            )

            return

        try:

            self.action_manager.flow_manager.execute_custom_event(
                event
            )

            print(
                f"✅ Event completed: {event_name}"
            )

        except Exception as e:

            print(
                f"❌ Event failed: {event_name}"
            )

            print(
                f"   {e}"
            )

    # =============================================================
    # GESTURE WORKER
    # =============================================================

    def start_custom_gesture_control(
        self,
        studio
    ):

        self.start_gesture_worker(
            "custom",
            custom_studio=studio
        )

    # =============================================================
    # GESTURE WORKER
    # =============================================================
    # One worker for every studio. It emits events (see
    # backend/automation/events.py); _on_gesture_event runs them and
    # status goes to whichever studio page started the worker.

    EVENT_COOLDOWN = 0.8   # seconds before the same event can run again

    def start_gesture_worker(
        self,
        profile_name,
        custom_studio=None
    ):

        # Only one thing can use the camera; stop anything already running.
        self.stop_gesture_worker()

        print(
            f"🎯 Starting gestures: "
            f"{custom_studio.get('title') if custom_studio else profile_name}"
        )

        self.gesture_context = (
            "custom" if custom_studio is not None else profile_name
        )

        self.gesture_studio_name = (
            custom_studio.get("title", "")
            if custom_studio is not None
            else profile_name.title()
        )

        self._last_event_run = {}

        self.feedback.reload()

        try:

            worker = GestureWorker(
                profile_name,
                custom_studio=custom_studio
            )

        except Exception as e:

            print(f"❌ Could not start gestures: {e}")

            self._gesture_feedback(f"⚠ Could not start gestures: {e}", ERROR)

            return

        self.gesture_thread = QThread()

        self.gesture_worker = worker

        self.gesture_worker.moveToThread(
            self.gesture_thread
        )

        self.gesture_thread.started.connect(
            self.gesture_worker.run
        )

        # When the camera loop exits, end the thread's event loop too.
        # Direct connection: quit() runs on the worker thread itself, so this
        # works even while the UI thread is blocked waiting (closeEvent).
        self.gesture_worker.finished.connect(
            self.gesture_thread.quit,
            Qt.ConnectionType.DirectConnection
        )

        # Bound methods (not lambdas) so these run on the UI thread.
        self.gesture_worker.custom_event_detected.connect(
            self._on_gesture_event
        )

        self.gesture_worker.gesture_detected.connect(
            self._on_gesture_seen
        )

        self.gesture_worker.status_changed.connect(
            self._on_gesture_status
        )

        self.gesture_worker.error.connect(
            self._on_gesture_error
        )

        self.gesture_worker.scroll_requested.connect(
            self._on_scroll
        )

        self.gesture_worker.hold_progress.connect(
            self._on_hold_progress
        )

        self.gesture_worker.volume_requested.connect(
            self._on_volume
        )

        self.gesture_worker.studio_changed.connect(
            self._on_auto_studio
        )

        self.gesture_worker.mouse_ops.connect(
            self._on_mouse_ops
        )

        self.gesture_worker.mouse_mode_changed.connect(
            self._on_mouse_mode
        )

        if self.gesture_context == "custom":
            self.custom_page.set_gesture_control_running(
                True,
                "Starting camera…"
            )
        else:
            self._gesture_feedback("Starting camera…")

        self.gesture_thread.start()

        self._start_voice(worker.voice_events)

    def _gesture_feedback(
        self,
        message,
        color=None
    ):

        context = getattr(self, "gesture_context", None)

        if context == "custom":
            self.custom_page.show_gesture_feedback(message, color)

        elif context == "presentation":
            if color:
                self.presentation_page._set_status(message, color)
            else:
                self.presentation_page._set_status(message)

        elif context == "browse":
            if color:
                self.browse_page.set_status(message, color)
            else:
                self.browse_page.set_status(message)

        elif context == "auto":
            print(f"🖐 Hands-free: {message}")

    @Slot(dict)
    def _on_gesture_event(
        self,
        event
    ):

        gesture = event.get("gesture", "")
        name = event.get("name", "event")

        # "Hey Wield, help": what can I do here?
        if event.get("action") == "Help":
            self.show_cheat_sheet()
            return

        # Hand mouse on / off: the worker moves the pointer itself.
        if event.get("action") == "Mouse":
            worker = self.gesture_worker
            if worker is not None:
                if worker.require_arm and event.get("value") == "on":
                    worker._set_armed(True)
                worker.request_mouse(event.get("value") == "on")
            return

        # "Hey Wield, wake up / go to sleep" (hands-free mode).
        if event.get("action") in ("App", "LensFlow"):
            worker = self.gesture_worker
            if worker is not None and worker.require_arm:
                worker._set_armed(event.get("value") != "deactivate")
            return

        now = time.monotonic()

        if now - self._last_event_run.get(name, 0) < self.EVENT_COOLDOWN:
            return

        self._last_event_run[name] = now

        print(
            f"🎯 {gesture} → {name} "
            f"({self.gesture_studio_name})"
        )

        self._record(
            "event",
            name,
            studio=self.gesture_studio_name,
            event=event,
            trigger="gesture",
        )

        try:

            self.action_manager.flow_manager.execute_custom_event(
                event
            )

        except Exception as e:

            print(f"❌ Event failed: {name}: {e}")

            self._gesture_feedback(
                f"{gesture}  →  {name} failed: {e}",
                ERROR
            )

            self.feedback.failed(name, str(e))

            return

        self._gesture_feedback(
            f"{gesture}  →  {name}"
        )

        self.feedback.action(gesture, name)

        # Ending the slideshow by gesture or voice also turns the camera
        # and microphone off, like the End button.
        if (
            self.gesture_context == "presentation"
            and event.get("action") == "PowerPoint"
            and str(event.get("value", "")).strip().lower() in ("end", "end presentation")
        ):
            QTimer.singleShot(0, lambda: self.set_presentation_listening(False))

    @Slot(str, float)
    def _on_gesture_seen(
        self,
        gesture,
        confidence
    ):

        print(
            f"Detected: {gesture} | "
            f"Confidence: {confidence:.2f}"
        )

        if self.gesture_context == "custom":
            self._gesture_feedback(
                f"Saw {gesture} ({int(confidence * 100)}%)"
            )

    @Slot(str)
    def _on_gesture_status(
        self,
        status
    ):

        worker = self.gesture_worker

        arm_hint = (
            f"Make {worker.arm_gesture} to activate gestures"
            if worker is not None and worker.require_arm
            else None
        )

        if status == "READY" and self.gesture_context == "presentation":
            self.presentation_page.set_listening(True)

        if status == "READY" and self.gesture_context == "browse":
            self.browse_page.set_listening(True)

        if self.gesture_context == "auto" and worker is not None:
            if status == "ARMED":
                self.home_page.set_hands_free("Hands-free: listening")
            elif status in ("READY", "DISARMED"):
                self.home_page.set_hands_free(f"Hands-free: {worker.arm_gesture} to wake")

        if status == "READY":
            message = arm_hint or "Listening for gestures…"
            if self._voice_note:
                message += f"   ·   {self._voice_note}"
            self._gesture_feedback(message)

        elif status == "ARMED":
            self._gesture_feedback("Gestures active")
            self.feedback.armed(worker.arm_gesture if worker else "")

        elif status == "DISARMED" and arm_hint:
            self._gesture_feedback(f"Paused. {arm_hint}")
            self.feedback.disarmed()

    @Slot(str)
    def _on_gesture_error(
        self,
        message
    ):

        print(f"❌ Gesture Error: {message}")

        context = self.gesture_context

        self.stop_gesture_worker()

        if context == "custom":
            self.custom_page.set_gesture_control_running(
                False,
                f"⚠ {message}"
            )
        elif context == "auto":
            # Hands-free mode stays off until the camera works again (it
            # retries when a studio or the camera on Home gives it back).
            self.home_page.set_hands_free("Hands-free: camera not available")
        else:
            self.gesture_context = context
            self._gesture_feedback(f"⚠ {message}", ERROR)

    # =============================================================
    # STOP GESTURE WORKER
    # =============================================================

    def stop_gesture_worker(
        self
    ):

        # A studio (or the camera on Home) finishing gives the camera back
        # to hands-free mode, if it's on.
        if self.gesture_context not in (None, "auto"):
            QTimer.singleShot(1500, self._resume_hands_free)

        if self.gesture_context == "presentation" or self.gesture_worker is None:
            # Keep the camera indicator honest whatever stopped it.
            self.presentation_page.set_listening(False)

        if self.gesture_context == "browse" or self.gesture_worker is None:
            self.browse_page.set_listening(False)

        if self.gesture_worker is None:

            return

        print(
            "🛑 Stopping gesture worker..."
        )

        try:

            # Ask the camera loop to finish. Called directly (not through a
            # signal) because the worker's thread is busy inside run().
            self.gesture_worker.stop()

        except Exception as e:

            print(
                f"⚠ Could not stop gesture worker: {e}"
            )

        # Don't block the UI waiting for the camera: on Windows releasing a
        # webcam can take several seconds. Keep the old thread alive in
        # `_retiring_threads` until it has really finished — destroying a
        # QThread that is still running makes Qt abort the whole app (this
        # was the Presentation Studio "Back" crash).
        thread = self.gesture_thread
        worker = self.gesture_worker

        if thread is not None:

            entry = (thread, worker)

            self._retiring_threads.append(entry)

            thread.finished.connect(
                lambda e=entry: self._forget_thread(e)
            )

            if not thread.isRunning():
                self._forget_thread(entry)

        self._stop_voice()

        self.gesture_worker = None

        self.gesture_thread = None

        self.gesture_context = None

        self.feedback.stopped()

        if self.custom_page.gesture_control_running:

            self.custom_page.set_gesture_control_running(
                False
            )

    # =============================================================
    # VOICE COMMANDS
    # =============================================================

    def _start_voice(
        self,
        events
    ):
        """
        Listen for this studio's voice triggers, if voice is turned on.
        Always leaves a reason in the log (and in self._voice_note, shown
        with the "listening" status) when voice doesn't start.
        """

        self._stop_voice()
        self._voice_note = ""

        settings = gesture_settings.load()

        if not settings["voice_enabled"]:
            print("🎤 Voice commands are off (Settings > Voice commands).")
            return

        # First time voice is used with Presentation Studio: give it the
        # standard phrases so "Hey Wield, next slide" just works.
        if self.gesture_context == "presentation":
            events = self._with_default_voice_phrases(events)

        phrases = [
            phrase_of(gesture_of(event))
            for event in events or []
            if is_voice_trigger(gesture_of(event))
        ]

        if not phrases:
            self._voice_note = (
                "🎤 No voice commands here yet: add them in Presentation Studio"
            )
            print("🎤 Voice is on, but this studio has no voice commands.")
            return

        if not vosk_available():
            self._voice_note = (
                "⚠ Voice needs two packages: pip install vosk sounddevice"
            )
            print("🎤 Voice not started: vosk / sounddevice not installed.")
            return

        if not model_ready():
            self._voice_note = (
                "⚠ Voice: download the speech model in Settings"
            )
            print("🎤 Voice not started: speech model not downloaded.")
            return

        wake = settings["voice_wake_word"]
        example = phrases[0]
        self._voice_note = (
            f"🎤 Say \u201cHey Wield, {example}\u201d" if wake
            else f"🎤 Say \u201c{example}\u201d"
        )

        from backend.voice.voice_worker import VoiceWorker

        self._voice_events = list(events)

        worker = VoiceWorker(phrases, wake_word=settings["voice_wake_word"])
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)

        # Bound methods so these run on the UI thread.
        worker.command.connect(self._on_voice_command)
        worker.armed.connect(self._on_voice_armed)
        worker.error.connect(self._on_voice_error)

        self.voice_worker = worker
        self.voice_thread = thread
        thread.start()

        print(f"🎤 Listening for: {', '.join(phrases)}")

    def set_presentation_listening(
        self,
        on
    ):
        """Turn Presentation Studio's camera + microphone on or off."""

        if on:
            if self.gesture_context == "presentation" and self.gesture_worker is not None:
                return
            self.presentation_page.set_listening("starting")
            self.start_gesture_worker("presentation")
            if self.gesture_worker is None:
                # Couldn't start (the error is already shown).
                self.presentation_page.set_listening(False)
        else:
            if self.gesture_context == "presentation":
                print("📷 Camera and microphone off")
                self.stop_gesture_worker()
            self.presentation_page.set_listening(False)

    # =============================================================
    # HANDS-FREE MODE
    # =============================================================
    # Always watching in the background. The activation gesture (or "Hey
    # Wield, wake up") wakes Wield; the gestures follow the app in front
    # (Presentation Studio's for PowerPoint, Browse & Media's otherwise);
    # it sleeps again after a while without gestures. Any studio, the
    # camera on Home, or the gesture recorder borrows the webcam and gives
    # it back.

    def _on_studio_removed(self, title):
        print(f"🗑 Removed studio: {title}")
        # A custom studio that was running stops with it.
        if self.gesture_context == "custom" and self.gesture_studio_name == title:
            self.stop_gesture_worker()

    def set_hands_free(self, on):
        if on:
            self._resume_hands_free()
        elif self.gesture_context == "auto":
            self.stop_gesture_worker()
            self.home_page.set_hands_free("")

    def _resume_hands_free(self):
        if (
            gesture_settings.load()["hands_free"]
            and self.gesture_worker is None
            and not camera_claims.in_use()
            and not self._quitting
        ):
            print("🖐 Hands-free mode: watching for the wake gesture")
            self.start_gesture_worker("auto")
            if self.gesture_worker is None:
                self.home_page.set_hands_free("")

    @Slot(bool)
    def _on_camera_claims(self, in_use):
        if in_use and self.gesture_context == "auto":
            print("🖐 Hands-free mode: lending the camera")
            self.stop_gesture_worker()
            self.home_page.set_hands_free("Hands-free: paused")
        elif not in_use:
            QTimer.singleShot(1500, self._resume_hands_free)

    @Slot(str)
    def _on_auto_studio(self, studio):
        label = {"presentation": "Presentation gestures", "browse": "Browse & Media gestures"}
        text = label.get(studio, studio)
        print(f"🖐 Hands-free mode: {text}")
        worker = self.gesture_worker
        if worker is not None and worker.armed:
            self.feedback.info(f"🖐 {text}")

    # =============================================================
    # BROWSE & MEDIA STUDIO
    # =============================================================

    def set_browse_listening(self, on):
        """Turn Browse & Media Studio's camera (and microphone) on or off."""

        if on:
            if self.gesture_context == "browse" and self.gesture_worker is not None:
                return
            self.browse_page.set_listening("starting")
            self._scroll_error_shown = False
            self.start_gesture_worker("browse")
            if self.gesture_worker is None:
                self.browse_page.set_listening(False)
        else:
            if self.gesture_context == "browse":
                self.stop_gesture_worker()
            self.browse_page.set_listening(False)

    def _on_browse_bindings_changed(self):
        self.gesture_page.refresh_gesture_list()
        if self.gesture_context == "browse" and self.gesture_worker is not None:
            self._browse_restart.start()

    def _apply_browse_bindings(self):
        if self.gesture_context == "browse" and self.gesture_worker is not None:
            print("🔄 Browse & Media controls changed: reloading")
            self.start_gesture_worker("browse")
            self.browse_page.set_listening(
                "starting" if self.gesture_worker is not None else False
            )

    @Slot(int, str)
    def _on_scroll(self, amount, direction):
        """The worker asks to scroll the window in front (live, while held)."""

        if amount:
            try:
                self.desktop_input.scroll(amount)
            except (InputUnavailable, OSError) as e:
                if not self._scroll_error_shown:
                    self._scroll_error_shown = True
                    self._gesture_feedback(f"⚠ Can't scroll: {e}", ERROR)
                    self.feedback.failed("Scroll", str(e))
                return

        label = {"up": "Scrolling up ↑", "down": "Scrolling down ↓"}.get(direction)
        if amount == 0:
            self._gesture_feedback(label or "Holding: move up or down to scroll")
            if label:
                self.feedback.info(label)

    @Slot(int, str)
    def _on_volume(self, steps, direction):
        """The worker asks to change the volume (live, while held)."""

        if steps:
            try:
                self.desktop_input.volume(steps)
            except (InputUnavailable, OSError) as e:
                if not self._scroll_error_shown:
                    self._scroll_error_shown = True
                    self._gesture_feedback(f"⚠ Can't change the volume: {e}", ERROR)
                    self.feedback.failed("Volume", str(e))
                return
            return

        label = {"up": "Volume up 🔊", "down": "Volume down 🔉"}.get(direction)
        self._gesture_feedback(label or "Holding: move up or down to change the volume")
        if label:
            self.feedback.info(label)

    def show_cheat_sheet(self, studio=None):
        """Show (or hide) the "What can I do?" card for what's running."""

        from backend import cheat_sheet
        from backend.profile_manager import ProfileManager
        from frontend.components.cheat_sheet import CheatSheet

        if getattr(self, "_cheat_sheet", None) is None:
            self._cheat_sheet = CheatSheet()

        worker = self.gesture_worker
        context = self.gesture_context
        if studio is None:
            if context == "auto" and worker is not None:
                studio = worker.studio or "browse"
            elif context in ("presentation", "browse", "custom"):
                studio = context
            else:
                studio = "browse"

        settings = gesture_settings.load()
        wake = False        # "Hey Wield" is said once in the footer, not on every line

        if studio == "custom" and worker is not None:
            title = self.gesture_studio_name or "This studio"
            sections = cheat_sheet.sheet_for_events(worker.events, title, wake)
        else:
            profile = ProfileManager()
            profile.load(studio)
            gesture_map = profile.get_gesture_map()
            if studio == "presentation":
                title = "Presentation Studio"
                sections = cheat_sheet.sheet(gesture_map, cheat_sheet.PRESENTATION_SECTIONS, wake)
            else:
                title = "Browse & Media Studio"
                sections = cheat_sheet.sheet(gesture_map, cheat_sheet.BROWSE_SECTIONS, wake)

        notes = []
        if settings["voice_wake_word"]:
            notes.append("Start phrases with “Hey Wield”")
        if context == "auto" and worker is not None:
            notes.append(f"{worker.arm_gesture} wakes Wield · “Hey Wield, go to sleep” sends it to sleep")
        if not settings["voice_enabled"]:
            notes.append("Voice commands are off (Settings → Voice commands)")
        notes.append("Click it or ✕ to close, or say “Hey Wield, help” again")

        self._cheat_sheet.toggle(f"What you can do · {title}", sections, "   ·   ".join(notes))

    @Slot(list)
    def _on_mouse_ops(self, ops):
        """The hand mouse: move the pointer and press buttons."""
        try:
            for op in ops:
                if op[0] == "move":
                    self.desktop_input.move_to(op[1], op[2])
                elif op[0] == "left_down":
                    self.desktop_input.button("left", True)
                elif op[0] == "left_up":
                    self.desktop_input.button("left", False)
                elif op[0] == "right_click":
                    self.desktop_input.click("right")
        except (InputUnavailable, OSError) as e:
            if not self._scroll_error_shown:
                self._scroll_error_shown = True
                self._gesture_feedback(f"⚠ Hand mouse: {e}", ERROR)
                self.feedback.failed("Hand mouse", str(e))
            worker = self.gesture_worker
            if worker is not None:
                worker.request_mouse(False)

    @Slot(bool)
    def _on_mouse_mode(self, on):
        if on:
            text = "🖱 Hand mouse: pinch to click · ✊ hold to stop"
            self._gesture_feedback(text)
            self.feedback.info(text, sticky=True)
            self.feedback.sounds.play("armed")
        else:
            self._gesture_feedback("Hand mouse off")
            self.feedback.info("🖱 Hand mouse off")

    @Slot(str, float)
    def _on_hold_progress(self, name, progress):
        """Show the bar of a held action (e.g. closing a tab) as it fills."""

        name = name.replace(" (hold)", "")

        if progress <= 0:
            self._gesture_feedback(f"{name}: cancelled", None)
            if self.feedback.overlay.kind == "info":
                self.feedback.overlay.clear()
            return

        if progress >= 1:
            return      # the action runs now and reports itself

        steps = 10
        filled = int(progress * steps)
        bar = "▰" * filled + "▱" * (steps - filled)
        text = f"Keep holding: {name}  {bar}"
        self._gesture_feedback(text)
        self.feedback.info(text, sticky=True)

    def _on_presentation_bindings_changed(
        self
    ):

        self.gesture_page.refresh_gesture_list()

        if self.gesture_context == "presentation" and self.gesture_worker is not None:
            self._bindings_restart.start()

    def _apply_presentation_bindings(
        self
    ):

        if self.gesture_context == "presentation" and self.gesture_worker is not None:
            print("🔄 Presentation controls changed: reloading gestures and voice")
            self.start_gesture_worker("presentation")
            self.presentation_page.set_listening(
                "starting" if self.gesture_worker is not None else False
            )

    def _with_default_voice_phrases(
        self,
        events
    ):
        from backend.automation.events import profile_events
        from backend.profile_manager import ProfileManager
        from backend.voice.defaults import add_default_voice_phrases

        try:
            profile = ProfileManager()
            profile.load("presentation")
            added = add_default_voice_phrases(profile)
        except Exception as e:
            print(f"⚠ Could not add default voice phrases: {e}")
            return events

        if not added:
            return events

        print(f"🎤 Added voice commands to Presentation Studio: {', '.join(added)}")
        # Show them in Gesture Studio and Presentation Studio straight away.
        self.gesture_page.refresh_gesture_list()
        self.presentation_page.refresh_bindings()

        return profile_events(profile.current_profile)

    def _stop_voice(
        self
    ):

        worker, thread = self.voice_worker, self.voice_thread

        self.voice_worker = None
        self.voice_thread = None

        if worker is None:
            return

        worker.stop()

        if thread is not None:
            entry = (thread, worker)
            self._retiring_threads.append(entry)
            thread.finished.connect(lambda e=entry: self._forget_thread(e))
            if not thread.isRunning():
                self._forget_thread(entry)

    @Slot(str)
    def _on_voice_command(
        self,
        trigger
    ):

        if self.sender() is not self.voice_worker:
            return

        events = events_for_gesture(self._voice_events, trigger)

        if not events:
            print(f"[voice] {trigger} isn't assigned to anything here")
            return

        for event in events:
            self._on_gesture_event(event)

    @Slot()
    def _on_voice_armed(
        self
    ):

        if self.sender() is not self.voice_worker:
            return

        self._gesture_feedback("🎤 Listening… say a command")
        self.feedback.armed()

    @Slot(str)
    def _on_voice_error(
        self,
        message
    ):

        print(f"❌ Voice: {message}")

        # Gestures keep working; just tell the user.
        self._gesture_feedback(f"⚠ {message}", ERROR)
        self.feedback.failed("Voice commands", message)

    def _forget_thread(
        self,
        entry
    ):

        if entry in self._retiring_threads:

            self._retiring_threads.remove(entry)

            entry[0].deleteLater()

    # =============================================================
    # WINDOW CLOSE
    # =============================================================

    def closeEvent(
        self,
        event
    ):

        # Keep running in the tray (so routines can fire) if the user chose
        # that, unless they picked Quit.
        hands_free = gesture_settings.load()["hands_free"]

        if (
            not self._quitting
            and self.tray is not None
            and (SettingsManager().get_setting("run_in_background") or hands_free)
        ):

            event.ignore()

            # Hands-free mode keeps watching from the tray; studios stop.
            if self.gesture_context != "auto":
                self.stop_gesture_worker()

            self.hide()

            if not self._told_about_tray:
                self._told_about_tray = True
                self.tray.showMessage(
                    f"{APP_NAME} is still running",
                    "Your routines will run on time. Right-click the tray "
                    "icon to quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )

            return

        # Let the camera thread finish before the app exits. Hide first so
        # closing feels instant even if the webcam is slow to release.
        self.hide()

        self.stop_gesture_worker()

        for thread, _worker in list(self._retiring_threads):

            if not thread.wait(5000):

                print(
                    "⚠ Camera thread did not stop before exit."
                )

        # The foggy window on Home has its own camera thread.
        self.home_page.fog.stop_camera()
        self.home_page.fog.wait_for_camera()

        if self.tray is not None:
            self.tray.hide()

        super().closeEvent(event)

        QApplication.instance().quit()

    # =============================================================
    # ROUTINES
    # =============================================================

    ROUTINE_CHECK_MS = 30_000

    def _setup_routines(self):

        self.activity_log = ActivityLog()
        self.routine_store = RoutineStore()

        # Re-register start-at-sign-in if it was set up under the old name.
        try:
            startup.migrate_legacy()
        except Exception as e:
            print(f"⚠ Could not update the sign-in entry: {e}")

        # How the next recorded action was started ("click", "gesture",
        # "routine"). Routine runs are logged but never learned from.
        self._trigger_source = "click"

        try:
            self.activity_log.prune()
        except OSError:
            pass

        self.routine_timer = QTimer(self)
        self.routine_timer.timeout.connect(self._run_due_routines)
        self.routine_timer.start(self.ROUTINE_CHECK_MS)

        QTimer.singleShot(3000, self._run_due_routines)

        self._refresh_suggestion()

        # First run: the welcome. Then (later) any routine suggestion.
        self._welcome_open = False
        QTimer.singleShot(300, self._maybe_welcome)

        # Ask about a new routine shortly after the app opens.
        QTimer.singleShot(1200, self._show_suggestion_popup)

        # Look for a newer version (at most once a day, in the background).
        QTimer.singleShot(5000, self.check_for_updates)

        # Hands-free mode, if it's on.
        QTimer.singleShot(2500, self._resume_hands_free)

    # =============================================================
    # UPDATES
    # =============================================================

    def check_for_updates(self, force=False):
        """Ask GitHub for a newer release off the UI thread."""

        if getattr(self, "_update_thread", None) is not None:
            return

        self._update_force = force
        self._update_thread = QThread(self)
        self._update_checker = UpdateChecker(force=force)
        self._update_checker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_checker.run)
        self._update_checker.found.connect(self._on_update_result)
        self._update_checker.found.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._update_finished)
        self._update_thread.start()

    def _update_finished(self):
        self._update_thread = None

    @Slot(object)
    def _on_update_result(self, release):
        if release:
            self.update_banner.show_update(release)
        if self._update_force:
            self.settings_page.show_update_result(release)

    def _record(
        self,
        kind,
        target,
        studio=None,
        event=None,
        trigger=None
    ):

        self.activity_log.record(
            kind,
            target,
            studio=studio,
            trigger=trigger or self._trigger_source,
            event=event,
        )

    def _pending_suggestions(self):

        try:
            self.routine_store.load()
            return suggest_routines(
                self.activity_log.entries(),
                self.routine_store,
            )
        except Exception as e:
            print(f"⚠ Could not check for routines: {e}")
            return []

    def _refresh_suggestion(self):
        """Update the Notifications count (suggestions waiting for an answer)."""

        self.sidebar.set_badge(
            "notifications",
            len(self._pending_suggestions())
        )

    def _show_suggestion_popup(self):
        """When Wield opens: offer the top new suggestion, once a day."""

        if not self.isVisible():
            return  # started in the tray; the badge waits for them

        if self._welcome_open or needs_welcome() or getattr(self, "_tour", None):
            return  # not on top of (or before) the welcome or the tour

        for suggestion in self._pending_suggestions():

            if self.routine_store.was_prompted_today(suggestion):
                continue

            self.routine_store.mark_prompted(suggestion)

            dialog = SuggestionDialog(suggestion, self)

            if dialog.exec():
                self._accept_suggestion(suggestion)

            # "Not now": it stays in Notifications.
            break

        self._refresh_suggestion()

    def _accept_suggestion(
        self,
        suggestion
    ):

        self.routine_store.add(suggestion)

        self._after_accept(suggestion)

    @Slot(dict)
    def _after_accept(
        self,
        suggestion
    ):

        settings = SettingsManager()

        if not settings.get_setting("run_in_background") and not startup.is_enabled():

            answer = QMessageBox.question(
                self,
                f"Keep {APP_NAME} running?",
                f"Automations only run while {APP_NAME} is open. Keep it running "
                "in the system tray when you close the window?",
            )

            if answer == QMessageBox.Yes:
                settings.set_setting("run_in_background", True)

        self._refresh_suggestion()

        self.home_page.refresh_studios()

    def _maybe_welcome(self):
        if self.isVisible() and needs_welcome():
            self.show_welcome()
        # Then the tour: after installing, and after every update.
        QTimer.singleShot(400, self._maybe_tour)

    # =============================================================
    # TOUR
    # =============================================================

    def _maybe_tour(self):
        from backend import whats_new
        if not self.isVisible() or self._welcome_open or getattr(self, "_tour", None):
            return
        due = whats_new.tour_due()
        if due:
            self.start_tour(due)

    def start_tour(self, mode="full"):
        """mode: "first" (new install), "update" (starts with what's new) or "full"."""

        from backend import whats_new
        from backend.app_info import VERSION
        from frontend.components.tour import Tour, TourStep
        from PySide6.QtWidgets import QScrollArea

        if getattr(self, "_tour", None) is not None:
            return

        home, browse, settings = self.home_page, self.browse_page, self.settings_page

        def show_home(top=True):
            def run():
                self.go_home()
                if top:
                    home.scroll.verticalScrollBar().setValue(0)
            return run

        def show_page(page, widget=None):
            def run():
                self.stack.setCurrentWidget(page)
                if widget is not None:
                    area = page.findChild(QScrollArea, "ContentScroll") or getattr(page, "scroll", None)
                    if area is not None:
                        area.ensureWidgetVisible(widget, 50, 120)
            return run

        def home_studios():
            self.go_home()
            home.scroll.ensureWidgetVisible(home.studios_anchor, 0, 40)

        def studio_rows():
            from PySide6.QtWidgets import QFrame
            return [home.studios_anchor] + home.findChildren(QFrame, "StudioRow")

        def open_browse():
            self.open_live_workspace(BrowsePage.TITLE)

        if mode == "update":
            intro = TourStep(
                f"What's new in {APP_NAME} {VERSION}",
                "Here's what changed. Next, a quick look around (or skip it).",
                prepare=show_home(), extra=whats_new.notes(),
            )
        elif mode == "first":
            intro = TourStep(
                f"Welcome to {APP_NAME} 👋",
                "A quick look around: about a minute. Use Next, or the arrow keys.",
                prepare=show_home(),
            )
        else:
            intro = TourStep(
                f"A quick tour of {APP_NAME}",
                "Use Next, or the arrow keys. Esc ends the tour.",
                prepare=show_home(),
            )

        steps = [
            intro,
            TourStep(
                "Your window",
                "Press <b>Start camera</b>, then point one finger to write on the fog. "
                "A fist pauses, an open palm held for a second wipes it. Pick the pen "
                "size and fog colour just below.",
                target=lambda: home.fog, prepare=show_home(),
            ),
            TourStep(
                "Camera status",
                "Always shows whether your camera is on, and what hands-free mode is "
                "doing. Your camera is only ever used on this computer.",
                target=lambda: home.camera_pill, prepare=show_home(),
            ),
            TourStep(
                "Your studios",
                "Each studio is a set of gestures for one job. <b>Click a row</b> to "
                "open it. Optional studios have a ✕ to remove them; bring them back "
                "in Settings.",
                target=studio_rows, prepare=home_studios,
            ),
            TourStep(
                "Browse & Media Studio",
                "Scroll, control videos and music, switch tabs and use the hand mouse. "
                "<b>Click a section</b> to open it; <b>+</b> adds a gesture, motion or "
                "phrase, ✕ removes one.",
                target=lambda: [f for f, *_ in browse.sections.values()], prepare=open_browse,
            ),
            TourStep(
                "Start",
                "Press Start, then switch to your browser, a PDF or Word. Wield keeps "
                "watching in the background.",
                target=lambda: browse.start_button, prepare=open_browse,
            ),
            TourStep(
                "What can I do?",
                "Shows every gesture and phrase on screen, over any app. You can also "
                "say <b>“Hey Wield, help”</b>.",
                target=lambda: browse.help_button, prepare=open_browse,
            ),
            TourStep(
                "Hands-free mode",
                "Turn this on and you won't need to open a studio: make ✋ (or say "
                "“Hey Wield, wake up”) and your gestures work in any app.",
                target=lambda: settings.hands_free, prepare=show_page(settings, settings.hands_free),
            ),
            TourStep(
                "Voice commands",
                "Turn on voice and download the small speech model once. Then say "
                "“Hey Wield, scroll down”, “next slide”, “mouse mode”…",
                target=lambda: settings.voice_enabled, prepare=show_page(settings, settings.voice_enabled),
            ),
            TourStep(
                "You're all set",
                "Take this tour again any time: <b>Settings → About → Take the tour</b>.",
                prepare=show_home(),
            ),
        ]

        self._tour = Tour(self, steps)
        self._tour.finished.connect(self._after_tour)
        self._tour.start()

    def _after_tour(self, completed):
        from backend import whats_new
        whats_new.mark_seen()
        self._tour = None
        self.go_home()

    def show_welcome(self):

        self._welcome_open = True

        dialog = WelcomeDialog(self)
        dialog.exec()

        self._welcome_open = False

        self.sidebar.refresh_user()
        self.home_page.refresh_studios()

        if dialog.theme_changed:
            # Themes apply at startup.
            self.restart_app()

    def _on_name_changed(self):
        self.sidebar.refresh_user()
        self.home_page.refresh_studios()

    def _run_due_routines(self):

        self.routine_store.load()

        for routine in due_routines(self.routine_store.routines):

            print(f"⏰ Routine: {routine['kind']} {routine['target']}")

            self._trigger_source = "routine"

            try:

                if routine["kind"] == "studio":
                    self.show_from_tray()
                    self.open_live_workspace(routine["target"])

                elif routine["kind"] == "launch":
                    self.launch_all_events(routine["target"])

                elif routine.get("event"):
                    self.launch_specific_event(
                        routine.get("studio") or "",
                        routine["event"],
                    )

            except Exception as e:
                print(f"❌ Routine failed: {e}")

            finally:
                self._trigger_source = "click"

            self.routine_store.mark_run(
                routine["id"],
                datetime.date.today(),
            )

            if self.tray is not None:
                self.tray.showMessage(
                    f"{APP_NAME} routine",
                    f"Done: {routine['kind'].replace('studio', 'opened')} "
                    f"{routine['target']} ({routine['time']})",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )

        if self.stack.currentWidget() is self.activity_page:
            self.activity_page.refresh()

        if self.stack.currentWidget() is self.notifications_page:
            self.notifications_page.refresh()

    # =============================================================
    # SYSTEM TRAY
    # =============================================================

    def _setup_tray(self):

        self._quitting = False
        self._told_about_tray = False
        self.tray = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray = QSystemTrayIcon(_app_icon(), self)
        self.tray.setToolTip(APP_NAME)

        menu = QMenu(self)

        open_action = QAction(f"Open {APP_NAME}", self)
        open_action.triggered.connect(self.show_from_tray)
        menu.addAction(open_action)

        help_action = QAction("What can I do?", self)
        help_action.triggered.connect(lambda: self.show_cheat_sheet())
        menu.addAction(help_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

        self.tray.activated.connect(
            lambda reason: self.show_from_tray()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )

        self.tray.show()

    def show_from_tray(self):

        self.showNormal()
        self.raise_()
        self.activateWindow()

        # Started in the tray after an update: the tour waits until now.
        QTimer.singleShot(500, self._maybe_welcome)

    def restart_app(self):
        """Start a fresh Wield (themes apply at startup), then quit."""

        args = [a for a in sys.argv if a != "--background"]

        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, args[1:])
        else:
            QProcess.startDetached(sys.executable, args)

        self.quit_app()

    def quit_app(self):

        self._quitting = True
        self.close()



# =============================================================
# STYLESHEET
# =============================================================

def _load_stylesheet(
    app
):

    # theme.qss mapped to the theme chosen in Settings.
    app.setStyleSheet(
        global_stylesheet()
    )


# =============================================================
# CRASH NOTICE
# =============================================================

class _CrashNotifier(QObject):
    """Carries an uncaught error (from any thread) to the UI thread."""

    crashed = Signal(object)

    def __init__(self):
        super().__init__()
        self._shown = False
        self.crashed.connect(self._show)

    @Slot(object)
    def _show(self, error):

        if self._shown:
            return

        self._shown = True

        QMessageBox.warning(
            None,
            f"{APP_NAME} hit a problem",
            f"Something went wrong: {error}\n\n"
            f"{APP_NAME} will keep running, but if things look wrong, "
            "restart it. Details were saved to the log "
            "(Settings → About → Open log).",
        )


# =============================================================
# APP ICON
# =============================================================

def _app_icon():
    """The Wield icon (assets/icons/wield.png, made by tools/make_icon.py)."""

    path = os.path.join(APP_DIR, "assets", "icons", "wield.png")

    if os.path.isfile(path):
        return QIcon(path)

    # Fallback if the file is missing: the brand colour.
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(PRIMARY))
    return QIcon(pixmap)


# =============================================================
# MAIN
# =============================================================

def main():

    if "--self-test" in sys.argv:
        from backend.self_test import run
        sys.exit(run())

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)

    # Scrolling over a dropdown/slider scrolls the page instead of
    # changing the value (kept on the app object so it lives as long).
    from frontend.components import wheel_guard
    app.wheel_guard = wheel_guard.install(app)

    # The packaged app has no console: keep a log, and tell the user (once)
    # if something unexpected goes wrong instead of silently misbehaving.
    # Kept on the app object so it lives as long as the app does.
    app.crash_notifier = _CrashNotifier()
    log_file = app_log.install(on_crash=app.crash_notifier.crashed.emit)
    print(f"📝 Logging to {log_file}")

    app.setFont(
        QFont(
            "Inter",
            14
        )
    )

    _load_stylesheet(
        app
    )

    # Closing the window may only hide it (tray); quit explicitly instead.
    app.setQuitOnLastWindowClosed(False)

    app.setWindowIcon(_app_icon())

    window = MainWindow()

    if "--background" in sys.argv and window.tray is not None:
        # Started at sign-in: stay in the tray until the user opens it.
        pass
    else:
        window.show()
        window._center_on_screen()

    sys.exit(
        app.exec()
    )


# =============================================================
# ENTRY POINT
# =============================================================

if __name__ == "__main__":

    main()