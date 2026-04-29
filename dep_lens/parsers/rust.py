import re
from pathlib import Path
from typing import Dict, List, Optional, Set

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .base import Dependency, DependencyParser


class RustParser(DependencyParser):
    def __init__(self, project_path: Path):
        super().__init__(project_path)
        self._cargo_lock: Dict = {}
        self._target_dir: Optional[Path] = None

    def parse(self) -> None:
        self._parse_cargo_toml()
        self._parse_cargo_lock()
        self._find_target_dir()
        self._build_dependency_tree()

    def _parse_cargo_toml(self) -> None:
        cargo_toml = self.project_path / "Cargo.toml"
        if cargo_toml.exists():
            try:
                with open(cargo_toml, "rb") as f:
                    self._cargo_toml = tomllib.load(f)
            except Exception:
                self._cargo_toml = {}

    def _parse_cargo_lock(self) -> None:
        cargo_lock = self.project_path / "Cargo.lock"
        if cargo_lock.exists():
            try:
                with open(cargo_lock, "rb") as f:
                    self._cargo_lock = tomllib.load(f)
            except Exception:
                self._cargo_lock = {}

    def _find_target_dir(self) -> None:
        target_dir = self.project_path / "target"
        if target_dir.exists():
            self._target_dir = target_dir

    def _build_dependency_tree(self) -> None:
        deps = self._cargo_toml.get("dependencies", {})
        dev_deps = self._cargo_toml.get("dev-dependencies", {})
        build_deps = self._cargo_toml.get("build-dependencies", {})

        for name, version in deps.items():
            dep = self._create_dependency(name, version, is_direct=True, is_dev=False)
            self._direct_deps[name] = dep
            self._all_deps[name] = dep

        for name, version in dev_deps.items():
            dep = self._create_dependency(name, version, is_direct=True, is_dev=True)
            self._dev_deps[name] = dep
            if name not in self._all_deps:
                self._all_deps[name] = dep

        for name, version in build_deps.items():
            dep = self._create_dependency(name, version, is_direct=True, is_dev=True)
            if name not in self._dev_deps:
                self._dev_deps[name] = dep
            if name not in self._all_deps:
                self._all_deps[name] = dep

        self._parse_transitive_dependencies_from_lock()

    def _create_dependency(
        self, name: str, version_spec: str | Dict, is_direct: bool = False, is_dev: bool = False
    ) -> Dependency:
        if isinstance(version_spec, dict):
            version = version_spec.get("version", "")
            specified_version = version or str(version_spec)
        else:
            version = version_spec
            specified_version = version_spec

        actual_version = self._get_actual_version(name)
        dep_path = self._get_dependency_path(name)
        
        return Dependency(
            name=name,
            version=actual_version or version,
            specified_version=specified_version,
            is_direct=is_direct,
            is_dev=is_dev,
            path=dep_path,
        )

    def _get_actual_version(self, name: str) -> Optional[str]:
        if not self._cargo_lock:
            return None

        packages = self._cargo_lock.get("package", [])
        for pkg in packages:
            if pkg.get("name") == name:
                return pkg.get("version")
        return None

    def _get_dependency_path(self, name: str) -> Optional[Path]:
        if not self._target_dir:
            return None
        
        cargo_home = Path.home() / ".cargo" / "registry" / "src"
        if cargo_home.exists():
            for registry_dir in cargo_home.iterdir():
                if registry_dir.is_dir():
                    pkg_pattern = f"{name}-*"
                    pkg_dirs = list(registry_dir.glob(pkg_pattern))
                    if pkg_dirs:
                        return pkg_dirs[0]
        
        return None

    def _parse_transitive_dependencies_from_lock(self) -> None:
        if not self._cargo_lock:
            return

        packages = self._cargo_lock.get("package", [])
        pkg_map: Dict[str, Dict] = {}
        
        for pkg in packages:
            name = pkg.get("name", "")
            version = pkg.get("version", "")
            key = f"{name}@{version}"
            pkg_map[key] = pkg

        visited = set()

        def traverse(pkg_name: str, pkg_version: str, parent: Optional[Dependency] = None) -> None:
            key = f"{pkg_name}@{pkg_version}"
            if key in visited:
                return
            visited.add(key)

            pkg = pkg_map.get(key)
            if not pkg:
                return

            if pkg_name not in self._all_deps:
                dep = Dependency(
                    name=pkg_name,
                    version=pkg_version,
                    specified_version=pkg_version,
                    is_direct=False,
                    is_dev=False,
                    path=self._get_dependency_path(pkg_name),
                )
                self._all_deps[pkg_name] = dep

                if parent:
                    parent.dependencies.append(dep)

            dependencies = pkg.get("dependencies", [])
            for dep_str in dependencies:
                parts = dep_str.split()
                dep_name = parts[0]
                dep_version = parts[1] if len(parts) > 1 else ""
                
                if dep_name in self._all_deps:
                    current_dep = self._all_deps[dep_name]
                    traverse(dep_name, current_dep.version, current_dep)
                else:
                    traverse(dep_name, dep_version, self._all_deps.get(pkg_name))

        for dep in self._direct_deps.values():
            traverse(dep.name, dep.version, dep)

        for dep in self._dev_deps.values():
            traverse(dep.name, dep.version, dep)

    def get_direct_dependencies(self) -> Dict[str, Dependency]:
        return self._direct_deps

    def get_all_dependencies(self) -> Dict[str, Dependency]:
        return self._all_deps

    def get_dev_dependencies(self) -> Dict[str, Dependency]:
        return self._dev_deps

    def get_source_files(self) -> List[Path]:
        patterns = ["**/*.rs"]
        files: List[Path] = []
        for pattern in patterns:
            files.extend(self.project_path.glob(pattern))
        
        exclude_dirs = ["target", ".git", "node_modules"]
        
        return [
            f for f in files
            if not any(exclude in str(f.parent) for exclude in exclude_dirs)
        ]

    def get_imports_from_source(self, source_path: Path) -> Set[str]:
        imports: Set[str] = set()
        
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            use_patterns = [
                r'use\s+(?:(?:mut|const|pub)\s+)?(\w+(?:::\w+)*)',
                r'use\s+(?:(?:mut|const|pub)\s+)?\{([^}]+)\}',
                r'extern\s+crate\s+(\w+)',
            ]
            
            for pattern in use_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, str):
                        parts = match.split("::")
                        if parts and parts[0] not in ["self", "super", "crate", "std", "core", "alloc"]:
                            imports.add(parts[0])
                    elif isinstance(match, tuple):
                        for item in match:
                            parts = item.split("::")
                            if parts and parts[0] not in ["self", "super", "crate", "std", "core", "alloc"]:
                                imports.add(parts[0])
        
        except (IOError, UnicodeDecodeError):
            pass
        
        return imports
