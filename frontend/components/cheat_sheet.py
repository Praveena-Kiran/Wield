"""
The "What can I do?" card: shown over any app by "Hey Wield, help" (or a
button), listing what works right now. It never takes clicks or focus,
and fades after a while; asking again closes it.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

SHOW_MS = 20000
COLUMNS = 3


class CheatSheet(QWidget):

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
        """)
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

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.layout_.addWidget(heading)

        if not sections:
            empty = QLabel("Nothing is set up here yet. Add gestures or phrases in the studio.")
            empty.setStyleSheet("color: #A69F96; font-size: 14px;")
            self.layout_.addWidget(empty)
        else:
            grid = QGridLayout()
            grid.setHorizontalSpacing(28)
            grid.setVerticalSpacing(14)
            for i, (section, rows) in enumerate(sections):
                grid.addWidget(_section(section, rows), i // COLUMNS, i % COLUMNS, Qt.AlignTop)
            self.layout_.addLayout(grid)

        if footer:
            note = QLabel(footer)
            note.setStyleSheet("color: #968F86; font-size: 12px;")
            self.layout_.addWidget(note)

        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(SHOW_MS)

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
        line.setFixedWidth(300)
        line.setStyleSheet("font-size: 13px;")
        line.ensurePolished()        # measure with the real font size
        line.setMinimumHeight(line.heightForWidth(300) + 4)
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
