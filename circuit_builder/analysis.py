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
    # Return the required number of connected terminals for this component type.
    return TERMINAL_REQUIREMENTS.get(component.type, 2)


def _is_passive_load(component: CircuitComponent) -> bool:
    # Check whether the component should behave like a passive load in analysis.
    if component.type in PASSIVE_LOAD_TYPES:
        return component.get_resistance() > 0
    if component.type == "battery":
        return False
    resistance = component.get_resistance()
    return resistance > 0


def _is_switch(component: CircuitComponent) -> bool:
    # Determine if the component is treated as a switch.
    return component.type in SWITCH_TYPES


def _is_switch_closed(component: CircuitComponent) -> bool:
    # Inspect a switch component to see if its contacts are closed.
    if not _is_switch(component):
        return True
    return getattr(component, "switch_closed", True)


def classify_circuit(
    component_group: List[CircuitComponent],
    adjacency: Adjacency,
    loads: List[CircuitComponent],
    component_nodes: Optional[Dict[CircuitComponent, List[str]]] = None,
) -> str:
    # Infer whether the connected group functions as series, parallel, or single load.
    if len(loads) <= 1:
        return "Single Load"

    if component_nodes:
        node_pair_counts: Dict[Tuple[str, str], int] = {}
        for load in loads:
            nodes = sorted({node for node in component_nodes.get(load, []) if node is not None})
            if len(nodes) >= 2:
                pair = (nodes[0], nodes[1])
                node_pair_counts[pair] = node_pair_counts.get(pair, 0) + 1
        if any(count >= 2 for count in node_pair_counts.values()):
            return "Parallel"

    branch_nodes = [comp for comp in component_group if len(adjacency.get(comp, set())) > 2]
    if branch_nodes:
        return "Parallel"

    return "Series"


def describe_active_path(
    component_group: List[CircuitComponent],
    adjacency: Adjacency,
    batteries: List[CircuitComponent],
) -> str:
    # Build a readable path description by traversing the energized graph.
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
    # Calculate aggregate and per-component electrical metrics for the active circuit.
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
    # Evaluate circuit connectivity and electrical characteristics from components and wires.
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

    def _find_root(parents: Dict[int, int], node: int) -> int:
        parents.setdefault(node, node)
        if parents[node] != node:
            parents[node] = _find_root(parents, parents[node])
        return parents[node]

    def _union_nodes(parents: Dict[int, int], a: int, b: int) -> None:
        root_a = _find_root(parents, a)
        root_b = _find_root(parents, b)
        if root_a != root_b:
            parents[root_b] = root_a

    def _find_terminal_root(parents: Dict[str, str], terminal: str) -> str:
        parents.setdefault(terminal, terminal)
        if parents[terminal] != terminal:
            parents[terminal] = _find_terminal_root(parents, parents[terminal])
        return parents[terminal]

    def _union_terminals(parents: Dict[str, str], a: str, b: str) -> None:
        root_a = _find_terminal_root(parents, a)
        root_b = _find_terminal_root(parents, b)
        if root_a != root_b:
            parents[root_b] = root_a

    adjacency: Adjacency = {component: set() for component in components}
    endpoint_counts: Dict[CircuitComponent, int] = {component: 0 for component in components}

    wire_indices: Dict[CircuitWire, int] = {wire: idx for idx, wire in enumerate(wires)}
    wire_parents: Dict[int, int] = {idx: idx for idx in wire_indices.values()}

    for wire in wires:
        wire_idx = wire_indices[wire]
        for link_set in wire.links.values():
            for linked_wire, _ in link_set:
                if linked_wire in wire_indices:
                    _union_nodes(wire_parents, wire_idx, wire_indices[linked_wire])

        attachments_count = sum(1 for attachment in wire.attachments.values() if attachment)
        linked_count = sum(len(link) for link in wire.links.values())
        if attachments_count + linked_count == 0:
            analysis["issues"].append("Wire with no connections detected")
        elif attachments_count + linked_count == 1:
            analysis["issues"].append("Wire with a floating endpoint detected")

        for attachment in wire.attachments.values():
            if attachment:
                comp, _ = attachment
                endpoint_counts[comp] = endpoint_counts.get(comp, 0) + 1

    wire_clusters: Dict[int, Set[CircuitWire]] = {}
    wire_cluster_lookup: Dict[CircuitWire, int] = {}
    for wire, idx in wire_indices.items():
        root = _find_root(wire_parents, idx)
        wire_clusters.setdefault(root, set()).add(wire)
        wire_cluster_lookup[wire] = root

    terminal_parents: Dict[str, str] = {}
    terminal_component: Dict[str, CircuitComponent] = {}
    cluster_components: Dict[int, Set[CircuitComponent]] = {}

    for cluster_id, cluster_wires in wire_clusters.items():
        terminals: List[str] = []
        component_set: Set[CircuitComponent] = set()
        for wire in cluster_wires:
            for attachment in wire.attachments.values():
                if not attachment:
                    continue
                comp, side = attachment
                terminal_id = f"{comp.id}:{side}"
                terminals.append(terminal_id)
                terminal_component[terminal_id] = comp
                component_set.add(comp)
        cluster_components[cluster_id] = component_set
        if len(terminals) >= 2:
            base = terminals[0]
            for terminal in terminals[1:]:
                _union_terminals(terminal_parents, base, terminal)
        elif len(terminals) == 1:
            _find_terminal_root(terminal_parents, terminals[0])

    node_members: Dict[str, Set[CircuitComponent]] = {}
    component_nodes: Dict[CircuitComponent, List[str]] = {component: [] for component in components}

    for terminal_id, component in terminal_component.items():
        node_id = _find_terminal_root(terminal_parents, terminal_id)
        node_members.setdefault(node_id, set()).add(component)
        nodes = component_nodes.setdefault(component, [])
        if node_id not in nodes:
            nodes.append(node_id)

    for node_id, comps in node_members.items():
        comp_list = list(comps)
        for i in range(len(comp_list)):
            for j in range(i + 1, len(comp_list)):
                comp_a = comp_list[i]
                comp_b = comp_list[j]
                adjacency.setdefault(comp_a, set()).add(comp_b)
                adjacency.setdefault(comp_b, set()).add(comp_a)

    for component in components:
        connected = endpoint_counts.get(component, 0)
        required = expected_connections(component)
        if connected < required:
            analysis["issues"].append(f"{component.display_label}: {connected}/{required} terminals connected")
        if _is_switch(component) and not _is_switch_closed(component):
            analysis["issues"].append(f"{component.display_label} is open; close it to complete the circuit")

    visited: Set[CircuitComponent] = set()
    active_group: Optional[List[CircuitComponent]] = None
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
        break

    component_metrics: ComponentMetrics = {}
    active_wires: Optional[List[CircuitWire]] = None

    if active_group:
        active_set = set(active_group)
        active_cluster_ids: Set[int] = set()
        for cluster_id, comps in cluster_components.items():
            in_group = [comp for comp in comps if comp in active_set]
            if len(in_group) >= 2:
                active_cluster_ids.add(cluster_id)

        if active_cluster_ids:
            active_wires = [
                wire
                for wire in wires
                if wire_cluster_lookup.get(wire) in active_cluster_ids
            ]
        else:
            active_wires = []

        circuit_type = classify_circuit(active_group, adjacency, group_loads, component_nodes)
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
