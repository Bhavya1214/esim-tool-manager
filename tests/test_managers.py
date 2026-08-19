import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from esim_tool_manager.core.models import (
    InstalledToolInfo,
    InstallMethod,
    OSType,
    PlatformConfig,
    ToolDefinition,
    ToolStatus,
    ToolVersion,
)
from esim_tool_manager.core.platform import PlatformManager
from esim_tool_manager.managers.configurator import Configurator
from esim_tool_manager.managers.dependency import DependencyChecker
from esim_tool_manager.managers.installer import Installer
from esim_tool_manager.managers.updater import Updater

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_platform():
    with patch("esim_tool_manager.core.platform.PlatformManager._instance", None):
        m = PlatformManager()

        m.has_manager = MagicMock(return_value=True)
        m.run_command = MagicMock(return_value=(0, "stdout", ""))
        m.find_binary = MagicMock(return_value=Path("/usr/bin/ngspice"))
        m.get_env_path = MagicMock(return_value="/usr/bin:/bin")
        m.add_to_path_permanent = MagicMock()

        with (
            patch.object(
                PlatformManager, "available_managers", new_callable=PropertyMock
            ) as mock_mgrs,
            patch.object(PlatformManager, "os_type", new_callable=PropertyMock) as mock_os,
        ):
            mock_mgrs.return_value = [InstallMethod.APT]
            mock_os.return_value = OSType.LINUX

            yield m


@pytest.fixture
def sample_tool_def():
    cfg_linux = PlatformConfig(
        install_method=InstallMethod.APT,
        packages=["ngspice"],
        binary_name="ngspice",
        version_flag="--version",
        version_regex=r"ngspice-(\d+)",
    )
    cfg_win = PlatformConfig(
        install_method=InstallMethod.CHOCOLATEY,
        packages=["ngspice"],
        binary_name="ngspice.exe",
        version_flag="--version",
        version_regex=r"ngspice-(\d+)",
    )

    ver = ToolVersion(
        version="42",
        release_date="2023-01-01",
        linux=cfg_linux,
        windows=cfg_win,
        dependencies=["libc6"],
    )
    return ToolDefinition(
        name="Ngspice",
        description="Simulator",
        category="sim",
        versions={"42": ver, "40": ver},
        recommended_version="42",
    )


@pytest.fixture
def mock_repo(sample_tool_def):
    with patch("esim_tool_manager.repositories.tool_repo.repo") as mock:
        mock.get_tool.return_value = sample_tool_def
        mock.get_tool_ids.return_value = ["ngspice", "kicad"]
        mock.get_all_tools.return_value = [sample_tool_def]
        yield mock


class TestInstaller:
    def test_install_apt_success(self, mock_platform, mock_repo, sample_tool_def):
        installer = Installer(mock_platform)
        installer.configurator.configure_tool = MagicMock()

        installer.verify_installation = MagicMock(
            return_value=InstalledToolInfo(
                tool_id="ngspice",
                name="Ngspice",
                version="42",
                path="/usr/bin/ngspice",
                status=ToolStatus.INSTALLED,
            )
        )

        with patch.object(installer, "_check_dependencies", return_value=True):
            result = installer.install_tool("ngspice", version="42")

        assert result is True
        calls = mock_platform.run_command.call_args_list
        assert len(calls) >= 2
        assert "apt" in str(calls[0])
        assert "update" in str(calls[0])
        assert "install" in str(calls[1])
        assert "ngspice" in str(calls[1])

    def test_install_tool_not_found(self, mock_platform, mock_repo):
        mock_repo.get_tool.return_value = None
        installer = Installer(mock_platform)
        result = installer.install_tool("nonexistent")
        assert result is False

    def test_install_dependency_failure(self, mock_platform, mock_repo):
        installer = Installer(mock_platform)
        with patch.object(installer, "_check_dependencies", return_value=False):
            result = installer.install_tool("ngspice")
        assert result is False

    def test_verify_installation_success(self, mock_platform, mock_repo, sample_tool_def):
        installer = Installer(mock_platform)
        mock_platform.find_binary.return_value = Path("/usr/bin/ngspice")
        mock_platform.run_command.return_value = (0, "ngspice-42", "")
        info = installer.verify_installation("ngspice", "42")

        assert info is not None
        assert info.tool_id == "ngspice"
        assert info.version == "42"
        assert info.status == ToolStatus.INSTALLED

    def test_verify_installation_not_found(self, mock_platform, mock_repo):
        installer = Installer(mock_platform)
        mock_platform.find_binary.return_value = None
        info = installer.verify_installation("ngspice", "42")
        assert info is None


