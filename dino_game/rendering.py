"""Curses rendering for the terminal dino game."""

import curses
import time

from .art import *
from .constants import *
from .engine import DinoGame
from .input import PauseState, pause_overlay_lines
from .llm import CachedFrameWindow
from .scores import format_compact_tokens

def footer_hint(agent_name: str, speed: float) -> str:
    """根据当前模式返回底部操作提示。"""
    if agent_name == "Competition":
        return f"SPACE/↑ 跳跃 | ↓ 蹲下 | Enter 暂停 | Q 退出 | 竞技 | 速度 {speed:.1f}x"
    if agent_name == "Replay":
        return f"Enter 暂停 | Q 退出 | 回放 | 速度 {speed:.1f}x"
    if agent_name:
        return f"Enter 暂停 | Q 退出 | 速度 {speed:.1f}x"
    return f"SPACE/↑ 跳跃 | ↓ 蹲下 | Enter 暂停 | Q 退出 | 速度 {speed:.1f}x"

def loading_dino_blinks(animation_time: float) -> bool:
    return int(animation_time / LOADING_DINO_ANIM_INTERVAL) % 2 == 1

def dino_art_for_state(
        game: DinoGame,
        loading: bool = False,
        animation_time: float = 0.0) -> list[str]:
    """Select visual dino art without affecting physics or collision boxes."""
    if loading:
        blink = loading_dino_blinks(animation_time)
        if game.ducking:
            return DINO_LOADING_DUCK if blink else DINO_LOADING_DUCK_OPEN
        if game.jumping:
            return DINO_LOADING_JUMP if blink else DINO_LOADING_JUMP_OPEN
        return DINO_LOADING_STAND_BLINK if blink else DINO_LOADING_STAND
    if game.ducking:
        return DINO_DUCK
    if game.jumping:
        return DINO_JUMP
    if (game.frame // RUN_ANIM_FRAME_INTERVAL) % 2 == 0:
        return DINO_RUN_1
    return DINO_RUN_2

class Renderer:
    """curses 终端渲染器

    坐标映射:
      游戏世界 Y 轴（向上为正）→ 终端行号（向下递增）
      转换公式: screen_row = ground_row - art_height - game_y

    颜色方案 (curses color pair):
      1 = 绿色  → 恐龙
      2 = 红色  → 障碍物
      3 = 黄色  → 分数、Game Over
      4 = 青色  → 标题、云朵
      5 = 白色  → 地面
      6 = 紫色  → Agent 标签和思考可视化
    """

    def __init__(self, stdscr):
        self.scr = stdscr
        curses.curs_set(0)              # 隐藏光标
        stdscr.nodelay(True)            # getch() 非阻塞
        stdscr.timeout(FRAME_MS)        # getch() 超时 = 帧间隔

        curses.start_color()
        curses.use_default_colors()     # 使用终端默认背景色
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)

    def safe_addstr(self, y: int, x: int, text: str, attr: int = 0):
        """安全地向屏幕写字符串 — 自动裁剪越界部分

        curses 在写到屏幕右下角时会抛异常，这个方法处理所有边界情况。
        """
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x >= w:
            return
        if x < 0:
            text = text[-x:]        # 左边被裁掉的部分
            x = 0
        if x + len(text) >= w:
            text = text[:w - x - 1] # 右边裁剪
        if text:
            try:
                self.scr.addstr(y, x, text, attr)
            except curses.error:
                pass                 # 忽略右下角写入异常

    def draw_competition_lane(
            self,
            game: DinoGame,
            label: str,
            ground_row: int,
            dino_color_pair: int,
            status: str):
        """绘制竞技模式中的单条赛道。"""
        h, w = self.scr.getmaxyx()
        header_y = max(0, ground_row - 8)
        self.safe_addstr(
            header_y,
            2,
            f" {label} ",
            curses.A_BOLD | curses.color_pair(dino_color_pair),
        )
        score_text = f"HI {game.high_score:05d}  {status}  {game.score:05d}"
        self.safe_addstr(
            header_y,
            max(2, w - len(score_text) - 2),
            score_text,
            curses.A_BOLD | curses.color_pair(3),
        )

        if game.ducking:
            art = DINO_DUCK
        elif game.jumping:
            art = DINO_JUMP
        elif (game.frame // RUN_ANIM_FRAME_INTERVAL) % 2 == 0:
            art = DINO_RUN_1
        else:
            art = DINO_RUN_2

        dino_screen_y = ground_row - len(art) - int(game.dino_y)
        for i, line in enumerate(art):
            self.safe_addstr(
                dino_screen_y + i,
                DINO_COL,
                line,
                curses.color_pair(dino_color_pair) | curses.A_BOLD,
            )

        for obs in game.obstacles:
            ox = int(obs.x)
            if obs.kind == "bird":
                if (game.frame // BIRD_ANIM_FRAME_INTERVAL) % 2 == 0:
                    obs_art = BIRD_1
                else:
                    obs_art = BIRD_2
            else:
                obs_art = obs.art

            obs_screen_y = ground_row - len(obs_art) - obs.height
            for i, line in enumerate(obs_art):
                self.safe_addstr(
                    obs_screen_y + i,
                    ox,
                    line,
                    curses.color_pair(2) | curses.A_BOLD,
                )

        ground = ""
        offset = int(game.ground_offset)
        pattern = "▁▁▁▁▂▁▁▁▂▁▁▁▁▁▂▁▁▁"
        while len(ground) < w:
            ground += pattern
        ground = ground[offset:offset + w - 1]
        self.safe_addstr(ground_row, 0, ground, curses.color_pair(5) | curses.A_DIM)

        if game.game_over:
            self.safe_addstr(
                max(header_y + 1, ground_row - 7),
                2,
                f"GAME OVER  Score: {game.score:05d}",
                curses.A_BOLD | curses.color_pair(3),
            )

    def draw_competition(self, competition: CompetitionRun):
        """绘制竞技模式的双赛道画面。"""
        self.scr.erase()
        h, w = self.scr.getmaxyx()

        title = " DINO RUNNER [竞技模式] "
        self.safe_addstr(0, 2, title, curses.A_BOLD | curses.color_pair(1))

        top_ground = max(8, min(10, h // 2 - 2))
        bottom_ground = min(h - 3, max(top_ground + 8, h - 3))
        separator_y = min(h - 2, max(top_ground + 1, (top_ground + bottom_ground) // 2))
        self.safe_addstr(separator_y, 0, "─" * max(0, w - 1), curses.A_DIM)

        history_status = "撞毁" if competition.history_game.game_over else "结束"
        if not competition.history_finished:
            history_status = "回放"
        player_status = "撞毁" if competition.player_game.game_over else "操作"
        if competition.player_finished and not competition.player_game.game_over:
            player_status = "结束"

        self.draw_competition_lane(
            competition.history_game,
            "历史赛道",
            top_ground,
            6,
            history_status,
        )
        self.draw_competition_lane(
            competition.player_game,
            "玩家赛道",
            bottom_ground,
            1,
            player_status,
        )

        if competition.finished:
            msg = "竞技结束  Q = 退出"
            self.safe_addstr(
                max(1, h // 2),
                max(0, w // 2 - len(msg) // 2),
                msg,
                curses.A_BOLD | curses.color_pair(3),
            )

        hint = footer_hint("Competition", competition.player_game.speed)
        self.safe_addstr(h - 1, 2, hint[:max(0, w - 4)], curses.A_DIM)
        self.scr.refresh()

    def draw_center_overlay(self, lines: list[str], color_pair: int = 3):
        """在屏幕中央绘制多行提示。"""
        if not lines:
            return
        h, w = self.scr.getmaxyx()
        mid_y = h // 2 - len(lines) // 2
        for index, line in enumerate(lines):
            x = max(0, w // 2 - len(line) // 2)
            self.safe_addstr(
                mid_y + index,
                x,
                line,
                curses.A_BOLD | curses.color_pair(color_pair),
            )

    def draw_pause_overlay(self, pause_state: PauseState, now: float):
        """绘制暂停或恢复倒计时提示。"""
        self.draw_center_overlay(pause_overlay_lines(pause_state, now), color_pair=3)

    def draw_cached_frame_window(self, y: int, x: int, window: CachedFrameWindow):
        """Draw cached LLM action frames as a colored sliding window."""
        segments: list[tuple[str, int]] = [
            (
                f"Frame {window.current_frame:>5}  ",
                curses.color_pair(6) | curses.A_DIM,
            )
        ]
        for cell in window.cells:
            text = f"{cell.symbol}"
            if cell.status == "current":
                attr = curses.color_pair(3) | curses.A_BOLD
                text = f"[{text}]"
            elif cell.status == "consumed":
                attr = curses.color_pair(5) | curses.A_DIM
                text = f" {text} "
            elif cell.status == "future":
                attr = curses.color_pair(6) | curses.A_BOLD
                text = f" {text} "
            else:
                attr = curses.A_DIM
                text = " · "
            segments.append((text, attr))

        cursor = x
        for text, attr in segments:
            self.safe_addstr(y, cursor, text, attr)
            cursor += len(text)

    def draw_dashboard(self, summary: list[dict], now: float | None = None):
        """Draw the animated score and token usage dashboard."""
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        animation_time = time.monotonic() if now is None else now

        title = "DINO"
        subtitle = "Score Dashboard"
        title_x = max(2, w // 2 - len(title) // 2)
        self.safe_addstr(1, title_x, title, curses.A_BOLD | curses.color_pair(1))
        self.safe_addstr(
            2,
            max(2, w // 2 - len(subtitle) // 2),
            subtitle,
            curses.color_pair(4) | curses.A_DIM,
        )

        dino = DINO_RUN_1 if int(animation_time / 0.25) % 2 == 0 else DINO_RUN_2
        dino_x = max(2, min(w - 12, title_x - 16))
        for row, line in enumerate(dino):
            self.safe_addstr(1 + row, dino_x, line, curses.A_BOLD | curses.color_pair(1))

        ground_y = min(h - 3, 8)
        pattern = "▁▁▁▁▂▁▁▁▂▁▁▁▁▁▂▁▁▁"
        ground = (pattern * ((w // len(pattern)) + 2))[:max(0, w - 1)]
        self.safe_addstr(ground_y, 0, ground, curses.color_pair(5) | curses.A_DIM)

        table_y = ground_y + 2
        headers = ("Window", "Mode", "Score", "Tokens")
        widths = (16, 14, 12, 10)
        header = (
            f"{headers[0]:<{widths[0]}}"
            f"{headers[1]:<{widths[1]}}"
            f"{headers[2]:>{widths[2]}}  "
            f"{headers[3]:>{widths[3]}}"
        )
        self.safe_addstr(table_y, 2, header, curses.A_BOLD | curses.color_pair(3))
        self.safe_addstr(table_y + 1, 2, "-" * len(header), curses.A_DIM)

        row_y = table_y + 2
        any_rows = False
        for window in summary:
            label = str(window.get("label", ""))
            modes = window.get("modes", {})
            if not modes:
                continue
            for mode in sorted(modes):
                totals = modes[mode]
                line = (
                    f"{label:<{widths[0]}}"
                    f"{mode:<{widths[1]}}"
                    f"{int(totals.get('score', 0)):>{widths[2]}}  "
                    f"{format_compact_tokens(totals.get('total_tokens', 0)):>{widths[3]}}"
                )
                self.safe_addstr(row_y, 2, line, curses.color_pair(5))
                row_y += 1
                any_rows = True
                if row_y >= h - 2:
                    break
            if row_y >= h - 2:
                break

        if not any_rows:
            self.safe_addstr(
                table_y + 3,
                2,
                "No completed games recorded yet.",
                curses.color_pair(6) | curses.A_DIM,
            )

        self.safe_addstr(h - 1, 2, "Q 退出", curses.A_DIM)
        self.scr.refresh()

    def draw(
            self,
            game: DinoGame,
            agent_name: str,
            pause_state: PauseState | None = None,
            now: float | None = None,
            loading_text: str | None = None,
            cached_frames_text: str | None = None,
            cached_frames_view: CachedFrameWindow | None = None,
            llm_usage_text: str | None = None,
            game_over_save_status: str | None = None,
            game_over_retry_available: bool = False):
        """绘制完整的一帧画面

        绘制顺序（从后到前）:
          1. 标题栏和分数
          2. 云朵（背景层）
          3. 恐龙（主角）
          4. 障碍物
          5. 地面
          6. Agent 思考可视化
          7. Game Over 弹窗（如果死了）
          8. 底部操作提示
        """
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        ground_row = min(GROUND_ROW, h - 5)  # 终端太小时自动上移

        # ── 标题栏 ──
        title = " DINO RUNNER "
        self.safe_addstr(0, 2, title, curses.A_BOLD | curses.color_pair(1))

        if agent_name:
            tag = f" [{agent_name}] "
            self.safe_addstr(0, 2 + len(title) + 1, tag,
                             curses.A_BOLD | curses.color_pair(6))

        # 右上角显示最高分和当前分
        score_text = f"HI {game.high_score:05d}  {game.score:05d}"
        self.safe_addstr(0, w - len(score_text) - 2, score_text,
                         curses.A_BOLD | curses.color_pair(3))

        # ── 云朵（装饰） ──
        for c in game.clouds:
            cx = int(c["x"])
            cy = c["y"]
            for i, line in enumerate(CLOUD):
                self.safe_addstr(cy + i, cx, line, curses.color_pair(4) | curses.A_DIM)

        # ── 恐龙 ──
        # 根据状态选择动画帧
        loading_dino = bool(loading_text and not (pause_state and pause_state.status != "running"))
        animation_time = now if now is not None else time.monotonic()
        art = dino_art_for_state(
            game,
            loading=loading_dino,
            animation_time=animation_time,
        )

        # 游戏 Y 坐标 → 屏幕行号
        dino_screen_y = ground_row - len(art) - int(game.dino_y)
        color = curses.color_pair(1) | curses.A_BOLD
        for i, line in enumerate(art):
            self.safe_addstr(dino_screen_y + i, DINO_COL, line, color)

        # ── 障碍物 ──
        for obs in game.obstacles:
            ox = int(obs.x)
            if obs.kind == "bird":
                if (game.frame // BIRD_ANIM_FRAME_INTERVAL) % 2 == 0:
                    art = BIRD_1
                else:
                    art = BIRD_2
            else:
                art = obs.art

            obs_screen_y = ground_row - len(art) - obs.height
            for i, line in enumerate(art):
                self.safe_addstr(obs_screen_y + i, ox, line,
                                 curses.color_pair(2) | curses.A_BOLD)

        # ── 地面（滚动纹理） ──
        gnd = ""
        offset = int(game.ground_offset)
        pattern = "▁▁▁▁▂▁▁▁▂▁▁▁▁▁▂▁▁▁"
        while len(gnd) < w:
            gnd += pattern
        gnd = gnd[offset:offset + w - 1]
        self.safe_addstr(ground_row, 0, gnd, curses.color_pair(5) | curses.A_DIM)

        # ── Agent 思考可视化 ──
        # 在地面下方显示 Agent 当前「看到」的信息
        if agent_name:
            state = game.get_state()
            if state["obstacles"]:
                obs = state["obstacles"][0]
                thought = f"[dist={obs['distance']:.0f} spd={state['speed']:.1f}]"
                self.safe_addstr(ground_row + 2, 2, thought,
                                 curses.color_pair(6) | curses.A_DIM)

        # ── Game Over 弹窗 ──
        if game.game_over:
            replay_line = "║   S = 保存游戏记录       ║"
            if game_over_save_status == "saved":
                replay_line = "║        已保存记录        ║"
            retry_line = "║   C = 失败处重试         ║"
            msgs = [
                "╔══════════════════════════╗",
                "║      G A M E  O V E R   ║",
                f"║      Score: {game.score:>5d}       ║",
                replay_line if game_over_save_status else "║                          ║",
                retry_line if game_over_retry_available else "║                          ║",
                "║   R = 重新开始 Q = 退出  ║",
                "╚══════════════════════════╝",
            ]
            mid_y = h // 2 - len(msgs) // 2
            mid_x = w // 2 - len(msgs[0]) // 2
            for i, line in enumerate(msgs):
                self.safe_addstr(mid_y + i, mid_x, line,
                                 curses.A_BOLD | curses.color_pair(3))

        if pause_state and pause_state.status != "running":
            self.draw_pause_overlay(pause_state, now if now is not None else time.monotonic())
        elif loading_text:
            self.draw_center_overlay([loading_text], color_pair=6)

        # ── 底部操作提示 ──
        status_y = h - 2
        if cached_frames_view:
            self.draw_cached_frame_window(
                h - 3 if llm_usage_text else status_y,
                2,
                cached_frames_view,
            )
        elif cached_frames_text:
            self.safe_addstr(
                h - 3 if llm_usage_text else status_y,
                2,
                cached_frames_text,
                curses.color_pair(6) | curses.A_DIM,
            )
        if llm_usage_text:
            self.safe_addstr(status_y, 2, llm_usage_text, curses.color_pair(6) | curses.A_DIM)

        hint = footer_hint(agent_name, game.speed)
        self.safe_addstr(h - 1, 2, hint, curses.A_DIM)

        self.scr.refresh()
