"""Module for Git related functions."""

import os
from contextlib import contextmanager, nullcontext
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
            (f"Error in Git repository {repo.path}. " if repo else "")
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

    def branch_status_deprecated(self) -> Status:
        """Runs a "git status" command on the repo and returns whether the
        current branch is up-to-date.
        """
        status_msg = self.git.status()
        if "branch is up to date" in status_msg:
            return Status.UP_TO_DATE
        if "branch is behind" in status_msg and "can be fast-forwarded" in status_msg:
            return Status.BEHIND
        if "branch is ahead" in status_msg:
            return Status.AHEAD
        if "have diverged" in status_msg:
            return Status.DIVERGED
        return Status.NO_UPSTREAM

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
            raise GitRepoError(f"{e} Cannot switch to {branch_name}.") from None
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
        Local branches can also be checkout-out, but using "self.switch()" is
        perferred for that use case.
        """
        # If the specified reference is a local branch, fallback on the
        # "switch" command.
        if refspec in self.branch_names:
            self.switch(branch_name=refspec)
            return

        # Checkout the specified reference in "detached head" mode.
        try:
            self.git.checkout("-d", refspec)
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
        remote: Optional[git.Remote] = None,
        raise_error_on_missing_upstream: bool = False,
    ) -> None:
        """Perform a git pull (fetch + merge) on the specified branch. The pull
        opperation is only performed if the merge with the upstream branch is
        fast-forward. If history has diverged, an error is raised.

        :param branch_name: name of branch to update.
        :param repo: git repository to update.
        :param with_fetch: if True, a git fetch is performed before checking
            whether the branch is up-to-date and can be fast-forward merged.
        :param remote: remote from which to fetch changes.
        :param raise_error_on_missing_upstream: if True, an error is raised in
            the case where a branch has no upstream tracking branch on the
            remote. If False, no pull is made and no error is raised.
        :raises GitRepoError:
        """
        # Get the status of the branch to push, e.g. is it ahead or behind its
        # remote tracking branch.
        remote = remote if remote else self.default_remote
        if with_fetch:
            remote.fetch()
        status = self.branch_status(branch_name)

        # If the local branch in behind its remote tracking branch, perform
        # a git pull.
        if status in (Status.UP_TO_DATE, Status.AHEAD):
            pass
        elif status is Status.BEHIND:
            if self.active_branch.name == branch_name:
                refspec = branch_name
                info = remote.pull(refspec=refspec)[0]
            else:
                refspec = f"{branch_name}:{branch_name}"
                info = remote.fetch(refspec=refspec)[0]
            if info.flags != 0:
                raise GitRepoError(
                    f"Git command failed: "
                    f"git {'pull' if refspec == branch_name else 'fetch'} "
                    f"{remote.name} {refspec}",
                    repo=self,
                )
        elif status is Status.DIVERGED:
            raise GitRepoError(
                f"Cannot pull branch '{branch_name}' because it has diverged "
                "from its upstream. Please resolve manually.",
                repo=self,
            )
        elif status is Status.NO_UPSTREAM and raise_error_on_missing_upstream:
            raise GitRepoError(
                f"Cannot pull branch '{branch_name}' because it has no "
                f"upstream on remote '{remote.name}'. Please resolve manually.",
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
        remote = remote if remote else self.default_remote
        if with_fetch:
            remote.fetch()
        status = self.branch_status(branch_name)
        cmd_with_error = ""

        # Perform git push with the appropriate options depending on the
        # branche's status.
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
                GitRepoError(
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

    def new_branch(self, name: str, raise_error_if_exists: bool = False) -> None:
        """Create a new branch with the specified name. If a branch with that
        name already exists on the default remote, the new branch is created
        from the remote branch and the remote branch is used set as upstream.
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
        new_branch = self.create_head(name)

        # If a remote branch with the same name exists, set the local
        # branch to track that remote branch.
        remote = self.default_remote
        remote.fetch()
        if f"{remote.name}/{name}" in self.remote_branch_names:
            new_branch.commit = f"{remote.name}/{name}"
            new_branch.set_tracking_branch(
                remote_reference=self.remote_branch(name, remote)
            )
        return

    def reset_hard_to_upstream(
        self,
        branch_name: str,
        with_fetch: bool = True,
    ) -> None:
        """Performs a 'reset --hard origin/branch_name' on the specified branch."""
        if with_fetch:
            self.default_remote.fetch()
        with self.switch_to_branch(branch_name, revert_on_exit=True):
            self.git.reset("--hard", f"{self.default_remote.name}/{branch_name}")

    def rebase_branch(
        self,
        branch_name: str,
        rebase_location: str,
        with_fetch: bool = True,
        remote: Optional[git.Remote] = None,
    ) -> None:
        """Rebase the specified branch on the specified rebase_location."""
        if with_fetch:
            _ = remote.fetch() if remote else self.default_remote.fetch()

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
    return nullcontext()
