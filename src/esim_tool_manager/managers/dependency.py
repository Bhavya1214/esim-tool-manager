import shutil
from typing import Any

from ..core.logger import get_logger
from ..core.models import InstallMethod, OSType

log = get_logger(__name__)


class DependencyChecker:
    def __init__(self, platform_mgr: Any) -> None:
        self.platform = platform_mgr

    def check_system_deps(self, deps: list[str]) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for dep in deps:
            found = shutil.which(dep) is not None
            if not found and self.platform.os_type == OSType.LINUX:
                code, _, _ = self.platform.run_command(["dpkg", "-l", dep])
                if code == 0:
                    found = True
                else:
                    code, _, _ = self.platform.run_command(["pkg-config", "--exists", dep])
                    if code == 0:
                        found = True
            results[dep] = found
        return results

    @staticmethod
    def check_python_deps(requirements: list[str]) -> dict[str, bool]:
        import importlib.util

        results: dict[str, bool] = {}
        for req in requirements:
            pkg_name = req.split(">")[0].split("=")[0].split("<")[0].strip()
            spec = importlib.util.find_spec(pkg_name)
            results[req] = spec is not None
        return results

    def get_missing_deps_report(self, deps: list[str]) -> str:
        results = self.check_system_deps(deps)
        missing = [k for k, v in results.items() if not v]
        if not missing:
            return "All dependencies satisfied."

        report = "Missing Dependencies:\n"
        for m in missing:
            hint = self._get_install_hint(m)
            report += f"  - {m}: {hint}\n"
        return report

    def _get_install_hint(self, dep: str) -> str:
        if self.platform.os_type == OSType.LINUX:
            if self.platform.has_manager(InstallMethod.APT):
                return f"Run: sudo apt install {dep}"
        elif self.platform.os_type == OSType.WINDOWS:
            if self.platform.has_manager(InstallMethod.CHOCOLATEY):
                return f"Run: choco install {dep}"
            if self.platform.has_manager(InstallMethod.WINGET):
                return f"Run: winget install {dep}"
        return "Manual installation required."
