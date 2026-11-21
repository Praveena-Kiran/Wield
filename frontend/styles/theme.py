"""
Wield design tokens and themes.

Every screen imports its colours from here (BG_DARK, SURFACE, PRIMARY, ...).
The values come from the theme the user picked in Settings, read once when
the app starts; changing theme asks for a restart.

Themes: dark (default), light, jungle, galaxy. Jungle and Galaxy also have a
decorative backdrop (BACKDROP) painted behind the pages.

Tokens beyond the classic palette, so screens never hardcode white/black:
    OVERLAY_1 / OVERLAY_2   subtle fills for secondary buttons (rest / hover)
    OVERLAY_BORDER          border for hovered secondary buttons
    TEXT_STRONG             strongest text (pure white on dark themes)
    ON_PRIMARY              text on a PRIMARY-coloured button
"""

import json
import os


THEMES = {
    "dark": {
        # Warm charcoal with an apricot accent (the peach of the logo).
        "label": "Dark",
        "BG_DARK": "#0F0E0D",
        "SURFACE": "#181715",
        "SURFACE_HOVER": "#201E1B",
        "SURFACE_ACTIVE": "#282521",
        "SURFACE_OVERLAY": "#1C1A18",
        "BORDER": "#2F2B27",
        "BORDER_SUBTLE": "#25221F",
        "PRIMARY": "#FF9466",
        "PRIMARY_HOVER": "#FFA781",
        "PRIMARY_PRESSED": "#F07E4E",
        "PRIMARY_MUTED": "rgba(255, 148, 102, 0.15)",
        "SECONDARY_ACCENT": "#6FD3B0",
        "PRIMARY_TEXT": "#F5F1EB",
        "SECONDARY_TEXT": "#A69F96",
        "TEXT_MUTED": "#968F86",
        "TEXT_DISABLED": "#55504A",
        "TEXT_STRONG": "#FFFFFF",
        # Dark text on the light apricot reads better than white.
        "ON_PRIMARY": "#1F120B",
        "OVERLAY_1": "rgba(255, 245, 235, 0.04)",
        "OVERLAY_2": "rgba(255, 245, 235, 0.08)",
        "OVERLAY_BORDER": "rgba(255, 245, 235, 0.16)",
        "BACKDROP": None,
    },
    "light": {
        # Warm paper with a burnt-orange accent.
        "label": "Light",
        "BG_DARK": "#F7F3EC",
        "SURFACE": "#FFFDF9",
        "SURFACE_HOVER": "#F3EEE6",
        "SURFACE_ACTIVE": "#EBE4D9",
        "SURFACE_OVERLAY": "#FFFDF9",
        "BORDER": "#E3DACC",
        "BORDER_SUBTLE": "#EDE6DB",
        "PRIMARY": "#B8501C",
        "PRIMARY_HOVER": "#C75E28",
        "PRIMARY_PRESSED": "#A04515",
        "PRIMARY_MUTED": "rgba(184, 80, 28, 0.10)",
        "SECONDARY_ACCENT": "#1F8A6A",
        "PRIMARY_TEXT": "#1C1916",
        "SECONDARY_TEXT": "#5A534B",
        "TEXT_MUTED": "#68615A",
        "TEXT_DISABLED": "#ADA597",
        "TEXT_STRONG": "#000000",
        "ON_PRIMARY": "#FFFFFF",
        "OVERLAY_1": "rgba(40, 30, 20, 0.04)",
        "OVERLAY_2": "rgba(40, 30, 20, 0.07)",
        "OVERLAY_BORDER": "rgba(40, 30, 20, 0.18)",
        "BACKDROP": None,
    },
    "jungle": {
        "label": "Jungle",
        "BG_DARK": "#07110D",
        "SURFACE": "#0E1B15",
        "SURFACE_HOVER": "#14251D",
        "SURFACE_ACTIVE": "#1A2F25",
        "SURFACE_OVERLAY": "#0F1E17",
        "BORDER": "#223A2D",
        "BORDER_SUBTLE": "#1A2C23",
        "PRIMARY": "#3DD68C",
        "PRIMARY_HOVER": "#5BE3A0",
        "PRIMARY_PRESSED": "#2BB774",
        "PRIMARY_MUTED": "rgba(61, 214, 140, 0.14)",
        "SECONDARY_ACCENT": "#E2C75C",
        "PRIMARY_TEXT": "#EEF5EF",
        "SECONDARY_TEXT": "#9DB3A6",
        "TEXT_MUTED": "#7E978A",
        "TEXT_DISABLED": "#466052",
        "TEXT_STRONG": "#FFFFFF",
        "ON_PRIMARY": "#06110C",
        "OVERLAY_1": "rgba(220, 255, 235, 0.04)",
        "OVERLAY_2": "rgba(220, 255, 235, 0.08)",
        "OVERLAY_BORDER": "rgba(220, 255, 235, 0.18)",
        "BACKDROP": "leaves",
    },
    "galaxy": {
        "label": "Galaxy",
        "BG_DARK": "#07061A",
        "SURFACE": "#100E28",
        "SURFACE_HOVER": "#171436",
        "SURFACE_ACTIVE": "#1E1A45",
        "SURFACE_OVERLAY": "#131130",
        "BORDER": "#2A2550",
        "BORDER_SUBTLE": "#211D42",
        "PRIMARY": "#A78BFA",
        "PRIMARY_HOVER": "#B9A2FF",
        "PRIMARY_PRESSED": "#8E6FF2",
        "PRIMARY_MUTED": "rgba(167, 139, 250, 0.16)",
        "SECONDARY_ACCENT": "#F472B6",
        "PRIMARY_TEXT": "#F3F1FF",
        "SECONDARY_TEXT": "#A9A3CC",
        "TEXT_MUTED": "#8C86B3",
        "TEXT_DISABLED": "#4E4878",
        "TEXT_STRONG": "#FFFFFF",
        "ON_PRIMARY": "#0B0A1F",
        "OVERLAY_1": "rgba(235, 230, 255, 0.05)",
        "OVERLAY_2": "rgba(235, 230, 255, 0.09)",
        "OVERLAY_BORDER": "rgba(235, 230, 255, 0.18)",
        "BACKDROP": "stars",
    },
}

