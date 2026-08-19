import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .logger import get_logger
from .models import InstallMethod, OSType

log = get_logger(__name__)


class PlatformManager:
    _instance: Optional["PlatformManager"] = None
    _os_type: OSType = OSType.UNKNOWN
    _package_managers: dict = {}

    def __new__(cls) -> "PlatformManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._detect_os()
        self._detect_package_managers()

    def _detect_os(self) -> None:
        if sys.platform.startswith("linux"):
            self._os_type = OSType.LINUX
        elif sys.platform == "win32":
            self._os_type = OSType.WINDOWS
        elif sys.platform == "darwin":
            self._os_type = OSType.MACOS
        else:
            self._os_type = OSType.UNKNOWN
        log.debug(f"Detected OS: {self._os_type.value}")

    def _detect_package_managers(self) -> None:
        managers = {
            InstallMethod.APT: "apt",
            InstallMethod.CHOCOLATEY: "choco",
            InstallMethod.WINGET: "winget",
            InstallMethod.HOMEBREW: "brew",
        }
        for method, cmd in managers.items():
            if shutil.which(cmd):
                self._package_managers[method] = cmd
                log.debug(f"Found package manager: {method.value} ({cmd})")

    @property
    def os_type(self) -> OSType:
        return self._os_type

    @property
    def available_managers(self) -> list[InstallMethod]:
        return list(self._package_managers.keys())

    def has_manager(self, method: InstallMethod) -> bool:
        return method in self._package_managers

    def get_install_cmd(self, method: InstallMethod, packages: list[str]) -> list[str]:
        base_cmd = self._package_managers.get(method)
        if not base_cmd:
            raise RuntimeError(f"Package manager {method.value} not found on system.")

        if method == InstallMethod.APT:
            return [
                "sudo",
                base_cmd,
                "update",
                "&&",
                "sudo",
                base_cmd,
                "install",
                "-y",
            ] + packages
        if method == InstallMethod.CHOCOLATEY:
            return [base_cmd, "install", "-y"] + packages
        if method == InstallMethod.WINGET:
            cmd = [base_cmd, "install"]
            for pkg in packages:
                cmd.extend(["--id", pkg])
            cmd.extend(["--accept-source-agreements", "--accept-package-agreements", "--silent"])
            return cmd
        if method == InstallMethod.HOMEBREW:
            return [base_cmd, "install"] + packages
        raise NotImplementedError(f"Install command for {method} not implemented.")

    def run_command(
        self,
        cmd: list[str] | str,
        shell: bool = False,
        cwd: Optional[Path] = None,
        timeout: int = 300,
    ) -> tuple[int, str, str]:
        log.debug(f"Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        try:
            if isinstance(cmd, str) and shell:
                pass
            elif isinstance(cmd, list) and "&&" in cmd:
                idx = cmd.index("&&")
                cmd1 = cmd[:idx]
                cmd2 = cmd[idx + 1 :]
                self.run_command(cmd1, shell=True)
                return self.run_command(cmd2, shell=shell, cwd=cwd, timeout=timeout)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=shell,
                cwd=cwd,
                timeout=timeout,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out ({timeout}s)"
        except Exception as e:
            return -1, "", str(e)

    @staticmethod
    def find_binary(binary_name: str) -> Optional[Path]:
        path = shutil.which(binary_name)
        return Path(path) if path else None

    @staticmethod
    def get_env_path() -> str:
        return os.environ.get("PATH", "")

    def add_to_path_permanent(self, path: Path) -> None:
        path_str = str(path)
        if self._os_type == OSType.WINDOWS:
            log.warning(
                f'Windows: Please run manually to persist PATH: setx PATH "%PATH%;{path_str}"'
            )
        else:
            rc_file = Path.home() / ".bashrc"
            if not rc_file.exists():
                rc_file = Path.home() / ".profile"
            entry = f'\nexport PATH="{path_str}:$PATH" # Added by Esim Tool-Manager'
            try:
                content = rc_file.read_text()
                if path_str not in content:
                    rc_file.write_text(content + entry)
                    log.info(f"Added {path_str} to {rc_file}. Run 'source {rc_file}' to apply.")
            except Exception as e:
                log.error(f"Failed to update {rc_file}: {e}")


platform = PlatformManager()
