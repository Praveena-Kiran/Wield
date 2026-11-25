"""
A section that opens and closes, used by the studios so they look and
work the same way. Closed, it's one line: an icon, a name and a short
summary of what it does now. Open, it shows its contents.

    section = CollapsibleSection("Scroll", "↕", "👍 scrolls down")
    section.body_layout.addWidget(...)
    section.toggled.connect(...)

An Accordion keeps only one section of a page open at a time:

    accordion = Accordion()
    accordion.add("scroll", section)
    accordion.toggle("scroll")
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frontend.styles.theme import (
    BORDER,
    OVERLAY_1,
    OVERLAY_2,
    PRIMARY,
    PRIMARY_TEXT,
    SECONDARY_TEXT,
    SURFACE,
)

NAME_WIDTH = 190


class CollapsibleSection(QFrame):

    toggled = Signal(bool)             # True = opened

    def __init__(self, title, icon="", summary="", parent=None, name_width=NAME_WIDTH):
        super().__init__(parent)
        self.setObjectName("Section")
        self.setProperty("open", False)
        self.setStyleSheet(f"""
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
            QFrame#Section QLabel#SectionBadge {{
                background: {OVERLAY_2}; color: {PRIMARY}; border-radius: 19px;
                font-size: 17px; font-weight: 700;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header: the whole line is the button.
        self.head = QPushButton()
        self.head.setObjectName("SectionHead")
        self.head.setCursor(Qt.CursorShape.PointingHandCursor)
        self.head.setAccessibleName(f"{title}: show or hide")
        self.head.setMinimumHeight(64)
        line = QHBoxLayout(self.head)
        line.setContentsMargins(16, 10, 18, 10)
        line.setSpacing(14)

        self.badge = QLabel(icon)
        self.badge.setObjectName("SectionBadge")
        self.badge.setFixedSize(38, 38)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line.addWidget(self.badge)

        self.name = QLabel(title)
        self.name.setFixedWidth(name_width)
        self.name.setStyleSheet(f"color: {PRIMARY_TEXT}; font-size: 15px; font-weight: 700;")
        line.addWidget(self.name)

        self.summary = QLabel()
        self.summary.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        self.summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        line.addWidget(self.summary, 1)

        self.chevron = QLabel("▸")
        self.chevron.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 14px;")
        line.addWidget(self.chevron)
        for label in (self.badge, self.name, self.summary, self.chevron):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        outer.addWidget(self.head)

        self.body = QWidget()
        self.body.setObjectName("SectionBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(68, 0, 18, 14)
        self.body_layout.setSpacing(8)
        self.body.hide()
        outer.addWidget(self.body)

        self.head.clicked.connect(lambda: self.set_open(not self.is_open(), user=True))
        self.set_summary(summary)

    def is_open(self):
        return not self.body.isHidden()

    def set_open(self, open_, user=False):
        """Open or close. user=True emits toggled (an Accordion listens)."""
        open_ = bool(open_)
        changed = open_ != self.is_open()
        self.body.setVisible(open_)
        self.chevron.setText("▾" if open_ else "▸")
        self.setProperty("open", open_)
        self.style().unpolish(self)
        self.style().polish(self)
        if changed or user:
            self.toggled.emit(open_)

    def set_summary(self, text):
        self.summary.setText(text)
        self.summary.setToolTip(text)


class Accordion:
    """Sections of which at most one is open."""

    def __init__(self):
        self.sections = {}

    def add(self, key, section):
        self.sections[key] = section
        section.toggled.connect(lambda open_, k=key: self._on_toggled(k, open_))
        return section

    def toggle(self, key):
        section = self.sections[key]
        section.set_open(not section.is_open())

    def _on_toggled(self, key, open_):
        if not open_:
            return
        for other, section in self.sections.items():
            if other != key and section.is_open():
                section.set_open(False)

    def open_key(self):
        return next((k for k, s in self.sections.items() if s.is_open()), None)
