"""Interactive CLI for managing container secrets."""

from __future__ import annotations

import re

import questionary
from rich.console import Console
from rich.table import Table

from .config import settings

console = Console()


def _get_keys() -> list[str]:
    """List existing secret key names."""
    secrets_dir = settings.secrets_dir
    if not secrets_dir.is_dir():
        return []
    return sorted(f.name for f in secrets_dir.iterdir() if f.is_file())


def _manage_keys() -> None:
    """Display and optionally delete existing keys."""
    keys = _get_keys()
    if not keys:
        console.print("\n[dim]No keys found.[/dim]\n")
        return

    console.print(f"\n[dim]Keys from {settings.secrets_dir}/[/dim]\n")

    table = Table(show_header=False, box=None)
    for key in keys:
        table.add_row(f"  {key}")
    console.print(table)
    console.print()

    choices = [*keys, "Back"]
    key_to_delete = questionary.select(
        "Select key to delete:",
        choices=choices,
    ).ask()

    if not key_to_delete or key_to_delete == "Back":
        return

    confirmed = questionary.confirm(f"Delete {key_to_delete}?", default=False).ask()
    if confirmed:
        (settings.secrets_dir / key_to_delete).unlink()
        console.print(f"\n[green]Deleted {key_to_delete}[/green]\n")
    else:
        console.print("\n[dim]Cancelled.[/dim]\n")


def _add_key() -> None:
    """Add a new secret key."""
    console.print("\n[dim]Example: OPENAI_API_KEY[/dim]\n")

    name = questionary.text(
        "Name:",
        validate=lambda val: (
            True
            if val and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", val)
            else "Use letters, numbers, and underscores only"
        ),
    ).ask()

    if not name:
        return

    value = questionary.password("Value:").ask()
    if not value:
        console.print("\n[dim]Value is required.[/dim]\n")
        return

    secrets_dir = settings.secrets_dir
    secrets_dir.mkdir(parents=True, exist_ok=True)
    # Set directory permissions
    secrets_dir.chmod(0o700)

    file_path = secrets_dir / name
    file_path.write_text(value)
    file_path.chmod(0o600)

    console.print(f"\n[green]Saved to {file_path}[/green]")
    console.print("[dim]Restart session to use: ./scripts/run.sh[/dim]\n")


def main() -> None:
    """Main menu loop."""
    try:
        while True:
            action = questionary.select(
                "What would you like to do?",
                choices=["Manage keys", "Add key", "Exit"],
            ).ask()

            if action == "Manage keys":
                _manage_keys()
            elif action == "Add key":
                _add_key()
            elif action == "Exit" or action is None:
                break
    except KeyboardInterrupt:
        console.print()


if __name__ == "__main__":
    main()
