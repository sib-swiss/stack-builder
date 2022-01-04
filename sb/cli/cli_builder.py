"""Command line builder module."""

import argparse
from typing import Any, Dict, Sequence, Optional, Callable


class Argument:
    """Command line argument that can be added to a CLI parser."""

    def __init__(self, *args: Any, **kwargs: Any):
        self.args = args
        self.kwargs = kwargs


class SubcommandBase:
    """Abstract definition (interface) for a single subcommand of a CLI.
    Objects derived from this class are accepted as input for the
    "subcommands" property of CliWithSubcommands.

    :param name: the name of the subcommand, as will be shown to the used in
        the CLI.
    :param function: function associated to the subcommand.
    :param arguments: list of arguments that are accepted by the subcommand.
    :param help_text: text displayed when the user requests the help for the
        subcommand.
    """

    def __init__(
        self,
        name: str,
        aliases: Sequence[str],
        function: Callable[..., Any],
        arguments: Sequence[Argument],
        help_text: Optional[str] = None,
    ):
        self.name = name
        self.aliases = aliases
        self.help = help_text
        self.function = function
        self.arguments = arguments


class Subcommand(SubcommandBase):
    """A single subcommand corresponding to a function f of the main workflow.
    The name of the subcommand and its help are derived from the function
    itself (unless overridden).
    """

    def __init__(
        self,
        f: Callable[..., Any],
        name: Optional[str] = None,
        aliases: Sequence[str] = (),
        arguments: Sequence[Argument] = (),
        help_text: Optional[str] = None,
    ):

        super().__init__(
            name=f.__name__.replace("_", "-") if name is None else name,
            aliases=aliases,
            function=f,
            arguments=arguments,
            help_text=f.__doc__ if help_text is None else help_text,
        )


class CliWithSubcommands:
    """Entry point to command line interfaces. This is the class that
    instantiates the main (top level) parser for the CLI, that invokes it, and
    retrieves the values passed by the user on the command line.

    Subcommands can be added by creating a new class derived from this class
    and passing the subcommands as 'Subcommand' objects to the static
    :subcommands: variable.

    Example:

        class Cli(CliWithSubcommands):
            description = "..."
            subcommands = (
                Subcommand(
                    f=..., aliases=..., arguments=(Argument(...), ...)
                ),
                Subcommand(
                    f=..., aliases=..., arguments=(Argument(...), ...)
                ),
            )

    Tu run the CLI, simply instantiate a new instance of the class: Cli()
    """

    description: Optional[str] = None
    required = True
    subcommands: Sequence[SubcommandBase] = ()
    version: Optional[str] = None

    def __init__(self, *args: Any, **kwargs: Any):

        # Create the main parser object for the command line, as well as a
        # dict object "actions" that will be used to store the function
        # associated to each subcommand.
        parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.functions_by_subcmd: Dict[str, Callable[..., Any]] = {}

        # Add the --version argument to the command line.
        if self.version is not None:
            parser.add_argument("--version", action="version", version=self.version)

        # Add subcommands to the command line.
        if self.subcommands:
            self.subparser_factory = parser.add_subparsers(
                dest="subcommand", help="subcommand help", required=True
            )
            for subcommand in self.subcommands:
                self.add_subcommand(subcommand)

        # Retrive command line arguments passed by the user. user_input_args is
        # a dictionary with all the arguments passed by the user on the command
        # line.
        user_input_args = vars(parser.parse_args(*args, **kwargs))

        # Run the function corresponding to the subcommand passed by the user.
        function_to_run = self.functions_by_subcmd[user_input_args.pop("subcommand")]
        function_to_run(**user_input_args)

    def add_subcommand(self, subcommand: SubcommandBase) -> None:
        """Add a subcommand to the main command line interface."""

        # Create parser for the subcommand.
        subcmd_parser = self.subparser_factory.add_parser(
            name=subcommand.name,
            aliases=subcommand.aliases,
            help=subcommand.help,
        )

        # Add the function associated to the subcommand to the dictionary that
        # associates functions with subcommand and alias names.
        for name_or_alias in (subcommand.name, *subcommand.aliases):
            if name_or_alias in self.functions_by_subcmd:
                raise ValueError(
                    f"Duplicated subcommand name or alias: '{name_or_alias}'."
                )
            self.functions_by_subcmd[name_or_alias] = subcommand.function

        # Add arguments from the subcommand to the subcommand parser.
        for arguments in subcommand.arguments:
            subcmd_parser.add_argument(*arguments.args, **arguments.kwargs)
