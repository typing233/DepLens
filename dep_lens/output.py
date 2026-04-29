from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from colorama import Fore, Style, init

from .analyzer import AnalysisResult, CircularDependency, GhostDependency, VersionConflict
from .parsers.base import Dependency

init(autoreset=True)


@dataclass
class ColorTheme:
    reset: str = Style.RESET_ALL
    
    # Node types
    root: str = Fore.CYAN + Style.BRIGHT
    direct_dep: str = Fore.GREEN + Style.BRIGHT
    transitive_dep: str = Fore.WHITE
    dev_dep: str = Fore.MAGENTA
    
    # Issues
    critical: str = Fore.RED + Style.BRIGHT
    warning: str = Fore.YELLOW + Style.BRIGHT
    info: str = Fore.BLUE
    
    # Tree symbols
    branch: str = Fore.LIGHTBLACK_EX
    last_branch: str = Fore.LIGHTBLACK_EX
    vertical: str = Fore.LIGHTBLACK_EX


THEME = ColorTheme()


class TreePrinter:
    def __init__(self, result: AnalysisResult):
        self._result = result
        self._circular_deps: Set[str] = set()
        self._ghost_deps: Set[str] = set()
        self._version_conflicts: Set[str] = set()
        self._printed: Set[str] = set()
        
        self._collect_issues()

    def _collect_issues(self) -> None:
        for cd in self._result.circular_dependencies:
            for dep in cd.path:
                self._circular_deps.add(dep)
        
        for gd in self._result.ghost_dependencies:
            self._ghost_deps.add(gd.name)
        
        for vc in self._result.version_conflicts:
            self._version_conflicts.add(vc.name)

    def print_tree(self) -> None:
        self._print_header()
        
        print()
        print(f"{THEME.root}📦 Dependency Tree:{THEME.reset}")
        print(f"{THEME.vertical}│{THEME.reset}")
        
        root_name = self._result.project_path.name
        print(f"{THEME.root}└── {root_name} ({self._result.project_type.value}){THEME.reset}")
        
        all_deps = list(self._result.direct_dependencies.items())
        total = len(all_deps)
        
        for i, (name, dep) in enumerate(all_deps):
            is_last = i == total - 1
            prefix = "    " if is_last else "│   "
            self._print_dependency(dep, prefix, is_last, depth=1)

    def _print_header(self) -> None:
        project_name = self._result.project_path.name
        project_type = self._result.project_type.value
        
        print(f"{THEME.root}╔════════════════════════════════════════════════════════════╗{THEME.reset}")
        print(f"{THEME.root}║{THEME.reset}              {THEME.info}DepLens - Dependency Analyzer{THEME.reset}                    {THEME.root}║{THEME.reset}")
        print(f"{THEME.root}╠════════════════════════════════════════════════════════════╣{THEME.reset}")
        print(f"{THEME.root}║{THEME.reset}  Project: {project_name:<48} {THEME.root}║{THEME.reset}")
        print(f"{THEME.root}║{THEME.reset}  Type:    {project_type.upper():<48} {THEME.root}║{THEME.reset}")
        print(f"{THEME.root}║{THEME.reset}  Path:    {str(self._result.project_path)[:48]:<48} {THEME.root}║{THEME.reset}")
        print(f"{THEME.root}╠════════════════════════════════════════════════════════════╣{THEME.reset}")
        
        direct_count = len(self._result.direct_dependencies)
        all_count = len(self._result.all_dependencies)
        dev_count = len(self._result.dev_dependencies)
        
        stats_line = (
            f"  Direct: {direct_count:<4}  |  Total: {all_count:<4}  |  Dev: {dev_count:<4}"
        )
        print(f"{THEME.root}║{THEME.reset}{stats_line:<62}{THEME.root}║{THEME.reset}")
        print(f"{THEME.root}╚════════════════════════════════════════════════════════════╝{THEME.reset}")

    def _print_dependency(
        self, dep: Dependency, prefix: str, is_last: bool, depth: int
    ) -> None:
        if dep.name in self._printed:
            self._print_reference(dep, prefix, is_last, depth)
            return
        
        self._printed.add(dep.name)
        
        branch = "└── " if is_last else "├── "
        color = self._get_dependency_color(dep)
        markers = self._get_issue_markers(dep)
        
        version_info = ""
        if dep.version and dep.version != "unknown":
            version_info = f" @ v{dep.version}"
        
        print(
            f"{THEME.branch}{prefix}{branch}{THEME.reset}"
            f"{color}{dep.name}{version_info}{THEME.reset}"
            f"{markers}"
        )
        
        children = dep.dependencies
        total_children = len(children)
        
        for i, child in enumerate(children):
            child_is_last = i == total_children - 1
            child_prefix = prefix + ("    " if is_last else "│   ")
            self._print_dependency(child, child_prefix, child_is_last, depth + 1)

    def _print_reference(
        self, dep: Dependency, prefix: str, is_last: bool, depth: int
    ) -> None:
        branch = "└── " if is_last else "├── "
        print(
            f"{THEME.branch}{prefix}{branch}{THEME.reset}"
            f"{Fore.LIGHTBLACK_EX}{dep.name} {THEME.info}(see above){THEME.reset}"
        )

    def _get_dependency_color(self, dep: Dependency) -> str:
        if dep.name in self._circular_deps:
            return THEME.critical
        if dep.name in self._ghost_deps:
            return THEME.warning
        if dep.name in self._version_conflicts:
            return THEME.critical
        if dep.is_dev:
            return THEME.dev_dep
        if dep.is_direct:
            return THEME.direct_dep
        return THEME.transitive_dep

    def _get_issue_markers(self, dep: Dependency) -> str:
        markers: List[str] = []
        
        if dep.name in self._circular_deps:
            markers.append(f"{THEME.critical} ⚠️  CYCLIC{THEME.reset}")
        if dep.name in self._ghost_deps:
            markers.append(f"{THEME.warning} 👻 GHOST{THEME.reset}")
        if dep.name in self._version_conflicts:
            markers.append(f"{THEME.critical} ⚡ VERSION CONFLICT{THEME.reset}")
        if dep.is_dev:
            markers.append(f"{THEME.dev_dep} [DEV]{THEME.reset}")
        
        return "".join(markers)

    def print_issues(self) -> None:
        print()
        print(f"{THEME.root}📋 Issues Summary:{THEME.reset}")
        print()
        
        has_issues = False
        
        if self._result.circular_dependencies:
            has_issues = True
            print(f"{THEME.critical}🚨 Circular Dependencies ({len(self._result.circular_dependencies)} found){THEME.reset}")
            for i, cd in enumerate(self._result.circular_dependencies, 1):
                cycle_str = " → ".join(cd.path)
                print(f"   {i}. {cycle_str}")
            print()
        
        if self._result.ghost_dependencies:
            has_issues = True
            print(f"{THEME.warning}👻 Ghost Dependencies ({len(self._result.ghost_dependencies)} found){THEME.reset}")
            for i, gd in enumerate(self._result.ghost_dependencies, 1):
                print(f"   {i}. {THEME.warning}{gd.name}{THEME.reset}")
                for file_path in gd.used_in[:3]:
                    rel_path = file_path.relative_to(self._result.project_path)
                    print(f"       Used in: {rel_path}")
                if len(gd.used_in) > 3:
                    print(f"       ... and {len(gd.used_in) - 3} more files")
            print()
        
        if self._result.version_conflicts:
            has_issues = True
            print(f"{THEME.critical}⚡ Version Conflicts ({len(self._result.version_conflicts)} found){THEME.reset}")
            for i, vc in enumerate(self._result.version_conflicts, 1):
                versions = ", ".join(vc.versions.keys())
                print(f"   {i}. {THEME.critical}{vc.name}{THEME.reset}: {versions}")
            print()
        
        if not has_issues:
            print(f"{THEME.direct_dep}✅ No issues found!{THEME.reset}")
            print()

    def print_statistics(self) -> None:
        print(f"{THEME.root}📊 Statistics:{THEME.reset}")
        print()
        
        total_direct = len(self._result.direct_dependencies)
        total_all = len(self._result.all_dependencies)
        total_dev = len(self._result.dev_dependencies)
        total_transitive = total_all - total_direct - total_dev
        
        print(f"  {THEME.info}📦 Direct dependencies:{THEME.reset} {total_direct}")
        print(f"  {THEME.info}🔗 Transitive dependencies:{THEME.reset} {max(0, total_transitive)}")
        print(f"  {THEME.info}🛠️  Dev dependencies:{THEME.reset} {total_dev}")
        print(f"  {THEME.info}📊 Total dependencies:{THEME.reset} {total_all}")
        print()
        
        issue_count = (
            len(self._result.circular_dependencies)
            + len(self._result.ghost_dependencies)
            + len(self._result.version_conflicts)
        )
        
        if issue_count > 0:
            print(f"  {THEME.critical}⚠️  Total issues:{THEME.reset} {issue_count}")
            print(f"     - Circular dependencies: {len(self._result.circular_dependencies)}")
            print(f"     - Ghost dependencies: {len(self._result.ghost_dependencies)}")
            print(f"     - Version conflicts: {len(self._result.version_conflicts)}")
        else:
            print(f"  {THEME.direct_dep}✅ No issues detected{THEME.reset}")
        
        print()


def print_results(result: AnalysisResult) -> None:
    printer = TreePrinter(result)
    printer.print_tree()
    printer.print_issues()
    printer.print_statistics()
