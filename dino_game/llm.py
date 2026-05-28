"""LLM configuration, planning protocol, and agent state."""

import json
import math
import os
import threading
from dataclasses import dataclass

from .constants import *
from .constants import _positive_int
from .engine import DinoGame, obstacle_debug_snapshot
from .llm_client import LLMClient

@dataclass(frozen=True)
class LLMConfig:
    """OpenAI-compatible LLM configuration."""

    api_key: str = ""
    base_url: str = DEFAULT_OPENAI_BASE_URL
    model: str = DEFAULT_OPENAI_MODEL
    llm_window_frames: int = DEFAULT_LLM_ACTION_WINDOW_FRAMES
    llm_mode: str = "API"

    def is_complete(self) -> bool:
        if normalize_llm_mode(self.llm_mode) == "CODEX":
            return True
        return bool(self.api_key and self.base_url and self.model)

@dataclass(frozen=True)
class CachedFrameCell:
    frame: int
    symbol: str
    status: str

@dataclass(frozen=True)
class CachedFrameWindow:
    current_frame: int
    cells: list[CachedFrameCell]

def normalize_llm_mode(value: str | None) -> str:
    """Return a supported LLM mode, defaulting invalid or missing values to API."""
    normalized = str(value or "").strip().upper()
    if normalized in {"API", "CODEX"}:
        return normalized
    return "API"

def config_file_path(home: str | None = None) -> str:
    """Return the fixed per-user config file path."""
    home_dir = home if home is not None else os.path.expanduser("~")
    return os.path.join(home_dir, ".config", CONFIG_DIR_NAME, CONFIG_FILE_NAME)

def load_llm_config(path: str | os.PathLike | None = None) -> LLMConfig:
    """Load LLM config from disk; missing or invalid files produce defaults."""
    config_path = os.fspath(path or config_file_path())
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return LLMConfig(base_url="", model="")
    if not isinstance(data, dict):
        return LLMConfig(base_url="", model="")
    llm_mode = normalize_llm_mode(data.get("llm_mode"))
    return LLMConfig(
        api_key=str(data.get("api_key") or ""),
        base_url=str(data.get("base_url") or ""),
        model=str(data.get("model") or ""),
        llm_window_frames=_positive_int(
            data.get("llm_window_frames"),
            DEFAULT_LLM_ACTION_WINDOW_FRAMES,
        ),
        llm_mode=llm_mode,
    )

