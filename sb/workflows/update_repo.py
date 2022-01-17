"""Functions and classes of the "update repo" workflow."""

from ..utils.git import GitRepo, Status
from ..utils.config import (
    StackBuilderConfig,
    load_config,
    EB_OFFICIAL_REPO,
    EB_OFFICIAL_REPO_NAME,
)
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
                repo.reset_branch_to_upstream(branch_name=branch, with_fetch=False)


def update_from_easybuild_upstream(sb_config: StackBuilderConfig) -> None:
    """Update the "develop" and "main" branches from the SIB remote and local
    copy of the repo with updates from the official EasyBuild GitHub
    repository.
    """

    # If needed, add the official EasyBuild upstream GitHub repo as a remote
    # to the local sib-easyconfigs repo.
    repo = sb_config.sib_easyconfigs_repo
    try:
        eb_remote = repo.remote(EB_OFFICIAL_REPO_NAME)
    except ValueError:
        eb_remote = repo.create_remote(EB_OFFICIAL_REPO_NAME, EB_OFFICIAL_REPO)
        # To delete a remote: repo.delete_remote(eb_remote)

    assert eb_remote.exists()

    # Get updates for both the SIB and official EasyBuild remotes.
    repo.fetch_updates()

    # Update the local repo and the SIB remote from the official EasyBuild
    # remote.
    # Note: if the status of the branch to update is already UP_TO_DATE there
    # is nothing to do.
    for branch_name in (repo.main_branch_name, "main"):
        sib_branch = f"{repo.default_remote.name}/{branch_name}"
        eb_branch = f"{eb_remote.name}/{branch_name}"
        status = repo.branch_status(
            branch_name=sib_branch, branch_to_compare_with=eb_branch
        )

        if status is Status.UP_TO_DATE:
            print(f"###  -> branch '{branch_name}' is up-to-date, nothing to do.")

        elif status is Status.BEHIND:
            print(f"###  -> updating branch '{branch_name}'.")

            # Make sure the local copy of branch "develop"/"main" is up-to-date
            # with the latest version on the SIB remote.
            # This will raise an error if the branches have diverged.
            if branch_name in repo.branch_names:
                if repo.branch_status(branch_name=branch_name) is not Status.UP_TO_DATE:
                    repo.pull_branch(branch_name, with_fetch=True)
                delete_branch_upon_completion = False
            else:
                repo.new_branch(branch_name)
                delete_branch_upon_completion = True

            # Merge the updates available from the official EasyBuild repo into
            # the local "develop" branch.
            try:
                repo.merge_branch(branch_name, branch_to_merge=eb_branch)
                print(f"###  -> pushing changes to '{sib_branch}'.")
                repo.push_branch(branch_name, allow_force=False)
            finally:
                if delete_branch_upon_completion:
                    _ = repo.git.branch("-d", branch_name)

        elif status in (Status.DIVERGED, status is Status.AHEAD):
            (url_sib_repo,) = repo.default_remote.urls
            raise ValueError(
                f"Branch '{sib_branch}' from [{url_sib_repo}] should never "
                f"{'diverge' if status is Status.DIVERGED else 'be ahead'} "
                f"of branch '{eb_branch}' from [{EB_OFFICIAL_REPO}]. "
                "Please resolve this issue manually."
            )


def update_repos() -> None:
    """Main workflow of the 'update' command."""

    # Load the EasyBuild and StackBuilder configuration values.
    sb_config = load_config()

    # Get updates from the official EasyBuild upstream repo.
    print(
        f"### Updating repo {sb_config.sib_easyconfigs_repo.name} "
        f"from {EB_OFFICIAL_REPO}:"
    )
    update_from_easybuild_upstream(sb_config=sb_config)
    print("### ")

    # Update the SIB Git repos.
    for repo in (sb_config.sib_easyconfigs_repo, sb_config.sib_software_stack_repo):
        print(f"### Updating repo {repo.name}:")
        update_local_repo(repo=repo, sb_config=sb_config)
        print("### ")
