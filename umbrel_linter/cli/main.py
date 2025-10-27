"""
Command-line interface for the Umbrel linter.

This module provides a user-friendly CLI for running the linter
with various options and configurations.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.linter import UmbrelLinter
from ..core.models import AppStoreType, LinterConfig, LintingContext, Severity
from .fixer import apply_fixes

# Initialize CLI app
app = typer.Typer(
    name="ulint",
    help="A linter for Umbrel app stores and applications",
    add_completion=False,
)

# Initialize console for rich output
console = Console()


@app.command()
def lint(
    path: str = typer.Argument(..., help="Path to the directory to lint"),
    app_id: str | None = typer.Option(
        None, "--app", "-a", help="Specific app ID to lint"
    ),
    log_level: str = typer.Option(
        "warning", "--log-level", "-l", help="Log level (error, warning, info)"
    ),
    strict: bool = typer.Option(
        False, "--strict", "-s", help="Treat warnings as errors"
    ),
    skip_architectures: bool = typer.Option(
        False, "--skip-architectures", help="Skip Docker image architecture checks"
    ),
    new_submission: bool = typer.Option(
        False, "--new-submission", help="This is a new app submission"
    ),
    pr_url: str | None = typer.Option(
        None, "--pr-url", help="Pull request URL for new submissions"
    ),
    store_type: str = typer.Option(
        "community", "--store-type", help="App store type (official, community)"
    ),
    output_format: str = typer.Option(
        "rich", "--format", "-f", help="Output format (rich, json, plain)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    fix: bool = typer.Option(False, "--fix", help="Automatically fix safe issues"),
    fix_secure: bool = typer.Option(
        False,
        "--fix-secure",
        help="Apply additional secure fixes (e.g., set container user)",
    ),
) -> None:
    """
    Lint Umbrel applications and app stores.

    This command performs comprehensive linting of Umbrel applications,
    including YAML validation, Docker Compose validation, and security checks.
    """
    try:
        # Parse and validate arguments
        directory = Path(path).resolve()
        if not directory.exists():
            console.print(f"[red]Error:[/red] Directory '{path}' does not exist")
            raise typer.Exit(1)

        if not directory.is_dir():
            console.print(f"[red]Error:[/red] '{path}' is not a directory")
            raise typer.Exit(1)

        # Parse log level
        try:
            severity = Severity(log_level.lower())
        except ValueError:
            console.print(
                f"[red]Error:[/red] Invalid log level '{log_level}'. Must be one of: error, warning, info"
            )
            raise typer.Exit(1)

        # Parse store type
        try:
            app_store_type = AppStoreType(store_type.lower())
        except ValueError:
            console.print(
                f"[red]Error:[/red] Invalid store type '{store_type}'. Must be one of: official, community"
            )
            raise typer.Exit(1)

        # Create configuration
        config = LinterConfig(
            check_image_architectures=(not skip_architectures),
            log_level=severity,
            strict_mode=strict,
        )

        # Create context
        context = LintingContext(
            app_id=app_id,
            app_store_type=app_store_type,
            is_new_submission=new_submission,
            pull_request_url=pr_url,
        )

        # Initialize linter
        linter = UmbrelLinter(config)

        # Run linting
        import asyncio

        if app_id:
            console.print(f"[blue]Linting app:[/blue] {app_id}")
            result = asyncio.run(linter.lint_app(directory, app_id, context))
        else:
            console.print(f"[blue]Linting directory:[/blue] {directory}")
            result = asyncio.run(linter.lint_all_apps(directory, context))

        # Display results
        if output_format == "json":
            _display_json_output(result)
        elif output_format == "plain":
            _display_plain_output(result, severity)
        else:
            _display_rich_output(result, severity, verbose)

        # Offer auto-fix guidance when issues are present
        fixable_ids = {
            "empty_app_data_directory",
            "missing_file_or_directory",
            "invalid_yaml_boolean_value",
            "invalid_restart_policy",
            "invalid_tagline",
            "invalid_container_user",
        }
        if any(err.id in fixable_ids for err in result.errors):
            console.print(
                "\n[dim]Tip:[/dim] You can auto-fix many issues with:\n  [bold]umbrel-linter lint[/bold] [cyan]<path>[/cyan] --fix\n  [bold]umbrel-linter lint[/bold] [cyan]<path>[/cyan] --fix --fix-secure"
            )

        # Apply fixes if requested
        if fix or fix_secure:
            apply_fixes(directory, app_id, result, fix_secure, console)
            console.print("\n[green]Auto-fix completed. Re-run lint to verify.[/green]")

        # Exit with appropriate code
        # Only exit with error code if there are actual errors (not just info messages)
        if result.has_errors() or (strict and result.has_warnings()):
            raise typer.Exit(1)
        # Success case - no need to raise typer.Exit(0), just return

    except KeyboardInterrupt:
        console.print("\n[yellow]Linting interrupted by user[/yellow]")
        raise typer.Exit(1)
    except typer.Exit:
        # Re-raise typer.Exit to preserve exit codes
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _display_rich_output(result, severity: Severity, verbose: bool) -> None:
    """Display results using rich formatting."""

    # Summary
    error_count = result.total_errors
    warning_count = result.total_warnings
    info_count = result.total_info

    if result.success and warning_count == 0 and info_count == 0:
        console.print(
            Panel(
                "[green]✓ No linting errors found! 🎉[/green]",
                title="Linting Complete",
                border_style="green",
            )
        )
    elif result.success:
        # No errors, but has warnings or info messages
        summary_parts = []
        if warning_count > 0:
            summary_parts.append(f"[yellow]{warning_count} warnings[/yellow]")
        if info_count > 0:
            summary_parts.append(f"[blue]{info_count} info messages[/blue]")

        summary_text = (
            f"[green]✓ Linting passed with {', '.join(summary_parts)}[/green]"
        )
        console.print(
            Panel(
                summary_text,
                title="Linting Complete",
                border_style="green",
            )
        )
    else:
        summary_text = f"[red]✗ Linting failed with {error_count} errors[/red]"
        if warning_count > 0:
            summary_text += f", [yellow]{warning_count} warnings[/yellow]"
        if info_count > 0:
            summary_text += f", [blue]{info_count} info messages[/blue]"

        console.print(
            Panel(
                summary_text,
                title="Linting Complete",
                border_style="red",
            )
        )

    # Filter errors by log level
    filtered_errors = []
    for error in result.errors:
        if (
            (severity == Severity.ERROR and error.severity == Severity.ERROR)
            or (
                severity == Severity.WARNING
                and error.severity in [Severity.ERROR, Severity.WARNING]
            )
            or severity == Severity.INFO
        ):
            filtered_errors.append(error)

    if not filtered_errors:
        return

    # Group errors by file
    errors_by_file = {}
    for error in filtered_errors:
        if error.file not in errors_by_file:
            errors_by_file[error.file] = []
        errors_by_file[error.file].append(error)

    # Display errors
    for file_path, file_errors in errors_by_file.items():
        console.print(f"\n[bold]{file_path}[/bold]")

        for error in file_errors:
            # Color based on severity
            if error.severity == Severity.ERROR:
                severity_color = "red"
                severity_icon = "✗"
            elif error.severity == Severity.WARNING:
                severity_color = "yellow"
                severity_icon = "⚠"
            else:
                severity_color = "blue"
                severity_icon = "ℹ"

            # Create error text
            error_text = Text()
            error_text.append(f"{severity_icon} ", style=severity_color)
            error_text.append(f"{error.severity.upper()} ", style=severity_color)
            error_text.append(f"{error.title}", style="bold")

            if error.properties_path:
                error_text.append(f" ({error.properties_path})", style="dim")

            console.print(error_text)
            console.print(f"  {error.message}", style="dim")

            if verbose and error.line:
                console.print(
                    f"  Line {error.line.start}-{error.line.end}", style="dim"
                )


def _display_plain_output(result, severity: Severity) -> None:
    """Display results in plain text format."""

    if result.success:
        print("No linting errors found!")
        return

    # Filter errors by log level
    filtered_errors = []
    for error in result.errors:
        if (
            (severity == Severity.ERROR and error.severity == Severity.ERROR)
            or (
                severity == Severity.WARNING
                and error.severity in [Severity.ERROR, Severity.WARNING]
            )
            or severity == Severity.INFO
        ):
            filtered_errors.append(error)

    for error in filtered_errors:
        print(f"{error.severity.upper()}: {error.title}")
        print(f"  File: {error.file}")
        if error.properties_path:
            print(f"  Path: {error.properties_path}")
        print(f"  Message: {error.message}")
        if error.line:
            print(f"  Line: {error.line.start}-{error.line.end}")
        print()


def _display_json_output(result) -> None:
    """Display results in JSON format."""
    import json

    output = {
        "success": result.success,
        "total_errors": result.total_errors,
        "total_warnings": result.total_warnings,
        "total_info": result.total_info,
        "errors": [
            {
                "id": error.id,
                "severity": error.severity,
                "title": error.title,
                "message": error.message,
                "file": error.file,
                "properties_path": error.properties_path,
                "line": (
                    {
                        "start": error.line.start,
                        "end": error.line.end,
                    }
                    if error.line
                    else None
                ),
                "column": (
                    {
                        "start": error.column.start,
                        "end": error.column.end,
                    }
                    if error.column
                    else None
                ),
            }
            for error in result.errors
        ],
    }

    print(json.dumps(output, indent=2))


@app.command()
def version() -> None:
    """Show version information."""
    from .. import __version__

    console.print(f"umbrel-linter version {__version__}")


@app.command()
def config() -> None:
    """Show configuration information."""
    config = LinterConfig()

    table = Table(title="Linter Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Check Image Architectures", str(config.check_image_architectures))
    table.add_row("Log Level", config.log_level.value)
    table.add_row("Strict Mode", str(config.strict_mode))
    table.add_row("Ignore Patterns", ", ".join(config.ignore_patterns) or "None")

    console.print(table)


if __name__ == "__main__":
    app()
