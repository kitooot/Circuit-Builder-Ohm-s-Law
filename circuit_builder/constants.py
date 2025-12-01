from __future__ import annotations

from typing import Any, Dict

GRID_SIZE = 20
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 640

COMPONENT_ICONS: Dict[str, str] = {
    "battery": "⚡",
    "resistor": "⎍",
    "bulb": "💡",
    "wire": "─",
    "switch": "⏚",
    "switch_spst": "⏚",
    "switch_spdt": "⏚",
}

COMPONENT_PROPS: Dict[str, Dict[str, Any]] = {
    "battery": {
        "label": "Battery",
        "resistance": 0,
        "voltage": 9.0,
        "color": "#fef3c7",
        "bg_gradient": "#fcd34d",
        "badge_bg": "#f97316",
        "badge_fg": "#1f2937",
        "active_body": "#fde68a",
    },
    "resistor": {
        "label": "Resistor",
        "resistance": 100,
        "color": "#fee2e2",
        "bg_gradient": "#fb7185",
        "badge_bg": "#be123c",
        "badge_fg": "#f8fafc",
        "active_body": "#fecdd3",
    },
    "bulb": {
        "label": "Light Bulb",
        "resistance": 150,
        "color": "#fef9c3",
        "bg_gradient": "#facc15",
        "badge_bg": "#ca8a04",
        "badge_fg": "#1f2937",
        "active_body": "#fef08a",
        "glow_inactive": "#d1d5db",
        "glow_active": "#fcd34d",
    },
    "wire": {
        "label": "Wire",
        "resistance": 0,
        "color": "#e0e7ff",
        "bg_gradient": "#818cf8",
        "badge_bg": "#312e81",
        "badge_fg": "#e0e7ff",
        "active_body": "#c7d2fe",
    },
    "switch": {
        "label": "Switch",
        "resistance": 0,
        "color": "#e9d5ff",
        "bg_gradient": "#c084fc",
        "badge_bg": "#6b21a8",
        "badge_fg": "#f3e8ff",
        "active_body": "#e0c3ff",
    },
    "switch_spst": {
        "label": "Switch (SPST)",
        "resistance": 0,
        "color": "#e9d5ff",
        "bg_gradient": "#c084fc",
        "badge_bg": "#5b21b6",
        "badge_fg": "#f3e8ff",
        "active_body": "#d8b4fe",
    },
    "switch_spdt": {
        "label": "Switch (SPDT)",
        "resistance": 0,
        "color": "#ede9fe",
        "bg_gradient": "#a855f7",
        "badge_bg": "#7c3aed",
        "badge_fg": "#ede9fe",
        "active_body": "#ddd6fe",
    },
}

COMPONENT_PREFIX: Dict[str, str] = {
    "battery": "B",
    "resistor": "R",
    "bulb": "L",
    "wire": "W",
    "switch": "S",
    "switch_spst": "S",
    "switch_spdt": "S",
}

BATTERY_VOLTAGE = 9.0

__all__ = [
    "GRID_SIZE",
    "CANVAS_WIDTH",
    "CANVAS_HEIGHT",
    "COMPONENT_ICONS",
    "COMPONENT_PROPS",
    "COMPONENT_PREFIX",
    "BATTERY_VOLTAGE",
]
