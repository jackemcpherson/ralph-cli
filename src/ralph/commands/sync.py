"""Ralph sync command - sync skills to ~/.claude/skills/.

This module implements the 'ralph sync' command which copies
skill definitions to the global Claude Code skills directory.
By default, syncs bundled skills from the package.
"""

import logging
from pathlib import Path

import typer

from ralph.services import SkillsService, SyncStatus
from ralph.utils import (
    console,
    print_error,
    print_success,
    print_warning,
)

logger = logging.getLogger(__name__)


def sync(
    skills_dir: Path | None = typer.Option(
        None,
        "--skills-dir",
        "-s",
        help="Custom skills directory (default: use bundled package skills).",
    ),
    remove: bool = typer.Option(
        False,
        "--remove",
        "-r",
        help="Remove previously synced skills instead of syncing.",
    ),
) -> None:
    """Sync Ralph skills to Claude Code.

    By default, copies bundled skill definitions from the ralph-cli package
    to ~/.claude/skills/ for native Claude Code integration.

    Use --skills-dir to sync from a custom directory instead.
    Use --remove to uninstall ralph skills that were previously synced.
    """
    service = SkillsService(skills_dir=skills_dir)

    if remove:
        _handle_remove(service)
        return

    if skills_dir is not None and not skills_dir.exists():
        print_warning(f"Skills directory not found: {skills_dir}")
        console.print("\nTo create skills, add a skills/ directory with subdirectories")
        console.print("containing SKILL.md files with frontmatter:\n")
        console.print("  ---")
        console.print('  name: "my-skill"')
        console.print('  description: "What this skill does"')
        console.print("  ---")
        raise typer.Exit(0)

    if skills_dir is None:
        console.print("\n[bold]Syncing bundled skills from:[/bold] ralph-cli package")
    else:
        skill_paths = service.list_local_skills()
        if not skill_paths:
            print_warning(f"No skills found in {skills_dir}")
            console.print("\nSkills are subdirectories containing a SKILL.md file.")
            raise typer.Exit(0)
        console.print(f"\n[bold]Syncing skills from:[/bold] {skills_dir}")

    console.print(f"[bold]Target directory:[/bold] {service.target_dir}\n")

    results = service.sync_all()

    created_count = 0
    updated_count = 0
    invalid_count = 0
    error_count = 0

    for result in results:
        if result.status == SyncStatus.CREATED:
            console.print(f"  [green][OK][/green] {result.skill_name} [dim](created)[/dim]")
            created_count += 1
        elif result.status == SyncStatus.UPDATED:
            console.print(f"  [green][OK][/green] {result.skill_name} [dim](updated)[/dim]")
            updated_count += 1
        elif result.status == SyncStatus.INVALID:
            console.print(f"  [yellow]![/yellow] {result.skill_name} [dim](invalid)[/dim]")
            if result.error:
                console.print(f"      [dim]{result.error}[/dim]")
            invalid_count += 1
        elif result.status == SyncStatus.SKIPPED:
            console.print(f"  [red][FAIL][/red] {result.skill_name} [dim](error)[/dim]")
            if result.error:
                console.print(f"      [dim]{result.error}[/dim]")
            error_count += 1

    console.print()

    total_synced = created_count + updated_count
    if total_synced > 0:
        print_success(f"Synced {total_synced} skill(s) to {service.target_dir}")
        if created_count > 0:
            console.print(f"  Created: {created_count}")
        if updated_count > 0:
            console.print(f"  Updated: {updated_count}")
    else:
        print_warning("No skills were synced.")

    if invalid_count > 0:
        print_warning(f"Skipped {invalid_count} invalid skill(s) (missing frontmatter)")

    if error_count > 0:
        print_error(f"Failed to sync {error_count} skill(s)")
        raise typer.Exit(1)


def _handle_remove(service: SkillsService) -> None:
    """Handle the --remove flag to uninstall skills.

    Args:
        service: The SkillsService instance to use for removal.
    """
    console.print(f"\n[bold]Removing skills from:[/bold] {service.target_dir}\n")

    removed = service.remove_skills()

    if not removed:
        print_warning("No ralph skills to remove (no manifest found or already removed)")
        return

    for skill_name in removed:
        console.print(f"  [green][OK][/green] {skill_name} [dim](removed)[/dim]")

    console.print()
    print_success(f"Removed {len(removed)} skill(s)")