def save_llm_config(config: LLMConfig, path: str | os.PathLike | None = None):
    """Persist LLM config as JSON."""
    config_path = os.fspath(path or config_file_path())
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    llm_mode = normalize_llm_mode(config.llm_mode)
    api_key = config.api_key if llm_mode == "API" else ""
    base_url = config.base_url if llm_mode == "API" else ""
    model = config.model if llm_mode == "API" else ""
    data = {
        "llm_mode": llm_mode,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "llm_window_frames": _positive_int(
            config.llm_window_frames,
            DEFAULT_LLM_ACTION_WINDOW_FRAMES,
        ),
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

def reset_llm_config(path: str | os.PathLike | None = None) -> bool:
    """Delete the config file if it exists."""
    config_path = os.fspath(path or config_file_path())
    try:
        os.remove(config_path)
        return True
    except FileNotFoundError:
        return False

def mask_api_key(api_key: str) -> str:
    """Mask an API key for display."""
    if not api_key:
        return "(not set)"
    if len(api_key) <= 8:
        return f"{api_key[:2]}...{api_key[-2:]}"
    return f"{api_key[:4]}...{api_key[-4:]}"

def render_llm_config(config: LLMConfig, path: str | os.PathLike | None = None) -> str:
    """Render config for CLI display without leaking the full API key."""
    config_path = os.fspath(path or config_file_path())
    llm_mode = normalize_llm_mode(config.llm_mode)
    api_key = config.api_key if llm_mode == "API" else ""
    base_url = config.base_url if llm_mode == "API" else ""
    model = config.model if llm_mode == "API" else ""
    llm_window_frames = _positive_int(
        config.llm_window_frames,
        DEFAULT_LLM_ACTION_WINDOW_FRAMES,
    )
    return "\n".join([
        f"path: {config_path}",
        f"llm_mode: {llm_mode}",
        f"api_key: {mask_api_key(api_key)}",
        f"base_url: {base_url or '(not set)'}",
        f"model: {model or '(not set)'}",
        f"llm_window_frames: {llm_window_frames}",
    ])

def prompt_for_positive_int(
        prompt: str,
        default: int,
        *,
        input_func=input,
        output_func=print) -> int:
    """Prompt until the user provides a positive integer or accepts the default."""
    while True:
        answer = input_func(prompt).strip()
        if not answer:
            return default
        value = _positive_int(answer, 0)
        if value > 0:
            return value
        output_func("Value must be a positive integer.")

def prompt_for_required_text(
        prompt: str,
        label: str,
        *,
        input_func=input,
        output_func=print) -> str:
    """Prompt until the user provides non-empty text."""
    while True:
        value = input_func(prompt).strip()
        if value:
            return value
        output_func(f"{label} is required.")

def prompt_for_llm_mode(
        existing: LLMConfig,
        *,
        input_func=input,
        output_func=print) -> str:
    """Prompt until the user selects a supported LLM mode."""
    default_mode = normalize_llm_mode(existing.llm_mode)
    prompt = f"LLM mode [1=API, 2=CODEX] ({default_mode}): "
    while True:
        answer = input_func(prompt).strip().upper()
        if not answer:
            return default_mode
        if answer in {"1", "API"}:
            return "API"
        if answer in {"2", "CODEX"}:
            return "CODEX"
        output_func("LLM mode must be API or CODEX.")

def prompt_for_llm_config(
        existing: LLMConfig | None = None,
        *,
        input_func=input,
        output_func=print,
        ask_persist: bool = False,
        require_endpoint_values: bool = False) -> tuple[LLMConfig, bool]:
    """Prompt for LLM settings and optionally ask whether to persist them."""
    existing = existing or LLMConfig()
    output_func("Configure LLM settings.")
    llm_mode = prompt_for_llm_mode(
        existing,
        input_func=input_func,
        output_func=output_func,
    )

    if llm_mode == "API":
        api_key = input_func("API key: ").strip() or existing.api_key
        while not api_key:
            output_func("API key is required.")
            api_key = input_func("API key: ").strip()

        if require_endpoint_values:
            base_url = prompt_for_required_text(
                "Base URL: ",
                "Base URL",
                input_func=input_func,
                output_func=output_func,
            )
        else:
            base_prompt = f"Base URL [{existing.base_url or DEFAULT_OPENAI_BASE_URL}]: "
            base_url = input_func(base_prompt).strip() or existing.base_url or DEFAULT_OPENAI_BASE_URL

        if require_endpoint_values:
            model = prompt_for_required_text(
                "Model: ",
                "Model",
                input_func=input_func,
                output_func=output_func,
            )
        else:
            model_prompt = f"Model [{existing.model or DEFAULT_OPENAI_MODEL}]: "
            model = input_func(model_prompt).strip() or existing.model or DEFAULT_OPENAI_MODEL
    else:
        api_key = ""
        base_url = ""
        model = ""

    existing_window = _positive_int(
        existing.llm_window_frames,
        DEFAULT_LLM_ACTION_WINDOW_FRAMES,
    )
    window_prompt = f"LLM window frames [{existing_window}]: "
    llm_window_frames = prompt_for_positive_int(
        window_prompt,
        existing_window,
        input_func=input_func,
        output_func=output_func,
    )

    persist = False
    if ask_persist:
        answer = input_func("Save config to local file? [y/N]: ").strip().lower()
        persist = answer in {"y", "yes"}

    return LLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        llm_window_frames=llm_window_frames,
        llm_mode=llm_mode,
    ), persist

def run_config_setup(
        *,
        config_path: str | os.PathLike | None = None,
        input_func=input,
        output_func=print) -> LLMConfig:
    """Interactive config setup that always writes to disk."""
    path = config_path or config_file_path()
    existing = load_llm_config(path)
    config, _ = prompt_for_llm_config(
        existing,
        input_func=input_func,
        output_func=output_func,
        ask_persist=False,
        require_endpoint_values=True,
    )
    save_llm_config(config, path)
    output_func(f"Saved config to {path}")
    return config

