from __future__ import annotations

import math
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .components import CircuitComponent


@runtime_checkable
class ComponentLike(Protocol):
    type: str

    def anchor_point(self, side: str) -> Tuple[float, float]:
        ...

    def attach_wire(self, wire: "CircuitWire", side: str) -> None:
        ...

    def detach_wire(self, wire: "CircuitWire", side: str | None = None) -> None:
        ...

ConnectorFinder = Callable[[float, float, Optional["CircuitWire"], Optional[str]], Tuple[Any | None, Any, Tuple[float, float]]]

PointId = str
LinkRef = Tuple["CircuitWire", PointId]
VisitedSet = Set[LinkRef]
ENDPOINT_IDS: Tuple[PointId, PointId] = ("a", "b")
ENDPOINT_RADIUS = 7
JOINT_RADIUS = 6


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
        # Initialize the wire geometry, state, and interactive bindings.
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
            "a": self.canvas.create_oval(
                x - ENDPOINT_RADIUS,
                y - ENDPOINT_RADIUS,
                x + ENDPOINT_RADIUS,
                y + ENDPOINT_RADIUS,
                fill="#475569",
                outline="#3b82f6",
                width=3,
            ),
            "b": self.canvas.create_oval(
                x + 80 - ENDPOINT_RADIUS,
                y - ENDPOINT_RADIUS,
                x + 80 + ENDPOINT_RADIUS,
                y + ENDPOINT_RADIUS,
                fill="#475569",
                outline="#3b82f6",
                width=3,
            ),
        }
        self.positions: Dict[PointId, Tuple[float, float]] = {
            "a": (x, y),
            "b": (x + 80, y),
        }
        self.attachments: Dict[PointId, Tuple[ComponentLike, str] | None] = {"a": None, "b": None}
        self.links: Dict[PointId, Set[LinkRef]] = {"a": set(), "b": set()}
        self.point_handles: Dict[PointId, Optional[int]] = {
            "a": self.endpoints["a"],
            "b": self.endpoints["b"],
        }
        self.active = False
        self.joint_ids: List[PointId] = []
        self.joint_handles: Dict[PointId, Optional[int]] = {}
        self._joint_counter = 0
        self._dragging_joint_id: Optional[PointId] = None

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

        self._set_point("a", x, y)
        self._set_point("b", x + 80, y)
        self._create_joint(((x + (x + 80)) / 2.0, y))

    def _all_point_ids(self) -> List[PointId]:
        # Provide the ordered list of endpoint and joint identifiers.
        return ["a", *self.joint_ids, "b"]

    @property
    def linked_endpoints(self) -> Dict[PointId, Set[LinkRef]]:
        # Expose the link mappings for external inspection.
        return self.links

    def _set_point(self, point_id: PointId, x: float, y: float, *, update_path: bool = True) -> None:
        # Update the stored coordinates for a point and move its handle.
        self.positions[point_id] = (x, y)
        handle_id = self.point_handles.get(point_id)
        if handle_id:
            radius = ENDPOINT_RADIUS if point_id in ENDPOINT_IDS else JOINT_RADIUS
            self.canvas.coords(handle_id, x - radius, y - radius, x + radius, y + radius)
            self.canvas.tag_raise(handle_id)
        if update_path:
            self._update_line_path()

    def _path_points(self) -> List[Tuple[float, float]]:
        # Return the ordered list of points that define the wire path.
        points: List[Tuple[float, float]] = []
        for point_id in self._all_point_ids():
            points.append(self.positions[point_id])
        return points

    def _update_line_path(self) -> None:
        # Refresh the line geometry to match current point positions.
        points = self._path_points()
        flat: List[float] = []
        for px, py in points:
            flat.extend([px, py])
        self.canvas.coords(self.line_id, *flat)
        for joint_id in self.joint_ids:
            handle = self.joint_handles.get(joint_id)
            if not handle:
                continue
            jx, jy = self.positions[joint_id]
            self.canvas.coords(handle, jx - JOINT_RADIUS, jy - JOINT_RADIUS, jx + JOINT_RADIUS, jy + JOINT_RADIUS)
            self.canvas.tag_raise(handle)
        self.canvas.tag_lower(self.line_id, "component")

    def _create_joint(self, point: Tuple[float, float], draggable: bool = True, insert_at: Optional[int] = None) -> PointId:
        # Insert a new intermediate joint along the wire path.
        joint_id = f"j{self._joint_counter}"
        self._joint_counter += 1
        if insert_at is None:
            self.joint_ids.append(joint_id)
        else:
            self.joint_ids.insert(max(0, min(insert_at, len(self.joint_ids))), joint_id)
        self.positions[joint_id] = point
        self.attachments[joint_id] = None
        self.links[joint_id] = set()
        handle: Optional[int] = None
        if draggable:
            jx, jy = point
            handle = self.canvas.create_oval(
                jx - JOINT_RADIUS,
                jy - JOINT_RADIUS,
                jx + JOINT_RADIUS,
                jy + JOINT_RADIUS,
                fill="#475569",
                outline="#0ea5e9",
                width=2,
            )
            self._bind_joint_handle(joint_id, handle)
        self.joint_handles[joint_id] = handle
        self.point_handles[joint_id] = handle
        self._update_line_path()
        return joint_id

    def _bind_joint_handle(self, joint_id: PointId, handle_id: int) -> None:
        # Attach drag and removal bindings to a joint handle.
        self.canvas.tag_bind(handle_id, "<Button-1>", lambda event, jid=joint_id: self._start_joint_drag(jid, event))
        self.canvas.tag_bind(handle_id, "<B1-Motion>", self._drag_joint)
        self.canvas.tag_bind(handle_id, "<ButtonRelease-1>", self._stop_joint_drag)
        self.canvas.tag_bind(handle_id, "<Double-Button-1>", lambda _event, jid=joint_id: self._remove_joint(jid))

    def _start_joint_drag(self, joint_id: PointId, _event: tk.Event) -> None:
        # Begin dragging a joint by recording its identifier.
        self._dragging_joint_id = joint_id
        handle = self.joint_handles.get(joint_id)
        if handle:
            self.canvas.tag_raise(handle)

    def _drag_joint(self, event: tk.Event) -> None:
        # Move the active joint along with the cursor and propagate links.
        if self._dragging_joint_id is None:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self._set_point(self._dragging_joint_id, canvas_x, canvas_y)
        self._propagate_position(self._dragging_joint_id, (canvas_x, canvas_y), {(self, self._dragging_joint_id)})

    def _stop_joint_drag(self, event: tk.Event) -> None:
        # Finish joint dragging and notify listeners.
        if self._dragging_joint_id is None:
            return
        self._drag_joint(event)
        self._dragging_joint_id = None
        if self.on_change:
            self.on_change(self)

    def _remove_joint(self, joint_id: PointId) -> None:
        # Remove a joint if it is unlinking and no wires depend on it.
        if joint_id not in self.joint_ids:
            return
        if self.links.get(joint_id):
            return
        handle = self.joint_handles.pop(joint_id, None)
        if handle is not None:
            self.canvas.delete(handle)
        self.point_handles.pop(joint_id, None)
        self.positions.pop(joint_id, None)
        self.attachments.pop(joint_id, None)
        self.links.pop(joint_id, None)
        self.joint_ids.remove(joint_id)
        self._update_line_path()
        if self.on_change:
            self.on_change(self)

    def _start_drag(self, endpoint: PointId, _event: tk.Event) -> None:
        # Initiate dragging of an endpoint and detach existing links.
        self._dragging_endpoint = endpoint
        self._detach_point(endpoint)

    def _drag(self, event: tk.Event) -> None:
        # Move a dragging endpoint with the cursor.
        if self._dragging_endpoint is None:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self._set_point(self._dragging_endpoint, canvas_x, canvas_y)

    def _stop_drag(self, event: tk.Event) -> None:
        # Attempt to snap a released endpoint to nearby connectors.
        if self._dragging_endpoint is None:
            return
        endpoint = self._dragging_endpoint
        self._dragging_endpoint = None

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        target, identifier, snap_point = self.connector_finder(canvas_x, canvas_y, self, endpoint)

        if isinstance(target, ComponentLike) and isinstance(identifier, str):
            self.attach_to_component(endpoint, target, identifier, snap_point)
        elif isinstance(target, CircuitWire):
            self.attach_to_wire(endpoint, target, identifier, snap_point)
        else:
            self._set_point(endpoint, canvas_x, canvas_y)
            if self.on_change:
                self.on_change(self)

    def _detach_point(self, point_id: PointId) -> None:
        # Break any component attachments or wire links for a point.
        attachment = self.attachments.get(point_id)
        if attachment:
            component, side = attachment
            component.detach_wire(self, side)
            self.attachments[point_id] = None
        if self.links.get(point_id):
            self._unlink_point(point_id)

    def _link_point(self, point_id: PointId, other_wire: "CircuitWire", other_point: PointId) -> None:
        # Record that this point is linked to another wire's point.
        if other_wire is self and other_point == point_id:
            return
        self.links.setdefault(point_id, set()).add((other_wire, other_point))
        other_wire.links.setdefault(other_point, set()).add((self, point_id))

    def _unlink_point(self, point_id: PointId) -> None:
        # Remove any existing links from the specified point.
        for other_wire, other_point in list(self.links.get(point_id, set())):
            other_wire.links.setdefault(other_point, set()).discard((self, point_id))
        self.links.setdefault(point_id, set()).clear()

    def has_free_endpoint(self) -> bool:
        # Check if either endpoint is unconnected to components or wires.
        for endpoint in ENDPOINT_IDS:
            if not self.attachments.get(endpoint) and not self.links.get(endpoint):
                return True
        return False

    def nearest_free_endpoint(self, point: Tuple[float, float]) -> Optional[str]:
        # Find the nearest unattached endpoint to the provided point.
        px, py = point
        selected: Optional[str] = None
        best_distance = float("inf")
        for endpoint in ENDPOINT_IDS:
            if self.attachments.get(endpoint) or self.links.get(endpoint):
                continue
            ex, ey = self.positions.get(endpoint, (0.0, 0.0))
            dist = math.hypot(ex - px, ey - py)
            if dist < best_distance:
                best_distance = dist
                selected = endpoint
        return selected

    def nearest_endpoint(self, point: Tuple[float, float]) -> Optional[str]:
        # Find the closest endpoint regardless of attachment state.
        px, py = point
        selected: Optional[str] = None
        best_distance = float("inf")
        for endpoint in ENDPOINT_IDS:
            ex, ey = self.positions.get(endpoint, (0.0, 0.0))
            dist = math.hypot(ex - px, ey - py)
            if dist < best_distance:
                best_distance = dist
                selected = endpoint
        return selected

    def path_points(self) -> List[Tuple[float, float]]:
        # Expose the path coordinates for external consumers.
        return self._path_points()

    def _propagate_attachment(
        self,
        point_id: PointId,
        component: ComponentLike,
        side: str,
        visited: Optional[VisitedSet] = None,
    ) -> None:
        # Spread attachment information across linked wires.
        if visited is None:
            visited = set()
        visited.add((self, point_id))
        for other_wire, other_point in list(self.links.get(point_id, set())):
            if (other_wire, other_point) in visited:
                continue
            other_wire._adopt_attachment(other_point, component, side, visited)

    def _adopt_attachment(
        self,
        point_id: PointId,
        component: ComponentLike,
        side: str,
        visited: VisitedSet,
    ) -> None:
        # Adopt a component attachment propagated from another wire.
        current = self.attachments.get(point_id)
        if not current or current[0] is not component or current[1] != side:
            if current:
                old_component, old_side = current
                old_component.detach_wire(self, old_side)
            component.attach_wire(self, side)
            self.attachments[point_id] = (component, side)
        anchor = component.anchor_point(side)
        self._set_point(point_id, *anchor)
        self._propagate_position(point_id, anchor, visited)
        self._propagate_attachment(point_id, component, side, visited)

    def _propagate_position(
        self,
        point_id: PointId,
        point: Tuple[float, float],
        visited: Optional[VisitedSet] = None,
    ) -> None:
        # Mirror a point's coordinates across all linked wires.
        if visited is None:
            visited = set()
        visited.add((self, point_id))
        for other_wire, other_point in list(self.links.get(point_id, set())):
            if (other_wire, other_point) in visited:
                continue
            other_wire._set_point(other_point, *point)
            other_wire._propagate_position(other_point, point, visited)
        self._update_line_path()

    def attach_to_component(
        self,
        point_id: PointId,
        component: ComponentLike,
        side: str,
        point: Tuple[float, float] | None = None,
    ) -> None:
        # Snap an endpoint to a component terminal and propagate updates.
        self._detach_point(point_id)
        anchor = point if point else component.anchor_point(side)
        self._set_point(point_id, *anchor)
        component.attach_wire(self, side)
        self.attachments[point_id] = (component, side)
        self._propagate_position(point_id, anchor, {(self, point_id)})
        self._propagate_attachment(point_id, component, side, {(self, point_id)})
        if self.on_change:
            self.on_change(self)

    def ensure_junction(self, point: Tuple[float, float], segment_index: Optional[int] = None) -> PointId:
        # Ensure there is a draggable joint near the desired point.
        px, py = point
        for candidate in self._all_point_ids():
            cx, cy = self.positions.get(candidate, (0.0, 0.0))
            if math.hypot(cx - px, cy - py) <= 8.0:
                return candidate
        insert_at = None
        if segment_index is not None:
            insert_at = min(max(segment_index, 0), len(self.joint_ids))
        return self._create_joint(point, draggable=True, insert_at=insert_at)

    def attach_to_wire(
        self,
        point_id: PointId,
        other_wire: "CircuitWire",
        other_endpoint: Union[str, Tuple[Any, ...]],
        point: Tuple[float, float] | None = None,
    ) -> None:
        # Connect this wire to another wire at a shared point.
        if other_wire is self:
            return

        snap_point = point
        target_point: Optional[PointId] = None

        if isinstance(other_endpoint, tuple):
            tag = other_endpoint[0]
            if tag == "segment":
                candidate_point = (other_endpoint[1], other_endpoint[2])
                segment_index = other_endpoint[3] if len(other_endpoint) > 3 else None
                target_point = other_wire.ensure_junction(candidate_point, segment_index)
                snap_point = other_wire.positions.get(target_point, candidate_point)
            else:
                return
        else:
            target_point = other_endpoint

        if not isinstance(target_point, str):
            return

        self._detach_point(point_id)
        if snap_point is None:
            snap_point = other_wire.positions.get(target_point, (0.0, 0.0))
        self._set_point(point_id, *snap_point)
        self._link_point(point_id, other_wire, target_point)

        other_attachment = other_wire.attachments.get(target_point)
        if other_attachment:
            component, side = other_attachment
            component.attach_wire(self, side)
            self.attachments[point_id] = (component, side)
            self._propagate_position(point_id, snap_point, {(self, point_id)})
            self._propagate_attachment(point_id, component, side, {(self, point_id)})
        else:
            self.attachments[point_id] = None
            self._propagate_position(point_id, snap_point, {(self, point_id)})

        if self.on_change:
            self.on_change(self)

    def detach_component(self, component: ComponentLike) -> None:
        # Detach the wire from a specific component wherever it is connected.
        updated = False
        for point_id, attachment in list(self.attachments.items()):
            if attachment and attachment[0] is component:
                component.detach_wire(self, attachment[1])
                self.attachments[point_id] = None
                updated = True
        if updated and self.on_change:
            self.on_change(self)

    def update_attachment_position(self, component: ComponentLike, side: str, point: Tuple[float, float]) -> None:
        # Move linked points to follow a component that has moved.
        for point_id, attachment in self.attachments.items():
            if attachment and attachment[0] is component and attachment[1] == side:
                self._set_point(point_id, *point)
                self._propagate_position(point_id, point, {(self, point_id)})

    def attached_components(self) -> list[ComponentLike]:
        # Return unique components currently connected to this wire.
        components: Set[ComponentLike] = set()
        for attachment in self.attachments.values():
            if attachment:
                components.add(attachment[0])
        return list(components)

    def set_active(self, active: bool) -> None:
        # Update wire visuals to reflect whether it carries current.
        self.active = active
        color = "#10b981" if active else "#94a3b8"
        width = 5 if active else 4
        self.canvas.itemconfigure(self.line_id, fill=color, width=width)
        for handle in self.endpoints.values():
            fill_color = "#10b981" if active else "#475569"
            outline_color = "#059669" if active else "#3b82f6"
            self.canvas.itemconfigure(handle, fill=fill_color, outline=outline_color)
        for handle in self.joint_handles.values():
            if handle is None:
                continue
            fill_color = "#10b981" if active else "#475569"
            outline_color = "#064e3b" if active else "#0ea5e9"
            self.canvas.itemconfigure(handle, fill=fill_color, outline=outline_color)

    def _cut(self, _event: tk.Event | None = None) -> None:
        # Remove the wire when double-clicked.
        self.remove()

    def remove(self) -> None:
        # Delete the wire, detaching all component and wire connections.
        for point_id, attachment in list(self.attachments.items()):
            if attachment:
                component, side = attachment
                component.detach_wire(self, side)
                self.attachments[point_id] = None
        for point_id in list(self.links.keys()):
            if self.links.get(point_id):
                self._unlink_point(point_id)
        self.canvas.delete(self.line_id)
        for handle in list(self.point_handles.values()):
            if handle is not None:
                self.canvas.delete(handle)
        if self.on_request_remove:
            self.on_request_remove(self)

    def _start_line_drag(self, event: tk.Event) -> None:
        # Prepare to drag the entire wire path when it is free-floating.
        if any(self.attachments.get(pid) for pid in self._all_point_ids()):
            return
        if any(self.links.get(pid) for pid in self._all_point_ids()):
            return
        self._dragging_line = True
        self._line_drag_last = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _drag_line(self, event: tk.Event) -> None:
        # Translate the entire wire path based on cursor movement.
        if not self._dragging_line or self._line_drag_last is None:
            return
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        dx = current_x - self._line_drag_last[0]
        dy = current_y - self._line_drag_last[1]
        if dx == 0 and dy == 0:
            return
        for point_id in self._all_point_ids():
            px, py = self.positions.get(point_id, (0.0, 0.0))
            self._set_point(point_id, px + dx, py + dy, update_path=False)
        self._update_line_path()
        self._line_drag_last = (current_x, current_y)

    def _stop_line_drag(self, _event: tk.Event) -> None:
        # Complete the full-wire drag and notify listeners.
        if not self._dragging_line:
            return
        self._dragging_line = False
        self._line_drag_last = None
        if self.on_change:
            self.on_change(self)


__all__ = ["CircuitWire"]
