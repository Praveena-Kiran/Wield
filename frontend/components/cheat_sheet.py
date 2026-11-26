"""
The "What can I do?" card: shown over any app by "Hey Wield, help" (or a
button), listing what works right now. It never takes the keyboard focus
from the app you're in. Close it with ✕, a click anywhere on it, by
asking again, or just wait: it goes after a while.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

SHOW_MS = 20000
COLUMNS = 3
LINE_WIDTH = 280


class CheatSheet(QWidget):

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("Sheet")
        self.card.setStyleSheet("""
            QFrame#Sheet {
                background: rgba(17, 16, 20, 238);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 24px;
            }
            QLabel { background: transparent; color: #F5F1EB; }
            QPushButton#Close {
                background: rgba(255, 255, 255, 0.08); color: #F5F1EB;
                border: none; border-radius: 16px;
                min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px;
                font-size: 15px; font-weight: 700; padding: 0;
            }
            QPushButton#Close:hover { background: rgba(255, 148, 102, 0.35); }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        outer.addWidget(self.card)
        self.layout_ = QVBoxLayout(self.card)
        self.layout_.setContentsMargins(28, 22, 28, 20)
        self.layout_.setSpacing(14)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def toggle(self, title, sections, footer=""):
        """Show the sheet (or hide it if it's already up)."""
        if self.isVisible():
            self.hide()
            return
        self.show_sheet(title, sections, footer)

    def show_sheet(self, title, sections, footer=""):

        while self.layout_.count():
            item = self.layout_.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                _clear(item.layout())

        top = QHBoxLayout()
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        top.addWidget(heading, 1)
        close = QPushButton("✕")
        close.setObjectName("Close")
        close.setToolTip("Close")
        close.setAccessibleName("Close")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.hide)
        self.close_button = close
        top.addWidget(close, 0, Qt.AlignTop)
        self.layout_.addLayout(top)

        if not sections:
            empty = QLabel("Nothing is set up here yet. Add gestures or phrases in the studio.")
            empty.setStyleSheet("color: #A69F96; font-size: 14px;")
            self.layout_.addWidget(empty)
        else:
            # Sections go into balanced columns (shortest column next), so a
            # long list doesn't make the card taller than a laptop screen.
            columns = COLUMNS if len(sections) <= 6 else COLUMNS + 1
            row = QHBoxLayout()
            row.setSpacing(28)
            stacks, heights = [], []
            for _ in range(columns):
                stack = QVBoxLayout()
                stack.setSpacing(14)
                row.addLayout(stack)
                stacks.append(stack)
                heights.append(0)
            for section, rows in sections:
                i = heights.index(min(heights))
                stacks[i].addWidget(_section(section, rows))
                heights[i] += len(rows) + 1
            for stack in stacks:
                stack.addStretch()
            self.layout_.addLayout(row)

        if footer:
            note = QLabel(footer)
            note.setStyleSheet("color: #968F86; font-size: 12px;")
            self.layout_.addWidget(note)

        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(SHOW_MS)

    def mousePressEvent(self, event):
        # A click anywhere on the card closes it.
        self.hide()

    def _place(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.setMaximumWidth(int(area.width() * 0.9))
        self.adjustSize()
        self.move(
            area.x() + (area.width() - self.width()) // 2,
            area.y() + (area.height() - self.height()) // 2,
        )


def _section(title, rows):
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    heading = QLabel(title.upper())
    heading.setStyleSheet("color: #FF9466; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
    layout.addWidget(heading)

    for action, triggers in rows:
        line = QLabel(
            f"<b>{_escape(action)}</b><br>"
            f"<span style='color:#B9B2A8;'>{_escape(' · '.join(triggers))}</span>"
        )
        line.setTextFormat(Qt.TextFormat.RichText)
        line.setWordWrap(True)
        line.setFixedWidth(LINE_WIDTH)
        line.setStyleSheet("font-size: 13px;")
        line.ensurePolished()        # measure with the real font size
        line.setMinimumHeight(line.heightForWidth(LINE_WIDTH) + 4)
        layout.addWidget(line)
    return box


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())
