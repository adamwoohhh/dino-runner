"""Runtime session selection for curses wrapper."""

import sys

from .cli import CliArgs, parse_cli_args


def main(stdscr, cli_args: CliArgs | None = None):
    """Select the runtime session for the parsed CLI arguments."""
    cli_args = cli_args or parse_cli_args(sys.argv[1:])
    from .sessions import session_for_cli_args

    session = session_for_cli_args(stdscr, cli_args)
    if session:
        session.run()
