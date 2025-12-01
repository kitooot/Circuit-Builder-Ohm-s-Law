from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    surface: str
    raised_surface: str
    accent: str
    accent_light: str
    accent_text: str
    text_primary: str
    text_secondary: str
    border: str
    shadow: str
    canvas_bg: str
    grid_color: str
    warning: str
    alert: str


THEMES: Dict[str, Theme] = {
    "light": Theme(
        name="Light",
        background="#f5f5f5",
        surface="#ffffff",
        raised_surface="#f8fafc",
        accent="#2563eb",
        accent_light="#dbeafe",
        accent_text="#ffffff",
        text_primary="#1f2937",
        text_secondary="#4b5563",
        border="#e2e8f0",
        shadow="#cbd5f5",
        canvas_bg="#ffffff",
        grid_color="#e2e8f0",
        warning="#f97316",
        alert="#dc2626",
    ),
}


def get_theme(_theme_id: str | None = None) -> Theme:
    # Retrieve a theme by identifier, defaulting to the bundled light theme.
    return THEMES["light"]


DEFAULT_THEME = THEMES["light"]

__all__ = ["Theme", "THEMES", "get_theme", "DEFAULT_THEME"]
