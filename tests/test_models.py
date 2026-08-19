import pytest
from pydantic import ValidationError

from esim_tool_manager.core.models import (
    InstallMethod,
    OSType,
    PlatformConfig,
    ToolDefinition,
    ToolVersion,
)


def test_platform_config_defaults():
    cfg = PlatformConfig(install_method=InstallMethod.APT, packages=["ngspice"])
    assert cfg.install_method == InstallMethod.APT
    assert cfg.packages == ["ngspice"]
    assert cfg.version_flag == "--version"
    assert cfg.version_regex == r"(\d+\.\d+(\.\d+)?)"


def test_tool_version_parsing():
    data = {
        "version": "42",
        "release_date": "2023-01-01",
        "linux": {"install_method": "apt", "packages": ["ngspice"], "binary_name": "ngspice"},
        "windows": {
            "install_method": "chocolatey",
            "packages": ["ngspice"],
            "binary_name": "ngspice.exe",
        },
        "dependencies": ["libc6"],
    }
    ver = ToolVersion(**data)
    assert ver.version == "42"
    assert ver.linux.packages == ["ngspice"]
    assert ver.windows.install_method == InstallMethod.CHOCOLATEY
    assert ver.dependencies == ["libc6"]


def test_tool_version_get_platform_config():
    data = {
        "version": "1.0",
        "release_date": "2023-01-01",
        "linux": {"install_method": "apt", "packages": ["a"]},
        "windows": {"install_method": "winget", "packages": ["b"]},
    }
    ver = ToolVersion(**data)
    linux_cfg = ver.get_platform_config(OSType.LINUX)
    win_cfg = ver.get_platform_config(OSType.WINDOWS)
    assert linux_cfg.packages == ["a"]
    assert win_cfg.packages == ["b"]

    with pytest.raises(ValueError):
        ver.get_platform_config(OSType.MACOS)


def test_tool_definition_recommended():
    ver_1 = {
        "version": "1.0",
        "release_date": "2023-01-01",
        "linux": {"install_method": "apt", "packages": []},
        "windows": {"install_method": "winget", "packages": []},
    }
    ver_2 = {
        "version": "2.0",
        "release_date": "2023-06-01",
        "linux": {"install_method": "apt", "packages": []},
        "windows": {"install_method": "winget", "packages": []},
    }
    tool_data = {
        "name": "Test",
        "description": "Desc",
        "category": "cat",
        "versions": {"1.0": ver_1, "2.0": ver_2},
        "recommended_version": "2.0",
    }
    tool = ToolDefinition(**tool_data)
    assert tool.recommended_version == "2.0"
    rec = tool.get_recommended()
    assert rec.version == "2.0"


def test_model_validation_error():
    with pytest.raises(ValidationError):
        PlatformConfig(packages=["ngspice"])
