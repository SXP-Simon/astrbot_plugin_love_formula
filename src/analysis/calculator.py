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
    W_REPEAT = 3.0  # 重复发言惩罚

    # 旧情/白月光权重 (Nostalgia)
    W_TOPIC = 10.0  # 破冰/开场高权重
    W_MEME = 2.0  # 图片/梗图带动气氛

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
        raw_ick = (
            data.recall_count * LoveCalculator.W_RECALL
            + data.repeat_count * LoveCalculator.W_REPEAT
        )

        # 4. 旧情/白月光计算 (M/Nostalgia)
        raw_nostalgia = (
            data.topic_count * LoveCalculator.W_TOPIC
            + data.image_sent * LoveCalculator.W_MEME
        )

        # 5. 归一化 (使用 sigmoid 函数映射到 0-100)
        # 使用平缓的 sigmoid: 100 * (2 / (1 + e^(-0.05 * x)) - 1)
        # 映射关系: 0 -> 0, 10 -> 24, 20 -> 46, 50 -> 84, 100 -> 98

        def normalize(x):
            if x <= 0:
                return 0
            return int(100 * (2 / (1 + math.exp(-0.05 * x)) - 1))

        v, n, i, s = (
            normalize(raw_vibe),
            normalize(raw_nostalgia),
            normalize(raw_ick),
            normalize(raw_simp),
        )

        # J_love = \int e^{-rt} * [V + \beta N - \lambda I - c S] dt
        # 考虑到归一化后的指标范围在 [0, 100]
        # (v + n) - (i + s) 的理论范围是 [-200, 200]
        # 我们将其线性映射到 [0, 100]: (Value + 200) / 4
        # 这样：
        # - 极致现充 (V=100, N=100, I=0, S=0) -> 100分
        # - 极致败犬 (V=0, N=0, I=100, S=100) -> 0分
        # - 平庸平衡 (V=50, N=50, I=50, S=50) -> 50分
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
