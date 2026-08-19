from typing import Any

from packaging.version import Version

from ..core.logger import get_logger
from ..core.models import ToolStatus
from ..managers.base import BaseManager
from ..managers.installer import Installer
from ..repositories.tool_repo import repo

log = get_logger(__name__)


class Updater(BaseManager):
    def __init__(self, platform_mgr: Any, installer: Installer) -> None:
        super().__init__(platform_mgr)
        self.installer = installer

    def execute(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Use check_updates() or update_tool() directly.")

    def check_updates(self, tool_ids: list[str] | None = None) -> list[dict]:
        targets = tool_ids or repo.get_tool_ids()
        results = []

        for tid in targets:
            tool_def = repo.get_tool(tid)
            if not tool_def:
                continue

            current = self.installer.verify_installation(tid, tool_def.recommended_version)

            if current and current.status == ToolStatus.INSTALLED and current.version != "unknown":
                latest_ver = tool_def.recommended_version
                try:
                    is_outdated = Version(current.version) < Version(latest_ver)
                except Exception:
                    is_outdated = current.version != latest_ver

                results.append(
                    {
                        "tool_id": tid,
                        "name": tool_def.name,
                        "current_version": current.version,
                        "latest_version": latest_ver,
                        "status": "outdated" if is_outdated else "up_to_date",
                        "path": current.path,
                    }
                )
            else:
                results.append(
                    {
                        "tool_id": tid,
                        "name": tool_def.name,
                        "current_version": "Not Installed",
                        "latest_version": tool_def.recommended_version,
                        "status": "not_installed",
                        "path": "",
                    }
                )
        return results

    def update_tool(self, tool_id: str, version: str | None = None) -> bool:
        tool_def = repo.get_tool(tool_id)
        if not tool_def:
            return False

        target_ver = version or tool_def.recommended_version
        log.info(f"Updating {tool_def.name} to {target_ver}...")

        return self.installer.install_tool(tool_id, version=target_ver, force=True)

    def update_all(self) -> dict[str, list[str]]:
        report: dict[str, list[str]] = {"updated": [], "failed": [], "skipped": []}
        checks = self.check_updates()

        for item in checks:
            if item["status"] == "outdated":
                log.info(f"Updating {item['name']}...")
                if self.update_tool(item["tool_id"]):
                    report["updated"].append(item["tool_id"])
                else:
                    report["failed"].append(item["tool_id"])
            else:
                report["skipped"].append(item["tool_id"])
        return report
