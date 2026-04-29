import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from packaging.requirements import Requirement
from packaging.version import Version

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .base import Dependency, DependencyParser


class PythonParser(DependencyParser):
    def __init__(self, project_path: Path):
        super().__init__(project_path)
        self._site_packages_path: Optional[Path] = None
        self._venv_paths: List[Path] = []

    def parse(self) -> None:
        self._find_virtual_envs()
        self._parse_dependencies()

    def _find_virtual_envs(self) -> None:
        venv_indicators = [
            "venv",
            ".venv",
            "env",
            ".env",
            "virtualenv",
        ]
        
        for indicator in venv_indicators:
            venv_path = self.project_path / indicator
            if venv_path.exists() and venv_path.is_dir():
                self._venv_paths.append(venv_path)
                
                lib_paths = list(venv_path.glob("lib/python*/site-packages"))
                if lib_paths:
                    self._site_packages_path = lib_paths[0]
                    break

    def _parse_dependencies(self) -> None:
        reqs = self._parse_requirements_txt()
        pyproject_deps = self._parse_pyproject_toml()
        setup_deps = self._parse_setup_py()
        setup_cfg_deps = self._parse_setup_cfg()
        
        all_deps = {**reqs, **pyproject_deps, **setup_deps, **setup_cfg_deps}
        
        for name, dep in all_deps.items():
            if dep.is_dev:
                self._dev_deps[name] = dep
            else:
                self._direct_deps[name] = dep
            self._all_deps[name] = dep
        
        self._parse_transitive_dependencies()

    def _parse_requirements_txt(self) -> Dict[str, Dependency]:
        deps: Dict[str, Dependency] = {}
        
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            req = Requirement(line)
                            name = req.name.lower().replace("-", "_")
                            version_str = str(req.specifier) if req.specifier else "unknown"
                            actual_version = self._get_actual_version(name)
                            
                            dep = Dependency(
                                name=name,
                                version=actual_version or version_str,
                                specified_version=version_str,
                                is_direct=True,
                                is_dev=False,
                                path=self._get_dependency_path(name),
                            )
                            deps[name] = dep
                        except Exception:
                            pass
        
        dev_req_file = self.project_path / "requirements-dev.txt"
        if dev_req_file.exists():
            with open(dev_req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            req = Requirement(line)
                            name = req.name.lower().replace("-", "_")
                            version_str = str(req.specifier) if req.specifier else "unknown"
                            actual_version = self._get_actual_version(name)
                            
                            dep = Dependency(
                                name=name,
                                version=actual_version or version_str,
                                specified_version=version_str,
                                is_direct=True,
                                is_dev=True,
                                path=self._get_dependency_path(name),
                            )
                            deps[name] = dep
                        except Exception:
                            pass
        
        return deps

    def _parse_pyproject_toml(self) -> Dict[str, Dependency]:
        deps: Dict[str, Dependency] = {}
        
        pyproject_file = self.project_path / "pyproject.toml"
        if pyproject_file.exists():
            try:
                with open(pyproject_file, "rb") as f:
                    pyproject = tomllib.load(f)
                
                project = pyproject.get("project", {})
                dependencies = project.get("dependencies", [])
                optional_deps = project.get("optional-dependencies", {})
                
                for dep_str in dependencies:
                    try:
                        req = Requirement(dep_str)
                        name = req.name.lower().replace("-", "_")
                        version_str = str(req.specifier) if req.specifier else "unknown"
                        actual_version = self._get_actual_version(name)
                        
                        dep = Dependency(
                            name=name,
                            version=actual_version or version_str,
                            specified_version=version_str,
                            is_direct=True,
                            is_dev=False,
                            path=self._get_dependency_path(name),
                        )
                        deps[name] = dep
                    except Exception:
                        pass
                
                for group, dev_deps in optional_deps.items():
                    if "dev" in group.lower() or "test" in group.lower():
                        for dep_str in dev_deps:
                            try:
                                req = Requirement(dep_str)
                                name = req.name.lower().replace("-", "_")
                                version_str = str(req.specifier) if req.specifier else "unknown"
                                actual_version = self._get_actual_version(name)
                                
                                dep = Dependency(
                                    name=name,
                                    version=actual_version or version_str,
                                    specified_version=version_str,
                                    is_direct=True,
                                    is_dev=True,
                                    path=self._get_dependency_path(name),
                                )
                                deps[name] = dep
                            except Exception:
                                pass
                
                poetry = pyproject.get("tool", {}).get("poetry", {})
                if poetry:
                    poetry_deps = poetry.get("dependencies", {})
                    poetry_dev_deps = poetry.get("dev-dependencies", {})
                    
                    for name, version in poetry_deps.items():
                        if name != "python":
                            name = name.lower().replace("-", "_")
                            actual_version = self._get_actual_version(name)
                            
                            dep = Dependency(
                                name=name,
                                version=actual_version or version,
                                specified_version=version,
                                is_direct=True,
                                is_dev=False,
                                path=self._get_dependency_path(name),
                            )
                            deps[name] = dep
                    
                    for name, version in poetry_dev_deps.items():
                        name = name.lower().replace("-", "_")
                        actual_version = self._get_actual_version(name)
                        
                        dep = Dependency(
                            name=name,
                            version=actual_version or version,
                            specified_version=version,
                            is_direct=True,
                            is_dev=True,
                            path=self._get_dependency_path(name),
                        )
                        deps[name] = dep
                        
            except Exception:
                pass
        
        return deps

    def _parse_setup_py(self) -> Dict[str, Dependency]:
        deps: Dict[str, Dependency] = {}
        
        setup_file = self.project_path / "setup.py"
        if setup_file.exists():
            try:
                with open(setup_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                install_requires_match = re.search(
                    r'install_requires\s*=\s*\[([^\]]*)\]', content, re.DOTALL
                )
                if install_requires_match:
                    requires_str = install_requires_match.group(1)
                    dep_strs = re.findall(r"['\"]([^'\"]+)['\"]", requires_str)
                    
                    for dep_str in dep_strs:
                        try:
                            req = Requirement(dep_str)
                            name = req.name.lower().replace("-", "_")
                            version_str = str(req.specifier) if req.specifier else "unknown"
                            actual_version = self._get_actual_version(name)
                            
                            dep = Dependency(
                                name=name,
                                version=actual_version or version_str,
                                specified_version=version_str,
                                is_direct=True,
                                is_dev=False,
                                path=self._get_dependency_path(name),
                            )
                            deps[name] = dep
                        except Exception:
                            pass
                
                tests_require_match = re.search(
                    r'tests_require\s*=\s*\[([^\]]*)\]', content, re.DOTALL
                )
                if tests_require_match:
                    requires_str = tests_require_match.group(1)
                    dep_strs = re.findall(r"['\"]([^'\"]+)['\"]", requires_str)
                    
                    for dep_str in dep_strs:
                        try:
                            req = Requirement(dep_str)
                            name = req.name.lower().replace("-", "_")
                            version_str = str(req.specifier) if req.specifier else "unknown"
                            actual_version = self._get_actual_version(name)
                            
                            dep = Dependency(
                                name=name,
                                version=actual_version or version_str,
                                specified_version=version_str,
                                is_direct=True,
                                is_dev=True,
                                path=self._get_dependency_path(name),
                            )
                            deps[name] = dep
                        except Exception:
                            pass
                            
            except Exception:
                pass
        
        return deps

    def _parse_setup_cfg(self) -> Dict[str, Dependency]:
        deps: Dict[str, Dependency] = {}
        
        setup_cfg_file = self.project_path / "setup.cfg"
        if setup_cfg_file.exists():
            try:
                with open(setup_cfg_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                install_requires_match = re.search(
                    r'install_requires\s*=\s*(.*?)(?:\n\n|\n\[|\Z)', content, re.DOTALL
                )
                if install_requires_match:
                    requires_str = install_requires_match.group(1)
                    dep_strs = re.findall(r'^([^\s#][^\n]*)', requires_str, re.MULTILINE)
                    
                    for dep_str in dep_strs:
                        dep_str = dep_str.strip()
                        if dep_str and not dep_str.startswith("#"):
                            try:
                                req = Requirement(dep_str)
                                name = req.name.lower().replace("-", "_")
                                version_str = str(req.specifier) if req.specifier else "unknown"
                                actual_version = self._get_actual_version(name)
                                
                                dep = Dependency(
                                    name=name,
                                    version=actual_version or version_str,
                                    specified_version=version_str,
                                    is_direct=True,
                                    is_dev=False,
                                    path=self._get_dependency_path(name),
                                )
                                deps[name] = dep
                            except Exception:
                                pass
                            
            except Exception:
                pass
        
        return deps

    def _get_actual_version(self, name: str) -> Optional[str]:
        if not self._site_packages_path:
            return None
        
        import importlib.metadata
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
        
        dist_info_pattern = f"{name.replace('-', '_')}-*.dist-info"
        dist_infos = list(self._site_packages_path.glob(dist_info_pattern))
        if dist_infos:
            dist_info = dist_infos[0]
            metadata_file = dist_info / "METADATA"
            if metadata_file.exists():
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("Version:"):
                                return line.split(":", 1)[1].strip()
                except Exception:
                    pass
        
        return None

    def _get_dependency_path(self, name: str) -> Optional[Path]:
        if not self._site_packages_path:
            return None
        
        name_normalized = name.replace("-", "_").lower()
        
        pkg_path = self._site_packages_path / name_normalized
        if pkg_path.exists():
            return pkg_path
        
        pkg_path_hyphen = self._site_packages_path / name
        if pkg_path_hyphen.exists():
            return pkg_path_hyphen
        
        return None

    def _parse_transitive_dependencies(self) -> None:
        if not self._site_packages_path:
            return

        visited = set()
        
        def traverse(pkg_name: str, parent: Optional[Dependency] = None) -> None:
            pkg_name_normalized = pkg_name.replace("-", "_").lower()
            if pkg_name_normalized in visited:
                return
            visited.add(pkg_name_normalized)

            pkg_path = self._get_dependency_path(pkg_name)
            if not pkg_path:
                return

            requirements = self._get_package_requirements(pkg_name)
            
            if pkg_name_normalized not in self._all_deps:
                actual_version = self._get_actual_version(pkg_name)
                dep = Dependency(
                    name=pkg_name_normalized,
                    version=actual_version or "unknown",
                    specified_version=actual_version or "unknown",
                    is_direct=False,
                    is_dev=False,
                    path=pkg_path,
                )
                self._all_deps[pkg_name_normalized] = dep
                
                if parent:
                    parent.dependencies.append(dep)

            for req in requirements:
                traverse(req, self._all_deps.get(pkg_name_normalized))

        for dep in self._direct_deps.values():
            traverse(dep.name, dep)

        for dep in self._dev_deps.values():
            traverse(dep.name, dep)

    def _get_package_requirements(self, pkg_name: str) -> List[str]:
        import importlib.metadata
        requirements: List[str] = []
        
        try:
            dist = importlib.metadata.distribution(pkg_name)
            reqs = dist.requires
            if reqs:
                for req in reqs:
                    try:
                        parsed = Requirement(req.split(";")[0].strip())
                        requirements.append(parsed.name)
                    except Exception:
                        pass
        except importlib.metadata.PackageNotFoundError:
            pass
        
        return requirements

    def get_direct_dependencies(self) -> Dict[str, Dependency]:
        return self._direct_deps

    def get_all_dependencies(self) -> Dict[str, Dependency]:
        return self._all_deps

    def get_dev_dependencies(self) -> Dict[str, Dependency]:
        return self._dev_deps

    def get_source_files(self) -> List[Path]:
        patterns = ["**/*.py"]
        files: List[Path] = []
        for pattern in patterns:
            files.extend(self.project_path.glob(pattern))
        
        exclude_dirs = ["venv", ".venv", "env", ".env", "virtualenv", "node_modules", ".git", "__pycache__", "build", "dist"]
        exclude_files = ["setup.py", "conftest.py"]
        
        return [
            f for f in files
            if not any(exclude in str(f.parent) for exclude in exclude_dirs)
            and f.name not in exclude_files
        ]

    def get_imports_from_source(self, source_path: Path) -> Set[str]:
        imports: Set[str] = set()
        
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name.split(".")[0]
                        imports.add(name.lower().replace("-", "_"))
                elif isinstance(node, ast.ImportFrom):
                    if node.level > 0:
                        continue
                    if node.module:
                        name = node.module.split(".")[0]
                        imports.add(name.lower().replace("-", "_"))
        
        except (IOError, UnicodeDecodeError, SyntaxError):
            pass
        
        return imports
