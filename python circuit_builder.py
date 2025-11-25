import tkinter as tk
from tkinter import simpledialog
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import random


GRID_SIZE = 20
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 500

COMPONENT_ICONS = {
    "battery": "⚡",
    "resistor": "⎍",
    "bulb": "💡",
    "wire": "─",
    "switch": "⏚",
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
}

COMPONENT_PREFIX: Dict[str, str] = {
    "battery": "B",
    "resistor": "R",
    "bulb": "L",
    "wire": "W",
    "switch": "S",
}

BATTERY_VOLTAGE = 9.0




class CircuitComponent:
    def __init__(
        self,
        canvas: tk.Canvas,
        comp_type: str,
        x: int,
        y: int,
        component_id: int,
        display_label: str,
        code_label: str,
        on_change: Callable[["CircuitComponent"], None],
        on_request_remove: Callable[["CircuitComponent"], None],
    ) -> None:
        self.canvas = canvas
        self.type = comp_type
        self.x = int(x)
        self.y = int(y)
        self.id = component_id
        self.display_label = display_label
        self.code_label = code_label
        self.on_change = on_change
        self.on_request_remove = on_request_remove

        props = COMPONENT_PROPS.get(comp_type, {})
        self.host_bg = props.get("color", "#f1f5f9")
        self.badge_bg = props.get("badge_bg", "#0f172a")
        self.badge_fg = props.get("badge_fg", "#f8fafc")
        self.active_body = props.get("active_body", self.host_bg)

        self.base_width = 160
        self.base_height = 120

        self.voltage_value = float(props.get("voltage", 0.0))
        self.resistance_value = float(props.get("resistance", 0.0))
        self.operating_current = 0.0
        self.operating_voltage = 0.0
        self.operating_power = 0.0
        self.active = False

        self.connected_wires: Dict[str, Set["CircuitWire"]] = {side: set() for side in ("left", "right", "top", "bottom")}
        self.terminal_canvases: List[tk.Canvas] = []

        self.pointer_offset_x = 0
        self.pointer_offset_y = 0
        self.dragging = False
        self.window_id: Optional[int] = None

        self.frame = tk.Frame(
            self.canvas,
            bg=self.host_bg,
            bd=0,
            highlightthickness=0,
        )
        self.frame.configure(width=self.base_width, height=self.base_height)

        self.toolbar_frame = tk.Frame(self.frame, bg=self.host_bg)
        self.toolbar_frame.pack(fill=tk.X, padx=8, pady=(8, 0))

        self.code_badge = tk.Label(
            self.toolbar_frame,
            text=self.code_label,
            font=("Arial", 9, "bold"),
            bg=self.badge_bg,
            fg=self.badge_fg,
            padx=6,
            pady=2,
        )
        self.code_badge.pack(side=tk.LEFT)

        icon_text = COMPONENT_ICONS.get(comp_type, "")
        name_text = f"{icon_text} {self.display_label}".strip()
        self.name_label = tk.Label(
            self.toolbar_frame,
            text=name_text,
            font=("Arial", 10, "bold"),
            bg=self.host_bg,
            fg="#0f172a",
        )
        self.name_label.pack(side=tk.LEFT, padx=(6, 0))

        remove_label = tk.Label(
            self.toolbar_frame,
            text="✕",
            font=("Arial", 9, "bold"),
            bg=self.host_bg,
            fg="#ef4444",
            cursor="hand2",
        )
        remove_label.pack(side=tk.RIGHT)
        remove_label.bind("<Button-1>", lambda _event: self.remove())

        self.body_frame = tk.Frame(self.frame, bg=self.host_bg, bd=0)
        self.body_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))

        self.visual_canvas = tk.Canvas(
            self.body_frame,
            width=120,
            height=80,
            bg=self.host_bg,
            highlightthickness=0,
            bd=0,
        )
        self.visual_canvas.pack(fill=tk.BOTH, expand=True)

        self.detail_label = tk.Label(
            self.body_frame,
            text="",
            font=("Arial", 8),
            bg=self.host_bg,
            fg="#475569",
            anchor="w",
            justify=tk.LEFT,
        )
        self.detail_label.pack(fill=tk.X, pady=(6, 0))

        self._draw_terminal_indicators()
        self._draw_visual_representation()
        self._update_detail_text()

        self.frame.update_idletasks()
        self.window_id = self.canvas.create_window(
            self.x,
            self.y,
            window=self.frame,
            anchor="nw",
            tags=(f"comp_{self.id}", "component"),
        )

        self._move_to(self.x, self.y)

        bind_targets = [
            self.frame,
            self.toolbar_frame,
            self.body_frame,
            self.code_badge,
            self.name_label,
            self.detail_label,
        ]
        if self.visual_canvas:
            bind_targets.append(self.visual_canvas)
        for widget in bind_targets:
            widget.bind("<Button-1>", self._on_press, add="+")
            widget.bind("<B1-Motion>", self._on_drag, add="+")
            widget.bind("<ButtonRelease-1>", self._on_release, add="+")
            widget.bind("<Double-Button-1>", self._on_double_click, add="+")

    def _component_detail_text(self) -> str:
        if self.type == "battery":
            text = f"{self.voltage_value:.2f} V source"
            if self.active and self.operating_current > 0:
                text += f" | {self.operating_current:.3f} A"
            return text
        if self.type == "resistor":
            text = f"{self.resistance_value:.2f} Ω load"
            if self.active and self.operating_current > 0:
                text += f" | {self.operating_current * 1000:.1f} mA"
            if self.active and self.operating_power > 0:
                text += f" | {self.operating_power:.2f} W"
            return text
        if self.type == "bulb":
            text = f"Filament {self.resistance_value:.2f} Ω"
            if self.active and self.operating_power > 0:
                text += f" | {self.operating_power:.2f} W"
            return text
        if self.type == "switch":
            return "Toggle connection"
        return COMPONENT_PROPS[self.type]["label"]

    def _update_detail_text(self) -> None:
        if self.detail_label:
            self.detail_label.configure(text=self._component_detail_text())

    def reset_operating_metrics(self) -> None:
        self.operating_current = 0.0
        self.operating_voltage = 0.0
        self.operating_power = 0.0
        self._update_detail_text()
        self._draw_visual_representation()

    def update_operating_metrics(self, current: float, voltage: float, power: float) -> None:
        self.operating_current = max(current, 0.0)
        self.operating_voltage = max(voltage, 0.0)
        self.operating_power = max(power, 0.0)
        self._update_detail_text()
        self._draw_visual_representation()

    def _nominal_reference(self) -> float:
        if self.type in ("resistor", "bulb"):
            if self.resistance_value > 0 and (self.operating_voltage > 0 or self.voltage_value > 0):
                voltage = self.operating_voltage if self.operating_voltage > 0 else self.voltage_value
                return max((voltage ** 2) / self.resistance_value, 0.05)
            return 0.5
        if self.type == "battery":
            return max(self.voltage_value / 12.0, 0.1)
        return 1.0

    def _intensity_ratio(self) -> float:
        reference = self._nominal_reference()
        if self.operating_power > 0 and reference > 0:
            ratio = self.operating_power / reference
        elif self.operating_current > 0 and reference > 0:
            ratio = self.operating_current / reference
        else:
            ratio = 0.0
        return max(0.0, min(ratio, 1.0))

    def _mix_color(self, start_hex: str, end_hex: str, ratio: float) -> str:
        ratio = max(0.0, min(ratio, 1.0))
        def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
            value = value.lstrip("#")
            return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

        def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
            return "#" + "".join(f"{channel:02x}" for channel in rgb)

        start_rgb = _hex_to_rgb(start_hex)
        end_rgb = _hex_to_rgb(end_hex)
        blended = tuple(
            int(start_channel + (end_channel - start_channel) * ratio)
            for start_channel, end_channel in zip(start_rgb, end_rgb)
        )
        return _rgb_to_hex(blended)

    def _draw_visual_representation(self) -> None:
        if not self.visual_canvas:
            return
        self.visual_canvas.delete("all")
        active = self.active
        if self.type == "battery":
            self._draw_battery_visual(active)
        elif self.type == "resistor":
            self._draw_resistor_visual(active)
        elif self.type == "bulb":
            self._draw_bulb_visual(active)
        elif self.type == "switch":
            self._draw_switch_visual(active)
        else:
            self._draw_wire_visual(active)

    def _draw_battery_visual(self, active: bool) -> None:
        if not self.visual_canvas:
            return
        vc = self.visual_canvas
        ratio = self._intensity_ratio() if active else 0.0
        casing_fill = self._mix_color("#fcd34d", "#f59e0b", ratio)
        cell_fill = self._mix_color("#fda4af", "#f87171", ratio)
        lead_color = self._mix_color("#64748b", "#047857", ratio)
        text_color = "#1f2937"

        vc.create_line(6, 40, 26, 40, fill=lead_color, width=4, capstyle=tk.ROUND)
        vc.create_line(84, 40, 104, 40, fill=lead_color, width=4, capstyle=tk.ROUND)
        vc.create_rectangle(26, 18, 52, 62, fill=cell_fill, outline="#0f172a", width=2)
        vc.create_rectangle(52, 22, 84, 58, fill=casing_fill, outline="#0f172a", width=2)
        vc.create_text(20, 24, text="+", font=("Arial", 12, "bold"), fill=text_color)
        vc.create_text(96, 24, text="-", font=("Arial", 12, "bold"), fill=text_color)
        vc.create_text(55, 70, text=f"{self.voltage_value:.1f} V", font=("Arial", 10, "bold"), fill=text_color)

    def _draw_resistor_visual(self, active: bool) -> None:
        if not self.visual_canvas:
            return
        vc = self.visual_canvas
        ratio = self._intensity_ratio() if active else 0.0
        lead_color = self._mix_color("#475569", "#0f766e", ratio)
        resistor_color = self._mix_color("#fbbf24", "#f97316", ratio)
        text_color = "#0f172a"

        vc.create_line(6, 40, 26, 40, fill=lead_color, width=4, capstyle=tk.ROUND)
        zigzag = [26, 40, 34, 28, 42, 52, 50, 28, 58, 52, 66, 28, 74, 40]
        vc.create_line(*zigzag, fill=resistor_color, width=4, joinstyle=tk.ROUND)
        vc.create_line(74, 40, 104, 40, fill=lead_color, width=4, capstyle=tk.ROUND)
        vc.create_text(55, 66, text=f"{self.resistance_value:.1f} Ω", font=("Arial", 10, "bold"), fill=text_color)

    def _draw_bulb_visual(self, active: bool) -> None:
        if not self.visual_canvas:
            return
        vc = self.visual_canvas
        ratio = self._intensity_ratio() if active else 0.0
        glow_fill = self._mix_color("#f3f4f6", "#fde68a", ratio)
        outline_color = self._mix_color("#cbd5f5", "#facc15", ratio)
        filament_color = self._mix_color("#64748b", "#b45309", ratio)
        base_color = "#475569"

        vc.create_oval(18, 8, 92, 72, fill=glow_fill, outline=outline_color, width=3)
        vc.create_line(38, 48, 72, 48, fill=filament_color, width=2)
        vc.create_line(55, 48, 55, 66, fill=filament_color, width=3)
        vc.create_arc(34, 30, 76, 66, start=225, extent=90, style=tk.ARC, outline=filament_color, width=2)
        vc.create_arc(34, 30, 76, 66, start=45, extent=90, style=tk.ARC, outline=filament_color, width=2)
        vc.create_rectangle(44, 66, 66, 76, fill=base_color, outline=base_color)
        vc.create_rectangle(48, 76, 62, 82, fill=base_color, outline=base_color)

    def _draw_switch_visual(self, active: bool) -> None:
        if not self.visual_canvas:
            return
        vc = self.visual_canvas
        ratio = self._intensity_ratio() if active else 0.0
        lead_color = self._mix_color("#64748b", "#2563eb", ratio)
        vc.create_line(6, 40, 46, 40, fill=lead_color, width=4, capstyle=tk.ROUND)
        vc.create_oval(42, 36, 50, 44, fill="#e2e8f0", outline="#475569")
        if ratio > 0.5:
            vc.create_line(46, 40, 104, 40, fill=lead_color, width=4, capstyle=tk.ROUND)
        else:
            vc.create_line(46, 40, 96, 24, fill=lead_color, width=4, capstyle=tk.ROUND)
            vc.create_line(96, 24, 104, 30, fill=lead_color, width=4, capstyle=tk.ROUND)

    def _draw_wire_visual(self, active: bool) -> None:
        if not self.visual_canvas:
            return
        vc = self.visual_canvas
        ratio = self._intensity_ratio() if active else 0.0
        wire_color = self._mix_color("#64748b", "#10b981", ratio)
        vc.create_line(8, 40, 102, 40, fill=wire_color, width=5, capstyle=tk.ROUND)

    def _on_press(self, event: tk.Event) -> None:
        if not self.frame:
            return
        self.dragging = True
        if self.window_id is not None:
            self.canvas.tag_raise(self.window_id)
        self.pointer_offset_x = event.x_root - self.frame.winfo_rootx()
        self.pointer_offset_y = event.y_root - self.frame.winfo_rooty()

    def _on_drag(self, event: tk.Event) -> None:
        if not self.dragging or not self.frame or self.window_id is None:
            return

        pointer_x = self.canvas.canvasx(event.x_root - self.canvas.winfo_rootx())
        pointer_y = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())

        target_x = pointer_x - self.pointer_offset_x
        target_y = pointer_y - self.pointer_offset_y

        snapped_x = round(target_x / GRID_SIZE) * GRID_SIZE
        snapped_y = round(target_y / GRID_SIZE) * GRID_SIZE

        width = self.frame.winfo_width() or self.frame.winfo_reqwidth()
        height = self.frame.winfo_height() or self.frame.winfo_reqheight()

        canvas_width, canvas_height = self._canvas_bounds()
        snapped_x = int(max(0, min(snapped_x, canvas_width - width)))
        snapped_y = int(max(0, min(snapped_y, canvas_height - height)))

        self._move_to(snapped_x, snapped_y)

    def _on_release(self, _event: tk.Event) -> None:
        if not self.dragging:
            return
        self.dragging = False
        if self.on_change:
            self.on_change(self)

    def _on_double_click(self, _event: tk.Event) -> None:
        if self.type == "battery":
            new_voltage = simpledialog.askfloat(
                "Adjust Battery",
                "Enter battery voltage (V):",
                initialvalue=self.voltage_value,
                minvalue=0.1,
            )
            if new_voltage is None:
                return
            self.voltage_value = float(new_voltage)
        elif self.type in ("resistor", "bulb"):
            new_resistance = simpledialog.askfloat(
                "Adjust Resistance",
                "Enter resistance (Ω):",
                initialvalue=self.resistance_value,
                minvalue=0.1,
            )
            if new_resistance is None:
                return
            self.resistance_value = float(new_resistance)
        else:
            return

        self._update_detail_text()
        self._draw_visual_representation()
        if self.on_change:
            self.on_change(self)

    def _move_to(self, x: int, y: int) -> None:
        if self.window_id is None:
            return
        if self.frame is None:
            return
        width = self.frame.winfo_width() or self.frame.winfo_reqwidth()
        height = self.frame.winfo_height() or self.frame.winfo_reqheight()
        canvas_width, canvas_height = self._canvas_bounds()
        clamped_x = int(max(0, min(x, canvas_width - width)))
        clamped_y = int(max(0, min(y, canvas_height - height)))
        self.x = clamped_x
        self.y = clamped_y
        self.canvas.coords(self.window_id, self.x, self.y)
        self._notify_attached_wires()

    def _current_dimensions(self) -> tuple[int, int]:
        if self.frame is None:
            return self.base_width, self.base_height
        width = self.frame.winfo_width() or self.frame.winfo_reqwidth() or self.base_width
        height = self.frame.winfo_height() or self.frame.winfo_reqheight() or self.base_height
        return int(width), int(height)

    def _canvas_bounds(self) -> tuple[int, int]:
        width = int(self.canvas.winfo_width() or self.canvas.winfo_reqwidth() or CANVAS_WIDTH)
        height = int(self.canvas.winfo_height() or self.canvas.winfo_reqheight() or CANVAS_HEIGHT)
        return width, height

    def center(self) -> tuple[float, float]:
        width, height = self._current_dimensions()
        return self.x + width / 2, self.y + height / 2

    def anchor_point(self, side: str) -> tuple[float, float]:
        width, height = self._current_dimensions()
        cy = self.y + height / 2
        if side == "left":
            return float(self.x), float(cy)
        if side == "right":
            return float(self.x + width), float(cy)
        if side == "top":
            return float(self.x + width / 2), float(self.y)
        if side == "bottom":
            return float(self.x + width / 2), float(self.y + height)
        return self.center()

    def get_resistance(self) -> float:
        return self.resistance_value

    def get_voltage(self) -> float:
        return self.voltage_value if self.type == "battery" else 0.0

    def remove(self) -> None:
        for side, wires in self.connected_wires.items():
            for wire in list(wires):
                wire.detach_component(self)
            wires.clear()
        if self.window_id is not None:
            self.canvas.delete(self.window_id)
            self.window_id = None
        if self.frame is not None:
            self.frame.destroy()
            self.frame = None
        if self.on_request_remove:
            self.on_request_remove(self)

    def set_active(self, active: bool) -> None:
        if self.frame is None:
            return
        self.active = active
        border_color = "#22c55e" if active else self.host_bg
        thickness = 3 if active else 0
        self.frame.configure(highlightbackground=border_color, highlightcolor=border_color, highlightthickness=thickness)

        if self.code_badge:
            badge_bg = "#047857" if active else self.badge_bg
            badge_fg = "#ecfdf5" if active else self.badge_fg
            self.code_badge.configure(bg=badge_bg, fg=badge_fg)

        if self.name_label:
            self.name_label.configure(fg="#047857" if active else "#0f172a")
        if self.detail_label:
            self.detail_label.configure(fg="#047857" if active else "#475569")

        connector_color = "#0ea5e9" if active else "#7c3aed"
        for dot in self.terminal_canvases:
            dot.configure(bg=self.host_bg)
            for item in dot.find_withtag("terminal"):
                dot.itemconfigure(item, fill=connector_color, outline=connector_color)

        self._draw_visual_representation()
        self._update_detail_text()

    def attach_wire(self, wire: "CircuitWire", side: str) -> None:
        if side not in self.connected_wires:
            self.connected_wires[side] = set()
        self.connected_wires[side].add(wire)
        self._notify_attached_wires()

    def detach_wire(self, wire: "CircuitWire", side: str | None = None) -> None:
        if side:
            if side in self.connected_wires and wire in self.connected_wires[side]:
                self.connected_wires[side].discard(wire)
        else:
            for wires in self.connected_wires.values():
                wires.discard(wire)

    def _notify_attached_wires(self) -> None:
        for side, wires in self.connected_wires.items():
            anchor = self.anchor_point(side)
            for wire in list(wires):
                wire.update_attachment_position(self, side, anchor)

    def _draw_terminal_indicators(self) -> None:
        """Draw small circles indicating connection points"""
        if not self.frame or not self.body_frame:
            return
        for dot in self.terminal_canvases:
            dot.destroy()
        self.terminal_canvases.clear()

        terminal_size = 5
        color = "#7c3aed"
        body_bg = self.host_bg

        left_dot = tk.Canvas(
            self.body_frame,
            width=terminal_size * 2,
            height=terminal_size * 2,
            bg=body_bg,
            highlightthickness=0,
            bd=0,
        )
        left_dot.create_oval(0, 0, terminal_size * 2, terminal_size * 2, fill=color, outline=color, tags="terminal")
        left_dot.place(x=2, rely=0.5, anchor="w")

        right_dot = tk.Canvas(
            self.body_frame,
            width=terminal_size * 2,
            height=terminal_size * 2,
            bg=body_bg,
            highlightthickness=0,
            bd=0,
        )
        right_dot.create_oval(0, 0, terminal_size * 2, terminal_size * 2, fill=color, outline=color, tags="terminal")
        right_dot.place(relx=1.0, x=-terminal_size * 2 - 2, rely=0.5, anchor="w")

        self.terminal_canvases.extend([left_dot, right_dot])


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

        # Ensure endpoints render above the line immediately
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
                current[0].detach_wire(self, current[1])
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

    def attached_components(self) -> List[CircuitComponent]:
        comps = []
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



class OhmsLawApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ohm's Law & Circuit Builder")
        self.root.geometry("1200x700")
        self.root.configure(bg="#f0f0f0")

        self.components: List[CircuitComponent] = []
        self.component_counter = 0
        self.component_type_counters: Dict[str, int] = {}
        self.wires: List[CircuitWire] = []

        self.status = tk.StringVar(value="Open Circuit")
        self.circuit_type_var = tk.StringVar(value="Type: Open")
        self.circuit_status_var = tk.StringVar(value="Status: Awaiting components")
        self.circuit_metrics_var = tk.StringVar(value="Voltage: — | Current: —")
        self.circuit_power_var = tk.StringVar(value="Power: — | Resistance: —")
        self.circuit_counts_var = tk.StringVar(value="Components: 0 | Wires: 0")
        self.circuit_path_var = tk.StringVar(value="Active path: —")

        self._create_widgets()
        self._draw_grid()

    def _create_widgets(self) -> None:
        # === Header ===
        header = tk.Frame(self.root, bg="#ffffff", relief=tk.RAISED, bd=1)
        header.pack(side=tk.TOP, fill=tk.X, padx=0, pady=0)

        tk.Label(
            header,
            text="⚡ Interactive Circuit Builder",
            font=("Arial", 14, "bold"),
            bg="#ffffff",
            fg="#1f2937"
        ).pack(pady=(12, 2))

        tk.Label(
            header,
            text="Drag components, connect with wires, and watch Ohm's Law calculations update in real-time",
            font=("Arial", 10),
            bg="#ffffff",
            fg="#6b7280"
        ).pack(pady=(0, 12))

        # === Main Layout ===
        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left Panel: Components
        left_panel = tk.Frame(main_frame, bg="#ffffff", width=150, relief=tk.SUNKEN, bd=1)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_panel.pack_propagate(False)

        tk.Label(left_panel, text="Component Palette", font=("Arial", 12, "bold"), bg="#ffffff").pack(pady=(10, 5))

        palette = [
            ("battery", "Battery"),
            ("resistor", "Resistor"),
            ("bulb", "Bulb"),
            ("switch", "Switch"),
            ("wire", "Wire"),
        ]

        for comp_type, label in palette:
            tile = tk.Frame(left_panel, bg="#f8fafc", bd=1, relief=tk.RIDGE, padx=6, pady=6)
            tile.pack(pady=5, padx=10, fill=tk.X)

            icon_label = tk.Label(tile, text=COMPONENT_ICONS.get(comp_type, "❓"), font=("Arial", 20), bg="#f8fafc")
            icon_label.pack()

            tk.Label(tile, text=label, font=("Arial", 9), bg="#f8fafc", fg="#334155").pack()

            def make_handler(item_type: str):
                if item_type == "wire":
                    return lambda _event=None: self._add_wire()
                return lambda _event=None: self._add_component(item_type)

            handler = make_handler(comp_type)
            tile.bind("<Button-1>", handler)
            icon_label.bind("<Button-1>", handler)

        help_frame = tk.Frame(left_panel, bg="#f0f9ff", relief=tk.RIDGE, bd=1)
        help_frame.pack(side=tk.BOTTOM, pady=10, padx=8, fill=tk.X)
        
        tk.Label(
            help_frame,
            text="💡 Quick Tips",
            font=("Arial", 9, "bold"),
            bg="#f0f9ff",
            fg="#1e40af"
        ).pack(pady=(6, 4))
        
        tips = [
            "• Click components to add",
            "• Drag wires to terminals",
            "• Violet dots = connectors",
            "• Link wires end-to-end",
            "• Double-click to edit values",
            "• Double-click wire to cut",
            "• Green = active circuit"
        ]
        for tip in tips:
            tk.Label(
                help_frame,
                text=tip,
                font=("Arial", 7),
                bg="#f0f9ff",
                fg="#475569",
                anchor="w"
            ).pack(anchor="w", padx=8, pady=1)
        
        tk.Label(help_frame, text="", bg="#f0f9ff").pack(pady=2)

        # Center: Circuit Canvas
        canvas_frame = tk.Frame(main_frame, bg="#f0f0f0")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(canvas_frame, text="Circuit Canvas", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=(0, 5))

        self.canvas = tk.Canvas(canvas_frame, bg="white", width=CANVAS_WIDTH, height=CANVAS_HEIGHT, relief=tk.SUNKEN, bd=2)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_width = CANVAS_WIDTH
        self.canvas_height = CANVAS_HEIGHT
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Right Panel: Calculator
        right_panel = tk.Frame(main_frame, bg="#ffffff", width=250, relief=tk.SUNKEN, bd=1)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        right_panel.pack_propagate(False)

        tk.Label(right_panel, text="Ohm's Law Calculator", font=("Arial", 12, "bold"), bg="#ffffff").pack(pady=(10, 5))

        # Formula
        formula_frame = tk.Frame(right_panel, bg="white", relief=tk.RAISED, bd=1)
        formula_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(formula_frame, text="V = I × R", font=("Arial", 14, "bold"), bg="white", fg="#333333").pack(pady=10)

        # Voltage
        v_frame = tk.Frame(right_panel, bg="#ffffff")
        v_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(v_frame, text="Voltage (V)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.v_entry = tk.Entry(v_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.v_entry.pack(fill=tk.X, padx=5, pady=2)

        # Current
        i_frame = tk.Frame(right_panel, bg="#ffffff")
        i_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(i_frame, text="Current (I)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.i_entry = tk.Entry(i_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.i_entry.pack(fill=tk.X, padx=5, pady=2)

        # Resistance
        r_frame = tk.Frame(right_panel, bg="#ffffff")
        r_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(r_frame, text="Resistance (R)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.r_entry = tk.Entry(r_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.r_entry.pack(fill=tk.X, padx=5, pady=2)

        # Power display
        power_frame = tk.Frame(right_panel, bg="#ffffff")
        power_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(power_frame, text="Power (P)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.p_entry = tk.Entry(power_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.p_entry.pack(fill=tk.X, padx=5, pady=2)
        
        # Info box
        info_frame = tk.Frame(right_panel, bg="#ecfdf5", relief=tk.RAISED, bd=1)
        info_frame.pack(padx=10, pady=10, fill=tk.X)
        tk.Label(
            info_frame,
            text="ℹ️ Build Your Circuit",
            font=("Arial", 9, "bold"),
            bg="#ecfdf5",
            fg="#047857"
        ).pack(padx=5, pady=(5, 2))
        tk.Label(
            info_frame,
            text="Add battery + load (resistor/bulb), then wire all terminals to form a complete loop. Values calculate automatically!",
            font=("Arial", 8),
            bg="#ecfdf5",
            fg="#065f46",
            wraplength=220,
            justify=tk.LEFT
        ).pack(padx=8, pady=(0, 5))

        analysis_frame = tk.Frame(right_panel, bg="#f8fafc", relief=tk.RIDGE, bd=1)
        analysis_frame.pack(padx=10, pady=(0, 10), fill=tk.X)

        tk.Label(
            analysis_frame,
            text="📊 Circuit Insight",
            font=("Arial", 10, "bold"),
            bg="#f8fafc",
            fg="#1d4ed8"
        ).pack(anchor="w", padx=8, pady=(6, 2))

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_type_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937"
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_status_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937"
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_metrics_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937"
        ).pack(anchor="w", padx=12, pady=(4, 1))

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_power_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937"
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_counts_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937"
        ).pack(anchor="w", padx=12, pady=(4, 1))

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_path_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937"
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            text="Issues & Tips",
            font=("Arial", 9, "bold"),
            bg="#f8fafc",
            fg="#475569"
        ).pack(anchor="w", padx=12, pady=(8, 2))

        self.circuit_issue_label = tk.Label(
            analysis_frame,
            text="• No issues detected",
            font=("Arial", 8),
            bg="#eef2ff",
            fg="#1f2937",
            justify=tk.LEFT,
            wraplength=210,
            relief=tk.FLAT,
            padx=8,
            pady=4,
        )
        self.circuit_issue_label.pack(fill=tk.X, padx=10, pady=(0, 8))

        # === Bottom Controls ===
        bottom_frame = tk.Frame(self.root, bg="#ffffff", relief=tk.RAISED, bd=1)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=0)

        btn_frame = tk.Frame(bottom_frame, bg="#ffffff")
        btn_frame.pack(side=tk.LEFT, padx=20, pady=10)

        tk.Button(btn_frame, text="🗑️ Clear All", font=("Arial", 10, "bold"),
                  bg="#dc2626", fg="white", width=12, command=self._reset_circuit,
                  relief=tk.RAISED, bd=2).pack(side=tk.LEFT, padx=5)

        status_frame = tk.Frame(bottom_frame, bg="#ffffff")
        status_frame.pack(side=tk.RIGHT, padx=20, pady=10)
        tk.Label(status_frame, text="Status:", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(side=tk.LEFT, padx=5)
        self.status_label = tk.Label(status_frame, textvariable=self.status, font=("Arial", 10, "bold"), bg="#ffffff")
        self.status_label.pack(side=tk.LEFT)

        self._update_analysis_panel({
            "component_count": 0,
            "wire_count": 0,
            "active_component_count": 0,
            "active_wire_count": 0,
            "type": "Open",
            "status": "Open",
            "status_detail": "⚫ Open Circuit",
            "total_voltage": 0.0,
            "total_current": 0.0,
            "total_resistance": 0.0,
            "total_power": 0.0,
            "path_description": "—",
            "issues": [],
        })

    def _draw_grid(self) -> None:
        """Draw a subtle grid on the canvas."""
        width = getattr(self, "canvas_width", CANVAS_WIDTH)
        height = getattr(self, "canvas_height", CANVAS_HEIGHT)
        for x in range(0, width, GRID_SIZE):
            for y in range(0, height, GRID_SIZE):
                self.canvas.create_rectangle(x, y, x + 1, y + 1, fill="#e0e0e0", outline="", tags="grid")
        self.canvas.tag_lower("grid")

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if event.width <= 0 or event.height <= 0:
            return
        if event.width == getattr(self, "canvas_width", 0) and event.height == getattr(self, "canvas_height", 0):
            return
        self.canvas_width = event.width
        self.canvas_height = event.height
        self.canvas.delete("grid")
        self._draw_grid()

    def _add_component(self, comp_type: str) -> None:
        # Position near center
        canvas_width = int(getattr(self, "canvas_width", CANVAS_WIDTH))
        canvas_height = int(getattr(self, "canvas_height", CANVAS_HEIGHT))
        x = canvas_width // 2 + random.randint(-100, 100)
        y = canvas_height // 2 + random.randint(-100, 100)

        # Snap to grid
        x = round(x / GRID_SIZE) * GRID_SIZE
        y = round(y / GRID_SIZE) * GRID_SIZE

        self.component_type_counters[comp_type] = self.component_type_counters.get(comp_type, 0) + 1
        index = self.component_type_counters[comp_type]
        display_label = f"{COMPONENT_PROPS[comp_type]['label']} {index}"
        prefix = COMPONENT_PREFIX.get(comp_type, comp_type[:1].upper())
        code_label = f"{prefix}{index}"

        component = CircuitComponent(
            self.canvas,
            comp_type,
            x,
            y,
            self.component_counter,
            display_label,
            code_label,
            self._on_component_changed,
            self._on_component_removed,
        )
        self.components.append(component)
        self.component_counter += 1
        self._calculate_circuit()

    def _add_wire(self) -> None:
        canvas_width = int(getattr(self, "canvas_width", CANVAS_WIDTH))
        canvas_height = int(getattr(self, "canvas_height", CANVAS_HEIGHT))
        x = canvas_width // 2
        y = canvas_height // 2
        wire = CircuitWire(
            self.canvas,
            x,
            y,
            self._on_wire_changed,
            self._on_wire_removed,
            self._find_nearest_connector,
        )
        self.wires.append(wire)
        self._calculate_circuit()

    def _on_component_changed(self, _component: CircuitComponent) -> None:
        self._calculate_circuit()

    def _on_component_removed(self, component: CircuitComponent) -> None:
        if component in self.components:
            self.components.remove(component)
        for wire in self.wires[:]:
            wire.detach_component(component)
        self._calculate_circuit()

    def _on_wire_changed(self, _wire: CircuitWire) -> None:
        self._calculate_circuit()

    def _on_wire_removed(self, wire: CircuitWire) -> None:
        if wire in self.wires:
            self.wires.remove(wire)
        self._calculate_circuit()

    def _find_nearest_connector(
        self,
        x: float,
        y: float,
        exclude_wire: Optional[CircuitWire] = None,
        exclude_endpoint: Optional[str] = None,
        threshold: float = 28.0,
    ) -> tuple[Any | None, Optional[str], tuple[float, float]]:
        target: Any | None = None
        identifier: Optional[str] = None
        snap_point: tuple[float, float] = (x, y)
        best_distance = threshold

        for component in self.components:
            for side in ("left", "right", "top", "bottom"):
                px, py = component.anchor_point(side)
                dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
                if dist < best_distance:
                    best_distance = dist
                    target = component
                    identifier = side
                    snap_point = (px, py)

        for wire in self.wires:
            for ep in ("a", "b"):
                if wire is exclude_wire and ep == exclude_endpoint:
                    continue
                px, py = wire.positions.get(ep, (None, None))
                if px is None or py is None:
                    continue
                dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
                if dist < best_distance:
                    best_distance = dist
                    target = wire
                    identifier = ep
                    snap_point = (px, py)

        return target, identifier, snap_point

    def _expected_connections(self, component: CircuitComponent) -> int:
        if component.type in ("battery", "resistor", "bulb", "switch"):
            return 2
        return 2

    def _update_component_highlights(self, active_group: List[CircuitComponent] | None) -> None:
        active_ids = {comp.id for comp in active_group} if active_group else set()
        for comp in self.components:
            comp.set_active(comp.id in active_ids)

    def _update_analysis_panel(self, analysis: Dict[str, Any]) -> None:
        circuit_type = analysis.get("type", "Open")
        status_detail = analysis.get("status_detail", "Open Circuit")
        status_state = analysis.get("status", "Open")
        total_voltage = analysis.get("total_voltage", 0.0)
        total_current = analysis.get("total_current", 0.0)
        total_power = analysis.get("total_power", 0.0)
        total_resistance = analysis.get("total_resistance", 0.0)

        self.circuit_type_var.set(f"Type: {circuit_type}")
        self.circuit_status_var.set(f"Status: {status_state} – {status_detail}")

        show_metrics = (total_voltage > 0 or total_current > 0 or status_state == "Alert")
        if show_metrics:
            self.circuit_metrics_var.set(f"Voltage: {total_voltage:.2f} V | Current: {total_current:.3f} A")
        else:
            self.circuit_metrics_var.set("Voltage: — | Current: —")

        show_power = (total_power > 0 or total_resistance > 0 or status_state == "Alert")
        if show_power:
            if total_resistance > 0:
                resistance_text = f"{total_resistance:.2f} Ω"
            elif total_resistance == 0:
                resistance_text = "0.00 Ω"
            else:
                resistance_text = "∞"
            self.circuit_power_var.set(f"Power: {total_power:.3f} W | Resistance: {resistance_text}")
        else:
            self.circuit_power_var.set("Power: — | Resistance: —")

        total_components = analysis.get('component_count', 0)
        total_wires = analysis.get('wire_count', 0)
        active_components = analysis.get('active_component_count', 0)
        active_wires = analysis.get('active_wire_count', 0)
        if active_components or active_wires:
            counts_text = (
                f"Components: {total_components} (active {active_components}) | "
                f"Wires: {total_wires} (active {active_wires})"
            )
        else:
            counts_text = f"Components: {total_components} | Wires: {total_wires}"
        self.circuit_counts_var.set(counts_text)

        path_description = analysis.get("path_description", "—")
        if path_description and path_description != "—":
            self.circuit_path_var.set(f"Active path: {path_description}")
        else:
            self.circuit_path_var.set("Active path: —")

        issues = analysis.get("issues", [])
        if issues:
            unique_issues = list(dict.fromkeys(issues))
            display_lines = [f"• {issue}" for issue in unique_issues[:4]]
            if len(unique_issues) > 4:
                display_lines.append(f"• +{len(unique_issues) - 4} more")
            issues_text = "\n".join(display_lines)
        else:
            issues_text = "• No issues detected"
        self.circuit_issue_label.config(text=issues_text)

    def _classify_circuit(
        self,
        component_group: List[CircuitComponent],
        adjacency: Dict[CircuitComponent, set[CircuitComponent]],
        loads: List[CircuitComponent],
    ) -> str:
        if len(loads) <= 1:
            return "Single Load"

        branch_nodes = [comp for comp in component_group if len(adjacency.get(comp, set())) > 2]
        if branch_nodes:
            return "Parallel"

        return "Series"

    def _describe_active_path(
        self,
        component_group: List[CircuitComponent],
        adjacency: Dict[CircuitComponent, set[CircuitComponent]],
        batteries: List[CircuitComponent],
    ) -> str:
        if not component_group:
            return "—"

        start = batteries[0] if batteries else component_group[0]
        visited: Set[CircuitComponent] = set()
        queue: List[CircuitComponent] = [start]
        ordered: List[str] = []

        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            ordered.append(node.code_label)

            neighbors = sorted(
                (neighbor for neighbor in adjacency.get(node, set()) if neighbor in component_group),
                key=lambda comp: comp.id,
            )
            for neighbor in neighbors:
                if neighbor not in visited:
                    queue.append(neighbor)

        return " → ".join(ordered) if ordered else "—"

    def _compute_circuit_metrics(
        self,
        component_group: List[CircuitComponent],
        batteries: List[CircuitComponent],
        loads: List[CircuitComponent],
        circuit_type: str,
    ) -> tuple[Dict[str, Any], Dict[CircuitComponent, Dict[str, float]], List[str]]:
        summary: Dict[str, Any] = {
            "total_voltage": sum(component.get_voltage() for component in batteries),
            "total_resistance": 0.0,
            "total_current": 0.0,
            "total_power": 0.0,
            "status_override": "Closed",
            "status_detail_override": "✓ Circuit Complete & Powered",
        }
        per_component: Dict[CircuitComponent, Dict[str, float]] = {}
        issues: List[str] = []

        total_voltage = summary["total_voltage"]
        if total_voltage <= 0:
            issues.append("No active voltage source detected")
            summary["status_override"] = "Alert"
            summary["status_detail_override"] = "⚠️ Add an active battery"
            return summary, per_component, issues

        if not loads:
            issues.append("No resistive load connected to the circuit")
            summary["status_override"] = "Alert"
            summary["status_detail_override"] = "⚠️ Add a resistor or bulb"
            return summary, per_component, issues

        positive_loads = [comp for comp in loads if comp.get_resistance() > 0]
        zero_loads = [comp for comp in loads if comp.get_resistance() <= 0]
        if zero_loads:
            for comp in zero_loads:
                issues.append(f"{comp.display_label} has zero resistance (short path)")
                per_component[comp] = {"current": 0.0, "voltage": 0.0, "power": 0.0}
            summary["status_override"] = "Alert"
            summary["status_detail_override"] = "⚠️ Short circuit detected"
            return summary, per_component, issues

        if circuit_type == "Parallel" and len(positive_loads) >= 2:
            inverse_sum = sum(1.0 / comp.get_resistance() for comp in positive_loads if comp.get_resistance() > 0)
            if inverse_sum <= 0:
                issues.append("Unable to compute equivalent resistance for parallel network")
                summary["status_override"] = "Alert"
                summary["status_detail_override"] = "⚠️ Calculation error"
                return summary, per_component, issues
            equivalent_resistance = 1.0 / inverse_sum
            total_current = sum(total_voltage / comp.get_resistance() for comp in positive_loads)
            total_power = sum((total_voltage ** 2) / comp.get_resistance() for comp in positive_loads)

            summary["total_resistance"] = equivalent_resistance
            summary["total_current"] = total_current
            summary["total_power"] = total_power

            for comp in positive_loads:
                branch_current = total_voltage / comp.get_resistance()
                branch_power = (total_voltage ** 2) / comp.get_resistance()
                per_component[comp] = {
                    "current": branch_current,
                    "voltage": total_voltage,
                    "power": branch_power,
                }
        else:
            if circuit_type not in ("Series", "Single Load"):
                issues.append("Circuit contains mixed branches; using series approximation")

            equivalent_resistance = sum(comp.get_resistance() for comp in positive_loads)
            if equivalent_resistance <= 0:
                issues.append("Equivalent resistance is zero; cannot compute current")
                summary["status_override"] = "Alert"
                summary["status_detail_override"] = "⚠️ Calculation error"
                return summary, per_component, issues

            total_current = total_voltage / equivalent_resistance
            total_power = total_voltage * total_current

            summary["total_resistance"] = equivalent_resistance
            summary["total_current"] = total_current
            summary["total_power"] = total_power

            for comp in positive_loads:
                voltage_drop = total_current * comp.get_resistance()
                branch_power = total_current ** 2 * comp.get_resistance()
                per_component[comp] = {
                    "current": total_current,
                    "voltage": voltage_drop,
                    "power": branch_power,
                }

        for battery in batteries:
            per_component[battery] = {
                "current": summary["total_current"],
                "voltage": battery.get_voltage(),
                "power": battery.get_voltage() * summary["total_current"],
            }

        for component in component_group:
            per_component.setdefault(component, {
                "current": summary["total_current"],
                "voltage": 0.0,
                "power": 0.0,
            })

        return summary, per_component, issues

    def _calculate_circuit(self) -> None:
        analysis: Dict[str, Any] = {
            "component_count": len(self.components),
            "wire_count": len(self.wires),
            "active_component_count": 0,
            "active_wire_count": 0,
            "type": "Open",
            "status": "Open",
            "status_detail": "⚫ Open Circuit",
            "total_voltage": 0.0,
            "total_current": 0.0,
            "total_resistance": 0.0,
            "total_power": 0.0,
            "path_description": "—",
            "issues": [],
        }

        for component in self.components:
            component.reset_operating_metrics()

        adjacency: Dict[CircuitComponent, set[CircuitComponent]] = {component: set() for component in self.components}
        edges: List[tuple[CircuitWire, CircuitComponent, CircuitComponent]] = []
        endpoint_counts: Dict[CircuitComponent, int] = {component: 0 for component in self.components}

        for wire in self.wires:
            attached_components = wire.attached_components()
            if len(attached_components) == 2 and attached_components[0] is not attached_components[1]:
                comp_a, comp_b = attached_components
                adjacency.setdefault(comp_a, set()).add(comp_b)
                adjacency.setdefault(comp_b, set()).add(comp_a)
                edges.append((wire, comp_a, comp_b))
            for attachment in wire.attachments.values():
                if attachment:
                    comp, _ = attachment
                    endpoint_counts[comp] = endpoint_counts.get(comp, 0) + 1

            attachments_count = sum(1 for attachment in wire.attachments.values() if attachment)
            linked_count = sum(len(link) for link in wire.linked_endpoints.values())
            if attachments_count + linked_count == 0:
                analysis["issues"].append("Wire with no connections detected")
            elif attachments_count + linked_count == 1:
                analysis["issues"].append("Wire with a floating endpoint detected")

        for component in self.components:
            connected = endpoint_counts.get(component, 0)
            required = self._expected_connections(component)
            if connected < required:
                analysis["issues"].append(f"{component.display_label}: {connected}/{required} terminals connected")

        visited: Set[CircuitComponent] = set()
        active_group: List[CircuitComponent] | None = None
        active_wires: List[CircuitWire] | None = None
        group_batteries: List[CircuitComponent] = []
        group_loads: List[CircuitComponent] = []

        for component in self.components:
            if component in visited:
                continue

            stack = [component]
            visited.add(component)
            candidate_group: List[CircuitComponent] = []

            while stack:
                node = stack.pop()
                candidate_group.append(node)
                for neighbor in adjacency.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

            if len(candidate_group) < 2:
                continue

            batteries = [comp for comp in candidate_group if comp.type == "battery"]
            loads = [comp for comp in candidate_group if comp.type in ("resistor", "bulb")]

            if not batteries or not loads:
                continue

            if not all(endpoint_counts.get(comp, 0) >= self._expected_connections(comp) for comp in candidate_group):
                continue

            active_group = candidate_group
            group_batteries = batteries
            group_loads = loads
            active_wires = [
                wire
                for wire, a, b in edges
                if a in candidate_group and b in candidate_group
            ]
            break

        if active_group:
            self._update_component_highlights(active_group)
            for wire in self.wires:
                wire.set_active(active_wires is not None and wire in active_wires)

            circuit_type = self._classify_circuit(active_group, adjacency, group_loads)
            summary, component_metrics, metric_issues = self._compute_circuit_metrics(active_group, group_batteries, group_loads, circuit_type)

            analysis.update({
                "type": circuit_type,
                "status": summary.get("status_override", "Closed"),
                "status_detail": summary.get("status_detail_override", "✓ Circuit Complete & Powered"),
                "total_voltage": summary.get("total_voltage", 0.0),
                "total_current": summary.get("total_current", 0.0),
                "total_resistance": summary.get("total_resistance", 0.0),
                "total_power": summary.get("total_power", 0.0),
                "active_component_count": len(active_group),
                "active_wire_count": len(active_wires) if active_wires else 0,
                "path_description": self._describe_active_path(active_group, adjacency, group_batteries),
            })
            analysis["issues"].extend(metric_issues)

            if analysis["status"] == "Closed" and summary.get("status_detail_override") == "✓ Circuit Complete & Powered":
                analysis["status_detail"] = f"✓ {circuit_type} circuit powered"

            for component in active_group:
                metrics = component_metrics.get(component, {
                    "current": analysis["total_current"],
                    "voltage": 0.0,
                    "power": 0.0,
                })
                component.update_operating_metrics(
                    metrics.get("current", 0.0),
                    metrics.get("voltage", 0.0),
                    metrics.get("power", 0.0),
                )

            self.v_entry.config(state="normal")
            self.i_entry.config(state="normal")
            self.r_entry.config(state="normal")
            self.p_entry.config(state="normal")

            self.v_entry.delete(0, tk.END)
            self.v_entry.insert(0, f"{analysis['total_voltage']:.3f} V")

            self.i_entry.delete(0, tk.END)
            self.i_entry.insert(0, f"{analysis['total_current']:.4f} A")

            if analysis["total_resistance"] > 0:
                resistance_display = f"{analysis['total_resistance']:.2f} Ω"
            elif analysis["total_resistance"] == 0:
                resistance_display = "0.00 Ω"
            else:
                resistance_display = "∞"
            self.r_entry.delete(0, tk.END)
            self.r_entry.insert(0, resistance_display)

            self.p_entry.delete(0, tk.END)
            self.p_entry.insert(0, f"{analysis['total_power']:.3f} W")

            self.v_entry.config(state="readonly")
            self.i_entry.config(state="readonly")
            self.r_entry.config(state="readonly")
            self.p_entry.config(state="readonly")

            status_color = "#facc15" if analysis["status"] == "Alert" else "#10b981"
            self.status.set(analysis["status_detail"])
            self.status_label.config(fg=status_color)
        else:
            self._update_component_highlights(None)
            for wire in self.wires:
                wire.set_active(False)

            if not self.components:
                self._reset_values()
            else:
                has_battery = any(comp.type == "battery" and comp.get_voltage() > 0 for comp in self.components)
                has_load = any(comp.type in ("resistor", "bulb") and comp.get_resistance() > 0 for comp in self.components)

                if has_battery and not has_load:
                    message = "⚠️ Add a resistor or bulb to complete the circuit"
                    color = "#d97706"
                elif has_load and not has_battery:
                    message = "⚠️ Add a battery to power the circuit"
                    color = "#d97706"
                elif len(self.components) >= 2:
                    message = "⚠️ Connect all terminals with wires to close the loop"
                    color = "#d97706"
                else:
                    message = "⚫ Open Circuit"
                    color = "#9ca3af"
                analysis["status_detail"] = message
                if message.startswith("⚠️"):
                    analysis["status"] = "Alert"
                    analysis["issues"].append(message.replace("⚠️ ", "").strip())
                else:
                    analysis["status"] = "Open"
                self._reset_values(message, color)

        analysis["issues"] = list(dict.fromkeys(analysis["issues"]))
        self._update_analysis_panel(analysis)

    def _reset_values(self, status_text: str = "⚫ Open Circuit", status_color: str = "#9ca3af") -> None:
        self.v_entry.config(state="normal")
        self.i_entry.config(state="normal")
        self.r_entry.config(state="normal")
        self.p_entry.config(state="normal")

        self.v_entry.delete(0, tk.END)
        self.v_entry.insert(0, "—")

        self.i_entry.delete(0, tk.END)
        self.i_entry.insert(0, "—")

        self.r_entry.delete(0, tk.END)
        self.r_entry.insert(0, "—")
        
        self.p_entry.delete(0, tk.END)
        self.p_entry.insert(0, "—")

        self.v_entry.config(state="readonly")
        self.i_entry.config(state="readonly")
        self.r_entry.config(state="readonly")
        self.p_entry.config(state="readonly")

        self.status.set(status_text)
        self.status_label.config(fg=status_color)

    def _reset_circuit(self) -> None:
        for comp in self.components[:]:
            comp.remove()
        self.components.clear()
        self.component_counter = 0
        self.component_type_counters.clear()
        self._reset_values()
        self.canvas.delete("all")
        self._update_component_highlights(None)
        for wire in self.wires[:]:
            wire.remove()
        self.wires.clear()
        self._draw_grid()

        self._update_analysis_panel({
            "component_count": 0,
            "wire_count": 0,
            "active_component_count": 0,
            "active_wire_count": 0,
            "type": "Open",
            "status": "Open",
            "status_detail": "⚫ Open Circuit",
            "total_voltage": 0.0,
            "total_current": 0.0,
            "total_resistance": 0.0,
            "total_power": 0.0,
            "issues": [],
        })


# ======================
# Entry Point
# ======================

if __name__ == "__main__":
    root = tk.Tk()
    app = OhmsLawApp(root)
    root.mainloop()