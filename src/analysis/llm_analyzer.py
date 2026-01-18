from astrbot.core.star.context import Context


class LLMAnalyzer:
    def __init__(self, context: Context):
        self.context = context

    async def generate_commentary(
        self, scores: dict, archetype: str, raw_data: dict, provider_id: str = None
    ) -> dict:
        s, v, i, n = scores["simp"], scores["vibe"], scores["ick"], scores["nostalgia"]

        prompt = f"""
        你现在是极度毒舌、冷酷且满口 ACG 术语的 Galgame 《恋爱法庭》首席裁判官。
        你的任务是审判这名“被告”（群成员）今日的表现，用最辛辣的文笔拆穿对方的社交伪装。

        【案件卷宗：被告数据】
        - 最终判定人设: {archetype}
        - 纯爱值 (Simp): {s}/100（数值越高，代表其在群里投入的无谓热情越多）
        - 存在感 (Presence/Vibe): {v}/100（数值越高，说明其在群里具有统治力或魅力）
        - 败犬值 (Loser/Ick): {i}/100（数值越高，越显得其像是一个在边缘挣扎、行为尴尬的失败者/败犬）
        - 旧情指数 (Nostalgia): {n}/100（数值代表其历史底蕴、破冰能力或作为“白月光”的厚度）

        【关键证言：详细行为记录】
        - 营业频率: {raw_data.get("msg_sent", 0)} 条发言
        - 互动实效: 被回复 {raw_data.get("reply_received", 0)} 次，被贴贴/表态 {raw_data.get("reaction_received", 0)} 次
        - 败犬行为: 撤回了 {raw_data.get("recall_count", 0)} 条消息，由于复读机行为触发了 {raw_data.get("repeat_count", 0)} 次刷屏惩罚
        - 破冰记录: 今日成功引导/开启了 {raw_data.get("topic_count", 0)} 次新话题（反映了其作为主角/白月光的带动力）

        【法庭宣判要求】
        请严格按以下格式输出，禁止任何多余解释：
        [JUDGMENT]
        一段 80 字以内、由于极度毒舌而显得充满魅力的宣判。必须包含一种特定的 ACG 角色属性（如“恶役大小姐”、“病娇倾向”、“空气系 NPC”、“退队边缘人”等）。
        [DIAGNOSTICS]
        1. 针对纯爱值与存在感的对比进行扎心点评（如：满腔热忱却无人理会的“单推地狱”）。
        2. 针对败犬值（撤回、刷屏）进行人格羞辱式的深度解构（如：用撤回来掩饰社交恐惧的滑稽行为）。
        3. 针对旧情指数/破冰能力的分析（是作为白月光强势归来，还是作为过时角色在边缘垂死挣扎）。
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
