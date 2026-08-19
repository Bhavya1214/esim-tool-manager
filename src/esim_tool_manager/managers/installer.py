import os
import re
import shutil
import tarfile
import zipfile
from contextlib import suppress
from pathlib import Path
from typing import Any

import requests
from rich.console import Console
from tqdm import tqdm

from ..core.logger import get_logger
from ..core.models import (
    InstalledToolInfo,
    InstallMethod,
    OSType,
    PlatformConfig,
    ToolDefinition,
    ToolStatus,
    ToolVersion,
)
from ..managers.base import BaseManager
from ..managers.configurator import Configurator
from ..repositories.tool_repo import repo

console = Console()
log = get_logger(__name__)


class Installer(BaseManager):
    def __init__(self, platform_mgr: Any) -> None:
        super().__init__(platform_mgr)
        self.configurator = Configurator(platform_mgr, self)

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Use install_tool() directly.")

    def install_tool(self, tool_id: str, version: str | None = None, force: bool = False) -> bool:
        tool_def = repo.get_tool(tool_id)
        if not tool_def:
            log.error(f"Tool '{tool_id}' not found in repository.")
            return False

        target_version = version or tool_def.recommended_version

        try:
            tool_ver = tool_def.get_version(target_version)
        except ValueError as e:
            log.error(e)
            return False

        plat_config = tool_ver.get_platform_config(self.platform.os_type)

        log.info(
            f"Installing {tool_def.name} v{target_version}via {plat_config.install_method.value}..."
        )

        if not self._check_dependencies(tool_ver.dependencies):
            log.error("Dependency check failed. Aborting install.")
            return False

        success = False
        method = plat_config.install_method

        try:
            if method == InstallMethod.APT:
                success = self._install_apt(plat_config.packages)
            elif method == InstallMethod.CHOCOLATEY:
                success = self._install_choco(plat_config.packages)
            elif method == InstallMethod.WINGET:
                success = self._install_winget(plat_config.packages)
            elif method == InstallMethod.HOMEBREW:
                success = self._install_brew(plat_config.packages)
            elif method == InstallMethod.COMPILE:
                success = self._install_compile(tool_def, tool_ver, plat_config)
            elif method == InstallMethod.MANUAL:
                success = self._install_manual(tool_def, tool_ver, plat_config)
            else:
                log.error(f"Unsupported install method: {method}")
                return False
        except Exception as e:
            log.exception(f"Installation crashed: {e}")
            return False

        if success:
            log.info(f"{tool_def.name} installed successfully.")
            installed_info = self.verify_installation(tool_id, target_version)
            if installed_info:
                self.configurator.configure_tool(installed_info)
            return True
        else:
            log.error(f"Failed to install {tool_def.name}.")
            return False

    def _check_dependencies(self, deps: list[str]) -> bool:
        if not deps:
            return True
        log.info(f"Checking dependencies: {deps}")
        missing = []
        for dep in deps:
            if not shutil.which(dep) and not self._is_pkg_installed(dep):
                missing.append(dep)
        if missing:
            log.warning(
                f"Missing dependencies: {missing}.Attempting auto-install via system pkg manager..."
            )
            if self.platform.os_type == OSType.LINUX and self.platform.has_manager(
                InstallMethod.APT
            ):
                self._install_apt(missing)
            still_missing = [
                d for d in missing if not shutil.which(d) and not self._is_pkg_installed(d)
            ]
            if still_missing:
                log.error(f"Could not satisfy dependencies: {still_missing}")
                return False
        return True

    def _is_pkg_installed(self, pkg: str) -> bool:
        if self.platform.os_type == OSType.LINUX:
            code, out, _ = self.platform.run_command(["dpkg", "-l", pkg])
            return code == 0 and "ii" in out
        return False

    def _install_apt(self, packages: list[str]) -> bool:
        if not self.platform.has_manager(InstallMethod.APT):
            return False
        code, _, err = self.platform.run_command(["sudo", "apt", "update"], shell=True)
        if code != 0:
            log.warning(f"APT update failed: {err}")
        cmd = ["sudo", "apt", "install", "-y"] + packages
        code, out, err = self.platform.run_command(cmd, shell=True)
        if code != 0:
            log.error(f"APT Install Error: {err}")
        return code == 0

    def _install_choco(self, packages: list[str]) -> bool:
        if not self.platform.has_manager(InstallMethod.CHOCOLATEY):
            return False
        for pkg in packages:
            code, out, err = self.platform.run_command(["choco", "install", "-y", pkg])
            if code != 0:
                log.error(f"Choco Error ({pkg}): {err}")
                return False
        return True

    def _install_winget(self, packages: list[str]) -> bool:
        if not self.platform.has_manager(InstallMethod.WINGET):
            return False
        for pkg in packages:
            cmd = [
                "winget",
                "install",
                "--id",
                pkg,
                "--silent",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ]
            code, out, err = self.platform.run_command(cmd)
            if code != 0:
                log.error(f"Winget Error ({pkg}): {err}")
                return False
        return True

    def _install_brew(self, packages: list[str]) -> bool:
        if not self.platform.has_manager(InstallMethod.HOMEBREW):
            return False
        cmd = ["brew", "install"] + packages
        code, out, err = self.platform.run_command(cmd)
        if code != 0:
            log.error(f"Brew Error: {err}")
        return code == 0

    def _install_compile(
        self, tool_def: ToolDefinition, tool_ver: ToolVersion, cfg: PlatformConfig
    ) -> bool:
        log.info(f"Compiling {tool_def.name} from source...")
        if not cfg.source_url:
            log.error("No source_url defined for compile method.")
            return False

        build_dir = Path.home() / ".esim_tool_manager" / "build" / tool_def.name
        build_dir.mkdir(parents=True, exist_ok=True)

        if cfg.build_deps:
            log.info(f"Installing build dependencies: {cfg.build_deps}")
            if not self._install_apt(cfg.build_deps):
                return False

        src_dir = build_dir / "src"
        if cfg.source_url.endswith(".git"):
            if not (src_dir / ".git").exists():
                code, _, err = self.platform.run_command(
                    ["git", "clone", cfg.source_url, str(src_dir)]
                )
                if code != 0:
                    log.error(f"Git clone failed: {err}")
                    return False
            else:
                self.platform.run_command(["git", "-C", str(src_dir), "pull"])
        else:
            log.error("Only git source_url supported in this prototype for compile method.")
            return False

        for install_cmd in cfg.build_commands:
            log.info(f"Running: {install_cmd}")
            code, out, err = self.platform.run_command(install_cmd, shell=True, timeout=600)
            if code != 0:
                log.error(f"Build failed at step: {install_cmd}\n{err}")
                return False
        return True

    def _install_manual(
        self, tool_def: ToolDefinition, tool_ver: ToolVersion, cfg: PlatformConfig
    ) -> bool:
        if not cfg.manual_url:
            log.error("Manual install selected but no manual_url provided.")
            return False

        log.info(f"Downloading {tool_def.name} from {cfg.manual_url}...")
        dest_dir = Path.home() / ".esim_tool_manager" / "pkg" / tool_def.name
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            response = requests.get(cfg.manual_url, stream=True, timeout=60)
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            filename = cfg.manual_url.split("/")[-1].split("?")[0]
            filepath = dest_dir / filename

            with (
                open(filepath, "wb") as f,
                tqdm(total=total, unit="B", unit_scale=True, desc=filename, leave=False) as pbar,
            ):
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))
        except Exception as e:
            log.error(f"Download failed: {e}")
            return False

        if self.platform.os_type == OSType.WINDOWS and filename.endswith((".exe", ".msi")):
            log.info("Checking for existing installation...")
            possible_roots = [
                Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "KiCad",
                Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "KiCad",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "KiCad",
            ]

            pf = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            kicad_root = pf / "KiCad"
            if kicad_root.exists():
                for ver_dir in kicad_root.iterdir():
                    if ver_dir.is_dir():
                        possible_roots.append(ver_dir / "bin")

            found_bin = None
            for root in possible_roots:
                candidate = root / cfg.binary_name
                if candidate.exists():
                    found_bin = candidate
                    log.info(f"Found existing installation at: {found_bin}")
                    break

            if not found_bin:
                log.info(f"Running Windows installer silently: {filename}")
                install_cmd = []
                if filename.endswith(".msi"):
                    install_cmd = [
                        "msiexec",
                        "/i",
                        str(filepath),
                        "/qn",
                        "/norestart",
                        "ALLUSERS=1",
                    ]
                else:
                    install_cmd = [str(filepath), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]

                log.info(f"Executing: {' '.join(install_cmd)}")
                code, out, err = self.platform.run_command(install_cmd, shell=True, timeout=600)
                if code != 0:
                    log.error(f"Installer failed (code {code}): {err}")
                    return False

                log.info("Installer completed. Locating installed binary...")
                for root in possible_roots:
                    candidate = root / cfg.binary_name
                    if candidate.exists():
                        found_bin = candidate
                        break

                if not found_bin:
                    log.error(
                        f"Could not locate installed binary '{cfg.binary_name}' after install."
                    )
                    return False

            return self._create_shim_and_finish(found_bin, cfg)

        log.info("Extracting archive...")
        extracted_path = dest_dir / "extracted"
        if extracted_path.exists():
            shutil.rmtree(extracted_path)
        extracted_path.mkdir()

        try:
            if filename.endswith(".zip"):
                with zipfile.ZipFile(filepath, "r") as zf:
                    zf.extractall(extracted_path)
            elif filename.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar.bz2")):
                with tarfile.open(filepath, "r:*") as tf:
                    tf.extractall(extracted_path)
            else:
                shutil.copy(filepath, extracted_path / filename)
        except Exception as e:
            log.error(f"Extraction failed: {e}")
            return False

        bin_dir = Path.home() / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        target_bin = bin_dir / cfg.binary_name

        found_bins = list(extracted_path.rglob(cfg.binary_name))
        if not found_bins:
            found_bins = [
                f for f in extracted_path.rglob("*") if f.is_file() and os.access(f, os.X_OK)
            ]

        if found_bins:
            src_bin = found_bins[0]
            src_bin.chmod(0o755)
            if target_bin.exists() or target_bin.is_symlink():
                target_bin.unlink()

            if self.platform.os_type == OSType.WINDOWS:
                shutil.copy2(src_bin, target_bin)
                log.info(f"Copied binary to {target_bin}")
            else:
                target_bin.symlink_to(src_bin)
                log.info(f"Linked binary to {target_bin}")

            self.platform.add_to_path_permanent(bin_dir)
            return True
        else:
            log.error(f"Could not find binary '{cfg.binary_name}' in extracted archive.")
            return False

    def _create_shim_and_finish(self, found_bin: Path, cfg: PlatformConfig) -> bool:
        log.info(f"Found binary at: {found_bin}")
        bin_dir = Path.home() / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        shim_name = Path(cfg.binary_name).with_suffix(".bat")
        shim_path = bin_dir / shim_name

        if shim_path.exists():
            with suppress(BaseException):
                shim_path.unlink()

        shim_content = f'@echo off\r\n"{found_bin}" %*\r\n'
        try:
            shim_path.write_text(shim_content, encoding="utf-8")
            log.info(f"Created shim at {shim_path}")
        except Exception as e:
            log.error(f"Failed to create shim: {e}")
            return False

        self.platform.add_to_path_permanent(bin_dir)
        return True

    def verify_installation(self, tool_id: str, expected_version: str) -> InstalledToolInfo | None:
        tool_def = repo.get_tool(tool_id)
        if not tool_def:
            return None
        tool_ver = tool_def.get_version(expected_version)
        cfg = tool_ver.get_platform_config(self.platform.os_type)

        binary_path = self.platform.find_binary(cfg.binary_name)
        if not binary_path:
            local_bin = Path.home() / ".local" / "bin" / cfg.binary_name
            if local_bin.exists():
                binary_path = local_bin
            else:
                if self.platform.os_type == OSType.WINDOWS:
                    shim_name = Path(cfg.binary_name).with_suffix(".bat")
                    local_shim = Path.home() / ".local" / "bin" / shim_name
                    if local_shim.exists():
                        binary_path = local_shim
                if not binary_path:
                    return None

        detected_version = "unknown"
        try:
            code, out, err = self.platform.run_command([str(binary_path), cfg.version_flag])
            if code == 0:
                match = re.search(cfg.version_regex, out)
                if match:
                    detected_version = match.group(1)
        except Exception:
            pass

        return InstalledToolInfo(
            tool_id=tool_id,
            name=tool_def.name,
            version=detected_version,
            path=str(binary_path),
            status=ToolStatus.INSTALLED,
            latest_version=tool_def.recommended_version,
        )