def resolve_llm_config_for_run(
        *,
        config_path: str | os.PathLike | None = None,
        input_func=input,
        output_func=print) -> LLMConfig:
    """Load config for `dino play --llm`, prompting if required values are absent."""
    path = config_path or config_file_path()
    if not os.path.exists(path):
        return run_config_setup(
            config_path=path,
            input_func=input_func,
            output_func=output_func,
        )

    config = load_llm_config(path)
    if config.is_complete():
        return config

    config, persist = prompt_for_llm_config(
        config,
        input_func=input_func,
        output_func=output_func,
        ask_persist=True,
    )
    if persist:
        save_llm_config(config, path)
        output_func(f"Saved config to {path}")
    return config

def extract_response_text(result: dict) -> str:
    """Extract text from common OpenAI Responses API response shapes."""
    output_text = result.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = result.get("output")
    if not isinstance(output, list):
        return ""
    parts = []
    for item in output:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "\n".join(parts)

def action_from_llm_text(text: str) -> str:
    """Map model text to a game action."""
    normalized = text.strip().lower()
    if "jump" in normalized:
        return "jump"
    if "duck" in normalized:
        return "duck"
    return "none"

def action_symbol(action: str) -> str:
    return ACTION_SYMBOLS.get(action, " ")

def cached_frame_window(
        planned_actions: dict[int, str],
        consumed_actions: dict[int, str],
        current_frame: int,
        radius: int = 12) -> CachedFrameWindow:
    cells = []
    for frame in range(current_frame - radius, current_frame + radius + 1):
        if frame < current_frame:
            action = consumed_actions.get(frame)
            status = "consumed" if action is not None else "missing"
        else:
            action = planned_actions.get(frame)
            if frame == current_frame:
                status = "current" if action is not None else "missing"
            else:
                status = "future" if action is not None else "missing"
        cells.append(CachedFrameCell(frame, action_symbol(action or ""), status))
    return CachedFrameWindow(current_frame=current_frame, cells=cells)

