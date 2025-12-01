from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict
import logging
logger = logging.getLogger(__name__)

CONFIG_FILENAME = "circuit_builder_config.json"


@dataclass
class UserSettings:
    grid_visible: bool = True
    default_battery_voltage: float = 9.0
    default_resistor_value: float = 100.0
    autosave_enabled: bool = True
    autosave_interval: int = 180  # seconds
    tutorial_completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        # Serialize the settings dataclass into a dictionary.
        return {
            "grid_visible": self.grid_visible,
            "default_battery_voltage": self.default_battery_voltage,
            "default_resistor_value": self.default_resistor_value,
            "autosave_enabled": self.autosave_enabled,
            "autosave_interval": self.autosave_interval,
            "tutorial_completed": self.tutorial_completed,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "UserSettings":
        # Create a settings object populated from a dictionary payload.
        data = cls()
        for key, value in payload.items():
            if hasattr(data, key):
                setattr(data, key, value)
        return data


class SettingsManager:
    def __init__(self, config_dir: str | None = None) -> None:
        # Initialize the settings manager and eagerly load stored values.
        self.config_dir = config_dir or self._default_config_dir()
        self.config_path = os.path.join(self.config_dir, CONFIG_FILENAME)
        self.settings = UserSettings()
        self.load()

    @staticmethod
    def _default_config_dir() -> str:
        # Provide the default directory for persisting configuration.
        base = os.path.expanduser("~")
        config_dir = os.path.join(base, ".circuit_builder")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def load(self) -> None:
        # Load settings from disk if a config file exists.
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load settings from %s: %s", self.config_path, exc)
            return
        self.settings = UserSettings.from_dict(payload)

    def save(self) -> None:
        # Persist the current settings to disk as JSON.
        os.makedirs(self.config_dir, exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump(self.settings.to_dict(), handle, indent=2)
        except OSError as exc:
            logger.warning("Failed to save settings to %s: %s", self.config_path, exc)

    def get(self, key: str, default: Any = None) -> Any:
        # Retrieve a settings value with optional default.
        return getattr(self.settings, key, default)

    def set(self, key: str, value: Any) -> None:
        # Update a settings value and persist the change if applicable.
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
            self.save()


__all__ = ["SettingsManager", "UserSettings", "CONFIG_FILENAME"]
