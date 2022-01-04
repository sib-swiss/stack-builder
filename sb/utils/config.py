"""Module for Config and package list file parsing."""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Sequence, List, Tuple, Iterator, Dict, Any

from .git import GitRepo

SIB_EASYCONFIGS_REPO = "sib-easyconfigs.git"
SIB_SOFTWARE_STACK_REPO = "sib-software-stack.git"
EASYCONFIGS_LIST_FILE = "sib_stack_package_list.txt"
EB_CONFIG_FILE = "config_easybuild.cfg"
SIB_EASYCONFIGS_MAIN_BRANCH = "develop"
SIB_SOFT_STACK_MAIN_BRANCH = "main"
# SB_CONFIG_FILE = "config_stackbuilder.cfg"


# List of easyconfigs for which a "-noAVX2.eb"
NO_AVX2_PACKAGES = [
    "FFTW-3.3.9-gompi-2021a.eb",
    "RDKit-2021.03.4-foss-2021a.eb",
    "OpenBabel-3.1.1-gompi-2021a-Python-3.9.5.eb",
]


class SIBNode(Enum):
    """SIB node names."""

    HUG = "hug"  # HUG Geneva hospitals
    IBU = "ibu"  # IBU cluster
    SCI = "scicore"  # sciCORE
    UBE = "ubelix"  # UBELIX cluster
    VIT = "vitalit"  # SIB lausanne


SIB_NODE_SYNONYMS: Dict[SIBNode, Tuple[str, ...]] = {
    SIBNode.HUG: ("hug", "HUG"),
    SIBNode.IBU: ("ibu", "IBU"),
    SIBNode.SCI: ("scicore", "sci", "SCI"),
    SIBNode.UBE: ("ubelix", "ube", "UBE"),
    SIBNode.VIT: ("vitalit", "vital-it", "vit", "VIT"),
}


class StackBuilderConfig:
    """Class holding the information from the EasyBuild configuration file as
    well as some additional information specific to the SIB stack builder
    tool.
    """

    def __init__(
        self,
        buildpath: str,
        sourcepath: str,
        installpath: str,
        robot_paths: Sequence[str],
        sib_node: SIBNode,
        optarch: Optional[str] = None,
        job_cores: Union[int, str] = 0,
    ) -> None:

        # Required properties.
        self.buildpath = os.path.expanduser(buildpath)
        self.sourcepath = os.path.expanduser(sourcepath)
        self.installpath = os.path.expanduser(installpath)
        self.robot_paths = [os.path.expanduser(x) for x in robot_paths]

        # Optional properties.
        self.optarch = optarch
        self.job_cores = int(job_cores)

        # SIB software stack properties.
        self.sib_node = sib_node or get_local_node()
        self.sib_easyconfigs_repo = GitRepo(
            self._dir_from_robotpath(SIB_EASYCONFIGS_REPO),
            main_branch_name=SIB_EASYCONFIGS_MAIN_BRANCH,
            main_remote_name="origin",
        )
        self.sib_software_stack_repo = GitRepo(
            self._dir_from_robotpath(SIB_SOFTWARE_STACK_REPO),
            main_branch_name=SIB_SOFT_STACK_MAIN_BRANCH,
            main_remote_name="origin",
        )

        self.__post_init__()

    # TODO: __post_init__ not called when class is instantiated.
    def __post_init__(self):
        self.validate()

    @property
    def node_synonyms(self) -> Tuple[str, ...]:
        """Returns list of synonym names for the local node."""
        return SIB_NODE_SYNONYMS[self.sib_node]

    @property
    def node_branch_name(self) -> str:
        """Returns Git branch name of the local node."""
        return self.sib_node.value

    @property
    def other_node_branch_names(self) -> Tuple[str, ...]:
        """Returns Git branch names of the other SIB nodes."""
        return tuple(
            x.value for x in tuple(SIBNode) if x.value != self.node_branch_name
        )

    @property
    def package_list_file(self) -> str:
        """Returns the path to the file containing the list of software
        packages to build on the current node.
        """
        file_path = Path(self.sib_software_stack_repo.path).joinpath(
            EASYCONFIGS_LIST_FILE
        )
        if file_path.is_file():
            return file_path.as_posix()

        raise ValueError(
            f"Error: unable to find file '{EASYCONFIGS_LIST_FILE}' in directory "
            f"'{self.sib_software_stack_repo}'."
        )

    def validate(self):
        """Verify values from the config file."""
        missing_dirs = [
            path
            for path in (
                [
                    self.buildpath,
                    self.sourcepath,
                    self.installpath,
                    self.sib_software_stack_repo.path,
                    self.sib_easyconfigs_repo.path,
                ]
                + self.robot_paths
            )
            if not os.path.isdir(path)
        ]
        if missing_dirs:
            raise ValueError(
                "One or more directories are missing or unaccessible:\n -> "
                + "\n -> ".join(missing_dirs)
            )

    def _dir_from_robotpath(self, dir_name: str) -> str:
        """Retrieve the specified directory name (dir_name) from the list of
        paths present in robot_paths.
        """
        dir_name = dir_name.replace(".git", "")
        try:
            # Test if directory is among the robot-path directories.
            (repo_path,) = [x for x in self.robot_paths if dir_name in x]

            # Remove any trailing sub-directory from the path.
            while not os.path.basename(repo_path).startswith(dir_name):
                repo_path = os.path.dirname(repo_path)
                if repo_path == os.path.sep:
                    raise ValueError()

        except ValueError:
            raise ValueError(
                f"Path to '{dir_name}' repo not found in the EasyBuild "
                "config file. The path should be part of robot-paths."
            ) from None

        return repo_path