DEFAULT_THEME = "dark"

# The settings key ("theme" was an older, unused setting with a different
# meaning, so a new key avoids surprising anyone with a sudden light theme).
SETTING_KEY = "ui_theme"


def _selected_theme():
    """Theme name from settings.json, read directly (no Qt, no circular imports)."""

    override = os.environ.get("WIELD_THEME") or os.environ.get("LENSFLOW_THEME")
    if override in THEMES:
        return override

    try:
        from backend.paths import user_config_path
        with open(user_config_path("settings.json"), encoding="utf-8") as f:
            name = json.load(f).get(SETTING_KEY, DEFAULT_THEME)
    except Exception:
        name = DEFAULT_THEME

    return name if name in THEMES else DEFAULT_THEME


THEME_NAME = _selected_theme()
_T = THEMES[THEME_NAME]

# ============================================================================
# COLOR TOKENS (from the selected theme)
# ============================================================================

BG_DARK = _T["BG_DARK"]
SURFACE = _T["SURFACE"]
SURFACE_HOVER = _T["SURFACE_HOVER"]
SURFACE_ACTIVE = _T["SURFACE_ACTIVE"]
SURFACE_OVERLAY = _T["SURFACE_OVERLAY"]

BORDER = _T["BORDER"]
BORDER_SUBTLE = _T["BORDER_SUBTLE"]
BORDER_HOVER = _T["PRIMARY_MUTED"]
BORDER_FOCUS = _T["PRIMARY"]

PRIMARY = _T["PRIMARY"]
PRIMARY_HOVER = _T["PRIMARY_HOVER"]
PRIMARY_PRESSED = _T["PRIMARY_PRESSED"]
PRIMARY_MUTED = _T["PRIMARY_MUTED"]

SECONDARY_ACCENT = _T["SECONDARY_ACCENT"]
SECONDARY_ACCENT_HOVER = _T["SECONDARY_ACCENT"]
SECONDARY_ACCENT_MUTED = _T["PRIMARY_MUTED"]

# Studio icon variations (unused names kept for older imports)
ACCENT_INDIGO = _T["SECONDARY_ACCENT"]
ACCENT_BLUE_INDIGO = _T["SECONDARY_ACCENT"]
ACCENT_VIOLET = _T["PRIMARY"]
ACCENT_PURPLE_INDIGO = _T["PRIMARY"]

# Semantic status colors
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"
INFO = _T["SECONDARY_ACCENT"]

