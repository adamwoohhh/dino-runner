"""Public package API for AI Dino in Terminal."""

import curses  # noqa: F401
import importlib
import random  # noqa: F401

from .agents import *  # noqa: F401,F403
from .art import *  # noqa: F401,F403
from .competition import *  # noqa: F401,F403
from .constants import *  # noqa: F401,F403
from .engine import *  # noqa: F401,F403
from .input import *  # noqa: F401,F403
from .llm import *  # noqa: F401,F403
from .replay import *  # noqa: F401,F403
from .rendering import *  # noqa: F401,F403

_CLI_EXPORTS = {
    "CliArgs",
    "arg_value",
    "competition_source_path",
    "game_mode_from_args",
    "is_competition_mode",
    "parse_cli_args",
    "render_command_help",
    "render_main_help",
    "tool_version",
}
_RUNTIME_EXPORTS = {"main"}
_SESSION_EXPORTS = {
    "AgentSession",
    "CompetitionSession",
    "ManualSession",
    "PlaySession",
    "ReplayListSession",
    "ReplaySession",
    "session_for_cli_args",
}


def cli(*args, **kwargs):
    """Run the console entrypoint without importing the submodule eagerly."""
    from .cli import cli as run_cli

    return run_cli(*args, **kwargs)


def __getattr__(name: str):
    if name in _CLI_EXPORTS:
        module = importlib.import_module(".cli", __name__)
    elif name in _RUNTIME_EXPORTS:
        module = importlib.import_module(".runtime", __name__)
    elif name in _SESSION_EXPORTS:
        module = importlib.import_module(".sessions", __name__)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(module, name)
    globals()[name] = value
    return value
