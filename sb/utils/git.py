"""Module for Git related functions."""

import os
import sys
import contextlib
from contextlib import contextmanager
from typing import (
    ContextManager,
    Iterable,
    Tuple,
    Generator,
    Any,
    Optional,
    cast,
)
from enum import Enum

import git
from git import refs


class Status(Enum):
    """Status of a git branch as compared to its upstream branch."""

    UP_TO_DATE = "up_to_date"
    BEHIND = "behind"
    DIVERGED = "diverged"
    AHEAD = "ahead"
    NO_UPSTREAM = "no_upstream"


class GitRepoError(Exception):
    """Error class for GitRepo"""

    def __init__(self, msg: Optional[str] = None, repo: Optional["GitRepo"] = None):
        super().__init__(
            (f"Error in Git repository [{repo.path}]. " if repo else "")
            + (msg if msg else "Unspecified error message.")
        )


class GitRepo(git.Repo):
    """Class that extends git.Repo."""

    def __init__(
        self,
        path: str,
        *args: Any,
        main_branch_name: str = "main",
        main_remote_name: str = "origin",
        **kwargs: Any,
    ):
        # Instantiate a new git.Repo object.
        try:
            super().__init__(os.path.expanduser(path), *args, **kwargs)
        except git.NoSuchPathError:
            raise GitRepoError(
                f"Unable to find path of the Git repo on the local host: {path}"
            ) from None
        except git.InvalidGitRepositoryError:
            raise GitRepoError(
                f"The specified path is not a valid Git repository: {path}"
            ) from None

        # Verify the repo is not a bare repo.
        if self.bare:
            raise GitRepoError("Repo is a bare repo.", repo=self)

        # Verify the repo has the specified default branch and remotes.
        if main_branch_name not in self.branch_names:
            raise GitRepoError(f"Repo has no branch '{main_branch_name}'.", repo=self)
        if main_remote_name not in self.remote_names:
            raise GitRepoError(f"Repo has no remote '{main_remote_name}'.", repo=self)
        self.main_branch_name = main_branch_name
        self.default_remote = self.remote(name=main_remote_name)

    @property
    def path(self) -> str:
        """Root directory of the Git repo (working tree directory)."""
        return str(self.working_dir)

    @property
    def name(self) -> str:
        """Name of git repo."""
        return os.path.basename(self.path)

    @property
    def branch_names(self) -> Tuple[str, ...]:
        """Returns the names of all local branches of the git repo."""
        return tuple(
            branch.name for branch in cast(Iterable[refs.head.Head], self.branches)
        )

    @property
    def remote_names(self) -> Tuple[str, ...]:
        """Returns the names of all remotes of the git repo."""
        return tuple(remote.name for remote in self.remotes)

    @property
    def remote_branch_names(self) -> Tuple[str, ...]:
        """Returns the names of all remote branches of the git repo."""
        return tuple(x.name for remote in self.remotes for x in remote.refs)

    def branch(self, name: Optional[str] = None) -> refs.head.Head:
        """Returns the branch object corresponding to the specified name.
        If no branch name is passed as argument, the default branch of the
        repository is returned.
        """
        branch: refs.head.Head
        for branch in cast(Iterable[refs.head.Head], self.branches):
            if branch.name == (name or self.main_branch_name):
                return branch
        raise GitRepoError(f"Repo has no branch '{name}'.", repo=self)

    def remote_branch(
        self, name: str, remote: Optional[git.Remote] = None
    ) -> git.RemoteReference:
        """Returns the remote branch object [RemoteReference] corresponding to
        the specified remote branch name on the specified remote.

        :param name: name of the remote branch. The name can be either in the
            form "branch" or "remote/branch", where "remote" indicates the
            name of the remote from which to retrieve the branch.
        :param remote: remote from where to retrieve the branch. If no value
            is passed, the branch is searched for on the default remote.
            Alternatively, the remote can also be specified via the "name"
            argument.
        """
        if "/" not in name:
            name = f"{remote.name if remote else self.default_remote.name}/{name}"

        for repo_remote in self.remotes:
            for remote_branch in repo_remote.refs:
                if remote_branch.name == name:
                    return remote_branch

        raise GitRepoError(f"Repo has no remote branch '{name}'.", repo=self)

    def branch_status(
        self, branch_name: str, branch_to_compare_with: Optional[str] = None
    ) -> Status:
        """Determines whether the specified branch is up-to-date, ahead or
        behind its tracking branch on the remote.
        """
        # If no branch to compare to is provided, use the upstream of the
        # specified branch.
        if not branch_to_compare_with:
            branch = self.branch(branch_name)
            remote_branch = branch.tracking_branch()
            if not remote_branch:
                return Status.NO_UPSTREAM
            branch_to_compare_with = remote_branch.name

        # Verify the branches to compare exist in the repo.
        for b in (branch_name, branch_to_compare_with):
            if b not in self.branch_names + self.remote_branch_names:
                raise GitRepoError(
                    f"Repo has no branch '{b}'. Cannot perform branch status "
                    f"comparison: {branch_name}...{branch_to_compare_with}",
                    repo=self,
                )

        # Use the "git rev-list --left-right --count branch...origin/branch"
        # command to determine whether the specified branch is ahead or behind
        # its remote counterpart. If it is both ahead and behind, it means that
        # the branches have diverged.
        ahead, behind = (
            int(x)
            for x in self.git.rev_list(
                "--left-right", "--count", f"{branch_name}...{branch_to_compare_with}"
            ).split()
        )
        if ahead == 0 and behind == 0:
            return Status.UP_TO_DATE
        if behind == 0:
            return Status.AHEAD
        if ahead == 0:
            return Status.BEHIND
        return Status.DIVERGED

    def fetch_updates(self) -> None:
        """Fetch updates from all remotes associated to the repo."""
        for remote in self.remotes:
            remote.fetch(prune=True)

    def switch(self, branch_name: str) -> None:
        """Switch/checkout to the specified branch."""

        # If the requested branch is already checked-out, nothing to do.
        if not self.head.is_detached and branch_name == self.active_branch.name:
            return

        # Switch to the requested branch.
        try:
            branch = self.branch(name=branch_name)
            branch.checkout()
        except GitRepoError as e:
            # Error case 1: the branch does not exist in the current repo.
            raise GitRepoError(f"{e} Cannot switch to '{branch_name}'.") from None
        except git.GitCommandError as e:
            # Error case 2: cannot switch branches because repo is not clean.
            raise GitRepoError(
                "Repo contains uncommitted changes, "
                f"cannot switch to branch '{branch_name}'.",
                repo=self,
            ) from e

    def checkout(self, refspec: str) -> None:
        """Checkout the working tree to the specified reference, e.g. a commit
        or a remote branch (e.g. "origin/branch").
        Local branches can also be checkout-out, but using `self.switch()` is
        preferred for that use case.
        """
        # If the specified reference is a local branch, fallback on the
        # `switch` command.
        if refspec in self.branch_names:
            self.switch(branch_name=refspec)
            return

        # Checkout the specified reference in "detached head" mode.
        try:
            self.git.checkout("--detach", refspec)
        except git.GitCommandError as e:
            if "would be overwritten" in str(e):
                error_msg = "repo contains uncommitted changes."
            elif "does not take a path argument" in str(e):
                error_msg = "reference does not exist in repo."
            else:
                error_msg = "see details above."
            raise GitRepoError(
                f"Cannot checkout commit/reference '{refspec}': {error_msg}",
                repo=self,
            ) from e

    @contextmanager
    def switch_to_branch(
        self, branch_or_refspec: str, revert_on_exit: bool = True
    ) -> Generator[None, None, None]:
        """Context manager that switches to the specified branch or does a
        checkout of the specified reference (e.g. a commit or a remote branch).
        It reverts back to the initial branch upon exit by default.
        """
        initial_branch = self.active_branch.name

        # Switch to the specified branch upon entering the context manager.
        # Note: switch has no effect if the requested branch is already
        # checked-out.
        if branch_or_refspec in self.branch_names:
            self.switch(branch_name=branch_or_refspec)
        else:
            self.checkout(refspec=branch_or_refspec)

        try:
            yield

        # Switch back to the original branch upon exit.
        finally:
            if revert_on_exit:
                self.switch(initial_branch)

    def pull_branch(
        self,
        branch_name: str,
        with_fetch: bool = True,
        error_on_missing_upstream: bool = True,
        error_on_diverged: bool = True,
    ) -> None:
        """Perform a git pull (fetch + merge) on the specified branch. The pull
        operation is only performed if the merge with the upstream branch is
        fast-forward. If history has diverged, an error is raised.

        :param branch_name: name of branch to update.
        :param with_fetch: if True, a git fetch is performed before checking
            whether the branch is up-to-date and can be fast-forward merged.
        :param error_on_missing_upstream: if True, an error is raised in the
            case where a branch has no upstream tracking branch on the remote.
            If False, no pull is made and no error is raised.
        :param error_on_diverged: if True, an error is raised if the local and
            upstream branches have diverged, i.e. no fast-forward pull is
            possible.
        :raises GitRepoError:
        """
        # Get the status of the branch to push, e.g. is it ahead or behind its
        # remote tracking branch.
        if with_fetch:
            self.fetch_updates()
        status = self.branch_status(branch_name)

        # If the local branch is behind its remote tracking branch, perform
        # a git pull. Nothing to do if status is UP_TO_DATE or AHEAD.
        if status is Status.BEHIND:
            # Get the remote associated to the branch's upstream.
            branch = self.branch(branch_name)
            remote_branch = cast(git.RemoteReference, branch.tracking_branch())
            remote = self.remote(remote_branch.remote_name)
            if self.active_branch == branch:
                # Case 1: the branch to update is the current branch.
                info = remote.pull(refspec=branch_name)[0]
                if info.flags != 0 or branch.commit != remote_branch.commit:
                    raise GitRepoError(
                        f"Git command failed: git pull {remote.name} {branch_name}",
                        repo=self,
                    )
            else:
                # Case 2: the branch to update is not the current branch.
                refspec = f"{branch_name}:{branch_name}"
                info = remote.fetch(refspec=refspec)[0]
                if (
                    info.flags != info.FAST_FORWARD
                    or branch.commit != remote_branch.commit
                ):
                    raise GitRepoError(
                        f"Git command failed: git fetch {remote.name} {refspec}",
                        repo=self,
                    )
        elif status is Status.DIVERGED and error_on_diverged:
            raise GitRepoError(
                f"Cannot auto-update (pull) branch '{branch_name}' because it "
                "has diverged from its upstream. Please resolve the issue "
                "manually.",
                repo=self,
            )
        elif status is Status.NO_UPSTREAM and error_on_missing_upstream:
            raise GitRepoError(
                f"Cannot auto-update (pull) branch '{branch_name}' because it "
                f"has no upstream. Please resolve the issue manually.",
                repo=self,
            )

    def push_branch(
        self,
        branch_name: str,
        remote: Optional[git.Remote] = None,
        allow_force: bool = False,
        with_fetch: bool = False,
    ) -> None:
        """Perform a git push on the specified branch to the specified remote.
        Set allow_force to True to authorize --force pushes.
        """
        # Get the status of the branch to push, e.g. is it ahead or behind its
        # remote tracking branch.
        if with_fetch:
            self.fetch_updates()
        status = self.branch_status(branch_name)
        cmd_with_error = ""

        # If not remote is set, get the remote associated to the upstream
        # branch or the repo's default remote.
        if not remote:
            if status is Status.NO_UPSTREAM:
                remote = self.default_remote
            else:
                # Get the remote associated to the branch's upstream.
                branch = self.branch(branch_name)
                remote_branch = cast(git.RemoteReference, branch.tracking_branch())
                remote = self.remote(remote_branch.remote_name)

        # Perform git push with the appropriate options depending on the
        # branch's status.
        # Note: nothing to do for Status.UP_TO_DATE and Status.BEHIND.
        if status is Status.AHEAD:
            info = remote.push(refspec=branch_name)[0]
            if info.flags != info.FAST_FORWARD:
                cmd_with_error = "git push"
        elif status is Status.DIVERGED:
            if allow_force:
                info = remote.push(refspec=branch_name, force=True)[0]
                if info.flags != info.FORCED_UPDATE:
                    cmd_with_error = "git push --force"
            else:
                raise GitRepoError(
                    f"Branch '{branch_name}' cannot be pushed to the "
                    f"remote '{remote.name}' because its history with the "
                    "upstream branch has diverged. "
                    "Please resolve manually or allow for '--force' push.",
                    repo=self,
                )
        elif status is Status.NO_UPSTREAM:
            info = remote.push(refspec=branch_name, set_upstream=True)[0]
            if info.flags != info.NEW_HEAD:
                cmd_with_error = "git push --set-upstream"

        # If an error occurred, raise an error.
        if cmd_with_error:
            raise GitRepoError(
                f"Git command failed: {cmd_with_error} {remote.name} {branch_name}",
                repo=self,
            )

    def new_branch(
        self, name: str, root_commit: str = "HEAD", raise_error_if_exists: bool = False
    ) -> None:
        """Create a new branch with the specified name. If a branch with that
        name already exists on the default remote, the new branch is created
        from the remote branch and the remote branch is used set as upstream.

        :param name: name of branch to create.
        :param root_commit: commit where the new branch should be
            created/rooted. By defaults new branches are created at the current
            position of HEAD.
        :param raise_error_if_exists: if True, and error is raised when
            attempting to create a new branch that already exists. If False,
            no action is taken if the branch already exists.
        """
        # If the branch already exists, do nothing or raise an error if the
        # user asked for it.
        if name in self.branch_names:
            if raise_error_if_exists:
                raise GitRepoError(
                    f"Cannot create new branch named '{name}' as it already exists.",
                    repo=self,
                )
            return

        # Create a new local branch.
        new_branch = self.create_head(name, commit=root_commit)

        # If a remote branch with the same name exists, set the local branch
        # to track that remote branch.
        for remote in self.remotes:
            remote.fetch()
            if f"{remote.name}/{name}" in self.remote_branch_names:
                new_branch.commit = f"{remote.name}/{name}"
                new_branch.set_tracking_branch(
                    remote_reference=self.remote_branch(name, remote)
                )
                return
        return

    def reset_branch(self, branch: git.Head, ref_to_reset_to: str) -> None:
        """Reset the specified branch to the specified reference, for instance
        a commit or another branch.

        :param branch: branch to reset (as a Head object).
        :param ref_to_reset_to: reference, e.g. a commit or the name of another
            branch, to which the branch should be reset to.
        :raises GitRepoError:
        """
        if self.active_branch == branch:
            # If the branch to reset is the current branch, the index and the
            # working tree must also be updated so that they match the
            # specified reference.
            if self.is_dirty():
                raise GitRepoError(
                    f"Cannot reset branch '{branch.name}' to "
                    f"'{ref_to_reset_to}' as it is the currently active "
                    "branch and the repo contains uncommitted changes "
                    "(working tree not clean).",
                    repo=self,
                )
            self.head.reset(commit=ref_to_reset_to, index=True, working_tree=True)
        else:
            # If the branch to update is not checked-out, it is sufficient to
            # set the branch's reference to the specified reference.
            branch.commit = ref_to_reset_to

    def reset_branch_to_upstream(
        self,
        branch_name: str,
        with_fetch: bool = True,
    ) -> None:
        """Reset the specified branch to the position of its upstream branch.

        If the branch to reset is the currently active branch, the index and
        working tree are also reset. In this sense, this is similar to a
        'reset --hard origin/branch_name' on the specified branch.

        If the branch has no upstream, an error is raised.
        """
        # Fetch updates from the remote.
        if with_fetch:
            self.fetch_updates()

        # Set the branch's reference (pointer) to the upstream's reference.
        branch = self.branch(branch_name)
        remote_branch = branch.tracking_branch()
        if not remote_branch:
            raise GitRepoError(
                f"Cannot reset branch '{branch_name}' to upstream as the "
                "branch has no upstream.",
                repo=self,
            )

        # Reset branch to the its upstream branch.
        self.reset_branch(branch=branch, ref_to_reset_to=remote_branch.commit)

    def rebase_branch(
        self,
        branch_name: str,
        rebase_location: str,
        with_fetch: bool = True,
    ) -> None:
        """Rebase the specified branch on the specified rebase_location."""
        if with_fetch:
            self.fetch_updates()

        with self.switch_to_branch(branch_name):
            try:
                self.git.rebase(rebase_location)
            except git.GitCommandError as e:
                self.git.rebase("--abort")
                raise GitRepoError(
                    f"Unable to automatically rebase {branch_name} on "
                    f"{rebase_location} because of merge conflicts. "
                    "Please rebase manually.",
                    repo=self,
                ) from e

    def merge_branch(
        self,
        branch_name: str,
        branch_to_merge: str,
    ) -> None:
        """Merges branch "branch_to_merge" into the specified branch."""

        # If the branch to merge into is exactly behind the branch to merge,
        # a fast-forward merge is possible (provided that the working tree is
        # clean or that the branch to merge into is not the currently active
        # branch. Such a fast-forward merge is the same as a hard-reset.
        status = self.branch_status(branch_name, branch_to_merge)
        if status is Status.BEHIND:
            try:
                self.reset_branch(
                    branch=self.branch(branch_name), ref_to_reset_to=branch_to_merge
                )
                return
            except GitRepoError:
                # If the branch to merge into is the currently active branch
                # and the repository is dirty, a error is raised.
                pass

        # If the above fast-forward merge is not possible, fall-back onto the
        # standard "git merge" command.
        with self.switch_to_branch(branch_name):
            try:
                self.git.merge(branch_to_merge)
            except git.GitCommandError as e:
                self.git.merge("--abort")
                raise GitRepoError(
                    f"Unable to automatically merge branch '{branch_to_merge}' "
                    f"into branch '{branch_name}' because of merge conflicts. "
                    "Please merge manually.",
                    repo=self,
                ) from e
        return

    def grep_history(self, search_term: str, branch_name: str) -> str:
        """Search for the specified pattern on the specified branch, but only in
        the part of the history that diverges from the "develop" branch.
        """
        return self.git.log(
            "--oneline",
            "--grep",
            search_term,
            f"{self.main_branch_name}..{branch_name}",
        )


def switch_to_branch_if_repo(
    repo: Optional[GitRepo], branch: Optional[str]
) -> ContextManager[None]:
    """If a GitRepo and branch are given as input, returns a context manager
    that switches the git repo to the specified local or remote branch.
    If both the repo and branch value are "None", a nullcontext context manager
    is returned.
    """
    if repo and branch:
        return repo.switch_to_branch(branch, revert_on_exit=True)
    if repo and not branch:
        raise ValueError("Either both or neither 'repo' and 'branch' should be 'None'.")

    # Note: to support python 3.6, return contextlib.suppress().
    #       This can be removed once support for 3.6 is no longer needed.
    if sys.version_info >= (3, 7):
        return contextlib.nullcontext()
    return contextlib.suppress()
