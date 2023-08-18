"""Logging and user display related functions."""

from typing import Sequence, Dict, List

from .config import StackBuilderConfig
from .easyconfigs import Easyconfig
from .timer import Timer


def print_summary_start(
    sb_config: StackBuilderConfig,
    build_from_scratch: bool,
    no_avx2: bool,
    dry_run: bool,
    easyconfigs_to_build: Dict[str, Easyconfig],
    pkgs_to_build: Sequence[str],
    pkgs_already_built: Sequence[str],
) -> None:
    """Print input data summary."""

    pkgs_not_found = [x for x in pkgs_to_build if x not in easyconfigs_to_build]
    pkgs_to_build_info = [
        f"{x} [{easyconfigs_to_build[x].path}] [branch={easyconfigs_to_build[x].branch}]"
        for x in pkgs_to_build
        if x not in pkgs_not_found
    ]
    print(
        "#" * 100 + "\n",
        "### EasyBuild config:\n",
        "###  -> builddir   : " + str(sb_config.buildpath) + "\n",
        "###  -> installdir : " + str(sb_config.installpath) + "\n",
        "###  -> robot-paths: " + str([str(x) for x in sb_config.robot_paths]) + "\n",
        "###  -> SIB EasyConfig repo: "
        + str(sb_config.sib_easyconfigs_repo.path)
        + "\n",
        "###  -> SIB SoftStack repo: "
        + str(sb_config.sib_software_stack_repo.path)
        + "\n",
        "###  -> optarch    : " + str(sb_config.optarch) + "\n",
        "###  -> job-cores  : " + str(sb_config.job_cores) + "\n",
        "### \n",
        "### Build summary:\n",
        "###  -> build_from_scratch: " + str(build_from_scratch) + "\n",
        "###  -> no_avx2           : " + str(no_avx2) + "\n",
        "###  -> dry_run           : " + str(dry_run) + "\n",
        "###  -> Node name         : " + sb_config.sib_node.value + "\n",
        "### ",
        sep="",
    )
    if pkgs_already_built:
        print(
            "### Packages already built:\n",
            "###  -> " + "\n###  -> ".join(pkgs_already_built) + "\n",
            "### ",
            sep="",
        )
    if not pkgs_to_build_info:
        pkgs_to_build_info = ["All packages already built - nothing to do."]
    print(
        "### Packages to build:\n",
        "###  -> " + "\n###  -> ".join(pkgs_to_build_info) + "\n",
        "### ",
        sep="",
    )
    if pkgs_not_found:
        print(
            "### Packages not found:\n",
            "###  -> " + "\n###  -> ".join(pkgs_not_found) + "\n",
            "### ",
            sep="",
        )


def print_summary_end(
    eb_cmd_description: str, timer: Timer, pkgs_to_build: List[str], dry_run: bool
) -> None:
    """Print end of command summary, e.g. build times."""

    # Display end summary info (build times).
    print(
        f"### Completed {eb_cmd_description} successfully in {timer.total_time_as_str}."
    )
    if not dry_run:
        build_times = [
            f"{x}: {timer.recorded_times_as_str[index]}"
            for index, x in enumerate(pkgs_to_build)
        ]
        build_times.append(f"Total time: {timer.total_time_as_str}")
        print(
            "### Build times (including dependencies):\n",
            "###  - " + "\n###  - ".join(build_times) + "\n",
            sep="",
        )

    print("#" * 100 + "\n")
