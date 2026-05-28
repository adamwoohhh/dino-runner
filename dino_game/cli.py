"""Command-line parsing and console script entrypoint."""

import curses
import sys
import types
from dataclasses import dataclass
from importlib import metadata

from .constants import VERSION
from .llm import (
    LLMConfig,
    config_file_path,
    load_llm_config,
    render_llm_config,
    reset_llm_config,
    resolve_llm_config_for_run,
    run_config_setup,
)
from .replay import clear_replay_files

@dataclass(frozen=True)
class CliArgs:
    """规范化后的命令行参数。"""

    command: str = "play"
    mode: str = "manual"
    record_path: str | None = None
    replay_path: str | None = None
    replay_action: str = "play"
    competition_path: str | None = None
    config_action: str = "show"
    llm_config: LLMConfig | None = None
    llm_debug: bool = False
    show_help: bool = False
    help_text: str | None = None
    version: str | None = None

COMMAND_GROUPS = [
    ("Core", [
        ("play", "Start a manual game"),
        ("agent", "Run with the local rule-based agent"),
        ("llm", "Run with the OpenAI LLM agent"),
    ]),
    ("Replay", [
        ("replay", "Play, inspect, or clear replay records"),
    ]),
    ("Competition", [
        ("compete", "Start competition mode from a replay"),
    ]),
    ("Config", [
        ("config", "View or update LLM configuration"),
    ]),
    ("Help", [
        ("help", "Show available commands and global options"),
    ]),
]

COMMAND_DESCRIPTIONS = {
    name: description
    for _, commands in COMMAND_GROUPS
    for name, description in commands
}

RUN_COMMAND_MODES = {
    "play": "manual",
    "agent": "agent",
    "llm": "llm",
}

HELP_FLAGS = {"--help", "-H"}

VERSION_FLAGS = {"--version", "-V"}

def tool_version() -> str:
    """返回安装包版本；源码运行时回退到本文件常量。"""
    try:
        return metadata.version("ai-dino-in-terminal")
    except metadata.PackageNotFoundError:
        return VERSION

def render_main_help() -> str:
    """渲染总 help，只展示子命令和公共参数。"""
    lines = [
        "Terminal Dino Runner",
        "",
        "Usage: dino <command> [options]",
        "Default: dino is equivalent to dino play",
        "",
        "Commands:",
    ]
    for group_name, commands in COMMAND_GROUPS:
        lines.append(f"  {group_name}")
        for name, description in commands:
            lines.append(f"    {name:<8} {description}")
        lines.append("")
    lines.extend([
        "Global options:",
        "  --help, -H       Show full usage and options for the current command",
        "  --version, -V    Show the tool version",
    ])
    return "\n".join(lines)

def render_command_help(command: str) -> str:
    """渲染某个子命令的完整用法和参数。"""
    if command == "play":
        usage = "dino play [--record FILE]"
        options = ["  --record FILE    Write the replay recording to FILE"]
    elif command == "agent":
        usage = "dino agent [--record FILE]"
        options = ["  --record FILE    Write the replay recording to FILE"]
    elif command == "llm":
        usage = "dino llm [--record FILE] [--debug]"
        options = [
            "  --record FILE    Write the replay recording to FILE",
            "  --debug          Write LLM request and response JSON lines to logs/",
        ]
    elif command == "replay":
        usage = "dino replay [FILE]"
        options = [
            "  FILE             Replay FILE directly; omit it to choose from a list",
            "  +list            List replay files and press Enter to inspect metadata",
            "  +clear           Delete all replay record files",
            "",
            "Examples:",
            "  dino replay +list",
            "  dino replay +clear",
        ]
    elif command == "compete":
        usage = "dino compete [FILE] [--record FILE]"
        options = [
            "  FILE             Start competition from FILE; omit it to choose from a list",
            "  --record FILE    Write the competition replay recording to FILE",
        ]
    elif command == "config":
        usage = "dino config [+setup|+reset]"
        options = [
            "  +setup           Prompt for LLM settings and save them locally",
            "  +reset           Remove the local LLM config file",
            "",
            "Examples:",
            "  dino config",
            "  dino config +setup",
            "  dino config +reset",
        ]
    elif command == "help":
        usage = "dino help [command]"
        options = ["  command          Show full usage and options for a command"]
    else:
        return render_main_help()

    lines = [
        f"Usage: {usage}",
        "",
        COMMAND_DESCRIPTIONS[command],
        "",
        "Options:",
        *options,
        "",
        "Global options:",
        "  --help, -H       Show full usage and options for the current command",
        "  --version, -V    Show the tool version",
    ]
    return "\n".join(lines)

def _split_record_option(args: list[str]) -> tuple[str | None, list[str]]:
    """从参数列表中取出 --record FILE，并返回剩余参数。"""
    record_path = None
    remaining = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--record":
            if index + 1 >= len(args) or args[index + 1].startswith("-"):
                raise ValueError("--record 需要一个文件路径")
            record_path = args[index + 1]
            index += 2
            continue
        remaining.append(arg)
        index += 1
    return record_path, remaining

def _split_debug_option(args: list[str]) -> tuple[bool, list[str]]:
    """从参数列表中取出 --debug，并返回剩余参数。"""
    debug = False
    remaining = []
    for arg in args:
        if arg == "--debug":
            debug = True
        else:
            remaining.append(arg)
    return debug, remaining

