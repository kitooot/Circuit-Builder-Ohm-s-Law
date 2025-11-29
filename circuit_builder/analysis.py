from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .components import CircuitComponent
from .wires import CircuitWire

AnalysisDict = Dict[str, object]
ComponentMetrics = Dict[CircuitComponent, Dict[str, float]]
Adjacency = Dict[CircuitComponent, Set[CircuitComponent]]

PASSIVE_LOAD_TYPES: Set[str] = {
    "resistor",
    "bulb",
    "led",
    "diode",
    "ammeter",
    "voltmeter",
}

TERMINAL_REQUIREMENTS: Dict[str, int] = {
    "ground": 1,
}

SWITCH_TYPES: Set[str] = {"switch", "switch_spst", "switch_spdt"}


def expected_connections(component: CircuitComponent) -> int:
    return TERMINAL_REQUIREMENTS.get(component.type, 2)


def _is_passive_load(component: CircuitComponent) -> bool:
    if component.type in PASSIVE_LOAD_TYPES:
        return component.get_resistance() > 0
    if component.type == "battery":
        return False
    resistance = component.get_resistance()
    return resistance > 0


def _is_switch(component: CircuitComponent) -> bool:
    return component.type in SWITCH_TYPES


def _is_switch_closed(component: CircuitComponent) -> bool:
    if not _is_switch(component):
        return True
    return getattr(component, "switch_closed", True)


def classify_circuit(
    component_group: List[CircuitComponent],
    adjacency: Adjacency,
    loads: List[CircuitComponent],
) -> str:
    if len(loads) <= 1:
        return "Single Load"

    branch_nodes = [comp for comp in component_group if len(adjacency.get(comp, set())) > 2]
    if branch_nodes:
        return "Parallel"

    return "Series"


def describe_active_path(
    component_group: List[CircuitComponent],
    adjacency: Adjacency,
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


def compute_circuit_metrics(
    component_group: List[CircuitComponent],
    batteries: List[CircuitComponent],
    loads: List[CircuitComponent],
    circuit_type: str,
) -> tuple[AnalysisDict, ComponentMetrics, List[str]]:
    summary: AnalysisDict = {
        "total_voltage": sum(component.get_voltage() for component in batteries),
        "total_resistance": 0.0,
        "total_current": 0.0,
        "total_power": 0.0,
        "status_override": "Closed",
        "status_detail_override": "✓ Circuit Complete & Powered",
    }
    per_component: ComponentMetrics = {}
    issues: List[str] = []

    total_voltage = summary["total_voltage"]
    if total_voltage <= 0:
        issues.append("No active voltage source detected")
        summary["status_override"] = "Alert"
        summary["status_detail_override"] = "⚠️ Add an active battery"
        return summary, per_component, issues

    if not loads:
        issues.append("No passive load connected to the circuit")
        summary["status_override"] = "Alert"
        summary["status_detail_override"] = "⚠️ Add a resistor, bulb, or other load"
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


def analyze_circuit(
    components: List[CircuitComponent],
    wires: List[CircuitWire],
) -> tuple[AnalysisDict, Optional[List[CircuitComponent]], Optional[List[CircuitWire]], ComponentMetrics]:
    analysis: AnalysisDict = {
        "component_count": len(components),
        "wire_count": len(wires),
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

    for component in components:
        component.reset_operating_metrics()

    adjacency: Adjacency = {component: set() for component in components}
    edges: List[tuple[CircuitWire, CircuitComponent, CircuitComponent]] = []
    endpoint_counts: Dict[CircuitComponent, int] = {component: 0 for component in components}

    for wire in wires:
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

    for component in components:
        connected = endpoint_counts.get(component, 0)
        required = expected_connections(component)
        if connected < required:
            analysis["issues"].append(f"{component.display_label}: {connected}/{required} terminals connected")
        if _is_switch(component) and not _is_switch_closed(component):
            analysis["issues"].append(f"{component.display_label} is open; close it to complete the circuit")

    visited: Set[CircuitComponent] = set()
    active_group: Optional[List[CircuitComponent]] = None
    active_wires: Optional[List[CircuitWire]] = None
    group_batteries: List[CircuitComponent] = []
    group_loads: List[CircuitComponent] = []

    for component in components:
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
        loads = [comp for comp in candidate_group if _is_passive_load(comp)]

        if any(_is_switch(comp) and not _is_switch_closed(comp) for comp in candidate_group):
            continue

        if not batteries or not loads:
            continue

        if not all(endpoint_counts.get(comp, 0) >= expected_connections(comp) for comp in candidate_group):
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

    component_metrics: ComponentMetrics = {}

    if active_group:
        circuit_type = classify_circuit(active_group, adjacency, group_loads)
        summary, component_metrics, metric_issues = compute_circuit_metrics(active_group, group_batteries, group_loads, circuit_type)

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
            "path_description": describe_active_path(active_group, adjacency, group_batteries),
        })
        analysis["issues"].extend(metric_issues)

        if analysis["status"] == "Closed" and summary.get("status_detail_override") == "✓ Circuit Complete & Powered":
            analysis["status_detail"] = f"✓ {circuit_type} circuit powered"

    return analysis, active_group, active_wires, component_metrics


__all__ = [
    "analyze_circuit",
    "classify_circuit",
    "compute_circuit_metrics",
    "describe_active_path",
    "expected_connections",
]
