from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .detector import ProjectDetector, ProjectType
from .parsers.base import Dependency, DependencyParser
from .parsers.nodejs import NodeJSParser
from .parsers.python import PythonParser
from .parsers.rust import RustParser


@dataclass
class CircularDependency:
    path: List[str]
    severity: str = "high"


@dataclass
class GhostDependency:
    name: str
    used_in: List[Path]
    severity: str = "medium"


@dataclass
class VersionConflict:
    name: str
    versions: Dict[str, str]
    severity: str = "high"


@dataclass
class AnalysisResult:
    project_path: Path
    project_type: ProjectType
    indicators: List[str]
    direct_dependencies: Dict[str, Dependency] = field(default_factory=dict)
    all_dependencies: Dict[str, Dependency] = field(default_factory=dict)
    dev_dependencies: Dict[str, Dependency] = field(default_factory=dict)
    circular_dependencies: List[CircularDependency] = field(default_factory=list)
    ghost_dependencies: List[GhostDependency] = field(default_factory=list)
    version_conflicts: List[VersionConflict] = field(default_factory=list)


class DependencyAnalyzer:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self._detector: Optional[ProjectDetector] = None
        self._parser: Optional[DependencyParser] = None
        self._result: Optional[AnalysisResult] = None

    def analyze(self) -> AnalysisResult:
        self._detector = ProjectDetector(self.project_path)
        project_type = self._detector.detect()

        self._result = AnalysisResult(
            project_path=self.project_path,
            project_type=project_type,
            indicators=self._detector.indicators,
        )

        if project_type == ProjectType.NODEJS:
            self._parser = NodeJSParser(self.project_path)
        elif project_type == ProjectType.PYTHON:
            self._parser = PythonParser(self.project_path)
        elif project_type == ProjectType.RUST:
            self._parser = RustParser(self.project_path)
        else:
            return self._result

        self._parser.parse()
        
        self._result.direct_dependencies = self._parser.get_direct_dependencies()
        self._result.all_dependencies = self._parser.get_all_dependencies()
        self._result.dev_dependencies = self._parser.get_dev_dependencies()

        self._detect_circular_dependencies()
        self._detect_ghost_dependencies()
        self._detect_version_conflicts()

        return self._result

    def _detect_circular_dependencies(self) -> None:
        if not self._result or not self._parser:
            return

        visited: Set[str] = set()
        recursion_stack: Set[str] = set()
        path: List[str] = []

        def has_cycle(dep_name: str, dep_map: Dict[str, Dependency]) -> bool:
            if dep_name in recursion_stack:
                idx = path.index(dep_name)
                cycle = path[idx:] + [dep_name]
                self._result.circular_dependencies.append(
                    CircularDependency(path=cycle, severity="high")
                )
                return True

            if dep_name in visited:
                return False

            visited.add(dep_name)
            recursion_stack.add(dep_name)
            path.append(dep_name)

            if dep_name in dep_map:
                dep = dep_map[dep_name]
                for child_dep in dep.dependencies:
                    if has_cycle(child_dep.name, dep_map):
                        recursion_stack.remove(dep_name)
                        path.pop()
                        return True

            recursion_stack.remove(dep_name)
            path.pop()
            return False

        all_deps = self._result.all_dependencies
        for dep_name in all_deps:
            if dep_name not in visited:
                has_cycle(dep_name, all_deps)

    def _detect_ghost_dependencies(self) -> None:
        if not self._result or not self._parser:
            return

        declared_deps: Set[str] = set()
        for dep_name in self._result.direct_dependencies:
            declared_deps.add(dep_name.lower().replace("-", "_"))
        for dep_name in self._result.dev_dependencies:
            declared_deps.add(dep_name.lower().replace("-", "_"))

        source_files = self._parser.get_source_files()
        used_deps: Dict[str, List[Path]] = {}

        for source_file in source_files:
            imports = self._parser.get_imports_from_source(source_file)
            for imp in imports:
                imp_normalized = imp.lower().replace("-", "_")
                if imp_normalized not in used_deps:
                    used_deps[imp_normalized] = []
                if source_file not in used_deps[imp_normalized]:
                    used_deps[imp_normalized].append(source_file)

        std_modules = self._get_standard_modules()
        
        for dep_name, files in used_deps.items():
            dep_normalized = dep_name.lower().replace("-", "_")
            if (
                dep_normalized not in declared_deps
                and dep_normalized not in std_modules
            ):
                self._result.ghost_dependencies.append(
                    GhostDependency(
                        name=dep_name,
                        used_in=files,
                        severity="medium",
                    )
                )

    def _get_standard_modules(self) -> Set[str]:
        if not self._detector:
            return set()

        project_type = self._detector.project_type

        if project_type == ProjectType.PYTHON:
            return self._get_python_std_modules()
        elif project_type == ProjectType.NODEJS:
            return self._get_nodejs_std_modules()
        elif project_type == ProjectType.RUST:
            return self._get_rust_std_modules()
        
        return set()

    def _get_python_std_modules(self) -> Set[str]:
        return {
            "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
            "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
            "bz2", "cProfile", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code",
            "codecs", "codeop", "collections", "colorsys", "compileall", "concurrent", "configparser",
            "contextlib", "contextvars", "copy", "copyreg", "crypt", "csv", "ctypes", "curses",
            "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis", "distutils", "doctest",
            "email", "encodings", "ensurepip", "enum", "errno", "faulthandler", "fcntl", "filecmp",
            "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt", "getpass",
            "gettext", "glob", "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html",
            "http", "imaplib", "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools",
            "json", "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap",
            "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing",
            "netrc", "nis", "nntplib", "ntpath", "numbers", "operator", "optparse", "os", "ossaudiodev",
            "parser", "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
            "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd", "py_compile",
            "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib", "resource",
            "rlcompleter", "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil",
            "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3",
            "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess", "sunau", "symbol",
            "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
            "test", "textwrap", "threading", "time", "timeit", "tkinter", "token", "tokenize", "trace",
            "traceback", "tracemalloc", "tty", "turtle", "types", "typing", "unicodedata", "unittest", "urllib",
            "uu", "uuid", "venv", "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
            "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
        }

    def _get_nodejs_std_modules(self) -> Set[str]:
        return {
            "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants",
            "crypto", "dgram", "diagnostics_channel", "dns", "domain", "events", "fs", "http",
            "http2", "https", "inspector", "module", "net", "os", "path", "perf_hooks", "process",
            "punycode", "querystring", "readline", "repl", "stream", "string_decoder", "sys", "timers",
            "tls", "trace_events", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib",
        }

    def _get_rust_std_modules(self) -> Set[str]:
        return {
            "std", "core", "alloc", "proc_macro",
        }

    def _detect_version_conflicts(self) -> None:
        if not self._result or not self._parser:
            return

        version_map: Dict[str, Set[str]] = {}

        def collect_versions(dep: Dependency) -> None:
            name = dep.name
            version = dep.version
            
            if name not in version_map:
                version_map[name] = set()
            if version and version != "unknown":
                version_map[name].add(version)

            for child_dep in dep.dependencies:
                collect_versions(child_dep)

        for dep in self._result.all_dependencies.values():
            collect_versions(dep)

        for name, versions in version_map.items():
            if len(versions) > 1:
                self._result.version_conflicts.append(
                    VersionConflict(
                        name=name,
                        versions={v: "found" for v in versions},
                        severity="high",
                    )
                )

    @property
    def result(self) -> Optional[AnalysisResult]:
        return self._result


def analyze_project(project_path: Path) -> AnalysisResult:
    analyzer = DependencyAnalyzer(project_path)
    return analyzer.analyze()
