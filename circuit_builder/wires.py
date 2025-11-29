from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .components import CircuitComponent

ConnectorFinder = Callable[[float, float, Optional["CircuitWire"], Optional[str]], Tuple[Any | None, Any, Tuple[float, float]]]


class CircuitWire:
    def __init__(
        self,
        canvas: tk.Canvas,
        x: int,
        y: int,
        on_change: Callable[["CircuitWire"], None],
        on_request_remove: Callable[["CircuitWire"], None],
        connector_finder: ConnectorFinder,
    ) -> None:
        self.canvas = canvas
        self.on_change = on_change
        self.on_request_remove = on_request_remove
        self.connector_finder = connector_finder

        self.line_id = self.canvas.create_line(
            x,
            y,
            x + 80,
            y,
            width=4,
            fill="#94a3b8",
            capstyle=tk.ROUND,
            smooth=False,
        )
        self.canvas.tag_lower(self.line_id, "component")

        self.endpoints = {
            "a": self.canvas.create_oval(x - 7, y - 7, x + 7, y + 7, fill="#475569", outline="#3b82f6", width=3),
            "b": self.canvas.create_oval(x + 80 - 7, y - 7, x + 80 + 7, y + 7, fill="#475569", outline="#3b82f6", width=3),
        }
        self.positions: Dict[str, Tuple[float, float]] = {
            "a": (x, y),
            "b": (x + 80, y),
        }
        self.attachments: Dict[str, Tuple[CircuitComponent, str] | None] = {"a": None, "b": None}
        self.linked_endpoints: Dict[str, Set[Tuple["CircuitWire", str]]] = {"a": set(), "b": set()}
        self.active = False
        self.joint_points: List[Tuple[float, float]] = []
        self.joint_handles: List[Optional[int]] = []
        self._dragging_joint_index: Optional[int] = None

        self._dragging_endpoint: Optional[str] = None
        self._dragging_line = False
        self._line_drag_last: Optional[Tuple[float, float]] = None

        for endpoint, handle_id in self.endpoints.items():
            self.canvas.tag_bind(handle_id, "<Button-1>", lambda event, ep=endpoint: self._start_drag(ep, event))
            self.canvas.tag_bind(handle_id, "<B1-Motion>", self._drag)
            self.canvas.tag_bind(handle_id, "<ButtonRelease-1>", self._stop_drag)
            self.canvas.tag_bind(handle_id, "<Double-Button-1>", self._cut)

        self.canvas.tag_bind(self.line_id, "<Button-1>", self._start_line_drag)
        self.canvas.tag_bind(self.line_id, "<B1-Motion>", self._drag_line)
        self.canvas.tag_bind(self.line_id, "<ButtonRelease-1>", self._stop_line_drag)
        self.canvas.tag_bind(self.line_id, "<Double-Button-1>", self._cut)

        self._set_endpoint("a", x, y)
        self._set_endpoint("b", x + 80, y)
        self._create_joint(((x + (x + 80)) / 2.0, y))

    def _set_endpoint(self, endpoint: str, x: float, y: float) -> None:
        self.positions[endpoint] = (x, y)
        handle_id = self.endpoints[endpoint]
        self.canvas.coords(handle_id, x - 7, y - 7, x + 7, y + 7)
        self.canvas.tag_raise(handle_id)
        self._update_line_path()

    def _path_points(self) -> List[Tuple[float, float]]:
        return [self.positions["a"], *self.joint_points, self.positions["b"]]

    def _update_line_path(self) -> None:
        points = self._path_points()
        flat: List[float] = []
        for px, py in points:
            flat.extend([px, py])
        self.canvas.coords(self.line_id, *flat)
        for handle, (jx, jy) in zip(self.joint_handles, self.joint_points):
            if handle is None:
                continue
            self.canvas.coords(handle, jx - 6, jy - 6, jx + 6, jy + 6)
            self.canvas.tag_raise(handle)
        self.canvas.tag_lower(self.line_id, "component")

    def _create_joint(self, point: Tuple[float, float], draggable: bool = True) -> None:
        jx, jy = point
        self.joint_points.append((jx, jy))
        if draggable:
            handle = self.canvas.create_oval(jx - 6, jy - 6, jx + 6, jy + 6, fill="#475569", outline="#0ea5e9", width=2)
            self._bind_joint_handle(handle)
            self.joint_handles.append(handle)
        else:
            self.joint_handles.append(None)
        self._update_line_path()

    def _bind_joint_handle(self, handle_id: int) -> None:
        self.canvas.tag_bind(handle_id, "<Button-1>", lambda event, hid=handle_id: self._start_joint_drag(hid, event))
        self.canvas.tag_bind(handle_id, "<B1-Motion>", self._drag_joint)
        self.canvas.tag_bind(handle_id, "<ButtonRelease-1>", self._stop_joint_drag)
        self.canvas.tag_bind(handle_id, "<Double-Button-1>", lambda _event, hid=handle_id: self._remove_joint(hid))

    def _start_joint_drag(self, handle_id: int, event: tk.Event) -> None:
        try:
            index = self.joint_handles.index(handle_id)
        except ValueError:
            return
        self._dragging_joint_index = index
        self.canvas.tag_raise(handle_id)

    def _drag_joint(self, event: tk.Event) -> None:
        if self._dragging_joint_index is None:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self.joint_points[self._dragging_joint_index] = (canvas_x, canvas_y)
        self._update_line_path()

    def _stop_joint_drag(self, event: tk.Event) -> None:
        if self._dragging_joint_index is None:
            return
        self._drag_joint(event)
        self._dragging_joint_index = None
        if self.on_change:
            self.on_change(self)

    def _remove_joint(self, handle_id: int) -> None:
        try:
            index = self.joint_handles.index(handle_id)
        except ValueError:
            return
        handle = self.joint_handles.pop(index)
        if handle is not None:
            self.canvas.delete(handle)
        self.joint_points.pop(index)
        self._dragging_joint_index = None
        self._update_line_path()
        if self.on_change:
            self.on_change(self)

    def _start_drag(self, endpoint: str, _event: tk.Event) -> None:
        self._dragging_endpoint = endpoint
        self._detach_endpoint(endpoint)

    def _drag(self, event: tk.Event) -> None:
        if self._dragging_endpoint is None:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self._set_endpoint(self._dragging_endpoint, canvas_x, canvas_y)

    def _stop_drag(self, event: tk.Event) -> None:
        if self._dragging_endpoint is None:
            return
        endpoint = self._dragging_endpoint
        self._dragging_endpoint = None

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        target, identifier, snap_point = self.connector_finder(canvas_x, canvas_y, self, endpoint)

        if isinstance(target, CircuitComponent) and isinstance(identifier, str):
            self.attach_to_component(endpoint, target, identifier, snap_point)
        elif isinstance(target, CircuitWire):
            self.attach_to_wire(endpoint, target, identifier, snap_point)
        else:
            self._set_endpoint(endpoint, canvas_x, canvas_y)
            if self.on_change:
                self.on_change(self)

    def _detach_endpoint(self, endpoint: str) -> None:
        attachment = self.attachments.get(endpoint)
        if attachment:
            component, side = attachment
            component.detach_wire(self, side)
            self.attachments[endpoint] = None
        if self.linked_endpoints.get(endpoint):
            self._unlink_endpoint(endpoint)

    def _link_endpoint(self, endpoint: str, other_wire: "CircuitWire", other_endpoint: str) -> None:
        if other_wire is self and other_endpoint == endpoint:
            return
        self.linked_endpoints.setdefault(endpoint, set()).add((other_wire, other_endpoint))
        other_wire.linked_endpoints.setdefault(other_endpoint, set()).add((self, endpoint))

    def _unlink_endpoint(self, endpoint: str) -> None:
        for other_wire, other_endpoint in list(self.linked_endpoints.get(endpoint, set())):
            other_wire.linked_endpoints.setdefault(other_endpoint, set()).discard((self, endpoint))
        self.linked_endpoints.setdefault(endpoint, set()).clear()

    def has_free_endpoint(self) -> bool:
        for endpoint in ("a", "b"):
            if not self.attachments.get(endpoint) and not self.linked_endpoints.get(endpoint):
                return True
        return False

    def nearest_free_endpoint(self, point: Tuple[float, float]) -> Optional[str]:
        px, py = point
        selected: Optional[str] = None
        best_distance = float("inf")
        for endpoint in ("a", "b"):
            if self.attachments.get(endpoint) or self.linked_endpoints.get(endpoint):
                continue
            ex, ey = self.positions.get(endpoint, (0.0, 0.0))
            dist = math.hypot(ex - px, ey - py)
            if dist < best_distance:
                best_distance = dist
                selected = endpoint
        return selected

    def nearest_endpoint(self, point: Tuple[float, float]) -> Optional[str]:
        px, py = point
        selected: Optional[str] = None
        best_distance = float("inf")
        for endpoint in ("a", "b"):
            ex, ey = self.positions.get(endpoint, (0.0, 0.0))
            dist = math.hypot(ex - px, ey - py)
            if dist < best_distance:
                best_distance = dist
                selected = endpoint
        return selected

    def path_points(self) -> List[Tuple[float, float]]:
        return self._path_points()

    def _propagate_attachment(
        self,
        endpoint: str,
        component: CircuitComponent,
        side: str,
        visited: Optional[Set[Tuple["CircuitWire", str]]] = None,
    ) -> None:
        if visited is None:
            visited = set()
        visited.add((self, endpoint))
        for other_wire, other_endpoint in list(self.linked_endpoints.get(endpoint, set())):
            if (other_wire, other_endpoint) in visited:
                continue
            other_wire._adopt_attachment(other_endpoint, component, side, visited)

    def _adopt_attachment(
        self,
        endpoint: str,
        component: CircuitComponent,
        side: str,
        visited: Set[Tuple["CircuitWire", str]],
    ) -> None:
        current = self.attachments.get(endpoint)
        if not current or current[0] is not component or current[1] != side:
            if current:
                old_component, old_side = current
                old_component.detach_wire(self, old_side)
            component.attach_wire(self, side)
            self.attachments[endpoint] = (component, side)
        anchor = component.anchor_point(side)
        self._set_endpoint(endpoint, *anchor)
        self._propagate_position(endpoint, anchor, visited)
        self._propagate_attachment(endpoint, component, side, visited)

    def _propagate_position(
        self,
        endpoint: str,
        point: Tuple[float, float],
        visited: Optional[Set[Tuple["CircuitWire", str]]] = None,
    ) -> None:
        if visited is None:
            visited = set()
        visited.add((self, endpoint))
        for other_wire, other_endpoint in list(self.linked_endpoints.get(endpoint, set())):
            if (other_wire, other_endpoint) in visited:
                continue
            other_wire._set_endpoint(other_endpoint, *point)
            other_wire._propagate_position(other_endpoint, point, visited)
        self._update_line_path()

    def attach_to_component(
        self,
        endpoint: str,
        component: CircuitComponent,
        side: str,
        point: Tuple[float, float] | None = None,
    ) -> None:
        self._detach_endpoint(endpoint)
        anchor = point if point else component.anchor_point(side)
        self._set_endpoint(endpoint, *anchor)
        component.attach_wire(self, side)
        self.attachments[endpoint] = (component, side)
        self._propagate_position(endpoint, anchor, {(self, endpoint)})
        self._propagate_attachment(endpoint, component, side, {(self, endpoint)})
        if self.on_change:
            self.on_change(self)

    def attach_to_wire(
        self,
        endpoint: str,
        other_wire: "CircuitWire",
        other_endpoint: Union[str, Tuple[str, float, float]],
        point: Tuple[float, float] | None = None,
    ) -> None:
        if other_wire is self:
            return

        snap_point = point
        target_endpoint: Optional[str]

        if isinstance(other_endpoint, tuple):
            tag = other_endpoint[0]
            if tag == "segment":
                candidate_point = (other_endpoint[1], other_endpoint[2])
                target_endpoint = other_wire.nearest_free_endpoint(candidate_point)
                if target_endpoint is None:
                    target_endpoint = other_wire.nearest_endpoint(candidate_point)
                if target_endpoint is None:
                    return
                snap_point = candidate_point
            else:
                return
        else:
            target_endpoint = other_endpoint

        if not isinstance(target_endpoint, str):
            return

        self._detach_endpoint(endpoint)
        if snap_point is None:
            snap_point = other_wire.positions.get(target_endpoint, (0.0, 0.0))
        self._set_endpoint(endpoint, *snap_point)
        self._link_endpoint(endpoint, other_wire, target_endpoint)

        other_attachment = other_wire.attachments.get(target_endpoint)
        if other_attachment:
            component, side = other_attachment
            component.attach_wire(self, side)
            self.attachments[endpoint] = (component, side)
            self._propagate_position(endpoint, snap_point, {(self, endpoint)})
            self._propagate_attachment(endpoint, component, side, {(self, endpoint)})
        else:
            self.attachments[endpoint] = None
            self._propagate_position(endpoint, snap_point, {(self, endpoint)})

        if self.on_change:
            self.on_change(self)

    def detach_component(self, component: CircuitComponent) -> None:
        updated = False
        for endpoint, attachment in list(self.attachments.items()):
            if attachment and attachment[0] is component:
                component.detach_wire(self, attachment[1])
                self.attachments[endpoint] = None
                updated = True
        if updated and self.on_change:
            self.on_change(self)

    def update_attachment_position(self, component: CircuitComponent, side: str, point: Tuple[float, float]) -> None:
        for endpoint, attachment in self.attachments.items():
            if attachment and attachment[0] is component and attachment[1] == side:
                self._set_endpoint(endpoint, *point)
                self._propagate_position(endpoint, point, {(self, endpoint)})

    def attached_components(self) -> list[CircuitComponent]:
        components: list[CircuitComponent] = []
        for attachment in self.attachments.values():
            if attachment:
                components.append(attachment[0])
        return components

    def set_active(self, active: bool) -> None:
        self.active = active
        color = "#10b981" if active else "#94a3b8"
        width = 5 if active else 4
        self.canvas.itemconfigure(self.line_id, fill=color, width=width)
        for handle in self.endpoints.values():
            fill_color = "#10b981" if active else "#475569"
            outline_color = "#059669" if active else "#3b82f6"
            self.canvas.itemconfigure(handle, fill=fill_color, outline=outline_color)
        for handle in self.joint_handles:
            if handle is None:
                continue
            fill_color = "#10b981" if active else "#475569"
            outline_color = "#064e3b" if active else "#0ea5e9"
            self.canvas.itemconfigure(handle, fill=fill_color, outline=outline_color)

    def _cut(self, _event: tk.Event | None = None) -> None:
        self.remove()

    def remove(self) -> None:
        for endpoint, attachment in list(self.attachments.items()):
            if attachment:
                component, side = attachment
                component.detach_wire(self, side)
                self.attachments[endpoint] = None
        for endpoint in ("a", "b"):
            if self.linked_endpoints.get(endpoint):
                self._unlink_endpoint(endpoint)
        self.canvas.delete(self.line_id)
        for handle in self.endpoints.values():
            self.canvas.delete(handle)
        for handle in self.joint_handles:
            if handle is not None:
                self.canvas.delete(handle)
        if self.on_request_remove:
            self.on_request_remove(self)

    def _start_line_drag(self, event: tk.Event) -> None:
        if any(self.attachments.get(ep) for ep in ("a", "b")):
            return
        if any(self.linked_endpoints.get(ep) for ep in ("a", "b")):
            return
        self._dragging_line = True
        self._line_drag_last = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _drag_line(self, event: tk.Event) -> None:
        if not self._dragging_line or self._line_drag_last is None:
            return
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        dx = current_x - self._line_drag_last[0]
        dy = current_y - self._line_drag_last[1]
        if dx == 0 and dy == 0:
            return
        for endpoint in ("a", "b"):
            ex, ey = self.positions.get(endpoint, (0.0, 0.0))
            self._set_endpoint(endpoint, ex + dx, ey + dy)
        for index, (jx, jy) in enumerate(self.joint_points):
            self.joint_points[index] = (jx + dx, jy + dy)
        self._update_line_path()
        self._line_drag_last = (current_x, current_y)

    def _stop_line_drag(self, _event: tk.Event) -> None:
        if not self._dragging_line:
            return
        self._dragging_line = False
        self._line_drag_last = None
        if self.on_change:
            self.on_change(self)


__all__ = ["CircuitWire"]
