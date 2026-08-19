from pathlib import Path
from typing import Optional

import yaml

from ..core.logger import get_logger
from ..core.models import ToolDefinition, ToolVersion

log = get_logger(__name__)


class ToolRepository:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._tools: dict[str, ToolDefinition] = {}
        self.load()

    def load(self) -> None:
        if not self.config_path.exists():
            log.error(f"Config file not found: {self.config_path}")
            return
        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        raw_tools = data.get("tools", {})
        for tool_id, tool_data in raw_tools.items():
            self._tools[tool_id] = ToolDefinition(**tool_data)
        log.info(f"Loaded {len(self._tools)} tool definitions.")

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)

    def get_all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_tool_ids(self) -> list[str]:
        return list(self._tools.keys())

    def get_recommended_version(self, tool_id: str) -> Optional[ToolVersion]:
        tool = self.get_tool(tool_id)
        if tool:
            return tool.get_recommended()
        return None


CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
DEFAULT_CONFIG = CONFIG_DIR / "tools.yaml"

repo = ToolRepository(DEFAULT_CONFIG)
