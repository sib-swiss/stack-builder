"""Module for Config and package list file parsing."""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Sequence, List, Tuple, Iterator, Dict, Any

from .git import GitRepo

EB_CONFIG_FILE = "config.cfg"
SB_CONFIG_FILE = "config_stackbuilder.cfg"
EB_DEFAULT_CONFIG_DIR = Path.home().joinpath(".config", "easybuild").as_posix()
SIB_EASYCONFIGS_REPO = "sib-easyconfigs.git"
SIB_SOFTWARE_STACK_REPO = "sib-software-stack.git"
EASYCONFIGS_LIST_FILE = "sib_stack_package_list.txt"
EASYCONFIGS_LIST_FILE_OVERRIDE = "package_list.txt"
SIB_EASYCONFIGS_MAIN_BRANCH = "develop"
SIB_SOFT_STACK_MAIN_BRANCH = "main"
LICENSE_FILES_DIR = Path.home().joinpath("licenses").as_posix()
EB_OFFICIAL_REPO = "https://github.com/easybuilders/easybuild-easyconfigs"
EB_OFFICIAL_REPO_NAME = "eb-source"

# List of easyconfigs for which a "-noAVX2.eb"
NO_AVX2_PACKAGES = [
    "FFTW-3.3.9-gompi-2021a.eb",
    "RDKit-2021.03.4-foss-2021a.eb",
    "RDKit-2022.03.3-foss-2021a.eb",
    "OpenBabel-3.1.1-gompi-2021a.eb",
]


class UserAnswer(Enum):
    """User confirmation."""

    YES = "yes"
    NO = "no"
    INTERACTIVE = "interactive"


class SIBNode(Enum):
    """SIB node names."""

    HUG = "hug"  # HUG Geneva hospitals
    IBU = "ibu"  # IBU cluster
    SCI = "scicore"  # sciCORE
    UBE = "ubelix"  # UBELIX cluster
    VIT = "vitalit"  # SIB lausanne
    TEST = "test_node"  # Node for running tests.


USER_ANSWER_SYNONYMS: Dict[UserAnswer, Tuple[str, ...]] = {
    UserAnswer.YES: (UserAnswer.YES.value, "y", "True", "true"),
    UserAnswer.NO: (UserAnswer.NO.value, "n", "False", "false"),
    UserAnswer.INTERACTIVE: (UserAnswer.INTERACTIVE.value,),
}

