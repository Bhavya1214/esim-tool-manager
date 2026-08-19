import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from packaging.version import Version as PkgVersion
from pydantic import BaseModel, Field, model_validator


class OSType(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "darwin"
    UNKNOWN = "unknown"


class InstallMethod(str, Enum):
    APT = "apt"
    CHOCOLATEY = "chocolatey"
    WINGET = "winget"
    HOMEBREW = "brew"
    MANUAL = "manual"
    COMPILE = "compile"
    PIP = "pip"


class ToolStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    OUTDATED = "outdated"
    ERROR = "error"
    UNKNOWN = "unknown"


class PlatformConfig(BaseModel):
    install_method: InstallMethod
    packages: list[str] = Field(default_factory=list)
    binary_name: str = ""
    version_flag: str = "--version"
    version_regex: str = r"(\d+\.\d+(\.\d+)?)"
    manual_url: Optional[str] = None
    build_deps: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    build_commands: list[str] = Field(default_factory=list)
    note: Optional[str] = None

    @model_validator(mode="after")
    def _fix_windows_binary_name(self) -> "PlatformConfig":
        if os.name == "nt" and self.binary_name and not Path(self.binary_name).suffix:
            self.binary_name = f"{self.binary_name}.exe"
        return self


class ToolVersion(BaseModel):
    version: str
    release_date: str
    linux: PlatformConfig
    windows: PlatformConfig
    dependencies: list[str] = Field(default_factory=list)

    def get_platform_config(self, os_type: OSType) -> PlatformConfig:
        if os_type == OSType.LINUX:
            return self.linux
        if os_type == OSType.WINDOWS:
            return self.windows
        raise ValueError(f"Unsupported OS: {os_type}")


class ToolDefinition(BaseModel):
    name: str
    description: str
    category: str
    versions: dict[str, ToolVersion]
    recommended_version: str

    def get_version(self, ver: str) -> ToolVersion:
        if ver not in self.versions:
            raise ValueError(
                f"Version {ver} not defined for {self.name}. "
                f"Available: {list(self.versions.keys())}"
            )
        return self.versions[ver]

    def get_recommended(self) -> ToolVersion:
        return self.get_version(self.recommended_version)


class InstalledToolInfo(BaseModel):
    tool_id: str
    name: str
    version: str
    path: str
    status: ToolStatus
    latest_version: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)

    def is_outdated(self) -> bool:
        if not self.latest_version or self.status != ToolStatus.INSTALLED:
            return False
        try:
            return PkgVersion(self.version) < PkgVersion(self.latest_version)
        except Exception:
            return False


class ActionLog(BaseModel):
    timestamp: str
    tool_id: str
    action: str
    status: str
    message: str
    duration_seconds: float
