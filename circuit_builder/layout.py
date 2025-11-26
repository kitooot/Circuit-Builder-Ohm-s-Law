from __future__ import annotations

import math
from typing import Dict, Iterable, List

from .constants import GRID_SIZE


def auto_layout_components(components: Iterable, adjacency: Dict) -> Dict[int, tuple[int, int]]:
    """Generate grid-aligned positions using a simple layered layout."""
    positions: Dict[int, tuple[int, int]] = {}
    layers: List[List] = []
    visited = set()

    for component in components:
        if component in visited:
            continue
        layer = [component]
        queue = [component]
        visited.add(component)
        while queue:
            current = queue.pop(0)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    layer.append(neighbor)
        layers.append(layer)

    x_spacing = GRID_SIZE * 12
    y_spacing = GRID_SIZE * 10
    base_x = GRID_SIZE * 4
    base_y = GRID_SIZE * 6

    for layer_index, layer in enumerate(layers):
        layer.sort(key=lambda comp: comp.id)
        radius = max(1, len(layer))
        for index, component in enumerate(layer):
            angle = (index / max(1, len(layer))) * 2 * math.pi
            offset_x = int(math.cos(angle) * GRID_SIZE * 4)
            offset_y = int(math.sin(angle) * GRID_SIZE * 2)
            x = base_x + layer_index * x_spacing + offset_x
            y = base_y + index * y_spacing + offset_y
            positions[component.id] = (x // GRID_SIZE * GRID_SIZE, y // GRID_SIZE * GRID_SIZE)

    return positions


__all__ = ["auto_layout_components"]
