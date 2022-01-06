"""Easyconfigs related functions."""

import os
import filecmp
import shutil
from dataclasses import dataclass
from typing import Generator, Iterable, Sequence, Dict, Tuple, Optional, List
from .config import StackBuilderConfig, LICENSE_FILES_DIR
from .utils import get_files_from_directory, create_directory
from .git import GitRepo, Status, switch_to_branch_if_repo


@dataclass
class Easyconfig:
    """Representation of an easyconfig file."""

    name: str
    path: str
    repo: Optional[GitRepo] = None
    branch: Optional[str] = None

    def __post_init__(self):
        if not self.name.endswith(".eb"):
            raise ValueError("Easyconfig name must end with '.eb' extension.")

    @property
    def full_name(self) -> str:
        """Full path and name of the easyconfig file."""
        return os.path.join(self.path, self.name)

    @property
    def module(self) -> str:
        """Module file associated with the easyconfig."""
        end_index = -10 if self.name.endswith("-noAVX2.eb") else -3
        return f"{self.name[:end_index]}.lua"


def branch_is_ahead_of_others(
    repo: GitRepo, branch: str, other_branches: Sequence[str]
) -> bool:
    """Tests whether the specied branch is ahead (in terms of commits) of all
    other specified branches. Returns True if it is the case, False otherwise.
    In other w
    """
    return not any(
        map(
            lambda x: repo.branch_status(branch_name=branch, branch_to_compare_with=x)
            in (Status.BEHIND, Status.UP_TO_DATE),
            other_branches,
        )
    )


def find_easyconfigs(
    file_names: Sequence[str], sb_config: StackBuilderConfig
) -> Dict[str, Easyconfig]:
    """Check whether the specified easyconfig files can be found in one of the
    directories/repositories listed in the "robot-path" of the EasyBuild
    config.
    Files that cannot be found will simply be missing from the returned
    dictionary.
    """

    def not_yet_found() -> Generator[str, None, None]:
        yield from (f for f in file_names if f not in easyconfigs_by_name)

    def repo_from_path(path: str) -> Optional[GitRepo]:
        for repo in (sb_config.sib_software_stack_repo, sb_config.sib_easyconfigs_repo):
            if path.startswith(repo.path):
                return repo
        return None

    # Make a list of all directories/repos and branches that can potentially be
    # searched for easyconfig files. Each location to search is stored as a
    # tuple of the form: (path, git repo, branch).
    # If a path is a regular directory (not a git repo), the "repo" and
    # "branch" values are set to "None".
    robot_paths: List[Tuple[str, Optional[GitRepo], Optional[str]]] = []
    branch: Optional[str]
    for path in sb_config.robot_paths:
        repo = repo_from_path(path)
        robot_paths.append((path, repo, sb_config.node_branch_name if repo else None))

    # Add additional branches to search paths that are inside Git repositories.
    for path, repo in ((path, repo) for path, repo, _ in robot_paths.copy() if repo):

        # List of branches that are already added to the "paths to explore" for
        # finding easyconfigs. This list is used below to check whether a new
        # branch contains commits that are different from already added
        # branches.
        branches_already_added = [sb_config.node_branch_name]

        for branch in (repo.main_branch_name,) + sb_config.other_node_branch_names:
            if branch not in repo.branch_names:
                branch = f"{repo.default_remote.name}/{branch}"
                if branch not in repo.remote_branch_names:
                    continue
            # It only makes sense to add a branch if it has commits that are
            # not already present on other explored branches.
            if branch_is_ahead_of_others(repo, branch, branches_already_added):
                robot_paths.append((path, repo, branch))
                branches_already_added.append(branch)

    # Search through all directories included in the EasyBuild "robot-path", in
    # the order in which they appear in the robot-path. It is important to
    # respect this order, as EasyBuild will also search in the same order.
    easyconfigs_by_name: Dict[str, Easyconfig] = {}
    for path, repo, branch in robot_paths:

        tmp = get_easyconfigs_from_directory(
            easyconfig_names=not_yet_found(),
            dir_path=path,
            git_repo=repo,
            git_branch=branch,
        )

        # TODO: remove this check at some point.
        assert not set(easyconfigs_by_name.keys()) & set(tmp.keys())

        # Add the newly found values to the output dictionary. If all
        # easyconfigs have been found, exit the function.
        easyconfigs_by_name.update(tmp)
        if len(easyconfigs_by_name) == len(file_names):
            return easyconfigs_by_name

    # This point is reached if not all easyconfigs could be found.
    return easyconfigs_by_name


def get_easyconfigs_from_directory(
    easyconfig_names: Iterable[str],
    dir_path: str,
    git_repo: Optional[GitRepo] = None,
    git_branch: Optional[str] = None,
) -> Dict[str, Easyconfig]:
    """Searches for the requested easyconfig files in the specified directory
    and, when found, returns them as a dictionary where each easyconfig name
    is associated to an Easyconfig object.

    If the directory to search is under Git version control, a specific branch
    of the repository can be searched by passing the git repo and branch name
    to search to the function.

    Easyconfigs that are not found are absent from the returned dictionary.

    :param easyconfig_names: names of the easyconfig files to retrieve. The
        name of the easyconfigs can include the full path, which can e.g. be
        useful if there are several easyconfigs with the same name in different
        directories.
    :param dir_path: path of directory to search.
    :param git_repo: optional. Git repo object of the Git repo to search.
    :param git_branch: optional. branch of the Git repo to search.
    """

    # If the directory is a git repo, switch to the specified branch before
    # searching through the target directory.
    with switch_to_branch_if_repo(git_repo, git_branch):

        # Retrieve all easyconfig files located in the target directory.
        files_in_dir = tuple(
            get_files_from_directory(dir_path, extension=".eb", full_path=True)
        )

        # Loop through all easyconfigs to recover from the directory, and check
        # whether they can be found in the target directory.
        easyconfigs_by_name: Dict[str, Easyconfig] = {}
        for easyconfig_name in easyconfig_names:
            for f in files_in_dir:
                if f.endswith(os.path.sep + easyconfig_name):
                    easyconfigs_by_name[easyconfig_name] = Easyconfig(
                        name=os.path.basename(easyconfig_name),
                        path=os.path.dirname(f),
                        repo=git_repo,
                        branch=git_branch,
                    )
                    break

        return easyconfigs_by_name


def install_license_files(sb_config: StackBuilderConfig) -> None:
    """Copies .lic license files found in the sib-software-stack git repository
    to the LICENSE_FILES_DIR"""

    # If needed, create the directory where EasyBuild searches for license
    # files. The function does nothing if the directory already exists.
    create_directory(LICENSE_FILES_DIR)

    # Copy license files that are not already present in the destination
    # directory.
    for license_file in get_files_from_directory(
        sb_config.sib_software_stack_repo.path, extension=".lic", full_path=True
    ):
        license_copy = os.path.join(LICENSE_FILES_DIR, os.path.basename(license_file))
        if not os.path.isfile(license_copy) or not filecmp.cmp(
            license_file, license_copy, shallow=True
        ):
            shutil.copy2(license_file, license_copy)
