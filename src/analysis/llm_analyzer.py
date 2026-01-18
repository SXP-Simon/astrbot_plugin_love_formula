from astrbot.core.star.context import Context


class LLMAnalyzer:
    def __init__(self, context: Context):
        self.context = context

    async def generate_commentary(
        self, scores: dict, archetype: str, raw_data: dict, provider_id: str = None
    ) -> str:
        s, v, i = scores["simp"], scores["vibe"], scores["ick"]

        prompt = f"""
        你现在是 Galgame 《恋爱法庭》中的“毒舌裁判官”。
        请根据以下被告（群成员）的今日恋爱成分数据，写一段 50 字以内的判词。
        
        【被告数据】
        - 判定人设: {archetype}
        - 舔狗值 (Simp): {s}/100
        - 魅力值 (Vibe): {v}/100
        - 下头值 (Ick): {i}/100
        
        【详细行为】
        - 发言: {raw_data.get("msg_sent", 0)} 条
        - 被回复: {raw_data.get("reply_received", 0)} 次
        - 撤回: {raw_data.get("recall_count", 0)} 次
        - 被贴贴: {raw_data.get("reaction_received", 0)} 次

        【要求】
        1. 语气：中二、毒舌、高高在上，或者像傲娇的 Galgame 女主角。
        2. 必须引用至少一个变量名（如 E, V, I, S）来进行伪科学解释。
        3. 严禁说教，要有趣味性。
        4. 字数控制在 50 字左右。
        """

        # 调用 AstrBot LLM API
        # 使用 tool_loop_agent=False 仅获取文本生成结果
        response = await self.context.llm_generate(
            prompt=prompt, chat_provider_id=provider_id
        )
        return response.completion_text
