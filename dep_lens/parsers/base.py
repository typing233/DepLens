from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class Dependency:
    name: str
    version: str
    specified_version: str
    is_direct: bool = False
    is_dev: bool = False
    dependencies: List["Dependency"] = field(default_factory=list)
    path: Optional[Path] = None

    def __hash__(self):
        return hash((self.name, self.version))

    def __eq__(self, other):
        if not isinstance(other, Dependency):
            return False
        return self.name == other.name and self.version == other.version


class DependencyParser(ABC):
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self._direct_deps: Dict[str, Dependency] = {}
        self._all_deps: Dict[str, Dependency] = {}
        self._dev_deps: Dict[str, Dependency] = {}

    @abstractmethod
    def parse(self) -> None:
        pass

    @abstractmethod
    def get_direct_dependencies(self) -> Dict[str, Dependency]:
        pass

    @abstractmethod
    def get_all_dependencies(self) -> Dict[str, Dependency]:
        pass

    @abstractmethod
    def get_dev_dependencies(self) -> Dict[str, Dependency]:
        pass

    @abstractmethod
    def get_source_files(self) -> List[Path]:
        pass

    @abstractmethod
    def get_imports_from_source(self, source_path: Path) -> Set[str]:
        pass

    @property
    def direct_dependencies(self) -> Dict[str, Dependency]:
        return self._direct_deps

    @property
    def all_dependencies(self) -> Dict[str, Dependency]:
        return self._all_deps

    @property
    def dev_dependencies(self) -> Dict[str, Dependency]:
        return self._dev_deps
