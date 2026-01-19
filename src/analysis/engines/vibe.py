from ...models.tables import LoveDailyRef
from .base import BaseMetricEngine


class VibeEngine(BaseMetricEngine):
    """
    存在感引擎 (Vibe Engine)
    负责计算用户的“社交回馈”程度。
    核心逻辑：被群友回复、被贴贴以及被戳一戳的数量，代表了用户在群聊中的吸引力和存在感。
    """

    W_REPLY_RECV = 3.0  # 被回复权重 (最高，代表核心互动)
    W_REACTION_RECV = 2.0  # 被贴贴权重 (代表情绪共鸣)
    W_POKE_RECV = 2.0  # 被戳一戳权重 (代表弱社交吸引)

    def calculate(self, data: LoveDailyRef) -> float:
        # 原始分值 = (被回复数 * 权重) + (被贴贴数 * 权重) + (被戳数 * 权重)
        return (
            data.reply_received * self.W_REPLY_RECV
            + data.reaction_received * self.W_REACTION_RECV
            + data.poke_received * self.W_POKE_RECV
        )