def parse_cli_args(args: list[str]) -> CliArgs:
    """解析新命令行接口；无法识别的子命令回退到总 help。"""
    args = list(args)
    if any(arg in VERSION_FLAGS for arg in args):
        return CliArgs(version=tool_version())
    if not args:
        return CliArgs()
    if args[0] in HELP_FLAGS:
        return CliArgs(show_help=True, help_text=render_main_help())
    if args[0] == "help":
        if len(args) > 1 and args[1] in COMMAND_DESCRIPTIONS:
            return CliArgs(show_help=True, help_text=render_command_help(args[1]))
        return CliArgs(show_help=True, help_text=render_main_help())
    if args[0] not in COMMAND_DESCRIPTIONS or args[0] == "help":
        return CliArgs(show_help=True, help_text=render_main_help())

    command = args[0]
    command_args = args[1:]
    if any(arg in HELP_FLAGS for arg in command_args):
        return CliArgs(command=command, show_help=True, help_text=render_command_help(command))

    if command in RUN_COMMAND_MODES:
        record_path, remaining = _split_record_option(command_args)
        llm_debug = False
        if command == "llm":
            llm_debug, remaining = _split_debug_option(remaining)
        if remaining:
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        return CliArgs(
            command=command,
            mode=RUN_COMMAND_MODES[command],
            record_path=record_path,
            llm_debug=llm_debug,
        )

    if command == "replay":
        if command_args == ["+list"]:
            return CliArgs(command=command, replay_action="list")
        if command_args == ["+clear"]:
            return CliArgs(command=command, replay_action="clear")
        if command_args and command_args[0].startswith("+"):
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        if len(command_args) > 1 or any(arg.startswith("-") for arg in command_args):
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        replay_path = command_args[0] if command_args else None
        return CliArgs(command=command, replay_path=replay_path)

    if command == "compete":
        record_path, remaining = _split_record_option(command_args)
        if len(remaining) > 1 or any(arg.startswith("-") for arg in remaining):
            return CliArgs(command=command, show_help=True, help_text=render_command_help(command))
        competition_path = remaining[0] if remaining else None
        return CliArgs(
            command=command,
            mode="competitive",
            record_path=record_path,
            competition_path=competition_path,
        )

    if command == "config":
        if not command_args:
            return CliArgs(command=command, config_action="show")
        if command_args == ["+setup"]:
            return CliArgs(command=command, config_action="setup")
        if command_args == ["+reset"]:
            return CliArgs(command=command, config_action="reset")
        return CliArgs(command=command, show_help=True, help_text=render_command_help(command))

    return CliArgs(show_help=True, help_text=render_main_help())

def game_mode_from_args(args: list[str]) -> str:
    """根据命令行参数返回运行模式名。"""
    return parse_cli_args(args).mode

def is_competition_mode(args: list[str]) -> bool:
    """判断命令行参数是否请求竞技模式。"""
    return parse_cli_args(args).command == "compete"

def competition_source_path(args: list[str]) -> str | None:
    """从竞技模式参数中读取源 replay 路径；缺省时由 UI 菜单选择。"""
    return parse_cli_args(args).competition_path

def arg_value(args: list[str], flag: str) -> str | None:
    """从命令行参数中读取形如 `--flag path` 的值。"""
    if flag not in args:
        return None
    index = args.index(flag)
    if index + 1 >= len(args):
        raise ValueError(f"{flag} 需要一个文件路径")
    return args[index + 1]

def cli():
    """Command-line entrypoint for the terminal dino game."""
    cli_args = parse_cli_args(sys.argv[1:])
    if cli_args.version:
        print(cli_args.version)
        return
    if cli_args.show_help:
        print(cli_args.help_text)
        return
    if cli_args.command == "config":
        if cli_args.config_action == "setup":
            run_config_setup()
            return
        if cli_args.config_action == "reset":
            removed = reset_llm_config()
            if removed:
                print(f"Removed config {config_file_path()}")
            else:
                print(f"No config found at {config_file_path()}")
            return
        print(render_llm_config(load_llm_config()))
        return
    if cli_args.command == "replay" and cli_args.replay_action == "clear":
        removed = clear_replay_files()
        print(f"已清除 {removed} 个 replay 记录文件")
        return
    if cli_args.mode == "llm":
        cli_args = CliArgs(
            command=cli_args.command,
            mode=cli_args.mode,
            record_path=cli_args.record_path,
            replay_path=cli_args.replay_path,
            replay_action=cli_args.replay_action,
            competition_path=cli_args.competition_path,
            config_action=cli_args.config_action,
            llm_config=resolve_llm_config_for_run(),
            llm_debug=cli_args.llm_debug,
            show_help=cli_args.show_help,
            help_text=cli_args.help_text,
            version=cli_args.version,
        )
    from .runtime import main

    curses.wrapper(main, cli_args)    # wrapper 自动处理 curses 初始化和清理


if __name__ == "__main__":
    cli()
else:
    sys.modules[__name__].__class__ = type(
        "CallableCliModule",
        (types.ModuleType,),
        {"__call__": lambda self, *args, **kwargs: cli(*args, **kwargs)},
    )
    package = sys.modules.get(__package__)
    if package is not None:
        setattr(package, "cli", cli)
