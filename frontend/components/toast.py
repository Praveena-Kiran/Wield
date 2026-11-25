"""
A small message that pops up at the bottom of the window and goes away
by itself, instead of a "Status: ..." line.

    toast(widget, "Saved.")                  # any widget in the window
    toast(widget, "Couldn't save.", "error")

kind: "success" (default), "info" or "error". A new message replaces the
one showing.
"""

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel

from frontend.styles.theme import BORDER, ERROR, PRIMARY, PRIMARY_TEXT, SUCCESS, SURFACE

SHOW_MS = 2600
ERROR_SHOW_MS = 5000
FADE_MS = 220
BOTTOM_GAP = 28

ICONS = {"success": "✓", "info": "ℹ", "error": "!"}
COLOURS = {"success": SUCCESS, "info": PRIMARY, "error": ERROR}


class Toast(QFrame):

    def __init__(self, window):
        super().__init__(window)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 20, 10)
        layout.setSpacing(10)
        self.icon = QLabel()
        self.icon.setFixedSize(22, 22)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon)
        self.text = QLabel()
        self.text.setWordWrap(True)
        layout.addWidget(self.text)

        self.opacity = QGraphicsOpacityEffect(self)
        self.opacity.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade.setDuration(FADE_MS)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self._after_fade)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)

        self._follow = _Follow(self)
        window.installEventFilter(self._follow)
        self.hide()

    def show_message(self, text, kind="success"):
        colour = COLOURS.get(kind, SUCCESS)
        self.setStyleSheet(f"""
            QFrame#Toast {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-left: 3px solid {colour};
                border-radius: 14px;
            }}
            QLabel {{ background: transparent; border: none; color: {PRIMARY_TEXT}; font-size: 13px; }}
        """)
        self.icon.setText(ICONS.get(kind, ICONS["success"]))
        self.icon.setStyleSheet(
            f"background: {colour}; color: {SURFACE}; border-radius: 11px; "
            "font-size: 12px; font-weight: 800;"
        )
        self.text.setText(text)
        # One line when it fits; wrap only past the maximum width.
        self.text.ensurePolished()           # measure with the real font size
        self.text.setFixedWidth(min(self.text.fontMetrics().horizontalAdvance(text) + 8, 520))
        self.adjustSize()
        self.place()

        self.fade.stop()
        self.opacity.setOpacity(1.0)
        self.show()
        self.raise_()
        self.timer.start(ERROR_SHOW_MS if kind == "error" else SHOW_MS)

    def place(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.move((parent.width() - self.width()) // 2,
                  parent.height() - self.height() - BOTTOM_GAP)

    def dismiss(self):
        if not self.isVisible():
            return
        self.fade.stop()
        self.fade.setStartValue(self.opacity.opacity())
        self.fade.setEndValue(0.0)
        self.fade.start()

    def _after_fade(self):
        if self.opacity.opacity() <= 0.01:
            self.hide()


class _Follow(QObject):
    """Keeps the toast at the bottom when the window is resized."""

    def __init__(self, toast_):
        super().__init__(toast_)
        self.toast = toast_

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and self.toast.isVisible():
            self.toast.place()
        return False


def toast(widget, text, kind="success"):
    """Show a message at the bottom of widget's window. Returns the Toast."""
    window = widget.window() if widget is not None else None
    if window is None or not text:
        return None
    current = getattr(window, "_wield_toast", None)
    if current is None:
        current = Toast(window)
        window._wield_toast = current
    current.show_message(text, kind)
    return current
