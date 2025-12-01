from __future__ import annotations

import random
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple
from .analysis import analyze_circuit
from .components import CircuitComponent
from .constants import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COMPONENT_ICONS,
    COMPONENT_PREFIX,
    GRID_SIZE,
)
from .wires import CircuitWire


class OhmsLawApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ohm's Law & Circuit Builder")
        self.root.geometry("1200x700")
        self.root.configure(bg="#f0f0f0")
        self.root.minsize(960, 600)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.fullscreen = False
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._exit_fullscreen)

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
        self.status_label: Optional[tk.Label] = None
        self.functions_display: Optional[tk.Label] = None
        self.latest_analysis: Dict[str, Any] = {}
        self._auto_snap_guard = False

        self._create_widgets()
        self._draw_grid()

    # ------------------------------------------------------------------
    # UI Construction & Layout
    # ------------------------------------------------------------------
    def _create_widgets(self) -> None:
        self._build_header()
        main_frame = self._build_main_frame()

        left_panel = self._build_left_panel(main_frame)
        self._populate_component_palette(left_panel)
        help_frame, help_title, help_hint, tip_labels = self._build_help_section(left_panel)
        self._bind_help_events(help_frame, help_title, help_hint, tip_labels)

        self._build_canvas_panel(main_frame)
        analysis_frame, analysis_title = self._build_right_panel(main_frame)
        self._bind_analysis_events(analysis_frame, analysis_title)

        self._initialize_analysis_state()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg="#ffffff", relief=tk.RAISED, bd=1)
        header.pack(side=tk.TOP, fill=tk.X, padx=0, pady=0)

        tk.Label(
            header,
            text="⚡ Interactive Circuit Builder",
            font=("Arial", 14, "bold"),
            bg="#ffffff",
            fg="#1f2937",
        ).pack(pady=(12, 2))

        tk.Label(
            header,
            text="Drag components, connect with wires, and watch Ohm's Law calculations update in real-time",
            font=("Arial", 10),
            bg="#ffffff",
            fg="#6b7280",
        ).pack(pady=(0, 12))

    def _build_main_frame(self) -> tk.Frame:
        main_frame = tk.Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=0, minsize=240)
        main_frame.grid_columnconfigure(1, weight=4, minsize=400)
        main_frame.grid_columnconfigure(2, weight=1, minsize=280)
        return main_frame

    def _build_left_panel(self, main_frame: tk.Frame) -> tk.Frame:
        left_panel = tk.Frame(main_frame, bg="#ffffff", relief=tk.SUNKEN, bd=1)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=5)
        left_panel.grid_propagate(True)
        return left_panel

    def _populate_component_palette(self, left_panel: tk.Frame) -> None:
        tk.Label(left_panel, text="Component Palette", font=("Arial", 12, "bold"), bg="#ffffff").pack(pady=(10, 5))

        palette = [
            ("battery", "Battery"),
            ("resistor", "Resistor"),
            ("bulb", "Bulb"),
            ("switch", "Switch"),
            ("wire", "Wire"),
        ]

        for comp_type, label in palette:
            tile = tk.Frame(
                left_panel,
                bg="#f8fafc",
                bd=1,
                relief=tk.RIDGE,
                padx=6,
                pady=6,
                highlightthickness=1,
                highlightbackground="#cbd5f5",
                cursor="hand2",
            )
            tile.pack(pady=5, padx=10, fill=tk.X)

            icon_label = tk.Label(
                tile,
                text=COMPONENT_ICONS.get(comp_type, "❓"),
                font=("Arial", 20),
                bg="#f8fafc",
            )
            icon_label.pack()

            text_label = tk.Label(
                tile,
                text=label,
                font=("Arial", 9),
                bg="#f8fafc",
                fg="#334155",
            )
            text_label.pack()
            for widget in (icon_label, text_label):
                widget.configure(cursor="hand2")

            def make_handler(item_type: str):
                if item_type == "wire":
                    return lambda _event=None: self._add_wire()
                return lambda _event=None: self._add_component(item_type)

            handler = make_handler(comp_type)
            tile.bind("<Button-1>", handler)
            icon_label.bind("<Button-1>", handler)
            text_label.bind("<Button-1>", handler)

            tile.bind("<Enter>", lambda _event, t=tile: self._set_palette_tile_state(t, True))
            tile.bind("<Leave>", lambda _event, t=tile: self._set_palette_tile_state(t, False))
            icon_label.bind("<Enter>", lambda _event, t=tile: self._set_palette_tile_state(t, True))
            icon_label.bind("<Leave>", lambda _event, t=tile: self._set_palette_tile_state(t, False))
            text_label.bind("<Enter>", lambda _event, t=tile: self._set_palette_tile_state(t, True))
            text_label.bind("<Leave>", lambda _event, t=tile: self._set_palette_tile_state(t, False))

    def _build_help_section(
        self, left_panel: tk.Frame
    ) -> Tuple[tk.Frame, tk.Label, tk.Label, List[tk.Label]]:
        help_frame = tk.Frame(left_panel, bg="#f0f9ff", relief=tk.RIDGE, bd=1, cursor="hand2")
        help_frame.pack(side=tk.BOTTOM, pady=10, padx=8, fill=tk.X)
        self.help_frame = help_frame

        help_title = tk.Label(
            help_frame,
            text="💡 Quick Tips",
            font=("Arial", 9, "bold"),
            bg="#f0f9ff",
            fg="#1e40af",
            cursor="hand2",
        )
        help_title.pack(pady=(6, 4))

        tip_labels: List[tk.Label] = []
        for tip_text in self._feature_lines():
            label = tk.Label(
                help_frame,
                text=f"• {tip_text}",
                font=("Arial", 8),
                bg="#f0f9ff",
                fg="#475569",
                anchor="w",
                justify=tk.LEFT,
                wraplength=210,
                cursor="hand2",
            )
            label.pack(anchor="w", padx=8, pady=1)
            tip_labels.append(label)

        help_hint = tk.Label(
            help_frame,
            text="Double-click for full guide",
            font=("Arial", 7, "italic"),
            bg="#f0f9ff",
            fg="#1e40af",
            cursor="hand2",
        )
        help_hint.pack(pady=4)

        return help_frame, help_title, help_hint, tip_labels

    def _bind_help_events(
        self,
        help_frame: tk.Frame,
        help_title: tk.Label,
        help_hint: tk.Label,
        tip_labels: List[tk.Label],
    ) -> None:
        help_frame.bind("<Double-1>", self._show_tips_dialog)
        help_title.bind("<Double-1>", self._show_tips_dialog)
        help_hint.bind("<Double-1>", self._show_tips_dialog)
        for label in tip_labels:
            label.bind("<Double-1>", self._show_tips_dialog)

    def _build_canvas_panel(self, main_frame: tk.Frame) -> None:
        canvas_frame = tk.Frame(main_frame, bg="#f0f0f0")
        canvas_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        canvas_frame.grid_rowconfigure(1, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        canvas_header = tk.Frame(canvas_frame, bg="#f0f0f0")
        canvas_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        tk.Label(
            canvas_header,
            text="Circuit Canvas",
            font=("Arial", 12, "bold"),
            bg="#f0f0f0",
            fg="#1f2937",
        ).pack(side=tk.LEFT)

        controls_frame = tk.Frame(canvas_header, bg="#f0f0f0")
        controls_frame.pack(side=tk.RIGHT)

        reset_button = tk.Button(
            controls_frame,
            text="♻ Reset Circuit",
            font=("Arial", 10, "bold"),
            bg="#dc2626",
            fg="white",
            width=12,
            command=self._reset_circuit,
            relief=tk.RAISED,
            bd=2,
        )
        reset_button.pack(side=tk.RIGHT, padx=(5, 0))

        self.status_label = tk.Label(
            controls_frame,
            textvariable=self.status,
            font=("Arial", 10, "bold"),
            bg="#f0f0f0",
            fg="#9ca3af",
        )
        self.status_label.pack(side=tk.RIGHT, padx=(0, 10))

        self.canvas = tk.Canvas(
            canvas_frame,
            bg="white",
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            relief=tk.SUNKEN,
            bd=2,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas_width = CANVAS_WIDTH
        self.canvas_height = CANVAS_HEIGHT
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _build_right_panel(self, main_frame: tk.Frame) -> Tuple[tk.Frame, tk.Label]:
        right_panel = tk.Frame(main_frame, bg="#ffffff", relief=tk.SUNKEN, bd=1)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(2, 5), pady=5)
        right_panel.grid_propagate(True)

        tk.Label(
            right_panel,
            text="Ohm's Law Calculator",
            font=("Arial", 12, "bold"),
            bg="#ffffff",
        ).pack(pady=(10, 5))

        self._build_formula_section(right_panel)
        self._build_calculator_entries(right_panel)
        self._build_info_section(right_panel)

        analysis_frame, analysis_title = self._build_analysis_panel(right_panel)
        return analysis_frame, analysis_title

    def _build_formula_section(self, right_panel: tk.Frame) -> None:
        formula_frame = tk.Frame(right_panel, bg="white", relief=tk.RAISED, bd=1)
        formula_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(
            formula_frame,
            text="V = I × R",
            font=("Arial", 14, "bold"),
            bg="white",
            fg="#333333",
        ).pack(pady=10)

    def _build_calculator_entries(self, right_panel: tk.Frame) -> None:
        v_frame = tk.Frame(right_panel, bg="#ffffff")
        v_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(v_frame, text="Voltage (V)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.v_entry = tk.Entry(v_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.v_entry.pack(fill=tk.X, padx=5, pady=2)

        i_frame = tk.Frame(right_panel, bg="#ffffff")
        i_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(i_frame, text="Current (I)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.i_entry = tk.Entry(i_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.i_entry.pack(fill=tk.X, padx=5, pady=2)

        r_frame = tk.Frame(right_panel, bg="#ffffff")
        r_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(r_frame, text="Resistance (R)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.r_entry = tk.Entry(r_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.r_entry.pack(fill=tk.X, padx=5, pady=2)

        power_frame = tk.Frame(right_panel, bg="#ffffff")
        power_frame.pack(padx=10, pady=5, fill=tk.X)
        tk.Label(power_frame, text="Power (P)", font=("Arial", 10), bg="#ffffff", fg="#666666").pack(anchor="w", padx=5)
        self.p_entry = tk.Entry(power_frame, font=("Arial", 12), justify="center", state="readonly", readonlybackground="white")
        self.p_entry.pack(fill=tk.X, padx=5, pady=2)

    def _build_info_section(self, right_panel: tk.Frame) -> None:
        info_frame = tk.Frame(right_panel, bg="#ecfdf5", relief=tk.RAISED, bd=1)
        info_frame.pack(padx=10, pady=10, fill=tk.X)
        tk.Label(
            info_frame,
            text="ℹ️ Build Your Circuit",
            font=("Arial", 9, "bold"),
            bg="#ecfdf5",
            fg="#047857",
        ).pack(padx=5, pady=(5, 2))
        tk.Label(
            info_frame,
            text="Add battery + load (resistor/bulb), then wire all terminals to form a complete loop. Values calculate automatically!",
            font=("Arial", 8),
            bg="#ecfdf5",
            fg="#065f46",
            wraplength=220,
            justify=tk.LEFT,
        ).pack(padx=8, pady=(0, 5))

    def _build_analysis_panel(self, right_panel: tk.Frame) -> Tuple[tk.Frame, tk.Label]:
        analysis_frame = tk.Frame(right_panel, bg="#f8fafc", relief=tk.RIDGE, bd=1, cursor="hand2")
        analysis_frame.pack(padx=10, pady=(0, 10), fill=tk.X)
        self.analysis_frame = analysis_frame

        analysis_title = tk.Label(
            analysis_frame,
            text="📊 Circuit Insight",
            font=("Arial", 10, "bold"),
            bg="#f8fafc",
            fg="#1d4ed8",
            cursor="hand2",
        )
        analysis_title.pack(anchor="w", padx=8, pady=(6, 2))

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_type_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937",
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_status_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937",
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_metrics_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937",
        ).pack(anchor="w", padx=12, pady=(4, 1))

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_power_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937",
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_counts_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937",
        ).pack(anchor="w", padx=12, pady=(4, 1))

        tk.Label(
            analysis_frame,
            textvariable=self.circuit_path_var,
            font=("Arial", 9),
            bg="#f8fafc",
            fg="#1f2937",
        ).pack(anchor="w", padx=12, pady=1)

        tk.Label(
            analysis_frame,
            text="Issues & Tips",
            font=("Arial", 9, "bold"),
            bg="#f8fafc",
            fg="#475569",
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

        return analysis_frame, analysis_title

    def _bind_analysis_events(self, analysis_frame: tk.Frame, analysis_title: tk.Label) -> None:
        analysis_frame.bind("<Double-1>", self._show_insight_info)
        analysis_title.bind("<Double-1>", self._show_insight_info)
        for child in analysis_frame.winfo_children():
            try:
                child.configure(cursor="hand2")
                child.bind("<Double-1>", self._show_insight_info)
            except tk.TclError:
                continue

    def _initialize_analysis_state(self) -> None:
        initial_analysis = {
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
        }
        self._update_analysis_panel(initial_analysis)
        self.latest_analysis = dict(initial_analysis)

    def _set_palette_tile_state(self, tile: tk.Frame, hover: bool) -> None:
        base_bg = "#f8fafc"
        hover_bg = "#e0f2fe"
        base_border = "#cbd5f5"
        hover_border = "#3b82f6"
        bg = hover_bg if hover else base_bg
        border = hover_border if hover else base_border
        tile.configure(bg=bg, highlightbackground=border)
        for child in tile.winfo_children():
            try:
                child.configure(bg=bg)
            except tk.TclError:
                continue

    def _flash_panel(self, panel: tk.Frame, highlight_bg: str = "#dbeafe") -> None:
        originals: Dict[tk.Widget, str] = {}

        def _collect(widget: tk.Widget) -> None:
            try:
                originals[widget] = widget.cget("bg")
                widget.configure(bg=highlight_bg)
            except tk.TclError:
                pass

        _collect(panel)
        for child in panel.winfo_children():
            _collect(child)

        def _restore() -> None:
            for widget, color in originals.items():
                try:
                    widget.configure(bg=color)
                except tk.TclError:
                    continue

        panel.after(220, _restore)

    def _open_modal(self, title: str, lines: List[str], accent: str = "#2563eb") -> None:
        modal = tk.Toplevel(self.root)
        modal.title(title)
        modal.configure(bg="#0f172a")
        modal.transient(self.root)
        modal.grab_set()
        modal.resizable(False, False)

        frame_width, frame_height = 520, 420
        self._center_window(modal, frame_width, frame_height)

        header = tk.Frame(modal, bg=accent)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=title,
            font=("Segoe UI", 14, "bold"),
            fg="#f8fafc",
            bg=accent,
            pady=8,
        ).pack(padx=20)

        body = tk.Frame(modal, bg="#f8fafc")
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        content = tk.Frame(body, bg="#f8fafc")
        content.pack(fill=tk.BOTH, expand=True)

        for line in lines:
            tk.Label(
                content,
                text=f"• {line}",
                font=("Segoe UI", 10),
                fg="#1f2937",
                bg="#f8fafc",
                justify=tk.LEFT,
                anchor="w",
                wraplength=460,
            ).pack(anchor="w", pady=2)

        footer = tk.Frame(body, bg="#f8fafc")
        footer.pack(fill=tk.X, pady=(12, 0))

        tk.Button(
            footer,
            text="Close",
            font=("Segoe UI", 10, "bold"),
            bg=accent,
            fg="#f8fafc",
            activebackground="#1d4ed8",
            activeforeground="#f8fafc",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            command=modal.destroy,
        ).pack(side=tk.RIGHT)

    def _center_window(self, window: tk.Toplevel, width: int, height: int) -> None:
        self.root.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        pos_x = root_x + max((root_width - width) // 2, 0)
        pos_y = root_y + max((root_height - height) // 2, 0)
        window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _feature_lines(self) -> List[str]:
        return [
            "Left-click a palette tile to add its component or wire to the canvas.",
            "Drag components around the grid to reposition them precisely.",
            "Right-click a component to rotate, edit values, duplicate, lock, or delete it.",
            "Double-click a component to edit its voltage, resistance, or other properties instantly.",
            "Drag wire endpoints onto component terminals or other wires to snap them together.",
            "Double-click a wire to cut it from the circuit.",
            "Hover a component tile to preview which item you are about to place.",
            "Use the ♻ Reset Circuit button to clear every component and wire.",
            "Select Circuit Functions to review this list of available interactions.",
            "Press F11 to toggle fullscreen mode and Escape to exit it.",
            "Watch the circuit insight panel for active path, metrics, and issues in real time.",
        ]

    def _formatted_feature_text(self) -> str:
        return "\n".join(f"• {line}" for line in self._feature_lines())

    def _show_functions(self) -> None:
        lines = self._feature_lines()
        message = "\n".join(f"• {line}" for line in lines)
        if self.functions_display is not None:
            self.functions_display.configure(text=message)
        if hasattr(self, "help_frame"):
            self._flash_panel(self.help_frame)
        self._open_modal("Circuit Functions", lines, accent="#2563eb")

    def _show_tips_dialog(self, _event: Optional[tk.Event] = None) -> None:
        lines = self._feature_lines()
        message = "\n".join(f"• {line}" for line in lines)
        if self.functions_display is not None:
            self.functions_display.configure(text=message)
        if hasattr(self, "help_frame"):
            self._flash_panel(self.help_frame, highlight_bg="#0ea5e9")
        self._open_modal("Circuit Quick Tips", lines, accent="#0ea5e9")

    def _insight_lines(self) -> List[str]:
        return [
            "Type indicates whether the circuit is open, complete, or follows a series/parallel path.",
            "Status summarises if the circuit is powered, open, or needs attention (Alert).",
            "Voltage, current, power, and resistance fields reflect the latest Ohm's Law calculations.",
            "Component and wire totals show how many items are present and how many are currently active.",
            "Active path describes the energized route between sources and loads when the loop is closed.",
            "Issues highlight missing connections or configuration warnings detected by the analyzer.",
        ]

    def _show_insight_info(self, _event: Optional[tk.Event] = None) -> None:
        if self.latest_analysis:
            lines: List[str] = [
                self.circuit_type_var.get(),
                self.circuit_status_var.get(),
                self.circuit_metrics_var.get(),
                self.circuit_power_var.get(),
                self.circuit_counts_var.get(),
                self.circuit_path_var.get(),
            ]
            issues_text = self.circuit_issue_label.cget("text") if self.circuit_issue_label else ""
            issue_lines = [entry.lstrip("• ").strip() for entry in issues_text.splitlines() if entry.strip()]
            if issue_lines:
                lines.append("Issues:")
                lines.extend(issue_lines)
        else:
            lines = self._insight_lines()
        message = "\n".join(f"• {line}" for line in lines)
        if self.functions_display is not None:
            self.functions_display.configure(text=message)
        if hasattr(self, "analysis_frame"):
            self._flash_panel(self.analysis_frame, highlight_bg="#fde68a")
        self._open_modal("Circuit Insight Guide", lines, accent="#f59e0b")

    def _toggle_fullscreen(self, _event: Optional[tk.Event] = None) -> str:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        return "break"

    def _exit_fullscreen(self, _event: Optional[tk.Event] = None) -> Optional[str]:
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)
            return "break"
        return None

    def _draw_grid(self) -> None:
        width = getattr(self, "canvas_width", CANVAS_WIDTH)
        height = getattr(self, "canvas_height", CANVAS_HEIGHT)
        for x in range(0, width, GRID_SIZE):
            for y in range(0, height, GRID_SIZE):
                self.canvas.create_oval(x, y, x + 1, y + 1, fill="#e5e7eb", outline="", tags="grid")
        self.canvas.tag_lower("grid")

    # ------------------------------------------------------------------
    # Canvas & Component Management
    # ------------------------------------------------------------------
    def _on_canvas_configure(self, event: tk.Event) -> None:
        if event.width <= 0 or event.height <= 0:
            return
        if event.width == getattr(self, "canvas_width", 0) and event.height == getattr(self, "canvas_height", 0):
            return
        self.canvas_width = event.width
        self.canvas_height = event.height
        self.canvas.delete("grid")
        self._draw_grid()

    def _register_component(self, component: CircuitComponent) -> None:
        component.on_request_duplicate = self._duplicate_component
        self.components.append(component)

    def _add_component(self, comp_type: str) -> None:
        canvas_width = int(getattr(self, "canvas_width", CANVAS_WIDTH))
        canvas_height = int(getattr(self, "canvas_height", CANVAS_HEIGHT))
        x = canvas_width // 2 + random.randint(-100, 100)
        y = canvas_height // 2 + random.randint(-100, 100)

        x = round(x / GRID_SIZE) * GRID_SIZE
        y = round(y / GRID_SIZE) * GRID_SIZE

        self.component_type_counters[comp_type] = self.component_type_counters.get(comp_type, 0) + 1
        index = self.component_type_counters[comp_type]
        display_label = f"{comp_type.capitalize()} {index}" if comp_type not in COMPONENT_PREFIX else f"{comp_type.title()} {index}"
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
        self._register_component(component)
        self.component_counter += 1
        self._calculate_circuit()

    def _duplicate_component(self, component: CircuitComponent) -> None:
        canvas_width = int(getattr(self, "canvas_width", CANVAS_WIDTH))
        canvas_height = int(getattr(self, "canvas_height", CANVAS_HEIGHT))
        comp_type = component.type

        self.component_type_counters[comp_type] = self.component_type_counters.get(comp_type, 0) + 1
        index = self.component_type_counters[comp_type]
        display_label = f"{comp_type.capitalize()} {index}" if comp_type not in COMPONENT_PREFIX else f"{comp_type.title()} {index}"
        prefix = COMPONENT_PREFIX.get(comp_type, comp_type[:1].upper())
        code_label = f"{prefix}{index}"

        width, height = component._current_dimensions()
        offset_x = component.x + GRID_SIZE * 4
        offset_y = component.y + GRID_SIZE * 2
        new_x = int(max(0, min(offset_x, canvas_width - width)))
        new_y = int(max(0, min(offset_y, canvas_height - height)))
        new_x = round(new_x / GRID_SIZE) * GRID_SIZE
        new_y = round(new_y / GRID_SIZE) * GRID_SIZE
        new_x = int(max(0, min(new_x, canvas_width - width)))
        new_y = int(max(0, min(new_y, canvas_height - height)))

        duplicate = CircuitComponent(
            self.canvas,
            comp_type,
            new_x,
            new_y,
            self.component_counter,
            display_label,
            code_label,
            self._on_component_changed,
            self._on_component_removed,
        )
        self.component_counter += 1

        duplicate.voltage_value = component.voltage_value
        duplicate.resistance_value = component.resistance_value
        duplicate.capacitance = component.capacitance
        duplicate.forward_voltage = component.forward_voltage
        duplicate.switch_closed = component.switch_closed
        duplicate.locked = component.locked

        if component.orientation != duplicate.orientation:
            duplicate.rotate()
        else:
            duplicate._draw_visual_representation()

        if duplicate.locked:
            duplicate._build_context_menu()
        duplicate.apply_theme(duplicate.theme)
        duplicate._update_detail_text()

        self._register_component(duplicate)
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
        if self._auto_snap_guard:
            return
        self._calculate_circuit()

    def _on_wire_removed(self, wire: CircuitWire) -> None:
        if wire in self.wires:
            self.wires.remove(wire)
        self._calculate_circuit()

    def _auto_snap_connections(self) -> None:
        if self._auto_snap_guard:
            return
        self._auto_snap_guard = True
        try:
            for wire in self.wires:
                for endpoint in ("a", "b"):
                    if wire.attachments.get(endpoint):
                        continue
                    if wire.links.get(endpoint):
                        continue
                    position = wire.positions.get(endpoint)
                    if not position:
                        continue
                    x, y = position
                    target, identifier, snap_point = self._find_nearest_connector(x, y, exclude_wire=wire, exclude_endpoint=endpoint)
                    if isinstance(target, CircuitComponent) and isinstance(identifier, str):
                        wire.attach_to_component(endpoint, target, identifier, snap_point)
                    elif isinstance(target, CircuitWire):
                        wire.attach_to_wire(endpoint, target, identifier, snap_point)
        finally:
            self._auto_snap_guard = False

    def _find_nearest_connector(
        self,
        x: float,
        y: float,
        exclude_wire: Optional[CircuitWire] = None,
        exclude_endpoint: Optional[str] = None,
        threshold: float = 36.0,
    ) -> tuple[Any | None, Any, tuple[float, float]]:
        target: Any | None = None
        identifier: Any = None
        snap_point: tuple[float, float] = (x, y)
        best_distance = threshold

        def project_point(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> tuple[float, float]:
            dx = bx - ax
            dy = by - ay
            if dx == 0 and dy == 0:
                return ax, ay
            t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            return ax + t * dx, ay + t * dy

        for component in self.components:
            for side in ("left", "right", "top", "bottom"):
                cx, cy = component.anchor_point(side)
                dist = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
                if dist <= best_distance:
                    best_distance = dist
                    target = component
                    identifier = side
                    snap_point = (cx, cy)

        for wire in self.wires:
            if wire is exclude_wire:
                continue
            for ep in ("a", "b"):
                if wire is exclude_wire and ep == exclude_endpoint:
                    continue
                wx, wy = wire.positions.get(ep, (0.0, 0.0))
                dist = ((wx - x) ** 2 + (wy - y) ** 2) ** 0.5
                if dist <= best_distance:
                    best_distance = dist
                    target = wire
                    identifier = ep
                    snap_point = (wx, wy)

            path_points: List[Tuple[float, float]]
            if hasattr(wire, "path_points"):
                path_points = list(wire.path_points())
            else:
                path_points = [
                    wire.positions.get("a", (0.0, 0.0)),
                    wire.positions.get("b", (0.0, 0.0)),
                ]
            for idx in range(len(path_points) - 1):
                ax, ay = path_points[idx]
                bx, by = path_points[idx + 1]
                px, py = project_point(x, y, ax, ay, bx, by)
                dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
                if dist <= best_distance:
                    end_a_dist = ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
                    end_b_dist = ((px - bx) ** 2 + (py - by) ** 2) ** 0.5
                    if min(end_a_dist, end_b_dist) < 6.0:
                        continue
                    best_distance = dist
                    target = wire
                    identifier = ("segment", px, py, idx)
                    snap_point = (px, py)

        return target, identifier, snap_point

    # ------------------------------------------------------------------
    # Analysis & Status Updates
    # ------------------------------------------------------------------
    def _update_component_highlights(self, active_group: Optional[List[CircuitComponent]]) -> None:
        active_ids = {comp.id for comp in active_group} if active_group else set()
        for comp in self.components:
            comp.set_active(comp.id in active_ids)

    def _update_analysis_panel(self, analysis: Dict[str, Any]) -> None:
        circuit_type = analysis.get("type", "Open")
        status_detail = analysis.get("status_detail", "Open Circuit")
        status_state = analysis.get("status", "Open")
        total_voltage = float(analysis.get("total_voltage", 0.0))
        total_current = float(analysis.get("total_current", 0.0))
        total_power = float(analysis.get("total_power", 0.0))
        total_resistance = float(analysis.get("total_resistance", 0.0))

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

        total_components = int(analysis.get("component_count", 0))
        total_wires = int(analysis.get("wire_count", 0))
        active_components = int(analysis.get("active_component_count", 0))
        active_wires = int(analysis.get("active_wire_count", 0))
        if active_components or active_wires:
            counts_text = (
                f"Components: {total_components} (active {active_components}) | "
                f"Wires: {total_wires} (active {active_wires})"
            )
        else:
            counts_text = f"Components: {total_components} | Wires: {total_wires}"
        self.circuit_counts_var.set(counts_text)

        path_description = analysis.get("path_description", "—")
        if isinstance(path_description, str) and path_description != "—":
            self.circuit_path_var.set(f"Active path: {path_description}")
        else:
            self.circuit_path_var.set("Active path: —")

        issues = list(analysis.get("issues", []))
        if issues:
            unique_issues = list(dict.fromkeys(issues))
            display_lines = [f"• {issue}" for issue in unique_issues[:4]]
            if len(unique_issues) > 4:
                display_lines.append(f"• +{len(unique_issues) - 4} more")
            issues_text = "\n".join(display_lines)
        else:
            issues_text = "• No issues detected"
        self.circuit_issue_label.config(text=issues_text)

    def _calculate_circuit(self) -> None:
        self._auto_snap_connections()
        analysis, active_group, active_wires, component_metrics = analyze_circuit(self.components, self.wires)

        self._update_component_highlights(active_group)
        for wire in self.wires:
            wire.set_active(active_wires is not None and wire in active_wires)

        if active_group:
            for component in active_group:
                metrics = component_metrics.get(component, {
                    "current": float(analysis.get("total_current", 0.0)),
                    "voltage": 0.0,
                    "power": 0.0,
                })
                component.update_operating_metrics(
                    float(metrics.get("current", 0.0)),
                    float(metrics.get("voltage", 0.0)),
                    float(metrics.get("power", 0.0)),
                )

            self.v_entry.config(state="normal")
            self.i_entry.config(state="normal")
            self.r_entry.config(state="normal")
            self.p_entry.config(state="normal")

            self.v_entry.delete(0, tk.END)
            self.v_entry.insert(0, f"{float(analysis.get('total_voltage', 0.0)):.3f} V")

            self.i_entry.delete(0, tk.END)
            self.i_entry.insert(0, f"{float(analysis.get('total_current', 0.0)):.4f} A")

            total_resistance = float(analysis.get("total_resistance", 0.0))
            if total_resistance > 0:
                resistance_display = f"{total_resistance:.2f} Ω"
            elif total_resistance == 0:
                resistance_display = "0.00 Ω"
            else:
                resistance_display = "∞"
            self.r_entry.delete(0, tk.END)
            self.r_entry.insert(0, resistance_display)

            self.p_entry.delete(0, tk.END)
            self.p_entry.insert(0, f"{float(analysis.get('total_power', 0.0)):.3f} W")

            self.v_entry.config(state="readonly")
            self.i_entry.config(state="readonly")
            self.r_entry.config(state="readonly")
            self.p_entry.config(state="readonly")

            status_color = "#facc15" if analysis.get("status") == "Alert" else "#10b981"
            self.status.set(str(analysis.get("status_detail", "✓ Circuit Complete & Powered")))
            if self.status_label is not None:
                self.status_label.config(fg=status_color)
        else:
            if not self.components:
                self._reset_values()
            else:
                has_battery = any(comp.type == "battery" and comp.get_voltage() > 0 for comp in self.components)
                load_types = {"resistor", "bulb", "led", "diode"}
                has_load = any(comp.type in load_types and comp.get_resistance() > 0 for comp in self.components)
                switch_components = [comp for comp in self.components if hasattr(comp, "is_switch") and comp.is_switch()]
                open_switches = [comp for comp in switch_components if not comp.is_switch_closed()]

                if open_switches and has_battery and has_load:
                    switch_names = ", ".join(comp.display_label for comp in open_switches[:2])
                    if len(open_switches) > 2:
                        switch_names += f" +{len(open_switches) - 2} more"
                    message = f"⚠️ Close {switch_names} to complete the circuit"
                    color = "#d97706"
                    analysis["status"] = "Alert"
                    analysis["issues"].append(f"{switch_names} open; close to complete the circuit")
                elif has_battery and not has_load:
                    message = "⚠️ Add a resistor or bulb to complete the circuit"
                    color = "#d97706"
                    analysis["status"] = "Alert"
                    analysis["issues"].append("Add a resistor or bulb to complete the circuit")
                elif has_load and not has_battery:
                    message = "⚠️ Add a battery to power the circuit"
                    color = "#d97706"
                    analysis["status"] = "Alert"
                    analysis["issues"].append("Add a battery to power the circuit")
                elif len(self.components) >= 2:
                    message = "⚠️ Connect all terminals with wires to close the loop"
                    color = "#d97706"
                    analysis["status"] = "Alert"
                    analysis["issues"].append("Connect all terminals with wires to close the loop")
                else:
                    message = "⚫ Open Circuit"
                    color = "#9ca3af"
                    analysis["status"] = "Open"
                analysis["status_detail"] = message
                self._reset_values(message, color)

        analysis["issues"] = list(dict.fromkeys(analysis.get("issues", [])))
        self.latest_analysis = dict(analysis)
        self.latest_analysis["issues"] = list(analysis.get("issues", []))
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
        if self.status_label is not None:
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
            "path_description": "—",
            "issues": [],
        })


__all__ = ["OhmsLawApp"]
