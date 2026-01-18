import math

from ..models.tables import LoveDailyRef


class LoveCalculator:
    """恋爱成分计算器，负责各项指标权重的定义和计算"""

    # 纯爱值权重 (付出/产出)
    W_MSG_SENT = 1.0
    W_POKE_SENT = 2.0
    W_AVG_LEN = 0.05  # 每个字符

    # 存在感权重 (反馈/输入)
    W_REPLY_RECV = 3.0
    W_REACTION_RECV = 2.0
    W_POKE_RECV = 2.0

    # 败犬值权重 (负面行为)
    W_RECALL = 5.0

    @staticmethod
    def calculate_scores(data: LoveDailyRef) -> dict:
        """根据每日数据计算各项得分"""
        # 1. 纯爱值计算 (S)
        avg_len = data.text_len_total / data.msg_sent if data.msg_sent > 0 else 0
        raw_simp = (
            data.msg_sent * LoveCalculator.W_MSG_SENT
            + data.poke_sent * LoveCalculator.W_POKE_SENT
            + avg_len * LoveCalculator.W_AVG_LEN
        )

        # 2. 存在感计算 (V)
        raw_vibe = (
            data.reply_received * LoveCalculator.W_REPLY_RECV
            + data.reaction_received * LoveCalculator.W_REACTION_RECV
            + data.poke_received * LoveCalculator.W_POKE_RECV
        )

        # 3. 败犬值计算 (I)
        raw_ick = data.recall_count * LoveCalculator.W_RECALL

        # 4. 归一化 (使用 sigmoid 函数映射到 0-100)
        # 使用平缓的 sigmoid: 100 * (2 / (1 + e^(-0.05 * x)) - 1)
        # 映射关系: 0 -> 0, 10 -> 24, 20 -> 46, 50 -> 84, 100 -> 98

        def normalize(x):
            if x <= 0:
                return 0
            return int(100 * (2 / (1 + math.exp(-0.05 * x)) - 1))

        return {
            "simp": normalize(raw_simp),
            "vibe": normalize(raw_vibe),
            "ick": normalize(raw_ick),
            "raw": {"simp": raw_simp, "vibe": raw_vibe, "ick": raw_ick},
        }
