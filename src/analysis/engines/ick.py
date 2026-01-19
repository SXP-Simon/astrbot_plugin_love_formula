from ...models.tables import LoveDailyRef
from .base import BaseMetricEngine


class IckEngine(BaseMetricEngine):
    """
    败犬值引擎 (Ick Engine)
    负责计算用户的“社交尴尬/负面”程度。
    核心逻辑：频繁的撤回（不自信表现）和复读刷屏（机械行为）会快速累积败犬值。
    """

    W_RECALL = 5.0  # 撤回处罚权重 (高，代表社交逃避)
    W_REPEAT = 3.0  # 复读处罚权重 (代表破坏社交节奏)

    def calculate(self, data: LoveDailyRef) -> float:
        # 原始分值 = (撤回数 * 权重) + (复读机次数 * 权重)
        return data.recall_count * self.W_RECALL + data.repeat_count * self.W_REPEAT
