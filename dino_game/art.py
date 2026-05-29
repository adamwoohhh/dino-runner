"""ASCII art sprites for the terminal dino game."""

DINO_LOGO = [
    "████▄  █  █  █   ██   ",
    "█   █  █  ██ █  █  █  ",
    "█   █  █  █ ██  █  █  ",
    "█   █  █  █  █  █  █  ",
    "█   █  █  █  █  █  █  ",
    "████▀  █  █  █   ██   ",
]

DINO_STAND = [            # 站立姿态（游戏开始前）
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",         # 头部，█▀█ 是眼睛
    r"  ▄██████ ",         # 身体
    r"  ████▄   ",
    r"   ██     ",         # 腿
    r"   █▄█▄   ",
]

DINO_RUN_1 = [            # 跑步帧 1 — 右脚前
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █▄ ▄   ",         # 两腿分开（右前）
]

DINO_RUN_2 = [            # 跑步帧 2 — 左脚前（与帧1交替播放产生跑步动画）
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"  ▄  █▄   ",         # 两腿分开（左前）
]

DINO_DUCK = [             # 蹲下姿态 — 整体下移2行，高度减小
    r"          ",         # 空行（原来头部的位置）
    r"          ",
    r"    ▄███▄ ",
    r"  ██▀█▀▀█ ",
    r"  ▀██████ ",
    r"    █▄ ▄█ ",
]

DINO_JUMP = [             # 跳跃姿态 — 腿伸直
    r"    ▄███▄ ",
    r"    █▀█▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █  █   ",         # 腿伸直张开
]

DINO_LOADING_STAND = DINO_RUN_1

DINO_LOADING_STAND_BLINK = [
    r"    ▄███▄ ",
    r"    ██▀▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █▄ ▄   ",
]

DINO_LOADING_JUMP_OPEN = DINO_JUMP

DINO_LOADING_JUMP = [     # LLM loading: 原始跳跃姿态眨眼
    r"    ▄███▄ ",
    r"    ██▀▀▀ ",
    r"  ▄██████ ",
    r"  ████▄   ",
    r"   ██     ",
    r"   █  █   ",
]

DINO_LOADING_DUCK_OPEN = DINO_DUCK

DINO_LOADING_DUCK = [     # LLM loading: 原始蹲下姿态眨眼
    r"          ",
    r"          ",
    r"    ▄███▄ ",
    r"  ██▀▀▀▀█ ",
    r"  ▀██████ ",
    r"    █▄ ▄█ ",
]

CACTUS_SM = [             # 小仙人掌（4行高，3列宽）
    " ▌ ",                # 顶部
    "▐█▌",                # 身体（两侧有臂）
    " █ ",
    " █ ",                # 根部
]

CACTUS_LG = [             # 大仙人掌（6行高，5列宽）— 最难跳过的障碍物
    "  ▌  ",
    "▌ █ ▌",              # 两侧伸出手臂
    "█▐█▌█",
    " ▀█▀ ",
    "  █  ",
    "  █  ",
]

CACTUS_PLANT_ART = {
    "short": CACTUS_SM,
    "tall": CACTUS_LG,
}

BIRD_1 = [                # 翼龙帧 1 — 翅膀朝上
    r" ▄  ",
    r"▀▀▀▀",
]

BIRD_2 = [                # 翼龙帧 2 — 翅膀朝下（与帧1交替产生拍翅动画）
    r"▄▄▄▄",
    r" ▀  ",
]

CLOUD = [                 # 装饰性云朵（不参与碰撞）
    "  ░░  ",
    " ░░░░ ",
    "░░░░░░",
]

SUN = [                   # 背景太阳（不参与碰撞）
    r" \ | / ",
    r"-- O --",
    r" / | \ ",
]

MOON = [                  # 背景月亮（不参与碰撞）
    r"  __ ",
    r" /  `",
    r"|    ",
    r" \__.",
]

CELESTIAL_ART = {
    "sun": SUN,
    "moon": MOON,
}


def celestial_art_width(kind: str) -> int:
    """Return the display width for a background celestial sprite."""
    art = CELESTIAL_ART[kind]
    return max(len(line) for line in art)


OBSTACLE_ART = {
    "cactus_sm": CACTUS_SM,
    "cactus_lg": CACTUS_LG,
    "bird": BIRD_1,       # 鸟在渲染时会在 BIRD_1/BIRD_2 之间交替
}
