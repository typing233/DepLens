from pathlib import Path
from typing import Dict, Set, Optional

from .analyzer import AnalysisResult, CircularDependency, GhostDependency, VersionConflict
from .parsers.base import Dependency


class DotGenerator:
    def __init__(self, result: AnalysisResult):
        self._result = result
        self._circular_deps: Set[str] = set()
        self._ghost_deps: Set[str] = set()
        self._version_conflicts: Set[str] = set()
        
        self._collect_issues()

    def _collect_issues(self) -> None:
        for cd in self._result.circular_dependencies:
            for dep in cd.path:
                self._circular_deps.add(dep)
        
        for gd in self._result.ghost_dependencies:
            self._ghost_deps.add(gd.name)
        
        for vc in self._result.version_conflicts:
            self._version_conflicts.add(vc.name)

    def generate(self, output_path: Path) -> None:
        lines = [
            "digraph DependencyGraph {",
            "    rankdir=LR;",
            "    node [shape=box, style=filled, fontname=\"Arial\"];",
            "    edge [fontname=\"Arial\"];",
            "",
            "    // Project root",
            f"    \"root\" [label=\"{self._result.project_path.name}\\n({self._result.project_type.value})\", shape=ellipse, fillcolor=\"#E3F2FD\"];",
            "",
        ]

        node_defs = self._generate_node_definitions()
        lines.extend(node_defs)
        
        lines.append("")
        
        edge_defs = self._generate_edge_definitions()
        lines.extend(edge_defs)
        
        lines.append("")
        
        legend = self._generate_legend()
        lines.extend(legend)
        
        lines.append("}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _generate_node_definitions(self) -> list:
        lines = ["    // Nodes"]
        
        for dep_name, dep in self._result.direct_dependencies.items():
            attrs = self._get_node_attributes(dep)
            label = self._get_node_label(dep)
            lines.append(f"    \"{dep_name}\" [label=\"{label}\"{attrs}];")
        
        seen = set(self._result.direct_dependencies.keys())
        
        for dep in self._result.all_dependencies.values():
            self._collect_transitive_nodes(dep, seen, lines)
        
        return lines

    def _collect_transitive_nodes(self, dep: Dependency, seen: set, lines: list) -> None:
        if dep.name in seen:
            return
        seen.add(dep.name)
        
        attrs = self._get_node_attributes(dep)
        label = self._get_node_label(dep)
        lines.append(f"    \"{dep.name}\" [label=\"{label}\"{attrs}];")
        
        for child_dep in dep.dependencies:
            self._collect_transitive_nodes(child_dep, seen, lines)

    def _get_node_attributes(self, dep: Dependency) -> str:
        attrs = []
        
        if dep.name in self._circular_deps:
            attrs.append("fillcolor=\"#FFCDD2\"")
            attrs.append("color=\"#C62828\"")
            attrs.append("penwidth=2")
        elif dep.name in self._ghost_deps:
            attrs.append("fillcolor=\"#FFF3E0\"")
            attrs.append("color=\"#E65100\"")
        elif dep.name in self._version_conflicts:
            attrs.append("fillcolor=\"#FCE4EC\"")
            attrs.append("color=\"#C2185B\"")
        elif dep.is_dev:
            attrs.append("fillcolor=\"#F3E5F5\"")
            attrs.append("color=\"#7B1FA2\"")
        elif not dep.is_direct:
            attrs.append("fillcolor=\"#E0E0E0\"")
            attrs.append("color=\"#616161\"")
        else:
            attrs.append("fillcolor=\"#E8F5E9\"")
            attrs.append("color=\"#388E3C\"")
        
        if attrs:
            return ", " + ", ".join(attrs)
        return ""

    def _get_node_label(self, dep: Dependency) -> str:
        label_parts = [dep.name]
        
        if dep.version and dep.version != "unknown":
            label_parts.append(f"\\nv{dep.version}")
        
        issues = []
        if dep.name in self._circular_deps:
            issues.append("cyclic")
        if dep.name in self._ghost_deps:
            issues.append("ghost")
        if dep.name in self._version_conflicts:
            issues.append("version conflict")
        
        if issues:
            label_parts.append(f"\\n({', '.join(issues)})")
        
        return "".join(label_parts)

    def _generate_edge_definitions(self) -> list:
        lines = ["    // Edges"]
        
        for dep_name, dep in self._result.direct_dependencies.items():
            style = "solid"
            color = "#388E3C"
            if dep.is_dev:
                style = "dashed"
                color = "#7B1FA2"
            lines.append(f"    \"root\" -> \"{dep_name}\" [style={style}, color=\"{color}\"];")
        
        seen: Set[tuple] = set()
        
        for dep in self._result.all_dependencies.values():
            self._collect_transitive_edges(dep, seen, lines)
        
        return lines

    def _collect_transitive_edges(self, dep: Dependency, seen: set, lines: list) -> None:
        for child_dep in dep.dependencies:
            edge_key = (dep.name, child_dep.name)
            if edge_key not in seen:
                seen.add(edge_key)
                
                style = "solid"
                color = "#9E9E9E"
                
                if (
                    dep.name in self._circular_deps 
                    and child_dep.name in self._circular_deps
                ):
                    color = "#C62828"
                    style = "bold"
                
                lines.append(f"    \"{dep.name}\" -> \"{child_dep.name}\" [style={style}, color=\"{color}\"];")
            
            self._collect_transitive_edges(child_dep, seen, lines)

    def _generate_legend(self) -> list:
        lines = [
            "    // Legend",
            "    subgraph cluster_legend {",
            "        label=\"Legend\";",
            "        style=dashed;",
            "        color=\"#9E9E9E\";",
            "",
            "        // Node types",
            "        \"legend_root\" [label=\"Project Root\", shape=ellipse, fillcolor=\"#E3F2FD\", style=filled];",
            "        \"legend_direct\" [label=\"Direct Dep\", fillcolor=\"#E8F5E9\", style=filled, color=\"#388E3C\"];",
            "        \"legend_transitive\" [label=\"Transitive Dep\", fillcolor=\"#E0E0E0\", style=filled, color=\"#616161\"];",
            "        \"legend_dev\" [label=\"Dev Dep\", fillcolor=\"#F3E5F5\", style=filled, color=\"#7B1FA2\"];",
            "",
            "        // Issues",
            "        \"legend_cyclic\" [label=\"Cyclic Dep\", fillcolor=\"#FFCDD2\", style=filled, color=\"#C62828\", penwidth=2];",
            "        \"legend_ghost\" [label=\"Ghost Dep\", fillcolor=\"#FFF3E0\", style=filled, color=\"#E65100\"];",
            "        \"legend_version\" [label=\"Version Conflict\", fillcolor=\"#FCE4EC\", style=filled, color=\"#C2185B\"];",
            "    }",
        ]
        return lines


def generate_dot(result: AnalysisResult, output_path: Path) -> None:
    generator = DotGenerator(result)
    generator.generate(output_path)
