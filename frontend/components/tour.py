"""
A guided tour, like a new phone's: the window dims, the thing being
explained is lit up, and a card next to it says what it does.

    tour = Tour(window, steps)
    tour.finished.connect(...)        # done or skipped
    tour.start()

A step is a TourStep:
    title, text      what the card says
    target()         -> widget or list of widgets to light up (None: a card
                        in the middle, for the welcome and the last step)
    prepare()        run first, e.g. open the right page

Keys: → / Enter next, ← back, Esc skip.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend.styles.theme import (
    BORDER,
    ON_PRIMARY,
    OVERLAY_1,
    PRIMARY,
    PRIMARY_HOVER,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
    SURFACE,
    TEXT_MUTED,
)

PADDING = 8           # space around the lit-up widget
CARD_WIDTH = 380
SETTLE_MS = 350       # let a page switch / scroll finish before measuring


@dataclass
class TourStep:
    title: str
    text: str
    target: Optional[Callable] = None
    prepare: Optional[Callable] = None
    extra: list = field(default_factory=list)     # bullet points (what's new)


class _Card(QFrame):

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("TourCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setStyleSheet(f"""
            QFrame#TourCard {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 18px;
            }}
            QLabel {{ background: transparent; border: none; }}
            QPushButton {{
                border-radius: 16px; padding: 0 16px; min-height: 32px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton#Next {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: none; }}
            QPushButton#Next:hover {{ background: {PRIMARY_HOVER}; }}
            QPushButton#Back {{ background: {OVERLAY_1}; color: {PRIMARY_TEXT}; border: 1px solid {BORDER}; }}
            QPushButton#Skip {{ background: transparent; color: {SECONDARY_TEXT}; border: none; padding: 0 6px; }}
            QPushButton#Skip:hover {{ color: {PRIMARY_TEXT}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(8)

        self.progress = QLabel()
        self.progress.setStyleSheet(f"color: {PRIMARY}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(self.progress)

        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet(f"color: {PRIMARY_TEXT}; font-size: 17px; font-weight: 700;")
        layout.addWidget(self.title)

        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 13px;")
        layout.addWidget(self.text)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.skip = QPushButton("Skip tour")
        self.skip.setObjectName("Skip")
        buttons.addWidget(self.skip)
        buttons.addStretch()
        self.back = QPushButton("Back")
        self.back.setObjectName("Back")
        buttons.addWidget(self.back)
        self.next = QPushButton("Next")
        self.next.setObjectName("Next")
        self.next.setDefault(True)
        buttons.addWidget(self.next)
        for button in (self.skip, self.back, self.next):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addSpacing(6)
        layout.addLayout(buttons)


class Tour(QWidget):

    finished = Signal(bool)        # True = went to the end, False = skipped

    def __init__(self, window, steps):
        super().__init__(window)
        self.window_ = window
        self.steps = list(steps)
        self.index = 0
        self.hole = None           # QRect lit up, in this widget's coordinates

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.card = _Card(self)
        self.card.next.clicked.connect(self.next)
        self.card.back.clicked.connect(self.back)
        self.card.skip.clicked.connect(lambda: self._end(False))

        window.installEventFilter(self)
        self.hide()

    # ---------------------------------------------------------
    # Steps
    # ---------------------------------------------------------

    def start(self, index=0):
        self.setGeometry(self.window_.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self.go(index)

    def go(self, index):
        self.index = max(0, min(index, len(self.steps) - 1))
        step = self.steps[self.index]
        if step.prepare is not None:
            step.prepare()
        # Measure once the page has switched / scrolled.
        self.hole = None
        self.card.hide()
        self.update()
        QTimer.singleShot(SETTLE_MS, self._show_step)

    def next(self):
        if self.index >= len(self.steps) - 1:
            self._end(True)
        else:
            self.go(self.index + 1)

    def back(self):
        if self.index > 0:
            self.go(self.index - 1)

    def _end(self, completed):
        self.hide()
        self.window_.removeEventFilter(self)
        self.finished.emit(completed)
        self.deleteLater()

    def _show_step(self):
        if not self.isVisible():
            return
        step = self.steps[self.index]
        last = self.index == len(self.steps) - 1

        self.card.progress.setText(f"{self.index + 1} OF {len(self.steps)}")
        self.card.title.setText(step.title)
        text = step.text
        if step.extra:
            text += "<ul style='margin-left:-20px;'>" + "".join(
                f"<li style='margin-bottom:4px;'>{item}</li>" for item in step.extra) + "</ul>"
        self.card.text.setText(text)
        # Rich text (the what's-new list) needs measuring at the real width,
        # or the card comes out too short and clips the last lines.
        self.card.text.ensurePolished()
        self.card.text.setMinimumHeight(self.card.text.heightForWidth(CARD_WIDTH - 44) + 8)
        self.card.back.setVisible(self.index > 0)
        self.card.next.setText("Done" if last else "Next")
        self.card.skip.setVisible(not last)

        self.hole = self._target_rect(step)
        self.card.adjustSize()
        self._place_card()
        self.card.show()
        self.card.raise_()
        self.update()
        self.setFocus()

    def _target_rect(self, step):
        if step.target is None:
            return None
        try:
            targets = step.target()
        except Exception:  # noqa: BLE001 - a missing widget just centres the card
            return None
        if targets is None:
            return None
        if not isinstance(targets, (list, tuple)):
            targets = [targets]
        rect = QRect()
        for widget in targets:
            if widget is None or not widget.isVisible():
                continue
            top_left = widget.mapTo(self.window_, widget.rect().topLeft())
            rect = rect.united(QRect(top_left, widget.size()))
        if rect.isNull():
            return None
        return rect.adjusted(-PADDING, -PADDING, PADDING, PADDING).intersected(
            self.rect().adjusted(4, 4, -4, -4))

    def _place_card(self):
        card = self.card
        w, h = card.width(), card.sizeHint().height()
        area = self.rect()

        if self.hole is None:
            card.move(area.center().x() - w // 2, area.center().y() - h // 2)
            return

        hole = self.hole
        gap = 14
        # Below, above, right, left of the lit-up area: the first that fits.
        options = [
            (hole.left(), hole.bottom() + gap),
            (hole.left(), hole.top() - gap - h),
            (hole.right() + gap, hole.top()),
            (hole.left() - gap - w, hole.top()),
        ]
        for x, y in options:
            x = max(area.left() + 12, min(x, area.right() - w - 12))
            if area.top() + 8 <= y and y + h <= area.bottom() - 8:
                card.move(x, y)
                return
        card.move(area.right() - w - 24, area.bottom() - h - 24)

    # ---------------------------------------------------------
    # Painting and input
    # ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        if self.hole is not None:
            path.addRoundedRect(QRectF(self.hole), 14, 14)
            path.setFillRule(Qt.FillRule.OddEvenFill)
        painter.fillPath(path, QColor(0, 0, 0, 165))
        if self.hole is not None:
            painter.setPen(QColor(PRIMARY))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.hole), 14, 14)

    def mousePressEvent(self, event):
        event.accept()             # the tour keeps the clicks while it's on

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.next()
        elif key == Qt.Key.Key_Left:
            self.back()
        elif key == Qt.Key.Key_Escape:
            self._end(False)
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.window_ and event.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(self.window_.rect())
            QTimer.singleShot(0, self._show_step)
        return False
