from ...models.tables import LoveDailyRef
from .base import BaseMetricEngine


class NostalgiaEngine(BaseMetricEngine):
    """
    旧情/白月光引擎 (Nostalgia Engine)
    负责计算用户的“历史沉淀与破冰能力”。
    核心逻辑：成功引导话题开启和发送具有共鸣感的图片/梗图，被视为白月光指数的体现。
    """

    W_TOPIC = 8.0  # 话题引领权重 (略微下调以平衡总分)
    W_MEME = 1.0  # 图片贡献权重

    def calculate(self, data: LoveDailyRef) -> float:
        # 原始分值 = (引领话题数 * 权重) + (发送图片数 * 权重)
        return data.topic_count * self.W_TOPIC + data.image_sent * self.W_MEME
