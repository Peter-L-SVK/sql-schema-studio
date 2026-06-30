# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Terminal Color Themes (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Terminal color theme definitions for VTE."""

# fmt: off
TERMINAL_THEMES = {
    "dark": {
        "name": "Dark",
        "fg": "#D3D7CF",
        "bg": "#1E1E1E",
        "palette": [
            "#000000", "#CC0000", "#4E9A06", "#C4A000",
            "#3465A4", "#75507B", "#06989A", "#D3D7CF",
            "#555753", "#EF2929", "#8AE234", "#FCE94F",
            "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC",
        ],
    },
    "light": {
        "name": "Light",
        "fg": "#000000",
        "bg": "#FFFFFF",
        "palette": [
            "#000000", "#CC0000", "#4E9A06", "#C4A000",
            "#3465A4", "#75507B", "#06989A", "#D3D7CF",
            "#555753", "#EF2929", "#8AE234", "#FCE94F",
            "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC",
        ],
    },
    "tango-dark": {
        "name": "Tango Dark",
        "fg": "#EEEEEC",
        "bg": "#2E3436",
        "palette": [
            "#2E3436", "#CC0000", "#4E9A06", "#C4A000",
            "#3465A4", "#75507B", "#06989A", "#D3D7CF",
            "#555753", "#EF2929", "#8AE234", "#FCE94F",
            "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC",
        ],
    },
    "tango-light": {
        "name": "Tango Light",
        "fg": "#2E3436",
        "bg": "#EEEEEC",
        "palette": [
            "#2E3436", "#CC0000", "#4E9A06", "#C4A000",
            "#3465A4", "#75507B", "#06989A", "#D3D7CF",
            "#555753", "#EF2929", "#8AE234", "#FCE94F",
            "#729FCF", "#AD7FA8", "#34E2E2", "#EEEEEC",
        ],
    },
    "solarized-dark": {
        "name": "Solarized Dark",
        "fg": "#839496",
        "bg": "#002B36",
        "palette": [
            "#073642", "#DC322F", "#859900", "#B58900",
            "#268BD2", "#D33682", "#2AA198", "#EEE8D5",
            "#002B36", "#CB4B16", "#586E75", "#657B83",
            "#839496", "#6C71C4", "#93A1A1", "#FDF6E3",
        ],
    },
    "solarized-light": {
        "name": "Solarized Light",
        "fg": "#657B83",
        "bg": "#FDF6E3",
        "palette": [
            "#073642", "#DC322F", "#859900", "#B58900",
            "#268BD2", "#D33682", "#2AA198", "#EEE8D5",
            "#002B36", "#CB4B16", "#586E75", "#657B83",
            "#839496", "#6C71C4", "#93A1A1", "#FDF6E3",
        ],
    },
    "monokai": {
        "name": "Monokai",
        "fg": "#F8F8F2",
        "bg": "#272822",
        "palette": [
            "#272822", "#F92672", "#A6E22E", "#FD971F",
            "#66D9EF", "#AE81FF", "#A1EFE4", "#F8F8F2",
            "#75715E", "#F92672", "#A6E22E", "#FD971F",
            "#66D9EF", "#AE81FF", "#A1EFE4", "#F9F8F5",
        ],
    },
    "nord": {
        "name": "Nord",
        "fg": "#D8DEE9",
        "bg": "#2E3440",
        "palette": [
            "#2E3440", "#BF616A", "#A3BE8C", "#EBCB8B",
            "#81A1C1", "#B48EAD", "#88C0D0", "#E5E9F0",
            "#4C566A", "#BF616A", "#A3BE8C", "#EBCB8B",
            "#81A1C1", "#B48EAD", "#8FBCBB", "#ECEFF4",
        ],
    },
}
# fmt: on


def get_terminal_theme_names():
    """Return list of (theme_id, display_name) tuples for all themes."""
    return [(theme_id, theme["name"]) for theme_id, theme in TERMINAL_THEMES.items()]
