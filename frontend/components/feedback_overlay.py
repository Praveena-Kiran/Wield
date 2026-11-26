"""
Wield - Feedback overlay and controller

FeedbackOverlay: a small pill at the bottom of the screen that stays on
top of everything (including a full-screen PowerPoint slideshow), never
takes focus and lets clicks through. It shows what Wield just did:

    ● Listening                  (activated, stays while active; the dot breathes)
    ● 👍  Next slide             (action ran, fades after a moment)
    ● Next slide didn't work     (error)

It's meant to feel calm: a soft dark pill with a small coloured dot, no
bright borders or warning symbols, fading in and out gently.

Feedback ties it to the sound cues and the user's settings, and only
shows the overlay when Wield's own window isn't the one in front (when
it is, the page's status line already says the same thing).
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from backend.feedback.sounds import SoundCues
from backend.settings import gesture_settings

# Soft, slightly muted dot colours.
KIND_COLORS = {
    "info": "#8FB8F0",
    "armed": "#7FD8B4",
    "action": "#FFB08A",
    "error": "#F2A0A0",
}

SHOW_MS = 1800
BOTTOM_MARGIN = 48
SHADOW_ROOM = 18          # transparent space around the pill for its shadow


class _Dot(QWidget):
    """A small round dot; it breathes (fades in and out) while listening."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(10, 10)
        self.color = QColor(KIND_COLORS["info"])
        self.level = 1.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._phase = 0.0

    def set_color(self, color, breathing=False):
        self.color = QColor(color)
        self.level = 1.0
        self._phase = 0.0
        if breathing:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self):
        import math
        self._phase += 0.04 * math.tau / 1.6        # one breath every ~1.6 s
        self.level = 0.55 + 0.45 * (0.5 + 0.5 * math.cos(self._phase))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.color)
        color.setAlphaF(self.level)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(1, 1, 8, 8)


class FeedbackOverlay(QWidget):

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(SHADOW_ROOM, SHADOW_ROOM, SHADOW_ROOM, SHADOW_ROOM)

        self.pill = QFrame()
        self.pill.setObjectName("Pill")
        self.pill.setStyleSheet("""
            QFrame#Pill {
                background: rgba(28, 26, 24, 214);
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 19px;
            }
            QLabel { background: transparent; border: none; }
        """)
        shadow = QGraphicsDropShadowEffect(self.pill)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.pill.setGraphicsEffect(shadow)
        outer.addWidget(self.pill)

        row = QHBoxLayout(self.pill)
        row.setContentsMargins(16, 9, 20, 9)
        row.setSpacing(10)
        self.dot = _Dot()
        row.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.label = QLabel()
        self.label.setStyleSheet(
            "color: rgba(246, 241, 234, 235); font-size: 15px; font-weight: 500;"
        )
        row.addWidget(self.label)

        # A thin line that fills up while you hold a sign (closing a tab).
        self.bar = QFrame()
        self.bar.setFixedSize(64, 4)
        self.bar.setStyleSheet("background: rgba(255, 255, 255, 40); border-radius: 2px;")
        self.bar_fill = QFrame(self.bar)
        self.bar_fill.setStyleSheet(f"background: {KIND_COLORS['action']}; border-radius: 2px;")
        self.bar_fill.setGeometry(0, 0, 0, 4)
        row.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignVCenter)
        self.bar.hide()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._after_fade)

        self.kind = None

    def show_message(self, text, kind="info", sticky=False, progress=None):
        """Show `text`. Sticky messages stay until replaced or cleared.
        progress (0..1) shows a line filling up next to it."""
        self.kind = kind
        self.label.setText(text)
        self.bar.setVisible(progress is not None)
        if progress is not None:
            self.bar_fill.setGeometry(0, 0, int(64 * max(0.0, min(progress, 1.0))), 4)
        self.dot.set_color(KIND_COLORS.get(kind, KIND_COLORS["info"]), breathing=kind == "armed")
        self.adjustSize()
        self._place()

        self._fade.stop()
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
            self._fade.setDuration(180)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        else:
            self.setWindowOpacity(1.0)
        self.raise_()

        self._hide_timer.stop()
        if not sticky:
            self._hide_timer.start(SHOW_MS)

    def clear(self):
        self._hide_timer.stop()
        if self.isVisible():
            self._fade_out()

    def _place(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.x() + (area.width() - self.width()) // 2,
            area.y() + area.height() - self.height() - BOTTOM_MARGIN + SHADOW_ROOM,
        )

    def _fade_out(self):
        self._fade.stop()
        self._fade.setDuration(350)
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _after_fade(self):
        if self.windowOpacity() <= 0.01:
            self.hide()
            self.dot.set_color(self.dot.color)      # stop breathing
            self.kind = None


class Feedback:
    """Sound + overlay feedback, following the user's settings."""

    def __init__(self, main_window=None, overlay=None, sounds=None):
        self.main_window = main_window
        self.overlay = overlay or FeedbackOverlay()
        self.sounds = sounds or SoundCues()
        self.overlay_enabled = True
        self.reload()

    def reload(self):
        settings = gesture_settings.load()
        self.sounds.enabled = settings["sound_feedback"]
        self.overlay_enabled = settings["feedback_overlay"]
        if not self.overlay_enabled:
            self.overlay.clear()

    def _overlay(self, text, kind, sticky=False):
        if not self.overlay_enabled:
            return
        # Wield's own window already shows this in its status line.
        if self.main_window is not None and self.main_window.isActiveWindow():
            return
        self.overlay.show_message(text, kind, sticky)

    # ---------------------------------------------------------
    # Events
    # ---------------------------------------------------------

    def armed(self, trigger=""):
        self.reload()  # settings may have changed
        self.sounds.play("armed")
        self._overlay("Listening", "armed", sticky=True)

    def disarmed(self):
        self.reload()  # settings may have changed
        self.sounds.play("disarmed")
        if self.overlay.kind == "armed":
            self.overlay.clear()

    def action(self, trigger, name):
        self.reload()  # settings may have changed
        self.sounds.play("action")
        self._overlay(f"{_short(trigger)}   {name}" if _short(trigger) else name, "action")

    def failed(self, name, message=""):
        self.reload()  # settings may have changed
        self.sounds.play("error")
        self._overlay(f"{name} didn't work", "error")

    def info(self, text, sticky=False, progress=None):
        self.reload()  # settings may have changed
        if not self.overlay_enabled:
            return
        if self.main_window is not None and self.main_window.isActiveWindow():
            return
        self.overlay.show_message(text, "info", sticky, progress)

    def stopped(self):
        self.overlay.clear()


def _short(trigger):
    """Just the emoji of a gesture ("👍 Thumbs Up" -> "👍"); words for the
    rest are left out, the action says enough."""
    trigger = (trigger or "").strip()
    first = trigger.split(" ", 1)[0]
    return first if first and not first[0].isalnum() and not first.startswith("🎤") else ""