SIB_NODE_SYNONYMS: Dict[SIBNode, Tuple[str, ...]] = {
    SIBNode.HUG: (SIBNode.HUG.value, "HUG"),
    SIBNode.IBU: (SIBNode.IBU.value, "IBU"),
    SIBNode.SCI: (SIBNode.SCI.value, "sci", "SCI"),
    SIBNode.UBE: (SIBNode.UBE.value, "ube", "UBE"),
    SIBNode.VIT: (SIBNode.VIT.value, "vital-it", "vit", "VIT"),
    SIBNode.TEST: (SIBNode.TEST.value, "TEST"),
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
        other_nodes: Optional[Sequence[SIBNode]] = None,
        sib_easyconfigs_repo: Optional[str] = None,
        sib_software_stack_repo: Optional[str] = None,
        optional_software: Optional[Sequence[SIBNode]] = None,
        optarch: Optional[str] = None,
        job_cores: Union[int, str] = 0,
        allow_reset_node_branch: UserAnswer = UserAnswer.INTERACTIVE,
        allow_reset_other_nodes_branch: UserAnswer = UserAnswer.INTERACTIVE,
    ) -> None:

        # Required EasyBuild properties.
        self.buildpath = os.path.expanduser(buildpath)
        self.sourcepath = os.path.expanduser(sourcepath)
        self.installpath = os.path.expanduser(installpath)
        self.robot_paths = [os.path.expanduser(x) for x in robot_paths]

        # Required stack-builder properties.
        self.sib_node = sib_node
        self.sib_easyconfigs_repo = GitRepo(
            path=sib_easyconfigs_repo or self._dir_from_robotpath(SIB_EASYCONFIGS_REPO),
            main_branch_name=SIB_EASYCONFIGS_MAIN_BRANCH,
            main_remote_name="origin",
        )
        self.sib_software_stack_repo = GitRepo(
            path=sib_software_stack_repo
            or self._dir_from_robotpath(SIB_SOFTWARE_STACK_REPO),
            main_branch_name=SIB_SOFT_STACK_MAIN_BRANCH,
            main_remote_name="origin",
        )
        self.allow_reset_node_branch = allow_reset_node_branch
        self.allow_reset_other_nodes_branch = allow_reset_other_nodes_branch

        # Optional EasyBuild properties.
        self.optarch = optarch
        self.job_cores = int(job_cores)

        # Optional stack-builder properties.
        self.other_nodes = tuple(
            x
            for x in (other_nodes if other_nodes else tuple(SIBNode))
            if x != self.sib_node
        )

        self.optional_software = (self.sib_node,) + tuple(
            x
            for x in (optional_software if optional_software else ())
            if x != self.sib_node
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
        for file_name in (EASYCONFIGS_LIST_FILE_OVERRIDE, EASYCONFIGS_LIST_FILE):
            file_path = Path(self.sib_software_stack_repo.path).joinpath(file_name)
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


def str_to_node(node_name: str) -> SIBNode:
    """Returns the SIBNode object corresponding to the given node name or one
    if its synonyms.
    """
    for node, synonyms in SIB_NODE_SYNONYMS.items():
        if node_name in synonyms:
            return node

    raise ValueError(
        f"Unable to determine the node value: the node name '{node_name}' "
        "does not match any accepted node name or one if its synonyms. "
        "Accepted values are: "
        + "; ".join(
            [
                f"{node.value}: {', '.join(synonyms)}"
                for node, synonyms in SIB_NODE_SYNONYMS.items()
            ]
        )
        + "."
    )


def str_to_useranswer(value: str) -> UserAnswer:
    """Converts a string value into the corresponding UserAnswer Enum value."""

    for user_answer, synonyms in USER_ANSWER_SYNONYMS.items():
        if value.lower() in synonyms:
            return user_answer

    raise ValueError(
        f"The value '{value}' does not match any accepted 'user answer' or "
        "one if its synonyms. Accepted values are: "
        + "; ".join(
            [
                f"{user_answer.value}: {', '.join(synonyms)}"
                for user_answer, synonyms in USER_ANSWER_SYNONYMS.items()
            ]
        )
        + "."
    )


def str_to_list(value: str) -> List[str]:
    """Converts a string to a list of strings by splitting it using a number
    of pre-defined separators.
    """
    value = value.strip()
    for sep in (":", ";", ","):
        if sep in value:
            return [x.strip() for x in value.split(sep)]
    return [value]


def config_values_from_file(
    config_file_path: str, args_required: Sequence[str], args_optional: Sequence[str]
) -> Dict[str, Any]:
    """Load arguments from the specified config file."""

    # "sequence_args" are arguments that are lists/sequences of one or more
    # values delimited by ":" characters.
    args_captured: Dict[str, Any] = {}
    sequence_args = ("robot_paths", "other_nodes", "optional_software")

    # Read through the config file, load required and optional arguments, and
    # ignore comment lines.
    with open(os.path.expanduser(config_file_path), mode="r", encoding="utf8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or " = " not in line:
                continue

            argument, value = map(str.strip, line.split(" = "))
            argument = argument.replace("-", "_")
            value = value.replace('"', "")
            if argument in args_required or argument in args_optional:
                if argument in sequence_args:
                    args_captured[argument] = str_to_list(value)
                else:
                    args_captured[argument] = value

    # If a required value is missing, raise an error.
    missing_args = set(args_required) - set(args_captured.keys())
    if missing_args:
        raise ValueError(
            "One or more required values are missing from the config file "
            f"[{config_file_path}]: {', '.join(missing_args)}."
        )

    return args_captured


def load_config() -> StackBuilderConfig:
    """Load an EasyBuild configuration file from disk and return the values
    as a StackBuilderConfig object.
    """

    # Load values from the EasyBuild config file.
    eb_config_file = get_eb_config_file()
    args_captured = config_values_from_file(
        config_file_path=eb_config_file,
        args_required=("buildpath", "sourcepath", "robot_paths", "installpath"),
        args_optional=("job_cores", "optarch"),
    )

    # Load values from the stack-builder config file.
    sb_config_file = get_sb_config_file()
    args_captured.update(
        config_values_from_file(
            config_file_path=sb_config_file,
            args_required=(
                "sib_easyconfigs_repo",
                "sib_software_stack_repo",
                "sib_node",
                "allow_reset_node_branch",
                "allow_reset_other_nodes_branch",
            ),
            args_optional=("other_nodes", "optional_software"),
        )
    )

    # Convert SIB node strings into SIBNode objects.
    args_captured["sib_node"] = str_to_node(args_captured["sib_node"])
    for arg_name in ("other_nodes", "optional_software"):
        if arg_name in args_captured:
            args_captured[arg_name] = list(map(str_to_node, args_captured[arg_name]))

    # Convert UserAnswer strings into UserAnswer objects.
    for arg_name in ("allow_reset_node_branch", "allow_reset_other_nodes_branch"):
        args_captured[arg_name] = str_to_useranswer(args_captured[arg_name])

    # Verify that all path values given in the config files exist on disk.
    # Note: the code is a bit tedious because we want to specify the name of
    # config file and the name of the argument when a path is missing.
    paths_to_check = [
        (args_captured[x], x, eb_config_file)
        for x in ("buildpath", "sourcepath", "installpath")
    ]
    paths_to_check.extend(
        (x, "robot_paths", eb_config_file) for x in args_captured["robot_paths"]
    )
    paths_to_check.extend(
        (args_captured[x], x, sb_config_file)
        for x in ("sib_easyconfigs_repo", "sib_software_stack_repo")
    )

    robot_paths = []
    for path, arg_name, config_file in paths_to_check:
        # Update path argument with expanded user home directory.
        path = os.path.expanduser(path)
        if arg_name == "robot_paths":
            robot_paths.append(path)
        else:
            args_captured[arg_name] = path

        if not os.path.isdir(path):
            raise ValueError(
                f"Config file error [{config_file}]: unable to find directory"
                f"specified for argument '{arg_name}' [{path}]."
            )

    # Update path values with expanded user home directory for robot-path.
    args_captured["robot_paths"] = robot_paths
    return StackBuilderConfig(**args_captured)


def config_file_from_environment_variable(environment_var_name: str) -> Optional[str]:
    """Test whether the specified shell environment variable exists and:
    * if True, further test whether it points to an existing file, and if so,
      return that file. Raises an error otherwise.
    * if False, returns None.
    """
    if environment_var_name in os.environ:
        config_file = Path(os.path.expanduser(os.environ[environment_var_name]))
        if config_file.is_file():
            return config_file.as_posix()

        raise ValueError(
            "Error loading config file: the file defined in the "
            f"[{environment_var_name}] environment variable is missing or "
            f"cannot be accessed: {config_file}"
        )

    return None


def get_eb_config_file() -> str:
    """Search for an EasyBuild config file in different locations and return
    the path to the file if found.
    The following locations are searched:
     * EASYBUILD_CONFIGFILES environment variable.
     * ~/.config/easybuild (the default easybuild location for config files).
    """

    # Try to retrieve the config file form the EASYBUILD_CONFIGFILES
    # environment variable.
    environment_var_name = "EASYBUILD_CONFIGFILES"
    config_file = config_file_from_environment_variable(environment_var_name)
    if config_file:
        return config_file

    # Try to retrieve the config file from the default EasyBuild location.
    config_file = os.path.join(EB_DEFAULT_CONFIG_DIR, EB_CONFIG_FILE)
    if os.path.isfile(config_file):
        return config_file

    raise ValueError(
        "Error loading the EasyBuild config file: cannot find config file. "
        "The following locations where searched: \n"
        f" * Environment variable: {environment_var_name}\n"
        f" * File: {config_file}"
    )


def get_sb_config_file() -> str:
    """Search for a stack-builder config file in different locations and return
    the path to the file if found.
    The following locations are searched:
     * STACKBUILDER_CONFIGFILES environment variable.
     * EASYBUILD_CONFIGFILES environment variable.
     * ~/.config/easybuild (the default easybuild location for config files).
    """
    # Try to retrieve the config file form the STACKBUILDER_CONFIGFILES
    # environment variable.
    environment_var_name = "STACKBUILDER_CONFIGFILES"
    config_file = config_file_from_environment_variable(environment_var_name)
    if config_file:
        return config_file

    # Try to retrieve the config file from the default EasyBuild location or
    # from the locations specified in the EASYBUILD_CONFIGFILES environment
    # variable.
    env_var_path = config_file_from_environment_variable("EASYBUILD_CONFIGFILES")
    config_files = [
        os.path.join(x, SB_CONFIG_FILE)
        for x in ([os.path.dirname(env_var_path)] if env_var_path else [])
        + [EB_DEFAULT_CONFIG_DIR]
    ]
    for config_file in (os.path.expanduser(x) for x in config_files):
        if os.path.isfile(config_file):
            return config_file

    raise ValueError(
        "Error loading EasyBuild config file: cannot find config file. "
        "The following locations where searched: \n"
        f" * Environment variable: {environment_var_name}\n"
        f" * File(s): {config_files}"
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