def get_local_node() -> SIBNode:
    """Searches environment variables for SIB_SOFTWARE_STACK_NODE. If the
    variable exists, its value is returned. If it is missing, an error is
    raised.
    """
    environment_value = "SIB_SOFTWARE_STACK_NODE"
    node_name = os.environ.get(environment_value)
    for node, synonyms in SIB_NODE_SYNONYMS.items():
        if node_name in synonyms:
            return node

    raise ValueError(
        "Unable to determine local node name. Please make sure that the "
        f"shell environment value '{environment_value}' is set. "
        "Accepted values are: "
        + "; ".join(
            [
                f"{node.value}: {', '.join(synonyms)}"
                for node, synonyms in SIB_NODE_SYNONYMS.items()
            ]
        )
        + "."
    )


def load_config(sib_node: Optional[SIBNode] = None) -> StackBuilderConfig:
    """Load an EasyBuild configuration file from disk and return the values
    as a StackBuilderConfig object.
    """

    # Retrieve the path to the EasyBuild config file.
    config_file_path = get_eb_config_file()

    args_required = ("buildpath", "sourcepath", "robot_paths", "installpath")
    args_optional = ("job_cores", "optarch")
    args_captured: Dict[str, Any] = {}

    # Load arguments from EasyBuild config file.
    with open(os.path.expanduser(config_file_path), mode="r", encoding="utf8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or " = " not in line:
                continue

            argument, value = map(str.strip, line.split(" = "))
            argument = argument.replace("-", "_")
            if argument in args_required or argument in args_optional:
                args_captured[argument] = (
                    value.split(":") if argument == "robot_paths" else value
                )

    missing_args = set(args_required) - set(args_captured.keys())
    if missing_args:
        raise ValueError(
            "One or more required values are missing from the EasyBuild "
            f"config file [{config_file_path}]: {', '.join(missing_args)}."
        )

    # If specified, add the sib_node value to the list of arguments that will
    # be passed to create the config object. Otherwise, try to retrieve it
    # from an environment variable.
    args_captured["sib_node"] = sib_node if sib_node else get_local_node()

    return StackBuilderConfig(**args_captured)


def get_eb_config_file() -> str:
    """Search for an EasyBuild config file in different locations and return
    the path to the file if found.
    """

    # Try to retrieve the config file form the EASYBUILD_CONFIGFILES
    # environment variable.
    environment_var_name = "EASYBUILD_CONFIGFILES"
    if environment_var_name in os.environ:
        config_file = Path(os.path.expanduser(os.environ[environment_var_name]))
        if config_file.is_file():
            return config_file.as_posix()

        raise ValueError(
            "Error loading EasyBuild config file: the file defined in the "
            f"[{environment_var_name}] environment variable is missing or "
            f"cannot be accessed: {config_file}"
        )

    # Try to retrieve the config file from the default EasyBuild location or
    # from the same directory as the script.
    paths_to_test = (
        Path.home().joinpath(".config", "easybuild"),
        Path(os.path.realpath(__file__)).parent,
    )
    for config_file in (x.joinpath(EB_CONFIG_FILE) for x in paths_to_test):
        if config_file.is_file():
            return config_file.as_posix()

    raise ValueError(
        "Error loading EasyBuild config file: cannot find config file. "
        "The following locations where searched: \n"
        f" * Environment variable: {environment_var_name}.\n"
        f" * Directories: {paths_to_test}."
    )


def load_package_list(
    sb_config: StackBuilderConfig, no_avx2: bool = False
) -> Tuple[List[str], List[str]]:
    """Read the text file containing the list of all software packages to build
    on the local node and return a tuple of 2 lists:
     -> packages_already_built: list of easyconfigs/packages that are already
                                built on the local node's EasyBuild stack.
     -> packages_to_build: list of easyconfigs to build.

    The local node information is provided in the sb_config object.
    """

    # Get list of already installed module files. This will be needed later to
    # determine whether a packages has already been built or not.
    already_installed_modules = list(get_installed_module_files(sb_config.installpath))

    # Read the file containing the list of packages to build, skipping comments
    # and empty lines.
    packages_to_build: List[str] = []
    packages_already_built: List[str] = []
    with open(sb_config.package_list_file, mode="r", encoding="utf8") as f:

        for line in (x for x in map(strip_comment, f) if x):

            # Skip packages that should not be built on the current node.
            split_line = line.split()
            if len(split_line) > 1:
                nodes, line = split_line
                if not any(x in nodes.split(",") for x in sb_config.node_synonyms):
                    continue

            # Add ".eb" extension to the package name if needed, and generate
            # name of module corresponding to the package. The reason the
            # "basename" of the package is taken is because it can happen that
            # the value of pkg_name is an entire path to an easyconfig, and not
            # just the name of the file.
            pkg_name = verify_and_add_extension(line)
            module_name = f"{os.path.basename(pkg_name)[:-3]}.lua"

            # If requested, replace packages for which an easyconfig without
            # avx2 support exists.
            if no_avx2 and pkg_name in NO_AVX2_PACKAGES:
                pkg_name = pkg_name[:-3] + "-noAVX2.eb"

            # Verify there is no duplicated package name.
            if os.path.basename(pkg_name) in (
                os.path.basename(x) for x in packages_already_built + packages_to_build
            ):
                raise ValueError(
                    f"Error while loading package list file. Duplicated "
                    f"package [{pkg_name}] in file [{sb_config.package_list_file}]"
                )

            # Place package in the correct "built"/"to build" list.
            if module_name in already_installed_modules:
                packages_already_built.append(pkg_name)
            else:
                packages_to_build.append(pkg_name)

    return (packages_already_built, packages_to_build)


def strip_comment(s: str, sep: str = "#") -> str:
    """Strips comments - any characters placed after a # - from strings."""
    return s[: s.find(sep)].strip() if sep in s else s.strip()


def verify_and_add_extension(package_name: str, extension: str = ".eb") -> str:
    """Verify the specified package_name value ends in ".eb", and if not, adds
    the extension.
    """
    if package_name.endswith(extension):
        return package_name
    print(
        f"Package name [{package_name}] is missing the '{extension}' "
        "extension. Adding it automatically."
    )
    return package_name + extension


def get_installed_module_files(installpath: str) -> Iterator[str]:
    """Returns the list of all installed EasyBuild module files.

    Example: ['GCCcore-10.3.0.lua', 'binutils-2.36.1.lua'].
    """
    for root, _, files in os.walk(os.path.join(installpath, "modules", "all")):
        for f in files:
            yield os.path.basename(root) + "-" + f
