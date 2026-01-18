class ArchetypeClassifier:
    """人设分类器，根据得分将用户归类为特定的网络人设"""

    ARCHETYPES = {
        "THE_SIMP": "纯爱战神 (反讽)",
        "THE_PLAYER": "现充达人",
        "HIMBO": "傲娇败犬",
        "NPC": "背景板 NPC",
        "IDOL": "顶级偶像",
        "NORMAL": "一般群友",
    }

    @staticmethod
    def classify(scores: dict) -> tuple[str, str]:
        """根据得分返回人设 Key 和名称"""
        s = scores["simp"]
        v = scores["vibe"]
        i = scores["ick"]

        # 判定逻辑
        if i > 60 and v > 50:
            return "HIMBO", ArchetypeClassifier.ARCHETYPES["HIMBO"]

        if s > 70 and v < 30:
            return "THE_SIMP", ArchetypeClassifier.ARCHETYPES["THE_SIMP"]

        if s < 40 and v > 70:
            return "THE_PLAYER", ArchetypeClassifier.ARCHETYPES["THE_PLAYER"]

        if s < 15 and v > 40:
            return "IDOL", ArchetypeClassifier.ARCHETYPES["IDOL"]

        if s < 20 and v < 20:
            return "NPC", ArchetypeClassifier.ARCHETYPES["NPC"]

        return "NORMAL", ArchetypeClassifier.ARCHETYPES["NORMAL"]
