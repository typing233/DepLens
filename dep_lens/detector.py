from enum import Enum
from pathlib import Path
from typing import Optional, List


class ProjectType(Enum):
    NODEJS = "nodejs"
    PYTHON = "python"
    RUST = "rust"
    UNKNOWN = "unknown"


class ProjectDetector:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self._type: Optional[ProjectType] = None
        self._indicators: List[str] = []

    def detect(self) -> ProjectType:
        if self._type is not None:
            return self._type

        if self._check_nodejs():
            self._type = ProjectType.NODEJS
        elif self._check_python():
            self._type = ProjectType.PYTHON
        elif self._check_rust():
            self._type = ProjectType.RUST
        else:
            self._type = ProjectType.UNKNOWN

        return self._type

    def _check_nodejs(self) -> bool:
        package_json = self.project_path / "package.json"
        if package_json.exists():
            self._indicators.append("package.json")
            return True
        return False

    def _check_python(self) -> bool:
        indicators = [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "Pipfile",
            "poetry.lock",
        ]
        found = []
        for indicator in indicators:
            file_path = self.project_path / indicator
            if file_path.exists():
                found.append(indicator)
        if found:
            self._indicators.extend(found)
            return True
        return False

    def _check_rust(self) -> bool:
        cargo_toml = self.project_path / "Cargo.toml"
        if cargo_toml.exists():
            self._indicators.append("Cargo.toml")
            return True
        return False

    @property
    def project_type(self) -> Optional[ProjectType]:
        return self._type

    @property
    def indicators(self) -> List[str]:
        return self._indicators

    def get_type_str(self) -> str:
        if self._type == ProjectType.NODEJS:
            return "Node.js"
        elif self._type == ProjectType.PYTHON:
            return "Python"
        elif self._type == ProjectType.RUST:
            return "Rust"
        else:
            return "Unknown"


def detect_project_type(project_path: Path) -> ProjectDetector:
    detector = ProjectDetector(project_path)
    detector.detect()
    return detector
