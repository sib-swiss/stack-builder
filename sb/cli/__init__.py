"""Command line interface module."""

from .cli_builder import Subcommand, CliWithSubcommands, Argument
from ..workflows.build_stack import build_stack
from ..workflows.update_repo import update_repos
from ..utils.config import SIB_EASYCONFIGS_REPO, SIB_SOFTWARE_STACK_REPO


class Cli(CliWithSubcommands):
    """Command line arguments and options."""

    description = "SIB software stack builder"
    subcommands = (
        Subcommand(
            f=build_stack,
            aliases=("build", "bs"),
            arguments=(
                Argument(
                    "-d",
                    "-D",
                    "--dry-run",
                    dest="dry_run",
                    help="Run command in test mode.",
                    default=False,
                    action="store_true",
                ),
                Argument(
                    "-n2",
                    "--no-avx2",
                    dest="no_avx2",
                    help="Build software stack without avx2 support.",
                    default=False,
                    action="store_true",
                ),
                Argument(
                    "--from-scratch",
                    dest="build_from_scratch",
                    help="Deletes the existing stack before running the build commands.",
                    default=False,
                    action="store_true",
                ),
                Argument(
                    "-s",
                    "--summary",
                    dest="summary_only",
                    help="Displays a summary of the tasks to execute.",
                    default=False,
                    action="store_true",
                ),
            ),
            help_text="Build or update a local instance of the software stack.",
        ),
        Subcommand(
            f=update_repos,
            aliases=("update", "ur"),
            arguments=(
                Argument(
                    "-u",
                    "--from-upstream",
                    dest="from_upstream",
                    help="Fetch updates from the upstream EasyBuild repo.",
                    default=False,
                    action="store_true",
                ),
            ),
            help_text=f"Update the '{SIB_EASYCONFIGS_REPO}' and "
            f"'{SIB_SOFTWARE_STACK_REPO}' repositories.",
        ),
    )


def run() -> int:
    """Launcher for the SIB software stack application."""
    if Cli():
        return 0
    return 1
