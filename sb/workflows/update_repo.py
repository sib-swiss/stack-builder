"""Functions and classes of the "update repo" workflow."""

from ..utils.git import GitRepo
from ..utils.config import StackBuilderConfig, load_config


def update_local_repo(repo: GitRepo, sb_config: StackBuilderConfig) -> None:
    """Update all branches of the specified Git repository.

    :param repo_path: path of repo to update.
    :param sib_node: SIB node perfor
    :param main_branch: name of the main branch of the Git repo. This is the
        branch onto which all other branches are rebased.
    :raises ValueError:
    """

    # Verify the repo is clean. If there are uncommitted changes, the repo
    # cannot be updated and a error is raised.
    if repo.is_dirty():
        raise ValueError(
            f"Repo {repo.path} contains uncommitted changes. "
            "Please commit or stash your changes and try again."
        )

    # Verify that the repo has at least 2 branches: the main branch, and the
    # SIB node's own local branch. If the latter is missing, it is created.
    node_branch = sb_config.node_branch_name
    main_branch = repo.main_branch_name
    repo.new_branch(name=node_branch, raise_error_if_exists=False)
    assert node_branch in repo.branch_names and main_branch in repo.branch_names

    # Fetch updates for the repo and pull changes for the main branch and the
    # node's local branch (only if the pulls are fast-forward!).
    # Rebase the local node's branch on the main branch.
    repo.pull_branch(branch_name=main_branch, with_fetch=True)
    repo.pull_branch(branch_name=node_branch, with_fetch=True)
    repo.rebase_branch(node_branch, rebase_location=main_branch, with_fetch=False)

    # Update local instances of branches from all other nodes (if any).
    # In principle this should be infrequent, as there is no need for a local
    # node to have a local copy of other node's branches.
    for branch in set(sb_config.other_node_branch_names) & set(repo.branch_names):
        repo.reset_hard_to_upstream(branch_name=branch, with_fetch=False)


def update_repos() -> None:
    """Main workflow of the 'update' command."""

    # Load the EasyBuild and StackBuilder configuration values.
    sb_config = load_config()

    # Update the SIB Git repos.
    for repo in (sb_config.sib_easyconfigs_repo, sb_config.sib_software_stack_repo):
        update_local_repo(repo=repo, sb_config=sb_config)