def parse_llm_action_window(
        text: str,
        requested_start_frame: int,
        expected_action_count: int | None = None) -> dict[int, str]:
    """Parse a model-returned JSON action window into frame-indexed actions."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("start_frame") != requested_start_frame:
        return {}
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return {}
    if expected_action_count is not None:
        actions = actions[:expected_action_count]
        actions = actions + ["none"] * (expected_action_count - len(actions))

    planned = {}
    for offset, action in enumerate(actions):
        if action not in VALID_ACTIONS:
            return {}
        planned[requested_start_frame + offset] = action
    return planned

def llm_action_window_text_format(start_frame: int, window_frames: int) -> dict:
    """Return the Responses API structured output format for action windows."""
    return {
        "type": "json_schema",
        "name": "dino_action_window",
        "description": "A fixed-length per-frame action plan for the dino game.",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "start_frame": {
                    "type": "integer",
                    "enum": [start_frame],
                },
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["jump", "duck", "none"],
                    },
                    "minItems": window_frames,
                    "maxItems": window_frames,
                },
            },
            "required": ["start_frame", "actions"],
            "additionalProperties": False,
        },
    }

def jump_physics_summary() -> tuple[int, float]:
    """Return the current jump airtime and peak height from game constants."""
    dino_y = 0.0
    dino_vy = JUMP_VELOCITY
    max_y = 0.0
    for frame in range(1, FPS * 2):
        dino_y -= dino_vy
        dino_vy += GRAVITY
        if dino_y <= 0 and frame > 1:
            return frame, max_y
        max_y = max(max_y, dino_y)
    return FPS * 2, max_y

def estimate_frames_until_horizontal_overlap(distance: float, speed: float) -> int:
    """Estimate frames until an obstacle reaches the dino collision band."""
    if distance <= LLM_HORIZONTAL_OVERLAP_DISTANCE:
        return 0
    target_distance = distance - LLM_HORIZONTAL_OVERLAP_DISTANCE
    travelled = 0.0
    for frames in range(1, LLM_ACTION_WINDOW_FRAMES * 2 + 1):
        frame_speed = min(MAX_SPEED, speed + SPEED_ACCELERATION * frames)
        travelled += frame_speed
        if travelled >= target_distance:
            return frames
    return math.ceil(target_distance / max(speed, 0.1))

def estimate_horizontal_clearance_frames(width: float, speed: float) -> int:
    """Estimate extra frames until the obstacle tail leaves the collision band."""
    trailing_width = max(0.0, width - 1.0)
    if trailing_width <= 0:
        return 0
    return math.ceil(trailing_width / max(speed, 0.1))

def obstacle_timing_estimate(
        obstacle: dict,
        speed: float,
        current_frame: int) -> dict:
    """Estimate overlap and clearance frames for one obstacle snapshot."""
    distance = float(obstacle.get("distance", 0.0))
    frames_until_overlap = estimate_frames_until_horizontal_overlap(distance, speed)
    overlap_frame = current_frame + frames_until_overlap
    overlap_speed = min(
        MAX_SPEED,
        speed + SPEED_ACCELERATION * frames_until_overlap,
    )
    raw_width = obstacle.get("width", 1.0)
    try:
        width = max(1.0, float(raw_width))
        width_text = f", width={width:g}"
    except (TypeError, ValueError):
        width = 1.0
        width_text = ""
    clearance_frames = estimate_horizontal_clearance_frames(width, overlap_speed)
    return {
        "distance": distance,
        "width": width,
        "width_text": width_text,
        "overlap_frame": overlap_frame,
        "clear_frame": overlap_frame + clearance_frames,
        "clearance_frames": clearance_frames,
    }

def llm_request_state_for_start_frame(
        state: dict,
        *,
        current_frame: int,
        start_frame: int) -> dict:
    """Drop obstacles that clear before the requested action window starts."""
    speed = float(state.get("speed", INITIAL_SPEED))
    filtered_obstacles = [
        obstacle
        for obstacle in (state.get("obstacles") or [])
        if obstacle_timing_estimate(
            obstacle,
            speed,
            current_frame,
        )["clear_frame"] >= start_frame
    ]
    request_state = dict(state)
    request_state["obstacles"] = filtered_obstacles
    return request_state

def llm_planning_guidance(state: dict, current_frame: int) -> str:
    """Build prompt guidance from local physics and obstacle timing estimates."""
    jump_frames, max_jump_height = jump_physics_summary()
    speed = float(state.get("speed", INITIAL_SPEED))
    lines = [
        "游戏物理设定:",
        (
            f"- 帧率 {FPS} FPS；一次 jump 约持续 {jump_frames} 帧，"
            f"最高高度约 {max_jump_height:.1f}。"
        ),
        "- jump 只有在地面且未 jumping 时生效；重复 jump 不会延长滞空。",
        (
            f"- 当前速度 {speed:.2f} 列/帧；速度每帧增加 "
            f"{SPEED_ACCELERATION:g}，最大速度 {MAX_SPEED:g}。"
        ),
        (
            f"- 水平碰撞通常在 distance <= "
            f"{LLM_HORIZONTAL_OVERLAP_DISTANCE:g} 左右开始，不是 distance=0。"
        ),
        (
            "- 宽障碍物会让水平重叠持续到 estimated_clear_frame；"
            "recommended_jump_window 会随 width 变大而后移，避免过早下落。"
        ),
        (
            "- 地面障碍或低空鸟不要过早起跳；推荐窗口大致覆盖 "
            f"estimated_clear_frame 前 {LLM_RECOMMENDED_JUMP_EARLY_FRAMES} 帧"
            f"到 estimated_overlap_frame 前 {LLM_RECOMMENDED_JUMP_LATE_FRAMES} 帧。"
        ),
        (
            "- 不要早于 recommended_jump_window 的起点起跳；"
            "优先选择 optimal_jump_frame。"
        ),
        "- 中空鸟 height=4 优先 duck；高空鸟 height=8 通常 none。",
        "推荐起跳窗口估算:",
    ]

    obstacles = state.get("obstacles") or []
    if not obstacles:
        lines.append("- 当前没有可见障碍物。")
        return "\n".join(lines)

    for index, obstacle in enumerate(obstacles, start=1):
        timing = obstacle_timing_estimate(obstacle, speed, current_frame)
        distance = timing["distance"]
        overlap_frame = timing["overlap_frame"]
        clear_frame = timing["clear_frame"]
        clearance_frames = timing["clearance_frames"]
        kind = obstacle.get("kind", "unknown")
        height = obstacle.get("height", 0)
        if kind == "bird" and height == 4:
            recommendation = "recommended_action=duck"
        elif kind == "bird" and height == 8:
            recommendation = "recommended_action=none"
        else:
            width_shift = clearance_frames
            if clearance_frames > 0:
                width_shift += 1
            jump_start = (
                overlap_frame
                - LLM_RECOMMENDED_JUMP_EARLY_FRAMES
                + width_shift
            )
            jump_end = overlap_frame - LLM_RECOMMENDED_JUMP_LATE_FRAMES
            if jump_start > jump_end:
                jump_start = jump_end
            optimal_jump_frame = (jump_start + jump_end) // 2
            recommendation = (
                f"estimated_clear_frame={clear_frame}, "
                f"recommended_jump_window={jump_start}-{jump_end}, "
                f"optimal_jump_frame={optimal_jump_frame}"
            )
        lines.append(
            f"- obstacle#{index}: kind={kind}, "
            f"distance={distance:g}{timing['width_text']}, "
            f"estimated_overlap_frame={overlap_frame}, {recommendation}"
        )
    return "\n".join(lines)

def llm_state_has_obstacles(state: dict) -> bool:
    """Return whether an LLM request state contains any obstacle information."""
    return bool(state.get("obstacles"))

def format_frame_ranges(frames: list[int]) -> str | None:
    """Return a compact frame range summary for display."""
    if not frames:
        return None
    ranges = []
    start = previous = frames[0]
    for frame in frames[1:]:
        if frame == previous + 1:
            previous = frame
            continue
        ranges.append((start, previous))
        start = previous = frame
    ranges.append((start, previous))
    return ", ".join(
        str(start) if start == end else f"{start}-{end}"
        for start, end in ranges
    )

class ActionWindowPlanner:
    """Build and parse the JSON action-window protocol used with the LLM.

    Protocol shape:
      {"start_frame": int, "actions": ["jump" | "duck" | "none", ...]}
    Each action maps to one frame starting at start_frame, and the schema pins
    both start_frame and action count for the requested planning window.
    """

    def build_request(
            self,
            state: dict,
            *,
            start_frame: int,
            current_frame: int,
            window_frames: int) -> tuple[dict, str, dict]:
        request_state = llm_request_state_for_start_frame(
            state,
            current_frame=current_frame,
            start_frame=start_frame,
        )
        planning_guidance = llm_planning_guidance(request_state, current_frame)
        prompt = f"""你正在玩一个恐龙跑酷游戏。请根据当前状态规划未来 {window_frames} actions。

