import math

from ..models.tables import LoveDailyRef
from .engines.ick import IckEngine
from .engines.nostalgia import NostalgiaEngine
from .engines.simp import SimpEngine
from .engines.vibe import VibeEngine


class LoveCalculator:
    """
    恋爱成分计算器 (Orchestrator)
    负责调度各个模块化引擎，执行分值归一化，并根据 $J_{love}$ 公演计算最终得分。
    """

    def __init__(self):
        # 初始化各个专业引擎
        self.simp_engine = SimpEngine()
        self.vibe_engine = VibeEngine()
        self.ick_engine = IckEngine()
        self.nostalgia_engine = NostalgiaEngine()

    def calculate_scores(self, data: LoveDailyRef, yesterday_score: int = 0) -> dict:
        """根据每日数据计算各项得分"""
        # 1. 调用模块化引擎计算原始分值
        raw_simp = self.simp_engine.calculate(data)
        raw_vibe = self.vibe_engine.calculate(data)
        raw_ick = self.ick_engine.calculate(data)
        raw_nostalgia = self.nostalgia_engine.calculate(data)

        # 2. 融入昨日好感度 (作为 Nostalgia 的核心)
        # 如果昨日有好感度，将其按一定比例转化为今日的 Nostalgia 原始分
        # 假设昨日 100 分 -> 今日额外提供 100 点原始白月光值（映射后约 92%）
        if yesterday_score > 0:
            raw_nostalgia += yesterday_score

        # 3. 归一化逻辑 (使用 sigmoid 函数映射到 0-100)
        # 映射关系: 0 -> 0, 10 -> 24, 20 -> 46, 50 -> 84, 100 -> 98
        def normalize(x):
            try:
                if x <= 0:
                    return 0
                return int(100 * (2 / (1 + math.exp(-0.05 * x)) - 1))
            except Exception:
                return 0

        v, n, i, s = (
            normalize(raw_vibe),
            normalize(raw_nostalgia),
            normalize(raw_ick),
            normalize(raw_simp),
        )

        # 4. 最终得分计算 (J_love = V + N - I - S)
        # 将原始计算结果映射到 [0, 100]： (Asset - Liability + 200) / 4
        total_score = ((v + n) - (i + s) + 200) / 4

        return {
            "simp": s,
            "vibe": v,
            "ick": i,
            "nostalgia": n,
            "score": int(max(0, min(100, total_score))),  # 综合好感度
            "raw": {
                "simp": raw_simp,
                "vibe": raw_vibe,
                "ick": raw_ick,
                "nostalgia": raw_nostalgia,
            },
        }
