"""Module with general functions."""

import os
import re
import sys
import shutil
import subprocess  # nosec
from pathlib import Path
from typing import Sequence, Optional, Iterator, Union

from .config import UserAnswer


def create_directory(
    dir_paths: Union[str, Sequence[str]], raise_error_if_exists: bool = False
) -> None:
    """Recursively create the specified directory(ies) on disk."""
    if isinstance(dir_paths, str):
        dir_paths = (dir_paths,)

    for dir_path in dir_paths:
        # Check whether the directory to create already exists.
        dir_to_create = Path(os.path.expanduser(dir_path))
        if dir_to_create.is_dir():
            if raise_error_if_exists:
                raise ValueError(
                    f"Cannot create directory '{dir_to_create}' as it "
                    "already exists."
                )
            continue

        # Recursively create the new dictroy. If a file/symlink with the same
        # name already exists, an error is raised.
        try:
            dir_to_create.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise ValueError(
                f"Cannot create directory '{dir_to_create}'. "
                "A file/symlink with the same name already exists."
            ) from None


def delete_directory_content(
    *dir_paths: str, dry_run: bool = False, verbose: bool = False
) -> None:
    """Recursively delete the entire content of the specified directory(ies),
    but not the directory(ies) itself.
    """
    for dir_path in map(Path, dir_paths):
        if not dir_path.is_dir():
            raise ValueError(f"Cannot delete content of [{dir_path}]: not a directory.")

        if dry_run:
            for path in dir_path.iterdir():
                print(
                    f"Would have deleted {'directory' if path.is_dir() else 'file'}:",
                    path,
                )
        else:
            if verbose:
                print(f"Deleting content of: {dir_path}")
            for path in dir_path.iterdir():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()


def get_files_from_directory(
    dir_path: str, extension: Optional[str] = None, full_path: bool = True
) -> Iterator[str]:
    """Returns all files found (recursively) in the specied directory.

    If an extension is specified, only the files with that extension are
    returned.
    """
    for root, _, files in os.walk(os.path.expanduser(dir_path)):
        if extension:
            files = [f for f in files if f.endswith(extension)]
        for f in files:
            yield os.path.join(root, f) if full_path else f


def run_subprocess(
    args: Sequence[str],
    capture_output: bool,
    return_stdout: bool = False,
    dry_run: bool = False,
) -> Optional[str]:
    """Wrapper for subprocess that checks whether an error occurred and,
    if so, raises an error.
    """
    if dry_run:
        print("Would have run: " + " ".join(args))
        return None

    try:
        if sys.version_info.minor >= 7:
            # nosec
            process = subprocess.run(
                args=args, capture_output=capture_output, check=True, shell=False
            )
        else:
            # nosec
            process = subprocess.run(args=args, check=True, shell=False)
    except subprocess.CalledProcessError as e:
        raise ValueError(f"subprocess command failed: {' '.join(args)}") from e

    if return_stdout:
        return process.stdout.decode("utf-8").strip()

    return None


def user_confirmation_dialog(*messages: str) -> UserAnswer:
    """Displays a dialog requesting the user for confirmation to proceed."""

    msg = (
        "### " + "\n### ".join(messages) + "\n"
        "###          Note: confirmation requests can be suppressed in the "
        "stack-builder config file.\n"
        "###          Are you sure you want to proceed [yes/y/no/n]?: "
    )
    return UserAnswer.YES if input(msg).lower() in ("y", "yes") else UserAnswer.NO
