from ...models.tables import LoveDailyRef
from .base import BaseMetricEngine


class SimpEngine(BaseMetricEngine):
    """
    纯爱值引擎 (Simp Engine)
    负责计算用户的“付出”程度。
    核心逻辑：高频的发言、主动的交互（戳一戳）以及长篇大论（小作文）都会增加纯爱值。
    """

    W_MSG_SENT = 1.0  # 基础发言权重
    W_POKE_SENT = 2.0  # 主动交互权重
    W_AVG_LEN = 0.05  # 文本字数权重 (小作文功率)

    def calculate(self, data: LoveDailyRef) -> float:
        # 计算平均每条消息的长度
        avg_len = data.text_len_total / data.msg_sent if data.msg_sent > 0 else 0

        # 原始分值 = (发言数 * 权重) + (戳一戳 * 权重) + (平均字数 * 权重)
        return (
            data.msg_sent * self.W_MSG_SENT
            + data.poke_sent * self.W_POKE_SENT
            + avg_len * self.W_AVG_LEN
        )
