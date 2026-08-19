from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


def print_header(title: str) -> None:
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False, border_style="blue"))


def print_tool_table(tools_data: list[dict], title: str = "Tool Status") -> None:
    table = Table(title=title, show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("Tool ID", style="dim", width=18, no_wrap=True)
    table.add_column("Name", width=22)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Current Ver", justify="center", width=14)
    table.add_column("Latest Ver", justify="center", width=14)
    table.add_column("Path", style="dim", min_width=30)

    for row in tools_data:
        status = row.get("status", "unknown")
        style = "green"
        if status == "outdated":
            style = "yellow"
        elif status in ["not_installed", "error"]:
            style = "red"
        elif status == "up_to_date":
            style = "green"

        table.add_row(
            row["tool_id"],
            row["name"],
            f"[{style}]{status.replace('_', ' ').title()}[/{style}]",
            row["current_version"],
            row["latest_version"],
            row.get("path", "N/A")[:50],
        )
    console.print(table)


def print_log(logs: list[dict]) -> None:
    for log in logs:
        ts = log.get("timestamp", "")
        level = log.get("level", "INFO")
        msg = log.get("message", "")
        style = "white"
        if level == "ERROR":
            style = "red"
        elif level == "WARNING":
            style = "yellow"
        elif level == "SUCCESS":
            style = "green"
        console.print(f"[dim]{ts}[/dim] [{style}]{level}[/{style}] {msg}")


def confirm_action(message: str, default: bool = True) -> bool:
    return Confirm.ask(f"[bold]{message}[/bold]", default=default)


def select_tool(tool_ids: list[str], prompt: str = "Select tool") -> Optional[str] | None:
    console.print("[dim]Available tools:[/dim]")
    for i, tid in enumerate(tool_ids):
        console.print(f"  [{i + 1}] {tid}")
    choices = [str(i + 1) for i in range(len(tool_ids))] + ["q", "Q"]
    choice = Prompt.ask(prompt, choices=choices, default="q", show_choices=False)
    if choice.lower() == "q":
        return None
    return tool_ids[int(choice) - 1]


def get_spinner_context(text: str) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    )


def print_error(msg: str) -> None:
    console.print(f"[bold red] Error:[/bold red] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[bold green] Success:[/bold green] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow] Warning:[/bold yellow] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[bold blue] Info:[/bold blue] {msg}")