class TestUpdater:
    def test_check_updates_outdated(self, mock_platform, mock_repo, sample_tool_def):
        installer_mock = MagicMock()
        installer_mock.verify_installation.return_value = InstalledToolInfo(
            tool_id="ngspice",
            name="Ngspice",
            version="40",
            path="/usr/bin/ngspice",
            status=ToolStatus.INSTALLED,
            latest_version="42",
        )

        updater = Updater(mock_platform, installer_mock)
        results = updater.check_updates(["ngspice"])

        assert len(results) == 1
        assert results[0]["status"] == "outdated"
        assert results[0]["current_version"] == "40"
        assert results[0]["latest_version"] == "42"

    def test_check_updates_up_to_date(self, mock_platform, mock_repo, sample_tool_def):
        installer_mock = MagicMock()
        installer_mock.verify_installation.return_value = InstalledToolInfo(
            tool_id="ngspice",
            name="Ngspice",
            version="42",
            path="/usr/bin/ngspice",
            status=ToolStatus.INSTALLED,
            latest_version="42",
        )

        updater = Updater(mock_platform, installer_mock)
        results = updater.check_updates(["ngspice"])

        assert results[0]["status"] == "up_to_date"

    def test_check_updates_not_installed(self, mock_platform, mock_repo, sample_tool_def):
        installer_mock = MagicMock()
        installer_mock.verify_installation.return_value = None

        updater = Updater(mock_platform, installer_mock)
        results = updater.check_updates(["ngspice"])

        assert results[0]["status"] == "not_installed"
        assert results[0]["current_version"] == "Not Installed"

    def test_update_tool_calls_installer(self, mock_platform, mock_repo, sample_tool_def):
        installer_mock = MagicMock()
        installer_mock.install_tool.return_value = True

        updater = Updater(mock_platform, installer_mock)
        result = updater.update_tool("ngspice", version="42")

        assert result is True
        installer_mock.install_tool.assert_called_once_with("ngspice", version="42", force=True)


class TestDependencyChecker:
    def test_check_system_deps_found_in_path(self, mock_platform):
        checker = DependencyChecker(mock_platform)
        with patch("shutil.which", return_value="/usr/bin/gcc"):
            results = checker.check_system_deps(["gcc", "make"])
        assert results["gcc"] is True

    def test_check_system_deps_found_dpkg(self, mock_platform):
        checker = DependencyChecker(mock_platform)
        mock_platform.os_type = OSType.LINUX

        with patch("shutil.which", return_value=None):
            mock_platform.run_command.return_value = (0, "ii  libc6...", "")
            results = checker.check_system_deps(["libc6"])

        assert results["libc6"] is True

    def test_get_missing_deps_report_all_ok(self, mock_platform):
        checker = DependencyChecker(mock_platform)
        with patch.object(checker, "check_system_deps", return_value={"gcc": True, "make": True}):
            report = checker.get_missing_deps_report(["gcc", "make"])
        assert "All dependencies satisfied." in report

    def test_get_missing_deps_report_missing(self, mock_platform):
        checker = DependencyChecker(mock_platform)
        mock_platform.os_type = OSType.LINUX
        mock_platform.has_manager.return_value = True

        with patch.object(checker, "check_system_deps", return_value={"gcc": True, "make": False}):
            report = checker.get_missing_deps_report(["gcc", "make"])

        assert "Missing Dependencies" in report
        assert "make" in report
        assert "apt install make" in report


class TestConfigurator:
    def test_configure_tool_linux_persist(self, mock_platform, tmp_path, sample_tool_def):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        bashrc = fake_home / ".bashrc"
        bashrc.write_text("# existing config\n")

        mock_platform.os_type = OSType.LINUX

        with patch("pathlib.Path.home", return_value=fake_home), patch("os.environ", {}):
            configurator = Configurator(mock_platform)
            info = InstalledToolInfo(
                tool_id="ngspice",
                name="Ngspice",
                version="42",
                path="/usr/bin/ngspice",
                status=ToolStatus.INSTALLED,
            )
            result = configurator.configure_tool(info)

        assert result is True
        content = bashrc.read_text()
        assert "ESIM_NGSPICE_PATH" in content
        expected_path = str(Path("/usr/bin/ngspice"))
        assert expected_path in content

    def test_configure_tool_windows_persist(self, mock_platform, sample_tool_def):
        with patch.object(PlatformManager, "os_type", new_callable=PropertyMock) as mock_os:
            mock_os.return_value = OSType.WINDOWS
            mock_platform.run_command.return_value = (0, "", "")

            configurator = Configurator(mock_platform)
            info = InstalledToolInfo(
                tool_id="ngspice",
                name="Ngspice",
                version="42",
                path="C:\\Program Files\\ngspice\\bin\\ngspice.exe",
                status=ToolStatus.INSTALLED,
            )

            with patch("os.environ", {}):
                result = configurator.configure_tool(info)

        assert result is True
        mock_platform.run_command.assert_called()
        args, _ = mock_platform.run_command.call_args
        assert "setx" in args[0]
        assert "ESIM_NGSPICE_PATH" in args[0]

    def test_generate_esim_config(self, mock_platform, tmp_path, sample_tool_def):
        mock_platform.os_type = OSType.LINUX
        configurator = Configurator(mock_platform)

        installer_mock = MagicMock()
        installer_mock.verify_installation.return_value = InstalledToolInfo(
            tool_id="ngspice",
            name="Ngspice",
            version="42",
            path="/usr/bin/ngspice",
            status=ToolStatus.INSTALLED,
        )

        out_file = tmp_path / "esim_config.json"
        result = configurator.generate_esim_config(out_file, installer_mock)

        assert result is True
        assert out_file.exists()
        import json

        data = json.loads(out_file.read_text())
        assert "Ngspice" in data
        assert data["Ngspice"]["binary_path"] == "/usr/bin/ngspice"
