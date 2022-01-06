"""Functions and classes of the "update repo" workflow."""

from ..utils.git import GitRepo, GitRepoError, Status
from ..utils.config import StackBuilderConfig, load_config
from ..utils.utils import user_confirmation_dialog


def update_local_repo(repo: GitRepo, sb_config: StackBuilderConfig) -> None:
    """Update all branches of the specified Git repository.

    :param repo: git repository to update, as a GitRepo object.
    :param sb_config: stack-builder config.
    :raises ValueError:
    """

    # Verify that the repo has at least 2 branches: the main branch, and the
    # SIB node's own local branch. If the latter is missing, it is created.
    main_branch = repo.main_branch_name
    node_branch = sb_config.node_branch_name
    if node_branch not in repo.branch_names:
        repo.new_branch(node_branch, root_commit=main_branch)
        remote_node_branch = f"{repo.default_remote.name}/{node_branch}"
        if remote_node_branch in repo.remote_branch_names:
            print(
                f"###  -> created new local branch '{node_branch}'"
                f"from '{remote_node_branch}'."
            )
        else:
            print(f"###  -> created new local branch '{node_branch}'.")
            repo.push_branch(node_branch)
            print(f"###  -> pushed new branch to remote '{remote_node_branch}'.")

    assert node_branch in repo.branch_names and main_branch in repo.branch_names

    # Fetch updates for the repo and pull changes for the main branch and the
    # node's local branch. If these branches have diverged from their upstream,
    # i.e. they cannot be fast-forwarded, an error is raised.
    for branch in (main_branch, node_branch):
        print(f"###  -> updating branch '{branch}' from upstream.")
        repo.pull_branch(branch_name=branch, with_fetch=True)

    # Rebase or merge the local node's branch on the main branch, if needed.
    status = repo.branch_status(node_branch, branch_to_compare_with=main_branch)
    if status is Status.BEHIND:
        print(f"###  -> merging branch '{main_branch}' into '{node_branch}'.")
        repo.merge_branch(node_branch, branch_to_merge=main_branch)
        print(f"###  -> pushing changes on branch '{node_branch}' to remote.")
        repo.push_branch(node_branch)

    elif status is Status.DIVERGED:
        # Verify the repo is clean. If there are uncommitted changes, the
        # branch cannot be rebased.
        print(f"###  -> rebasing local branch '{node_branch}' on '{main_branch}'.")
        if repo.is_dirty():
            raise ValueError(
                f"Repo {repo.path} contains uncommitted changes. Cannot "
                "rebase. Please commit or stash your changes and try again."
            )
        repo.rebase_branch(node_branch, rebase_location=main_branch, with_fetch=False)
        print("###  -> force-pushing rebased branch to remote.")
        repo.push_branch(node_branch, allow_force=True)

    else:
        print(
            f"###  -> branch '{node_branch}' is up-to-date with "
            f"'{main_branch}', nothing to rebase."
        )

    # Update local instances of branches from all other nodes (if any).
    # In principle this should be infrequent, as there is no need for a local
    # node to have a local copy of other node's branches.
    for branch in set(sb_config.other_node_branch_names) & set(repo.branch_names):
        status = repo.branch_status(branch)
        if status is Status.BEHIND:
            print(f"###  -> updating branch '{branch}' from upstream.")
            repo.pull_branch(branch_name=branch, with_fetch=False)
        elif status is Status.DIVERGED:
            print(
                f"###  -> local branch '{branch}' has diverged from "
                "its upstream and will be hard reset."
            )
            if not sb_config.confirm_hard_reset or user_confirmation_dialog(
                f"any local changes to branch '{branch}' will be lost!"
            ):
                print(f"###  -> resetting local branch '{branch}' to its upstream.")
                repo.reset_hard_to_upstream(branch_name=branch, with_fetch=False)


def update_repos() -> None:
    """Main workflow of the 'update' command."""

    # Load the EasyBuild and StackBuilder configuration values.
    sb_config = load_config()

    # Update the SIB Git repos.
    for repo in (sb_config.sib_easyconfigs_repo, sb_config.sib_software_stack_repo):
        print(f"### Updating git repo {repo.name}:")
        update_local_repo(repo=repo, sb_config=sb_config)
        print("### ")
