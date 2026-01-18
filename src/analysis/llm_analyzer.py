from astrbot.core.star.context import Context


class LLMAnalyzer:
    def __init__(self, context: Context):
        self.context = context

    async def generate_commentary(
        self, scores: dict, archetype: str, raw_data: dict, provider_id: str = None
    ) -> dict:
        s, v, i = scores["simp"], scores["vibe"], scores["ick"]

        prompt = f"""
        你现在是 Galgame 《恋爱法庭》中的“毒舌裁判官”。
        请根据以下被告（群成员）的今日恋爱成分数据，进行深度诊断。

        【被告数据】
        - 判定人设: {archetype}
        - 纯爱值 (Simp): {s}/100
        - 存在感 (Presence/Vibe): {v}/100
        - 败犬值 (Loser/Ick): {i}/100

        【详细行为】
        - 发言: {raw_data.get("msg_sent", 0)} 条
        - 被回复: {raw_data.get("reply_received", 0)} 次
        - 撤回: {raw_data.get("recall_count", 0)} 次
        - 被贴贴: {raw_data.get("reaction_received", 0)} 次

        【输出要求】
        请严格按以下格式输出，不要包含任何额外文字：
        [JUDGMENT]
        一段 50 字以内的判词，语气要极度中二、毒舌、充满 Galgame 恶役大小姐或冷酷裁判官的味道。
        [DIAGNOSTICS]
        1. 行为 1 的诊断（结合二次元术语如“傲娇”、“偷家”、“败犬”等解释数据）。
        2. 行为 2 的诊断。
        3. 行为 3 的诊断（如果有）。
        """

        # 调用 AstrBot LLM API
        try:
            response = await self.context.llm_generate(
                prompt=prompt, chat_provider_id=provider_id
            )
            text = response.completion_text

            # 简单解析
            parts = text.split("[DIAGNOSTICS]")
            judgment = parts[0].replace("[JUDGMENT]", "").strip()
            diagnostics_raw = parts[1].strip() if len(parts) > 1 else ""

            diagnostics = [d.strip() for d in diagnostics_raw.split("\n") if d.strip()]
            # 去掉可能的数字前缀 (如 "1. ") 如果存在
            diagnostics = [
                d[2:].strip() if d.startswith(("1.", "2.", "3.", "4.")) else d
                for d in diagnostics
            ]

            return {"comment": judgment, "diagnostics": diagnostics}
        except Exception:
            return {"comment": "LLM 暂时无法处理，请稍后再试。", "diagnostics": []}
