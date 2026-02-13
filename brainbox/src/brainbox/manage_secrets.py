"""Interactive CLI for managing container secrets."""

from __future__ import annotations

import os
import re
import subprocess

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


def _show_status() -> None:
    """Show 1Password configuration state, template entries, and plaintext files."""
    console.print()

    # 1Password status
    from .secrets import get_sa_token, has_op_integration

    if has_op_integration():
        token = get_sa_token()
        masked = token[:8] + "..." if token and len(token) > 8 else "***"
        console.print(f"[green]1Password:[/green] configured (token: {masked})")

        # Show token source
        if os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"):
            console.print("[dim]  Source: OP_SERVICE_ACCOUNT_TOKEN env var[/dim]")
        else:
            console.print(f"[dim]  Source: {settings.op_sa_token_file}[/dim]")
    else:
        console.print("[yellow]1Password:[/yellow] not configured")

    # Vault info
    if has_op_integration():
        vault = settings.op_vault
        console.print(f"\n[dim]Vault: {vault or '(all accessible)'}[/dim]")
        console.print("[dim]Items discovered automatically from vault — no template needed.[/dim]")

    # Plaintext files
    keys = _get_keys()
    if keys:
        console.print(f"\n[dim]Plaintext files in {settings.secrets_dir}/:[/dim]")
        for key in keys:
            console.print(f"  {key}")
    else:
        console.print(f"\n[dim]No plaintext files in {settings.secrets_dir}/[/dim]")

    console.print()


def _setup_op() -> None:
    """Set up 1Password Service Account integration."""
    console.print()

    if os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"):
        console.print(
            "[yellow]OP_SERVICE_ACCOUNT_TOKEN is already set in your environment.[/yellow]"
        )
        console.print("[dim]The env var takes priority over the token file.[/dim]\n")
        proceed = questionary.confirm("Write a token file anyway?", default=False).ask()
        if not proceed:
            return

    console.print("[dim]Create a Service Account at:[/dim]")
    console.print("[dim]  https://my.1password.com/developer-tools/infrastructure-secrets/serviceaccount/[/dim]")
    console.print("[dim]Scope it to the vault your secrets live in (e.g. Workspace-Personal).[/dim]")
    console.print()

    token = questionary.password("Service Account token:").ask()
    if not token or not token.strip():
        console.print("\n[dim]Cancelled.[/dim]\n")
        return

    token = token.strip()

    # Validate via op whoami
    console.print("\n[dim]Validating token...[/dim]")
    try:
        env = {**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": token}
        result = subprocess.run(
            ["op", "whoami"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if result.returncode != 0:
            console.print(f"\n[red]Validation failed:[/red] {result.stderr.strip()}")
            console.print("[dim]Check your token and try again.[/dim]\n")
            return
        console.print(f"[green]Valid![/green] {result.stdout.strip()}")
    except FileNotFoundError:
        console.print("\n[red]'op' CLI not found.[/red]")
        console.print("[dim]Install: https://developer.1password.com/docs/cli/get-started/[/dim]\n")
        return
    except subprocess.TimeoutExpired:
        console.print("\n[red]Validation timed out.[/red]\n")
        return

    # Write token file
    token_file = settings.op_sa_token_file
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token)
    token_file.chmod(0o400)

    console.print(f"\n[green]Saved to {token_file} (mode 0400)[/green]")
    console.print("[dim]Secrets will now be resolved from 1Password automatically.[/dim]\n")


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
                choices=["Status", "1Password setup", "Manage keys", "Add key", "Exit"],
            ).ask()

            if action == "Status":
                _show_status()
            elif action == "1Password setup":
                _setup_op()
            elif action == "Manage keys":
                _manage_keys()
            elif action == "Add key":
                _add_key()
            elif action == "Exit" or action is None:
                break
    except KeyboardInterrupt:
        console.print()


if __name__ == "__main__":
    main()