# Typography
PRIMARY_TEXT = _T["PRIMARY_TEXT"]
SECONDARY_TEXT = _T["SECONDARY_TEXT"]
TEXT_MUTED = _T["TEXT_MUTED"]
TEXT_DISABLED = _T["TEXT_DISABLED"]
TEXT_STRONG = _T["TEXT_STRONG"]
ON_PRIMARY = _T["ON_PRIMARY"]

# Neutral overlays for secondary buttons and hovers
OVERLAY_1 = _T["OVERLAY_1"]
OVERLAY_2 = _T["OVERLAY_2"]
OVERLAY_BORDER = _T["OVERLAY_BORDER"]

BACKDROP = _T["BACKDROP"]
IS_LIGHT = THEME_NAME == "light"

# Page backgrounds are transparent when the window paints a backdrop
# (stars, leaves) so it shows through; solid otherwise.
PAGE_BG = "transparent" if BACKDROP else BG_DARK

# ============================================================================
# COMPATIBILITY ALIASES
# ============================================================================

TEXT_PRIMARY = PRIMARY_TEXT
TEXT_SECONDARY = SECONDARY_TEXT
SURFACE_CARD = SURFACE
SURFACE_ELEVATED = SURFACE_HOVER
SURFACE_ROOT = BG_DARK
BORDER_DEFAULT = BORDER
ACCENT_BLUE = PRIMARY
ACCENT_PURPLE = PRIMARY
STATUS_GREEN = SUCCESS
STATUS_AMBER = WARNING
STATUS_RED = ERROR

# ============================================================================
# COMMON QSS MIXINS
# ============================================================================

CARD_FRAME_STYLE = f"""
    QFrame#StudioCard {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 16px;
    }}
    QFrame#StudioCard:hover {{
        background-color: {SURFACE_HOVER};
        border: 1px solid {BORDER_HOVER};
    }}
"""

BUTTON_PRIMARY_STYLE = f"""
    QPushButton {{
        background-color: {PRIMARY};
        color: {ON_PRIMARY};
        border: none;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background-color: {PRIMARY_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {PRIMARY_PRESSED};
    }}
"""

BUTTON_SECONDARY_STYLE = f"""
    QPushButton {{
        background-color: {OVERLAY_1};
        color: {PRIMARY_TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {OVERLAY_2};
        border: 1px solid {OVERLAY_BORDER};
        color: {TEXT_STRONG};
    }}
    QPushButton:pressed {{
        background-color: {OVERLAY_1};
    }}
"""

BUTTON_DESTRUCTIVE_STYLE = f"""
    QPushButton {{
        background-color: rgba(239, 68, 68, 0.10);
        color: {ERROR};
        border: 1px solid rgba(239, 68, 68, 0.25);
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: rgba(239, 68, 68, 0.20);
        border: 1px solid rgba(239, 68, 68, 0.40);
    }}
    QPushButton:pressed {{
        background-color: rgba(239, 68, 68, 0.28);
    }}
"""

MENU_STYLE = f"""
    QMenu {{
        background-color: {SURFACE};
        color: {PRIMARY_TEXT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 14px;
        border-radius: 6px;
        font-size: 12px;
    }}
    QMenu::item:selected {{
        background-color: {PRIMARY_MUTED};
        color: {PRIMARY_TEXT};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {BORDER};
        margin: 4px 6px;
    }}
"""


def global_stylesheet():
    """The app-wide stylesheet (replaces the fixed colours in theme.qss)."""

    from backend.paths import APP_DIR  # also correct inside the packaged .exe

    path = os.path.join(APP_DIR, "frontend", "styles", "theme.qss")

    try:
        with open(path, encoding="utf-8") as f:
            qss = f.read()
    except OSError:
        qss = ""

    # theme.qss is written in the dark palette; map its colours to this theme.
    replacements = {
        "#08090D": BG_DARK,
        "#101118": SURFACE,
        "#171923": SURFACE_HOVER,
        "#252936": BORDER,
        "#F5F5F7": PRIMARY_TEXT,
        "#7C5CFF": PRIMARY,
        "#FFFFFF": ON_PRIMARY,  # only used for text on PRIMARY
        "rgba(255, 255, 255, 0.10)": OVERLAY_2,
        "rgba(255, 255, 255, 0.20)": OVERLAY_BORDER,
    }

    for old, new in replacements.items():
        qss = qss.replace(old, new)

    return qss
