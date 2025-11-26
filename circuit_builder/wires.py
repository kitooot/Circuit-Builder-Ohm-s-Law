from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Dict, Optional, Set, Tuple

from .components import CircuitComponent


class CircuitWire:
    def __init__(
        self,
        canvas: tk.Canvas,
        x: int,
        y: int,
        on_change: Callable[["CircuitWire"], None],
        on_request_remove: Callable[["CircuitWire"], None],
        connector_finder: Callable[[float, float, Optional["CircuitWire"], Optional[str]], Tuple[Any | None, Optional[str], Tuple[float, float]]],
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
            smooth=True,
        )
        self.canvas.tag_lower(self.line_id, "component")
        self.endpoints = {
            "a": self.canvas.create_oval(x - 7, y - 7, x + 7, y + 7, fill="#475569", outline="#3b82f6", width=3),
            "b": self.canvas.create_oval(x + 80 - 7, y - 7, x + 80 + 7, y + 7, fill="#475569", outline="#3b82f6", width=3),
        }
        self.positions: Dict[str, tuple[float, float]] = {
            "a": (x, y),
            "b": (x + 80, y),
        }
        self.attachments: Dict[str, tuple[CircuitComponent, str] | None] = {"a": None, "b": None}
        self.active = False
        self.linked_endpoints: Dict[str, Set[Tuple["CircuitWire", str]]] = {"a": set(), "b": set()}

        self._dragging_endpoint: str | None = None

        for endpoint, handle_id in self.endpoints.items():
            self.canvas.tag_bind(handle_id, "<Button-1>", lambda e, ep=endpoint: self._start_drag(ep, e))
            self.canvas.tag_bind(handle_id, "<B1-Motion>", self._drag)
            self.canvas.tag_bind(handle_id, "<ButtonRelease-1>", self._stop_drag)
            self.canvas.tag_bind(handle_id, "<Double-Button-1>", self._cut)

        self.canvas.tag_bind(self.line_id, "<Double-Button-1>", self._cut)

        self._set_endpoint("a", x, y)
        self._set_endpoint("b", x + 80, y)

    def _set_endpoint(self, endpoint: str, x: float, y: float) -> None:
        self.positions[endpoint] = (x, y)
        handle_id = self.endpoints[endpoint]
        self.canvas.coords(handle_id, x - 7, y - 7, x + 7, y + 7)
        self.canvas.tag_raise(handle_id)
        ax, ay = self.positions["a"]
        bx, by = self.positions["b"]
        self.canvas.coords(self.line_id, ax, ay, bx, by)

    def _start_drag(self, endpoint: str, event: tk.Event) -> None:
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

        if isinstance(target, CircuitComponent) and identifier:
            self.attach_to_component(endpoint, target, identifier, snap_point)
        elif isinstance(target, CircuitWire) and identifier:
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
        if current and current[0] is component and current[1] == side:
            pass
        else:
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

    def attach_to_component(
        self,
        endpoint: str,
        component: CircuitComponent,
        side: str,
        point: tuple[float, float] | None = None,
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
        other_endpoint: str,
        point: tuple[float, float] | None = None,
    ) -> None:
        if other_wire is self:
            return
        self._detach_endpoint(endpoint)
        snap_point = point if point else other_wire.positions.get(other_endpoint, (0.0, 0.0))
        self._set_endpoint(endpoint, *snap_point)
        self._link_endpoint(endpoint, other_wire, other_endpoint)

        other_attachment = other_wire.attachments.get(other_endpoint)
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

    def update_attachment_position(self, component: CircuitComponent, side: str, point: tuple[float, float]) -> None:
        for endpoint, attachment in self.attachments.items():
            if attachment and attachment[0] is component and attachment[1] == side:
                self._set_endpoint(endpoint, *point)
                self._propagate_position(endpoint, point, {(self, endpoint)})

    def attached_components(self) -> list[CircuitComponent]:
        comps: list[CircuitComponent] = []
        for attachment in self.attachments.values():
            if attachment:
                comps.append(attachment[0])
        return comps

    def set_active(self, active: bool) -> None:
        self.active = active
        color = "#10b981" if active else "#94a3b8"
        width = 5 if active else 4
        self.canvas.itemconfigure(self.line_id, fill=color, width=width)
        for handle in self.endpoints.values():
            fill_color = "#10b981" if active else "#475569"
            outline_color = "#059669" if active else "#3b82f6"
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
        if self.on_request_remove:
            self.on_request_remove(self)


__all__ = ["CircuitWire"]
