from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ProjectFile:
    components: List[Dict[str, Any]]
    wires: List[Dict[str, Any]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "components": self.components,
            "wires": self.wires,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ProjectFile":
        components = payload.get("components", [])
        wires = payload.get("wires", [])
        metadata = payload.get("metadata", {})
        return cls(components=components, wires=wires, metadata=metadata)


class StorageError(Exception):
    """Raised when project persistence fails."""


def save_project(path: str, data: ProjectFile) -> None:
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data.to_dict(), handle, indent=2)
    except OSError as exc:
        logger.error("Failed to save project to %s: %s", path, exc)
        raise StorageError(f"Unable to save project to {path!s}") from exc


def load_project(path: str) -> ProjectFile:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load project from %s: %s", path, exc)
        raise StorageError(f"Unable to load project from {path!s}") from exc
    return ProjectFile.from_dict(payload)


def serialize_components(components: List[Any]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for component in components:
        serialized.append({
            "type": component.type,
            "x": component.x,
            "y": component.y,
            "id": component.id,
            "display_label": component.display_label,
            "code_label": component.code_label,
            "voltage": getattr(component, "voltage_value", 0.0),
            "resistance": getattr(component, "resistance_value", 0.0),
            "capacitance": getattr(component, "capacitance", 0.0),
            "locked": getattr(component, "locked", False),
            "orientation": getattr(component, "orientation", "horizontal"),
        })
    return serialized


def serialize_wires(wires: List[Any]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for wire in wires:
        serialized.append({
            "positions": wire.positions.copy(),
            "attachments": {
                endpoint: (
                    attachment[0].id,
                    attachment[1],
                ) if attachment else None
                for endpoint, attachment in wire.attachments.items()
            },
        })
    return serialized


def deserialize_project(
    payload: ProjectFile,
    component_factory,
    wire_factory,
) -> Tuple[List[Any], List[Any]]:
    components_lookup: Dict[int, Any] = {}
    components: List[Any] = []
    for data in payload.components:
        component = component_factory(data)
        components.append(component)
        components_lookup[data["id"]] = component

    wires: List[Any] = []
    for data in payload.wires:
        wire = wire_factory(data, components_lookup)
        wires.append(wire)

    return components, wires


__all__ = [
    "ProjectFile",
    "save_project",
    "load_project",
    "serialize_components",
    "serialize_wires",
    "deserialize_project",
    "StorageError",
]
