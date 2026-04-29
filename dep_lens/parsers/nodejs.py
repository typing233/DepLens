import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .base import Dependency, DependencyParser


class NodeJSParser(DependencyParser):
    def __init__(self, project_path: Path):
        super().__init__(project_path)
        self._package_json: Dict = {}
        self._node_modules_path: Optional[Path] = None

    def parse(self) -> None:
        self._parse_package_json()
        self._find_node_modules()
        self._parse_dependencies()

    def _parse_package_json(self) -> None:
        package_json_path = self.project_path / "package.json"
        if package_json_path.exists():
            with open(package_json_path, "r", encoding="utf-8") as f:
                self._package_json = json.load(f)

    def _find_node_modules(self) -> None:
        node_modules = self.project_path / "node_modules"
        if node_modules.exists():
            self._node_modules_path = node_modules

    def _parse_dependencies(self) -> None:
        deps = self._package_json.get("dependencies", {})
        dev_deps = self._package_json.get("devDependencies", {})

        for name, version in deps.items():
            dep = self._create_dependency(name, version, is_direct=True, is_dev=False)
            self._direct_deps[name] = dep
            self._all_deps[name] = dep

        for name, version in dev_deps.items():
            dep = self._create_dependency(name, version, is_direct=True, is_dev=True)
            self._dev_deps[name] = dep
            if name not in self._all_deps:
                self._all_deps[name] = dep

        self._parse_transitive_dependencies()

    def _create_dependency(
        self, name: str, version: str, is_direct: bool = False, is_dev: bool = False
    ) -> Dependency:
        actual_version = self._get_actual_version(name)
        dep_path = self._get_dependency_path(name)
        
        return Dependency(
            name=name,
            version=actual_version or version,
            specified_version=version,
            is_direct=is_direct,
            is_dev=is_dev,
            path=dep_path,
        )

    def _get_actual_version(self, name: str) -> Optional[str]:
        if not self._node_modules_path:
            return None
        
        pkg_path = self._node_modules_path / name / "package.json"
        if pkg_path.exists():
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg = json.load(f)
                return pkg.get("version")
        return None

    def _get_dependency_path(self, name: str) -> Optional[Path]:
        if not self._node_modules_path:
            return None
        
        dep_path = self._node_modules_path / name
        if dep_path.exists():
            return dep_path
        return None

    def _parse_transitive_dependencies(self) -> None:
        if not self._node_modules_path:
            return

        visited = set()
        
        def traverse(pkg_path: Path, parent: Optional[Dependency] = None) -> None:
            if pkg_path in visited:
                return
            visited.add(pkg_path)

            pkg_json = pkg_path / "package.json"
            if not pkg_json.exists():
                return

            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
            except (json.JSONDecodeError, IOError):
                return

            name = pkg.get("name", "")
            version = pkg.get("version", "")
            specified_version = pkg.get("version", "")

            if name and name not in self._all_deps:
                dep = Dependency(
                    name=name,
                    version=version,
                    specified_version=specified_version,
                    is_direct=False,
                    is_dev=False,
                    path=pkg_path,
                )
                self._all_deps[name] = dep

                if parent:
                    parent.dependencies.append(dep)

            deps = pkg.get("dependencies", {})
            for dep_name, _ in deps.items():
                dep_path = self._node_modules_path / dep_name
                if dep_path.exists():
                    current_dep = self._all_deps.get(dep_name)
                    if current_dep:
                        traverse(dep_path, current_dep)

        for dep in self._direct_deps.values():
            if dep.path and dep.path.exists():
                traverse(dep.path, dep)

        for dep in self._dev_deps.values():
            if dep.path and dep.path.exists():
                traverse(dep.path, dep)

    def get_direct_dependencies(self) -> Dict[str, Dependency]:
        return self._direct_deps

    def get_all_dependencies(self) -> Dict[str, Dependency]:
        return self._all_deps

    def get_dev_dependencies(self) -> Dict[str, Dependency]:
        return self._dev_deps

    def get_source_files(self) -> List[Path]:
        patterns = ["**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        files: List[Path] = []
        for pattern in patterns:
            files.extend(self.project_path.glob(pattern))
        
        exclude_dirs = ["node_modules", ".git", "dist", "build"]
        return [
            f for f in files
            if not any(exclude in str(f.parent) for exclude in exclude_dirs)
        ]

    def get_imports_from_source(self, source_path: Path) -> Set[str]:
        imports: Set[str] = set()
        
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            import_patterns = [
                r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            ]
            
            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if not match.startswith(".") and not match.startswith("/"):
                        parts = match.split("/")
                        if match.startswith("@") and len(parts) >= 2:
                            imports.add(f"{parts[0]}/{parts[1]}")
                        else:
                            imports.add(parts[0])
        
        except (IOError, UnicodeDecodeError):
            pass
        
        return imports