当前状态:
- 当前帧: {current_frame}
- 需要返回的第一帧 start_frame: {start_frame}
- start_frame 距当前状态还有 {start_frame - current_frame} 帧
- 恐龙高度: {request_state['dino_y']} (0=地面)
- 正在跳跃: {request_state['jumping']}
- 正在蹲下: {request_state['ducking']}
- 游戏速度: {request_state['speed']}
- 当前分数: {request_state['score']}
- 前方障碍物: {json.dumps(request_state['obstacles'], ensure_ascii=False)}

距离 distance 表示障碍物离恐龙的距离，越小越近。
障碍物每帧向恐龙靠近约 speed 列，因此 distance / speed 可估算还有多少帧相遇。
height 表示障碍物的高度(鸟)，0=低空，4=中空，8=高空。
当前恐龙状态由 dino_y、dino_vy、jumping、ducking 表示。

{planning_guidance}

你必须只返回 JSON，不要解释。格式:
{{"start_frame": {start_frame}, "actions": ["none", "jump"]}}

要求:
- start_frame 必须等于 {start_frame}
- actions 必须正好包含 {window_frames} actions
- 每个 action 只能是 jump / duck / none
- 每个 action 对应从 start_frame 开始的一帧
回答:"""
        return (
            request_state,
            prompt,
            llm_action_window_text_format(start_frame, window_frames),
        )

    def parse_response(
            self,
            response_text: str,
            *,
            start_frame: int,
            window_frames: int) -> dict[int, str]:
        return parse_llm_action_window(
            response_text,
            requested_start_frame=start_frame,
            expected_action_count=window_frames,
        )

class LLMAgent:
    """调用 OpenAI Responses API 的 LLM Agent，缓存未来逐帧动作。"""

    def __init__(
            self,
            config: LLMConfig | None = None,
            *,
            debug: bool = False,
            debug_path: str | os.PathLike | None = None):
        self.planned_actions: dict[int, str] = {}
        self.consumed_actions: dict[int, str] = {}
        self.requested_until_frame = 0
        self.request_in_flight = False
        self.requested_frame_ranges: list[tuple[int, int]] = []
        self.plan_generation = 0
        self.lock = threading.Lock()    # 线程安全锁
        self.config = config or load_llm_config()
        self.client = LLMClient(self.config)
        self.planner = ActionWindowPlanner()
        self.debug = debug
        self.debug_path = os.fspath(debug_path) if debug_path is not None else None
        if not self.config.is_complete():
            raise ValueError("LLM config requires api_key, base_url, and model")

    def set_debug_path(self, debug_path: str | os.PathLike | None):
        self.debug_path = os.fspath(debug_path) if debug_path is not None else None

    def _debug_log(self, event: str, **data):
        if not self.debug or not self.debug_path:
            return
        payload = {"event": event, **data}
        os.makedirs(os.path.dirname(self.debug_path), exist_ok=True)
        with open(self.debug_path, "a", encoding="utf-8") as f:
            print(json.dumps(payload, ensure_ascii=False), file=f, flush=True)

    def _call_llm(
            self,
            state: dict,
            *,
            start_frame: int,
            current_frame: int | None = None,
            window_frames: int = LLM_ACTION_WINDOW_FRAMES,
            generation: int | None = None):
        """在后台线程中调用 OpenAI Responses API。"""
        if current_frame is None:
            current_frame = start_frame - 1
        try:
            request_state, prompt, text_format = self.planner.build_request(
                state,
                current_frame=current_frame,
                start_frame=start_frame,
                window_frames=window_frames,
            )
            response = self.client.create_response(
                prompt=prompt,
                text_format=text_format,
                extract_text=extract_response_text,
            )
            self._debug_log(
                "llm_request",
                start_frame=start_frame,
                current_frame=current_frame,
                window_frames=window_frames,
                state=request_state,
                payload=response.request_payload,
            )
            planned = self.planner.parse_response(
                response.response_text,
                start_frame=start_frame,
                window_frames=window_frames,
            )
            if not planned:
                planned = self._fallback_actions(start_frame, window_frames)
            self._debug_log(
                "llm_response",
                start_frame=start_frame,
                current_frame=current_frame,
                window_frames=window_frames,
                raw_response=response.raw_response,
                response_text=response.response_text,
                planned_actions=planned,
            )

            with self.lock:
                if generation is not None and generation != self.plan_generation:
                    return
                self.planned_actions.update(planned)
                self.requested_until_frame = max(planned)

        except Exception as exc:
            with self.lock:
                if generation is not None and generation != self.plan_generation:
                    return
                planned = self._fallback_actions(start_frame, window_frames)
                self.planned_actions.update(planned)
                self.requested_until_frame = max(planned)
            self._debug_log(
                "llm_error",
                start_frame=start_frame,
                current_frame=current_frame,
                window_frames=window_frames,
                error=repr(exc),
                planned_actions=planned,
            )
        finally:
            with self.lock:
                if generation is None or generation == self.plan_generation:
                    self.request_in_flight = False

    def _fallback_actions(
            self,
            start_frame: int,
            window_frames: int = LLM_ACTION_WINDOW_FRAMES) -> dict[int, str]:
        return {
            start_frame + offset: "none"
            for offset in range(window_frames)
        }

    def _none_actions(self, start_frame: int, window_frames: int) -> dict[int, str]:
        return {
            start_frame + offset: "none"
            for offset in range(window_frames)
        }

    def needs_loading(self, frame: int) -> bool:
        with self.lock:
            return frame not in self.planned_actions

    def cached_frame_summary(self) -> str | None:
        with self.lock:
            frames = sorted(self.planned_actions)
        ranges = format_frame_ranges(frames)
        if ranges is None:
            return None
        return f"Cached frames: {ranges} ({len(frames)})"

    def cached_frame_window(self, current_frame: int, radius: int = 12) -> CachedFrameWindow | None:
        with self.lock:
            if not self.planned_actions and not self.consumed_actions:
                return None
            planned = dict(self.planned_actions)
            consumed = dict(self.consumed_actions)
        return cached_frame_window(planned, consumed, current_frame, radius)

    def reset_plan(self):
        with self.lock:
            self.plan_generation += 1
            self.planned_actions.clear()
            self.consumed_actions.clear()
            self.requested_until_frame = 0
            self.request_in_flight = False
            self.requested_frame_ranges.clear()

    def discard_plan_after(self, frame: int):
        """Discard cached/requested LLM actions after frame so planning can restart."""
        with self.lock:
            self.plan_generation += 1
            for planned_frame in list(self.planned_actions):
                if planned_frame > frame:
                    self.planned_actions.pop(planned_frame, None)
            for consumed_frame in list(self.consumed_actions):
                if consumed_frame > frame:
                    self.consumed_actions.pop(consumed_frame, None)
            self.requested_until_frame = max(
                [frame, *self.planned_actions.keys()],
            )
            self.request_in_flight = False
            self.requested_frame_ranges.clear()

    def ensure_plan(self, state: dict, start_frame: int):
        with self.lock:
            if self.request_in_flight:
                return
            if self.requested_until_frame - start_frame >= LLM_PREFETCH_THRESHOLD_FRAMES:
                return
            request_start = (
                self.requested_until_frame + 1
                if self.requested_until_frame > 0
                else start_frame
            )
            request_end = request_start + LLM_ACTION_WINDOW_FRAMES - 1
            if not llm_state_has_obstacles(state):
                planned = self._none_actions(request_start, LLM_ACTION_WINDOW_FRAMES)
                self.planned_actions.update(planned)
                self.requested_until_frame = request_end
                self.requested_frame_ranges.append((request_start, request_end))
                self.request_in_flight = False
                return
            self.request_in_flight = True
            self.requested_frame_ranges.append((request_start, request_end))
            generation = self.plan_generation
        t = threading.Thread(
            target=self._call_llm,
            args=(state,),
            kwargs={
                "start_frame": request_start,
                "current_frame": start_frame - 1,
                "window_frames": LLM_ACTION_WINDOW_FRAMES,
                "generation": generation,
            },
            daemon=True,
        )
        t.start()

    def decide(self, state: dict, frame: int | None = None) -> str:
        """返回当前帧已缓存动作，并预取后续动作窗口。"""
        if frame is None:
            frame = 1
        self.ensure_plan(state, frame + 1)

        with self.lock:
            action = self.planned_actions.pop(frame, "none")
            self.consumed_actions[frame] = action
            min_keep_frame = frame - LLM_ACTION_WINDOW_FRAMES
            for old_frame in list(self.planned_actions):
                if old_frame < min_keep_frame:
                    self.planned_actions.pop(old_frame, None)
            for old_frame in list(self.consumed_actions):
                if old_frame < min_keep_frame:
                    self.consumed_actions.pop(old_frame, None)

        return action

def cached_frames_text_for_agent(agent) -> str | None:
    if isinstance(agent, LLMAgent):
        return agent.cached_frame_summary()
    return None

def cached_frames_view_for_agent(agent, current_frame: int) -> CachedFrameWindow | None:
    if isinstance(agent, LLMAgent):
        return agent.cached_frame_window(current_frame)
    return None

def debug_log_llm_game_over(
        agent,
        game: DinoGame,
        *,
        frame: int,
        action: str):
    """Write a game-over diagnostic event to the LLM debug log."""
    if not isinstance(agent, LLMAgent):
        return
    agent._debug_log(
        "game_over",
        frame=frame,
        action=action,
        score=game.score,
        dino_y=round(game.dino_y, 2),
        dino_vy=round(game.dino_vy, 2),
        jumping=game.jumping,
        ducking=game.ducking,
        speed=round(game.speed, 3),
        collision=game.last_collision,
        obstacles=[
            obstacle_debug_snapshot(obstacle)
            for obstacle in game.obstacles
        ],
    )
