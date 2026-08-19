from pathlib import Path

import typer
from rich.panel import Panel

from .core.logger import get_logger, setup_logging
from .core.platform import platform
from .managers.configurator import Configurator
from .managers.dependency import DependencyChecker
from .managers.installer import Installer
from .managers.updater import Updater
from .repositories.tool_repo import repo
from .ui.console import confirm_action, console, print_header, print_tool_table, select_tool

app = typer.Typer(
    name="esim-tool",
    help="Automated Tool Manager for eSim EDA Suite",
    add_completion=False,
    rich_markup_mode="rich",
)

installer = Installer(platform)
updater = Updater(platform, installer)
dep_checker = DependencyChecker(platform)

configurator = Configurator(platform, installer)

setup_logging()
log = get_logger(__name__)


@app.command()
def list_(
    show_all: bool = typer.Option(
        False, "--all", "-a", help="Show all known tools, not just installed"
    ),
) -> None:
    print_header("eSim Tool Manager - Status")

    tool_ids = repo.get_tool_ids()
    checks = updater.check_updates(tool_ids)

    if not show_all:
        checks = [c for c in checks if c["status"] != "not_installed"]

    print_tool_table(checks)


@app.command()
def install(
    tool_id: str | None = typer.Argument(
        None, help="Tool ID to install (e.g., ngspice). If omitted, shows menu."
    ),
    version: str | None = typer.Option(None, "--version", "-v", help="Specific version to install"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall"),
) -> None:
    print_header("Install Tool")

    target_id = tool_id
    if not target_id:
        target_id = select_tool(repo.get_tool_ids(), "Enter tool number to install")
        if not target_id:
            return

    tool_def = repo.get_tool(target_id)
    if not tool_def:
        console.print(f"[red]Error:[/red] Tool '{target_id}' not found.")
        return

    ver = version or tool_def.recommended_version
    console.print(f"Preparing to install [bold]{tool_def.name}[/bold] v{ver}...")

    if not confirm_action(f"Proceed with installation via {platform.os_type.value}?"):
        return

    with console.status(f"[cyan]Installing {tool_def.name}...[/cyan]", spinner="dots"):
        success = installer.install_tool(target_id, version=ver, force=force)

    if success:
        console.print(f"[green] {tool_def.name} installed successfully![/green]")
    else:
        console.print("[red] Installation failed. Check logs.[/red]")


@app.command()
def update(
    tool_id: str | None = typer.Argument(
        None, help="Tool ID to update. If omitted, updates all outdated."
    ),
    version: str | None = typer.Option(None, "--version", "-v", help="Target version"),
) -> None:
    print_header("Update Tools")

    if tool_id:
        if confirm_action(f"Update {tool_id}?"):
            with console.status(f"Updating {tool_id}..."):
                success = updater.update_tool(tool_id, version)
            console.print("Done" if success else "Failed")
    else:
        console.print("Checking for updates...")
        report = updater.update_all()
        console.print(f"[green]Updated:[/green] {report['updated']}")
        console.print(f"[yellow]Skipped:[/yellow] {report['skipped']}")
        console.print(f"[red]Failed:[/red] {report['failed']}")


@app.command()
def check_deps(
    tool_id: str = typer.Argument(..., help="Tool ID to check dependencies for"),
) -> None:
    print_header(f"Dependency Check: {tool_id}")
    tool_def = repo.get_tool(tool_id)
    if not tool_def:
        console.print("[red]Tool not found.[/red]")
        return

    ver = tool_def.get_recommended()
    report = dep_checker.get_missing_deps_report(ver.dependencies)
    console.print(Panel(report, title="System Dependencies", border_style="blue"))


@app.command()
def config(
    tool_id: str | None = typer.Argument(
        None, help="Configure specific tool. If omitted, configures all installed."
    ),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate eSim config file"),
) -> None:
    print_header("Configuration")

    if generate:
        out = Path.home() / ".esim_tools.json"
        configurator.generate_esim_config(out, installer)
        console.print(
            "\n[bold]Note:[/bold] Restart your terminal/session for PATH changes to take effect."
        )
        return

    targets = [tool_id] if tool_id else repo.get_tool_ids()

    for tid in targets:
        tool_def = repo.get_tool(tid)
        if not tool_def:
            continue
        info = installer.verify_installation(tid, tool_def.recommended_version)
        if info:
            configurator.configure_tool(info)
            console.print(f"[green]Configured {tid}[/green]")
        else:
            console.print(f"[yellow]Skipped {tid} (not installed)[/yellow]")

    console.print(
        "\n[bold]Note:[/bold] Restart your terminal/session for PATH changes to take effect."
    )


@app.command()
def doctor() -> None:
    print_header("System Doctor 🩺")
    console.print(f"OS: [bold]{platform.os_type.value}[/bold]")
    pm_str = ", ".join(m.value for m in platform.available_managers)
    console.print(f"Package Managers: [bold]{pm_str}[/bold]")
    local_bin = str(Path.home() / ".local" / "bin")
    console.print(
        f"PATH includes ~/.local/bin: [bold]{local_bin in platform.get_env_path()}[/bold]"
    )

    list_(show_all=True)


if __name__ == "__main__":
    app()
