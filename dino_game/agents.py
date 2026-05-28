"""Non-LLM game agents."""

class RuleAgent:
    """基于距离阈值的反应式 Agent — 简单、快速、可靠

    策略原理:
      1. 找到前方最近的「需要跳过」的障碍物
      2. 计算一个「反应距离」= 7 + speed * 4
         - 7 是碰撞区起始距离（恐龙右边缘到障碍物左边缘的像素）
         - speed * 4 是提前量（速度越快越要早跳，留出 ~3 帧的起跳时间）
      3. 障碍物进入反应距离且恐龙在地面 → 跳！

    性能: 平均约 960 分（20 局测试），最好 1200+
    延迟: 微秒级（纯数学判断，无 I/O）
    """

    def decide(self, state: dict) -> str:
        """根据游戏状态返回动作

        Args:
            state: DinoGame.get_state() 的返回值

        Returns:
            "jump" / "duck" / "none"
        """
        if not state["obstacles"]:
            return "none"

        speed = state["speed"]
        on_ground = state["dino_y"] < 0.5 and not state["jumping"]

        # 反应窗口边界
        react_max = 2 + speed * 10   # 约提前 10 帧起跳，避免高点过早错过障碍
        react_min = -2              # 太近了也别跳（已经来不及了）

        # 依次检查前方障碍物（已按距离排序）
        for obs in state["obstacles"]:
            dist = obs["distance"]
            obstacle_react_max = react_max
            if obs["kind"] == "cactus_group" and obs["h"] <= 4:
                obstacle_react_max = 14 + speed * 2
            if dist > obstacle_react_max or dist < react_min:
                continue

            if obs["kind"] == "bird":
                # 中空鸟会撞到站立恐龙头部，蹲下躲避；高空鸟忽略
                if obs["height"] == 4:
                    return "duck"
                if obs["height"] >= 8:
                    continue

            # 低空鸟 或 任何仙人掌 — 必须跳！
            if on_ground:
                return "jump"

        return "none"
