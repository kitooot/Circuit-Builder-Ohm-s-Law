from __future__ import annotations

import math
import time
import tkinter as tk
from tkinter import simpledialog
from typing import Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .constants import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COMPONENT_ICONS,
    COMPONENT_PROPS,
    GRID_SIZE,
)
from .themes import Theme, get_theme

if TYPE_CHECKING:
    from .wires import CircuitWire


DRAG_THROTTLE_MS = 8
SWITCH_TYPES = {"switch", "switch_spst", "switch_spdt"}


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
        theme: Theme | None = None,
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
        self.theme = theme or get_theme("light")
        self.on_request_duplicate: Optional[Callable[["CircuitComponent"], None]] = None

        props = COMPONENT_PROPS.get(comp_type, {})
        self.host_bg = props.get("color", "#f1f5f9")
        self.badge_bg = props.get("badge_bg", "#0f172a")
        self.badge_fg = props.get("badge_fg", "#f8fafc")
        self.active_body = props.get("active_body", self.host_bg)

        self.base_width = 160
        self.base_height = 120

        self.voltage_value = float(props.get("voltage", 0.0))
        self.resistance_value = float(props.get("resistance", 0.0))
        self.capacitance = float(props.get("capacitance", 0.0))
        self.forward_voltage = float(props.get("forward_voltage", 0.0))
        self.operating_current = 0.0
        self.operating_voltage = 0.0
        self.operating_power = 0.0
        self.active = False
        self.locked = False
        self.orientation = "horizontal"
        self.switch_closed = True
        self._context_menu: Optional[tk.Menu] = None
        self._drag_last_ts = 0.0

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
        self._build_context_menu()
        self.apply_theme(self.theme)

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
            widget.bind("<Button-3>", self._on_right_click, add="+")

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
        if self.is_switch():
            state = "Closed" if self.switch_closed else "Open"
            return f"Switch ({state})"
        return COMPONENT_PROPS[self.type]["label"]

    def _update_detail_text(self) -> None:
        if self.detail_label:
            self.detail_label.configure(text=self._component_detail_text())

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        bg = self.host_bg if not self.locked else theme.surface
        fg_primary = theme.text_primary
        fg_secondary = theme.text_secondary
        badge_bg = self.badge_bg
        badge_fg = self.badge_fg
        if self.active:
            badge_bg = theme.accent
            badge_fg = theme.accent_text
        if self.frame:
            self.frame.configure(bg=bg, highlightbackground=theme.border)
        if self.toolbar_frame:
            self.toolbar_frame.configure(bg=bg)
        if self.body_frame:
            self.body_frame.configure(bg=bg)
        if self.code_badge:
            self.code_badge.configure(bg=badge_bg, fg=badge_fg)
        if self.name_label:
            self.name_label.configure(bg=bg, fg=fg_primary)
        if self.detail_label:
            self.detail_label.configure(bg=bg, fg=fg_secondary)
        if self.visual_canvas:
            self.visual_canvas.configure(bg=bg)
        for dot in self.terminal_canvases:
            dot.configure(bg=bg)
        self._draw_visual_representation()

    def _build_context_menu(self) -> None:
        if self._context_menu:
            self._context_menu.destroy()
        menu = tk.Menu(self.frame, tearoff=False)
        menu.add_command(label="Rotate", command=self.rotate)
        if self.is_switch():
            menu.add_command(label="Toggle Switch", command=self.toggle_switch)
        else:
            menu.add_command(label="Edit Value", command=lambda: self._on_double_click(None))
        menu.add_command(label="Duplicate", command=self.duplicate)
        menu.add_separator()
        lock_label = "Unlock" if self.locked else "Lock Position"
        menu.add_command(label=lock_label, command=self.toggle_lock)
        menu.add_separator()
        menu.add_command(label="Delete", command=self.remove)
        self._context_menu = menu

    def _on_right_click(self, event: tk.Event) -> None:
        if self._context_menu is None:
            self._build_context_menu()
        if self._context_menu:
            try:
                self._context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._context_menu.grab_release()

    def toggle_lock(self) -> None:
        self.locked = not self.locked
        self._build_context_menu()
        self.apply_theme(self.theme)

    def rotate(self) -> None:
        self.orientation = "vertical" if self.orientation == "horizontal" else "horizontal"
        self._draw_terminal_indicators()
        self._notify_attached_wires()
        self.apply_theme(self.theme)

    def duplicate(self) -> None:
        if self.on_request_duplicate:
            self.on_request_duplicate(self)

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

    @staticmethod
    def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    @staticmethod
    def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
        return "#" + "".join(f"{channel:02x}" for channel in rgb)

    def _mix_color(self, start_hex: str, end_hex: str, ratio: float) -> str:
        ratio = max(0.0, min(ratio, 1.0))
        start_rgb = self._hex_to_rgb(start_hex)
        end_rgb = self._hex_to_rgb(end_hex)
        blended = tuple(
            int(start_channel + (end_channel - start_channel) * ratio)
            for start_channel, end_channel in zip(start_rgb, end_rgb)
        )
        return self._rgb_to_hex(blended)

    def _visual_base_dimensions(self) -> tuple[int, int]:
        return 120, 80

    def _visual_dimensions(self) -> tuple[int, int]:
        width, height = self._visual_base_dimensions()
        if self.orientation == "horizontal":
            return width, height
        return height, width

    def _transform_point(self, x: float, y: float) -> tuple[float, float]:
        if self.orientation == "horizontal":
            return x, y
        base_width, base_height = self._visual_base_dimensions()
        vert_width, vert_height = base_height, base_width
        cx_base, cy_base = base_width / 2.0, base_height / 2.0
        dx = x - cx_base
        dy = y - cy_base
        x_rot = -dy
        y_rot = dx
        cx_vert, cy_vert = vert_width / 2.0, vert_height / 2.0
        return cx_vert + x_rot, cy_vert + y_rot

    def _transform_coords(self, coords: List[float]) -> List[float]:
        transformed: List[float] = []
        for x, y in zip(coords[0::2], coords[1::2]):
            tx, ty = self._transform_point(x, y)
            transformed.extend([tx, ty])
        return transformed

    def _transform_box(self, box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = box
        corners = [
            self._transform_point(x1, y1),
            self._transform_point(x1, y2),
            self._transform_point(x2, y1),
            self._transform_point(x2, y2),
        ]
        xs = [pt[0] for pt in corners]
        ys = [pt[1] for pt in corners]
        return min(xs), min(ys), max(xs), max(ys)

    def _transform_angle(self, angle: float) -> float:
        if self.orientation == "horizontal":
            return angle
        return (angle + 90.0) % 360.0

    def _vc_line(self, coords: List[float], **kwargs: object) -> None:
        if not self.visual_canvas:
            return
        transformed = self._transform_coords(coords)
        self.visual_canvas.create_line(*transformed, **kwargs)

    def _vc_rectangle(self, box: tuple[float, float, float, float], **kwargs: object) -> None:
        if not self.visual_canvas:
            return
        transformed = self._transform_box(box)
        self.visual_canvas.create_rectangle(*transformed, **kwargs)

    def _vc_oval(self, box: tuple[float, float, float, float], **kwargs: object) -> None:
        if not self.visual_canvas:
            return
        transformed = self._transform_box(box)
        self.visual_canvas.create_oval(*transformed, **kwargs)

    def _vc_arc(self, box: tuple[float, float, float, float], start: float, extent: float, **kwargs: object) -> None:
        if not self.visual_canvas:
            return
        transformed_box = self._transform_box(box)
        start_angle = self._transform_angle(start)
        self.visual_canvas.create_arc(*transformed_box, start=start_angle, extent=extent, **kwargs)

    def _vc_polygon(self, coords: List[float], **kwargs: object) -> None:
        if not self.visual_canvas:
            return
        transformed = self._transform_coords(coords)
        self.visual_canvas.create_polygon(*transformed, **kwargs)

    def _vc_text(self, x: float, y: float, **kwargs: object) -> None:
        if not self.visual_canvas:
            return
        tx, ty = self._transform_point(x, y)
        self.visual_canvas.create_text(tx, ty, **kwargs)

    def _draw_visual_representation(self) -> None:
        if not self.visual_canvas:
            return
        self.visual_canvas.delete("all")
        width, height = self._visual_dimensions()
        self.visual_canvas.configure(width=width, height=height)
        active = self.active
        if self.type == "battery":
            self._draw_battery_visual(active)
        elif self.type == "resistor":
            self._draw_resistor_visual(active)
        elif self.type == "bulb":
            self._draw_bulb_visual(active)
        elif self.type in {"switch", "switch_spst", "switch_spdt"}:
            self._draw_switch_visual(active)
        elif self.type == "led":
            self._draw_led_visual(active)
        elif self.type == "capacitor":
            self._draw_capacitor_visual(active)
        elif self.type == "diode":
            self._draw_diode_visual(active)
        elif self.type in {"ammeter", "voltmeter"}:
            self._draw_meter_visual(active)
        elif self.type == "ground":
            self._draw_ground_visual(active)
        else:
            self._draw_wire_visual(active)

    def _draw_battery_visual(self, active: bool) -> None:
        ratio = self._intensity_ratio() if active else 0.0
        casing_fill = self._mix_color("#fcd34d", "#f59e0b", ratio)
        cell_fill = self._mix_color("#fda4af", "#f87171", ratio)
        lead_color = self._mix_color("#64748b", "#047857", ratio)
        text_color = "#1f2937"

        self._vc_line([6, 40, 26, 40], fill=lead_color, width=4, capstyle=tk.ROUND)
        self._vc_line([84, 40, 104, 40], fill=lead_color, width=4, capstyle=tk.ROUND)
        self._vc_rectangle((26, 18, 52, 62), fill=cell_fill, outline="#0f172a", width=2)
        self._vc_rectangle((52, 22, 84, 58), fill=casing_fill, outline="#0f172a", width=2)
        self._vc_text(20, 24, text="+", font=("Arial", 12, "bold"), fill=text_color)
        self._vc_text(96, 24, text="-", font=("Arial", 12, "bold"), fill=text_color)
        self._vc_text(55, 70, text=f"{self.voltage_value:.1f} V", font=("Arial", 10, "bold"), fill=text_color)

    def _draw_resistor_visual(self, active: bool) -> None:
        ratio = self._intensity_ratio() if active else 0.0
        lead_color = self._mix_color("#475569", "#0f766e", ratio)
        resistor_color = self._mix_color("#fbbf24", "#f97316", ratio)
        text_color = "#0f172a"

        self._vc_line([6, 40, 26, 40], fill=lead_color, width=4, capstyle=tk.ROUND)
        zigzag = [26, 40, 34, 28, 42, 52, 50, 28, 58, 52, 66, 28, 74, 40]
        self._vc_line(zigzag, fill=resistor_color, width=4, joinstyle=tk.ROUND)
        self._vc_line([74, 40, 104, 40], fill=lead_color, width=4, capstyle=tk.ROUND)
        self._vc_text(55, 66, text=f"{self.resistance_value:.1f} Ω", font=("Arial", 10, "bold"), fill=text_color)

    def _draw_bulb_visual(self, active: bool) -> None:
        ratio = self._intensity_ratio() if active else 0.0
        glow_fill = self._mix_color("#f3f4f6", "#fde68a", ratio)
        outline_color = self._mix_color("#cbd5f5", "#facc15", ratio)
        filament_color = self._mix_color("#64748b", "#b45309", ratio)
        base_color = "#475569"

        self._vc_oval((18, 8, 92, 72), fill=glow_fill, outline=outline_color, width=3)
        self._vc_line([38, 48, 72, 48], fill=filament_color, width=2)
        self._vc_line([55, 48, 55, 66], fill=filament_color, width=3)
        self._vc_arc((34, 30, 76, 66), start=225, extent=90, style=tk.ARC, outline=filament_color, width=2)
        self._vc_arc((34, 30, 76, 66), start=45, extent=90, style=tk.ARC, outline=filament_color, width=2)
        self._vc_rectangle((44, 66, 66, 76), fill=base_color, outline=base_color)
        self._vc_rectangle((48, 76, 62, 82), fill=base_color, outline=base_color)

    def _draw_switch_visual(self, active: bool) -> None:
        closed = self.is_switch_closed()
        highlight_ratio = 1.0 if active and closed else (0.0 if not closed else 0.4)
        lead_color = self._mix_color("#64748b", "#2563eb", highlight_ratio)
        contact_color = "#059669" if closed else "#475569"
        self._vc_line([6, 40, 46, 40], fill=lead_color, width=4, capstyle=tk.ROUND)
        self._vc_oval((42, 36, 50, 44), fill="#e2e8f0", outline=contact_color, width=2)
        if closed:
            self._vc_line([46, 40, 104, 40], fill=lead_color, width=4, capstyle=tk.ROUND)
            self._vc_text(86, 60, text="ON", font=("Arial", 8, "bold"), fill=contact_color)
        else:
            self._vc_line([46, 40, 96, 22], fill=lead_color, width=4, capstyle=tk.ROUND)
            self._vc_oval((96, 20, 104, 28), fill="#e2e8f0", outline=contact_color, width=2)
            self._vc_line([96, 28, 104, 34], fill=lead_color, width=4, capstyle=tk.ROUND)
            self._vc_text(86, 60, text="OFF", font=("Arial", 8, "bold"), fill="#b91c1c")

    def _draw_led_visual(self, active: bool) -> None:
        ratio = min(1.0, self.operating_current / 0.02) if active else 0.0
        body_color = self._mix_color("#9f1239", "#dc2626", ratio)
        glow_color = self._mix_color("#fecdd3", "#fda4af", ratio)
        self._vc_oval((34, 18, 86, 70), fill=glow_color, outline=body_color, width=3)
        self._vc_polygon([20, 40, 52, 24, 52, 56], fill=body_color, outline=body_color)
        self._vc_line([86, 40, 104, 40], fill="#374151", width=4)
        label = f"{self.operating_current * 1000:.1f} mA" if active else "LED"
        self._vc_text(60, 82, text=label, font=("Arial", 9, "bold"), fill="#1f2937")

    def _draw_capacitor_visual(self, active: bool) -> None:
        plate_color = "#0ea5e9" if active else "#38bdf8"
        self._vc_line([6, 40, 42, 40], fill="#475569", width=3)
        self._vc_line([42, 20, 42, 60], fill=plate_color, width=4)
        self._vc_line([70, 20, 70, 60], fill=plate_color, width=4)
        self._vc_line([70, 40, 104, 40], fill="#475569", width=3)
        self._vc_text(56, 68, text=f"{self.capacitance * 1e6:.0f} μF", font=("Arial", 9, "bold"), fill="#0f172a")

    def _draw_diode_visual(self, active: bool) -> None:
        body_color = "#7f1d1d" if active else "#9ca3af"
        self._vc_line([6, 40, 36, 40], fill="#475569", width=3)
        self._vc_polygon([36, 28, 64, 40, 36, 52], fill=body_color, outline=body_color)
        self._vc_line([64, 24, 64, 56], fill=body_color, width=3)
        self._vc_line([64, 40, 104, 40], fill="#475569", width=3)
        self._vc_text(55, 68, text=f"{self.forward_voltage:.1f} V", font=("Arial", 9, "bold"), fill="#0f172a")

    def _draw_meter_visual(self, active: bool) -> None:
        ratio = self._intensity_ratio() if active else 0.0
        shell_color = self._mix_color("#e5e7eb", "#22c55e", ratio)
        self._vc_rectangle((24, 18, 96, 72), fill=shell_color, outline="#111827", width=2)
        label = "A" if self.type == "ammeter" else "V"
        needle_angle = min(60, max(-60, (self.operating_current if label == "A" else self.operating_voltage) * 10))
        center_x, center_y = 60, 50
        length = 20
        angle_rad = math.radians(needle_angle)
        end_x = center_x + length * math.cos(angle_rad)
        end_y = center_y - length * math.sin(angle_rad)
        self._vc_arc((32, 32, 88, 88), start=210, extent=120, style=tk.ARC, outline="#1f2937", width=2)
        self._vc_line([center_x, center_y, end_x, end_y], fill="#1f2937", width=3)
        self._vc_text(center_x, 30, text=label, font=("Arial", 12, "bold"), fill="#1f2937")

    def _draw_ground_visual(self, active: bool) -> None:
        color = "#16a34a" if active else "#475569"
        self._vc_line([56, 20, 56, 54], fill=color, width=4)
        self._vc_line([44, 54, 68, 54], fill=color, width=4)
        self._vc_line([48, 62, 64, 62], fill=color, width=4)
        self._vc_line([52, 70, 60, 70], fill=color, width=4)

    def _draw_wire_visual(self, active: bool) -> None:
        ratio = self._intensity_ratio() if active else 0.0
        wire_color = self._mix_color("#64748b", "#10b981", ratio)
        self._vc_line([8, 40, 102, 40], fill=wire_color, width=5, capstyle=tk.ROUND)

    def _on_press(self, event: tk.Event) -> None:
        if not self.frame or self.locked:
            return
        self.dragging = True
        if self.window_id is not None:
            self.canvas.tag_raise(self.window_id)
        self.pointer_offset_x = event.x_root - self.frame.winfo_rootx()
        self.pointer_offset_y = event.y_root - self.frame.winfo_rooty()

    def _on_drag(self, event: tk.Event) -> None:
        if not self.dragging or not self.frame or self.window_id is None or self.locked:
            return
        now = time.time() * 1000
        if now - self._drag_last_ts < DRAG_THROTTLE_MS:
            return
        self._drag_last_ts = now

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
        elif self.is_switch():
            self.toggle_switch()
            return
        else:
            return

        self._update_detail_text()
        self._draw_visual_representation()
        if self.on_change:
            self.on_change(self)

    def toggle_switch(self) -> None:
        if not self.is_switch():
            return
        self.switch_closed = not self.switch_closed
        self._update_detail_text()
        self._draw_visual_representation()
        if self.on_change:
            self.on_change(self)

    def is_switch(self) -> bool:
        return self.type in SWITCH_TYPES

    def is_switch_closed(self) -> bool:
        return not self.is_switch() or self.switch_closed

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
        if self.orientation == "vertical":
            if side == "left":
                return float(self.x + width / 2), float(self.y)
            if side == "right":
                return float(self.x + width / 2), float(self.y + height)
            if side == "top":
                return float(self.x), float(cy)
            if side == "bottom":
                return float(self.x + width), float(cy)
        else:
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
        border_color = self.theme.accent if active else self.host_bg
        thickness = 3 if active else 0
        self.frame.configure(highlightbackground=border_color, highlightcolor=border_color, highlightthickness=thickness)
        connector_color = self.theme.accent if active else "#7c3aed"
        for dot in self.terminal_canvases:
            dot.configure(bg=self.host_bg)
            for item in dot.find_withtag("terminal"):
                dot.itemconfigure(item, fill=connector_color, outline=connector_color)

        self.apply_theme(self.theme)
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
        for dot in self.terminal_canvases:
            dot.destroy()
        self.terminal_canvases.clear()


__all__ = ["CircuitComponent"]
