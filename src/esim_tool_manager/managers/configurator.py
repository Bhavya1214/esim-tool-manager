import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from ..core.logger import get_logger
from ..core.models import InstalledToolInfo, OSType
from ..repositories.tool_repo import repo

if TYPE_CHECKING:
    from esim_tool_manager.managers.installer import Installer

log = get_logger(__name__)


class Configurator:
    def __init__(self, platform_mgr: Any, installer: Optional["Installer"] = None) -> None:
        self.platform = platform_mgr
        self.installer = installer

    def configure_tool(self, tool_info: InstalledToolInfo) -> bool:
        tool_def = repo.get_tool(tool_info.tool_id)
        if not tool_def:
            return False

        log.info(f"Configuring {tool_def.name}...")

        bin_path = Path(tool_info.path)
        install_root = bin_path.parent.parent

        env_var = f"ESIM_{tool_info.tool_id.upper()}_PATH"
        os.environ[env_var] = str(bin_path)
        log.info(f"Set Session Env: {env_var}={bin_path}")

        self._persist_env_var(env_var, str(bin_path))
        self._configure_library_paths(install_root)

        return True

    def _persist_env_var(self, key: str, value: str) -> None:
        if self.platform.os_type == OSType.WINDOWS:
            cmd = ["setx", key, value]
            code, out, err = self.platform.run_command(cmd)
            if code == 0:
                log.info(
                    f"Persisted {key} to Windows User Environment (requires terminal restart)."
                )
            else:
                log.warning(f"Failed to setx {key}: {err}")
        else:
            rc_files = [Path.home() / ".bashrc", Path.home() / ".profile"]
            entry = f'export {key}="{value}" # eSim Tool Manager'
            for rc in rc_files:
                if rc.exists():
                    content = rc.read_text()
                    if key not in content:
                        rc.write_text(content + f"\n{entry}\n")
                        log.info(f"Added {key} to {rc.name}")

    def _configure_library_paths(self, install_root: Path) -> None:
        lib_dir = install_root / "lib"
        lib64_dir = install_root / "lib64"
        pkg_config_dir = install_root / "lib" / "pkgconfig"

        paths_to_add = [
            p for p in [lib_dir, lib64_dir, pkg_config_dir] if p.exists() and p.is_dir()
        ]

        if not paths_to_add:
            return

        current_ld = os.environ.get("LD_LIBRARY_PATH", "")
        new_ld_parts = [str(p) for p in paths_to_add if str(p) not in current_ld]
        if new_ld_parts:
            new_ld = ":".join(new_ld_parts) + ":" + current_ld
            os.environ["LD_LIBRARY_PATH"] = new_ld
            self._persist_env_var("LD_LIBRARY_PATH", new_ld)
            log.info("Updated LD_LIBRARY_PATH")

        current_pc = os.environ.get("PKG_CONFIG_PATH", "")
        new_pc_parts = [str(p) for p in paths_to_add if str(p) not in current_pc]
        if new_pc_parts:
            new_pc = ":".join(new_pc_parts) + ":" + current_pc
            os.environ["PKG_CONFIG_PATH"] = new_pc
            self._persist_env_var("PKG_CONFIG_PATH", new_pc)
            log.info("Updated PKG_CONFIG_PATH")

    @staticmethod
    def generate_esim_config(output_path: Path, installer_instance: "Installer") -> bool:
        log.info(f"Generating eSim config at {output_path}...")
        data: dict[str, dict] = {}

        for tool_def in repo.get_all_tools():
            info = installer_instance.verify_installation(
                tool_def.name, tool_def.recommended_version
            )
            if info and info.status == "installed":
                data[tool_def.name] = {
                    "binary_path": info.path,
                    "version": info.version,
                    "tool_id": tool_def.name.lower().replace(" ", "_"),
                }
            else:
                data[tool_def.name] = {
                    "binary_path": "",
                    "version": "",
                    "tool_id": tool_def.name.lower().replace(" ", "_"),
                    "status": "not_installed",
                }

        try:
            output_path.write_text(json.dumps(data, indent=2))
            log.info(f"Generated eSim config: {output_path}")
            return True
        except Exception as e:
            log.error(f"Failed to write config: {e}")
            return False
