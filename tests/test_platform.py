from pathlib import Path
from unittest.mock import patch

from esim_tool_manager.core.models import InstallMethod
from esim_tool_manager.core.platform import PlatformManager


def test_singleton_pattern():
    p1 = PlatformManager()
    p2 = PlatformManager()
    assert p1 is p2


@patch("sys.platform", "linux")
@patch("shutil.which", return_value="/usr/bin/apt")
def test_linux_detection(mock_which):
    pass


def test_has_manager_logic():
    p = PlatformManager()
    p._package_managers = {InstallMethod.APT: "apt"}
    assert p.has_manager(InstallMethod.APT) is True
    assert p.has_manager(InstallMethod.WINGET) is False


def test_get_install_cmd_apt():
    p = PlatformManager()
    p._package_managers = {InstallMethod.APT: "apt"}
    cmd = p.get_install_cmd(InstallMethod.APT, ["ngspice", "gcc"])
    assert "apt" in cmd
    assert "ngspice" in cmd


def test_get_install_cmd_winget():
    p = PlatformManager()
    p._package_managers = {InstallMethod.WINGET: "winget"}

    cmd = p.get_install_cmd(InstallMethod.WINGET, ["KiCad.KiCad"])

    expected = [
        "winget",
        "install",
        "--id",
        "KiCad.KiCad",
        "--accept-source-agreements",
        "--accept-package-agreements",
        "--silent",
    ]

    assert cmd == expected


def test_find_binary(monkeypatch):
    p = PlatformManager()
    mock_path = Path("/fake/bin/ngspice")
    monkeypatch.setattr("shutil.which", lambda x: str(mock_path) if x == "ngspice" else None)
    assert p.find_binary("ngspice") == mock_path
    assert p.find_binary("nonexistent") is None
