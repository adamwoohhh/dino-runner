"""Replay persistence, browsing, and deterministic simulation."""

import curses
import json
import os
import random
import time

from .constants import NORMAL_OBSTACLE_SPAWN_X, REPLAY_DIR
from .engine import (
    DinoGame,
    Obstacle,
    apply_game_action,
    obstacle_from_action_data,
    obstacle_to_action_data,
)

def load_replay_file(path) -> dict:
    """读取 replay JSON 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def default_replay_path(mode: str, seed: int | None = None, directory: str = REPLAY_DIR) -> str:
    """生成默认运行记录文件路径。"""
    if seed is None:
        seed = time.time_ns()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = str(seed)[-6:]
    return os.path.join(directory, f"{timestamp}-{mode}-{suffix}.json")

def record_path_for_run(
        record_path: str | None,
        mode: str,
        seed: int,
        run_index: int,
        directory: str = REPLAY_DIR) -> str:
    """返回某一局要写入的 replay 文件路径。"""
    if not record_path:
        return default_replay_path(mode, seed, directory)
    if run_index <= 1:
        return record_path
    root, ext = os.path.splitext(record_path)
    return f"{root}-{run_index}{ext or '.json'}"

def debug_log_path_for_replay(replay_path: str | os.PathLike, directory: str = "logs") -> str:
    """Return the debug log path that mirrors a replay filename under logs/."""
    return os.path.join(directory, os.path.basename(os.fspath(replay_path)))

def list_replay_files(directory: str = REPLAY_DIR) -> list[str]:
    """列出 replay JSON 文件，按最近修改时间倒序。"""
    if not os.path.isdir(directory):
        return []
    paths = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(".json") and os.path.isfile(os.path.join(directory, name))
    ]
    return sorted(paths, key=lambda path: os.path.getmtime(path), reverse=True)

def clear_replay_files(directory: str = REPLAY_DIR) -> int:
    """删除 replay 目录下的所有 JSON 记录文件，返回删除数量。"""
    removed = 0
    for path in list_replay_files(directory):
        os.remove(path)
        removed += 1
    return removed

def replay_created_at(path) -> float:
    """返回 replay 文件创建时间；不支持 birthtime 的平台退回 ctime。"""
    stat = os.stat(path)
    return getattr(stat, "st_birthtime", stat.st_ctime)

def replay_metadata(path) -> dict:
    """读取 replay 文件元信息，用于列表详情展示。"""
    path = os.fspath(path)
    data = load_replay_file(path)
    return {
        "path": path,
        "mode": data.get("mode", "unknown"),
        "frames": data.get("frames", 0),
        "created_at": replay_created_at(path),
        "competitive": bool(data.get("competitive", False)),
        "source_replay": data.get("source_replay") or "-",
    }

def render_replay_metadata(metadata: dict) -> str:
    """把 replay 元信息渲染成多行文本。"""
    created_at = time.strftime(
        "%Y-%m-%d %H:%M:%S",
        time.localtime(metadata["created_at"]),
    )
    competitive = "是" if metadata["competitive"] else "否"
    return "\n".join([
        f"文件: {os.path.basename(metadata['path'])}",
        f"模式: {metadata['mode']}",
        f"帧数: {metadata['frames']}",
        f"创建时间: {created_at}",
        f"是否竞技模式: {competitive}",
        f"竞技模式源记录: {metadata['source_replay']}",
    ])

def move_replay_selection(index: int, key: int, count: int) -> int:
    """根据上下方向键移动 replay 菜单光标。"""
    if count <= 0:
        return 0
    if key == curses.KEY_UP:
        return (index - 1) % count
    if key == curses.KEY_DOWN:
        return (index + 1) % count
    return index

def select_replay_file(stdscr, paths: list[str]) -> str | None:
    """在 curses 中列出运行记录，让用户选择要重放的文件。"""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(False)
    index = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        title = "选择要重放的运行记录"
        try:
            stdscr.addstr(1, 2, title, curses.A_BOLD)
        except curses.error:
            pass

        if not paths:
            msg = f"没有找到运行记录目录 {REPLAY_DIR}/ 下的 .json 文件"
            hint = "按 Enter / Q 返回"
            for y, text in ((3, msg), (5, hint)):
                try:
                    stdscr.addstr(y, 2, text[:max(0, w - 4)])
                except curses.error:
                    pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (10, 13, ord("q"), ord("Q"), 27):
                return None
            continue

        visible_rows = max(1, h - 5)
        start = min(max(0, index - visible_rows + 1), max(0, len(paths) - visible_rows))
        for row, path in enumerate(paths[start:start + visible_rows]):
            item_index = start + row
            basename = os.path.basename(path)
            mtime = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(os.path.getmtime(path)),
            )
            marker = "> " if item_index == index else "  "
            text = f"{marker}{basename}  {mtime}"
            attr = curses.A_REVERSE if item_index == index else curses.A_NORMAL
            try:
                stdscr.addstr(3 + row, 2, text[:max(0, w - 4)], attr)
            except curses.error:
                pass

        hint = "↑/↓ 选择 | Enter 回放 | Q 退出"
        try:
            stdscr.addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13):
            return paths[index]
        if key in (ord("q"), ord("Q"), 27):
            return None
        index = move_replay_selection(index, key, len(paths))

def show_replay_metadata(stdscr, path: str):
    """展示选中 replay 文件的元信息。"""
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(1, 2, "Replay 元信息", curses.A_BOLD)
        except curses.error:
            pass

        try:
            lines = render_replay_metadata(replay_metadata(path)).splitlines()
        except (OSError, json.JSONDecodeError) as exc:
            lines = [f"无法读取 replay 文件: {exc}"]

        for row, text in enumerate(lines):
            if row + 3 >= h - 1:
                break
            try:
                stdscr.addstr(row + 3, 2, text[:max(0, w - 4)])
            except curses.error:
                pass

        hint = "Enter / Q 返回列表"
        try:
            stdscr.addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13, ord("q"), ord("Q"), 27):
            return

def browse_replay_files(stdscr, paths: list[str]):
    """在 curses 中浏览 replay 文件，回车查看选中文件元信息。"""
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.nodelay(False)
    index = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(1, 2, "Replay 记录列表", curses.A_BOLD)
        except curses.error:
            pass

        if not paths:
            msg = f"没有找到运行记录目录 {REPLAY_DIR}/ 下的 .json 文件"
            hint = "按 Enter / Q 返回"
            for y, text in ((3, msg), (5, hint)):
                try:
                    stdscr.addstr(y, 2, text[:max(0, w - 4)])
                except curses.error:
                    pass
            stdscr.refresh()
            key = stdscr.getch()
            if key in (10, 13, ord("q"), ord("Q"), 27):
                return
            continue

        visible_rows = max(1, h - 5)
        start = min(max(0, index - visible_rows + 1), max(0, len(paths) - visible_rows))
        for row, path in enumerate(paths[start:start + visible_rows]):
            item_index = start + row
            basename = os.path.basename(path)
            mtime = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(os.path.getmtime(path)),
            )
            marker = "> " if item_index == index else "  "
            text = f"{marker}{basename}  {mtime}"
            attr = curses.A_REVERSE if item_index == index else curses.A_NORMAL
            try:
                stdscr.addstr(3 + row, 2, text[:max(0, w - 4)], attr)
            except curses.error:
                pass

        hint = "↑/↓ 选择 | Enter 查看元信息 | Q 退出"
        try:
            stdscr.addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key in (10, 13):
            show_replay_metadata(stdscr, paths[index])
            continue
        if key in (ord("q"), ord("Q"), 27):
            return
        index = move_replay_selection(index, key, len(paths))

class ReplayRecorder:
    """把一局游戏的随机种子、逐帧动作和障碍物事件写入文件。"""

    def __init__(
            self,
            path,
            seed: int,
            mode: str = "manual",
            competitive: bool = False,
            source_replay: str | None = None):
        self.path = path
        self.seed = seed
        self.mode = mode
        self.competitive = competitive
        self.source_replay = source_replay
        self.actions: list[dict] = []
        self.obstacles: list[dict] = []
        self.frames = 0
        self.input_count = 0
        self.saved = False

    def record(self, action: str):
        self.record_action(self.input_count + 1, action)

    def record_action(self, frame: int, action: str):
        self.input_count += 1
        self.frames = max(self.frames, frame)
        if action == "none":
            return
        self.actions.append({
            "frame": frame,
            "action": {
                "value": action,
            },
        })

    def record_obstacle(self, frame: int, obstacle: Obstacle):
        self.frames = max(self.frames, frame)
        self.obstacles.append({
            "frame": frame,
            "action": obstacle_to_action_data(obstacle),
        })

    def save(self):
        if self.saved:
            return
        data = {
            "version": 3,
            "seed": self.seed,
            "mode": self.mode,
            "frames": self.frames,
            "actions": self.actions,
            "obstacles": self.obstacles,
        }
        if self.competitive:
            data["competitive"] = True
            data["source_replay"] = self.source_replay
        directory = os.path.dirname(os.fspath(self.path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.saved = True

class ReplayPlayer:
    """按 replay 文件逐帧吐出动作和障碍物。"""

    def __init__(
            self,
            seed: int,
            actions: list[dict],
            obstacles: list[dict],
            mode: str = "manual",
            frames: int | None = None):
        self.seed = seed
        self.mode = mode
        self.action_events = actions
        self.obstacle_events = obstacles
        self.actions = [
            event.get("action", {}).get("value", event.get("action"))
            for event in actions
        ]
        self.actions_by_frame = {
            event["frame"]: event.get("action", {}).get("value", event.get("action"))
            for event in actions
        }
        self.obstacles_by_frame: dict[int, list[dict]] = {}
        for event in obstacles:
            self.obstacles_by_frame.setdefault(event["frame"], []).append(event["action"])
        last_action_frame = max((event["frame"] for event in actions), default=0)
        last_obstacle_frame = max((event["frame"] for event in obstacles), default=0)
        self.max_frame = max(frames or 0, last_action_frame, last_obstacle_frame)
        self.index = 0

    @classmethod
    def from_file(cls, path):
        data = load_replay_file(path)
        actions = data.get("actions")
        obstacles = data.get("obstacles", [])
        frames = data.get("frames")

        if data.get("events") is not None:
            actions = []
            obstacles = []
            for event in data["events"]:
                action = event.get("action", {})
                if action.get("type") == "input":
                    if action.get("value") != "none":
                        actions.append({
                            "frame": event["frame"],
                            "action": {"value": action.get("value", "none")},
                        })
                elif action.get("type") == "obstacle":
                    obstacle_action = dict(action)
                    obstacle_action.pop("type", None)
                    obstacles.append({
                        "frame": event["frame"],
                        "action": obstacle_action,
                    })
            frames = frames if frames is not None else max(
                (event["frame"] for event in data["events"]),
                default=0,
            )
        elif actions and all(isinstance(action, str) for action in actions):
            actions = [
                {
                    "frame": index + 1,
                    "action": {
                        "value": action,
                    },
                }
                for index, action in enumerate(actions)
                if action != "none"
            ]
            frames = frames if frames is not None else len(data.get("actions", []))

        return cls(
            seed=data["seed"],
            actions=list(actions or []),
            obstacles=list(obstacles or []),
            mode=data.get("mode", "manual"),
            frames=frames,
        )

    def action_for_frame(self, frame: int) -> str:
        return self.actions_by_frame.get(frame, "none")

    def obstacles_for_frame(self, frame: int) -> list[dict]:
        return list(self.obstacles_by_frame.get(frame, []))

    def has_frame(self, frame: int) -> bool:
        return frame <= self.max_frame

    def next_action(self) -> str | None:
        if self.index >= len(self.actions):
            return None
        action = self.actions[self.index]
        self.index += 1
        return action

def run_replay_simulation(seed: int, actions: list[str]) -> dict:
    """无 UI 重放，用于测试 replay 是否确定性。"""
    game = DinoGame(rng=random.Random(seed))
    for action in actions:
        if game.game_over:
            if action == "reset":
                game.reset()
            continue
        apply_game_action(game, action)
        game.update()
    return {
        "score": game.score,
        "game_over": game.game_over,
        "state": game.get_state(),
    }

def start_recording_run(
        mode: str,
        record_path: str | None,
        run_index: int,
        directory: str = REPLAY_DIR,
        seed: int | None = None) -> tuple[DinoGame, ReplayRecorder]:
    """启动一局新游戏，并为这一局创建独立 replay recorder。"""
    if seed is None:
        seed = time.time_ns()
    game = DinoGame(
        rng=random.Random(seed),
        obstacle_spawn_x=NORMAL_OBSTACLE_SPAWN_X,
    )
    path = record_path_for_run(record_path, mode, seed, run_index, directory)
    return game, ReplayRecorder(path, seed, mode=mode)

def finish_recording(recorder: ReplayRecorder | None):
    """Game Over 时保存当前局；重复调用不会重复写。"""
    if recorder:
        recorder.save()
