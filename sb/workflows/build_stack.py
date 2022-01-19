"""Module for the "build stack" workflow of the application, which builds or
updates the local instance of the SIB software stack.
"""
import os
import shutil
from contextlib import contextmanager
from typing import Generator

from ..utils.config import (
    UserAnswer,
    load_config,
    load_package_list,
    StackBuilderConfig,
)
from ..utils.easyconfigs import find_easyconfigs, install_license_files
from ..utils.utils import (
    delete_directory_content,
    run_subprocess,
    user_confirmation_dialog,
)
from ..utils.timer import Timer
from ..utils.git import switch_to_branch_if_repo
from ..utils.logging import print_summary_start, print_summary_end


@contextmanager
def clean_eb_tmp_files(sb_config: StackBuilderConfig) -> Generator:
    """Delete any 'eb-*' directories that are found in the /tmp directory.

    Note that this context manager will not clean the tmp files if an error
    occurs while it is active. This is on purpose, so that the EasyBuild log
    files are not deleted in case of a build error.
    """

    def clean_eb_tmp_path() -> None:
        for dir_name in [x for x in os.listdir("/tmp") if x.startswith("eb-")]:
            shutil.rmtree(os.path.join("/tmp", dir_name))

    # No "try: finally:"" block around the yield statement, because the desired
    # behavior is that the cleaning does not occur on error.
    clean_eb_tmp_path()
    delete_directory_content(sb_config.buildpath)
    yield None
    clean_eb_tmp_path()
    delete_directory_content(sb_config.buildpath)


def build_stack(
    build_from_scratch: bool = False,
    summary_only: bool = False,
    no_avx2: bool = False,
    dry_run: bool = False,
):
    """Main function of the "build" workflow."""

    # Load the EasyBuild and StackBuilder configuration values. Make sure that
    # the local node's branch is checked-out in the Git repos.
    sb_config = load_config()
    sb_config.sib_easyconfigs_repo.switch(sb_config.node_branch_name)
    sb_config.sib_software_stack_repo.switch(sb_config.node_branch_name)

    # Load the list of easyconfig files to build.
    pkgs_already_built, pkgs_to_build = load_package_list(sb_config, no_avx2)
    if build_from_scratch:
        pkgs_to_build.extend(pkgs_already_built)
        pkgs_already_built = []

    # Load easyconfig files to build as Easyconfig objects.
    easyconfigs_to_build = find_easyconfigs(
        file_names=pkgs_to_build, sb_config=sb_config
    )

    # Display start summary info.
    print_summary_start(
        sb_config=sb_config,
        build_from_scratch=build_from_scratch,
        no_avx2=no_avx2,
        dry_run=dry_run,
        easyconfigs_to_build=easyconfigs_to_build,
        pkgs_to_build=pkgs_to_build,
        pkgs_already_built=pkgs_already_built,
    )
    if summary_only or not pkgs_to_build:
        print("#" * 100 + "\n")
        return

    if any(x not in easyconfigs_to_build for x in pkgs_to_build):
        print(
            "### ERROR: easyconfig files for one or more packages to build "
            "could not be found. Aborting. \n"
            "###        Use the '--force' flag to build stack while ignoring "
            "non-found packages."
        )
        return

    # If requested, delete the current EasyBuild stack installation.
    if build_from_scratch:
        if (
            user_confirmation_dialog(
                "WARNING: you requested to rebuild the software stack from scratch.",
                "         This will delete the existing EasyBuild stack at: "
                f"{sb_config.installpath}",
            )
            is UserAnswer.YES
        ):
            delete_directory_content(sb_config.installpath, verbose=True)
        else:
            return

    # Verify that license files are present in the host's home directory.
    if not dry_run:
        install_license_files(sb_config)

    # Run EasyBuild.
    eb_cmd_arguments = ["eb", "--robot", "--rpath"]
    eb_cmd_description = "build"
    if dry_run:
        eb_cmd_arguments.append("--dry-run")
        eb_cmd_description += " [dry-run]"

    print(f"### Starting {eb_cmd_description}:")
    timer = Timer(start_timer=True)
    for easyconfig_name in pkgs_to_build:

        easyconfig = easyconfigs_to_build[easyconfig_name]
        assert easyconfig.name == easyconfig_name

        with clean_eb_tmp_files(sb_config), switch_to_branch_if_repo(
            easyconfig.repo, easyconfig.branch
        ):
            eb_args = eb_cmd_arguments + [easyconfig.full_name]
            print(
                f"### -> Building {easyconfig.full_name} [branch={easyconfig.branch}]\n"
                f"###    EasyBuild command: {' '.join(eb_args)}"
            )
            run_subprocess(
                args=eb_args, capture_output=False, return_stdout=False, dry_run=False
            )
            timer.lap()
            print("###")

    # Display end summary info (build times).
    print_summary_end(eb_cmd_description, timer, pkgs_to_build, dry_run)
