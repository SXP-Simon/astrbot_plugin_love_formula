import json
from astrbot.api import logger
from astrbot.core.star.context import Context


class LLMAnalyzer:
    def __init__(self, context: Context, config: dict = None):
        self.context = context
        self.config = config or {}

    async def generate_commentary(
        self, scores: dict, archetype: str, raw_data: dict, provider_id: str = None
    ) -> dict:
        s, v, i, n = scores["simp"], scores["vibe"], scores["ick"], scores["nostalgia"]

        # Prepare formatting context
        format_data = {
            "archetype": archetype,
            "s": s,
            "v": v,
            "i": i,
            "n": n,
            "msg_sent": raw_data.get("msg_sent", 0),
            "reply_received": raw_data.get("reply_received", 0),
            "reaction_received": raw_data.get("reaction_received", 0),
            "recall_count": raw_data.get("recall_count", 0),
            "repeat_count": raw_data.get("repeat_count", 0),
            "topic_count": raw_data.get("topic_count", 0),
        }

        # Get prompt template from config
        template_obj = self.config.get("llm_judgment_template", {})
        if isinstance(template_obj, str):  # Backward compatibility or simple string
            prompt_template = template_obj
        else:
            prompt_template = template_obj.get("template", "")

        # Fallback default
        if not prompt_template:
            prompt_template = """
你现在是极度毒舌、冷酷且满口 ACG 术语的 Galgame 《恋爱法庭》首席裁判官。
你的任务是审判这名“被告”（群成员）今日的表现，用最辛辣的文笔拆穿对方的社交伪装。

【案件卷宗：被告数据】
- 最终判定人设: {archetype}
- 纯爱值 (Simp): {s}/100（关联：主动投入、自我感动）
- 存在感 (Vibe): {v}/100（关联：被动反馈、社交引力）
- 败犬值 (Ick): {i}/100（关联：社交尴尬、边缘化行为）
- 旧情指数 (Nostalgia): {n}/100（关联：破冰能力、历史底蕴）

【关键证言：详细行为记录】
- 营业频率: {msg_sent} 条发言
- 互动实效: 被回复 {reply_received} 次，被贴贴/表态 {reaction_received} 次
- 败犬行为: 撤回了 {recall_count} 条消息，触发了 {repeat_count} 次复读惩罚
- 破冰记录: 开启了 {topic_count} 次新话题

【法庭宣判要求】
请严格按以下格式输出，禁止任何多余解释：
[JUDGMENT]
一段极度毒舌且充满魅力的宣判。必须包含特定的 ACG 角色属性。
[DIAGNOSTICS]
1. 针对纯爱值与存在感的扎心点评。
2. 针对败犬值（撤回、刷屏）的人格羞辱式解构。
3. 针对旧情指数/破冰能力的分析。
"""

        try:
            prompt = prompt_template.format(**format_data)
        except Exception as e:
            logger.error(f"Failed to format judgment prompt: {e}")
            prompt = prompt_template  # Use raw template if format fails (might produce weird output but better than crash)

        # 调用 AstrBot LLM API
        try:
            response = await self.context.llm_generate(
                prompt=prompt, chat_provider_id=provider_id
            )
            text = response.completion_text

            # 解析结果
            parts_judgement = text.split("[JUDGMENT]")
            remaining = parts_judgement[1] if len(parts_judgement) > 1 else text

            parts_diag = remaining.split("[DIAGNOSTICS]")
            judgment = parts_diag[0].strip()
            diagnostics_raw = parts_diag[1].strip() if len(parts_diag) > 1 else ""

            diagnostics = [d.strip() for d in diagnostics_raw.split("\n") if d.strip()]
            diagnostics = [
                d[2:].strip() if d.startswith(("1.", "2.", "3.", "4.")) else d
                for d in diagnostics
            ]

            logger.info(f"LLM Commentary Generated: {judgment}")
            return {"comment": judgment, "diagnostics": diagnostics}
        except Exception as e:
            logger.error(f"LLM Commentary failed: {e}")
            return {"comment": "LLM 暂时无法处理，请稍后再试。", "diagnostics": []}

    async def generate_deep_dive(
        self,
        scores: dict,
        archetype: str,
        raw_data: dict,
        chat_context: list,
        provider_id: str = None,
    ) -> dict:
        """New method for deep contextual analysis"""
        if not chat_context:
            return None

        # Format chat context
        lines = []
        for msg in chat_context:
            lines.append(
                f"[{msg['time']}] {msg['role']} {msg['nickname']}: {msg['content']}"
            )
        context_text = "\n".join(lines)

        s, v, i, n = scores["simp"], scores["vibe"], scores["ick"], scores["nostalgia"]

        # Prepare formatting context
        format_data = {
            "archetype": archetype,
            "s": s,
            "v": v,
            "i": i,
            "n": n,
            "msg_sent": raw_data.get("msg_sent", 0),
            "reply_received": raw_data.get("reply_received", 0),
            "recall_count": raw_data.get("recall_count", 0),
            "context_text": context_text,
        }

        # Get prompt template from config
        template_obj = self.config.get("llm_deep_dive_template", {})
        if isinstance(template_obj, str):
            prompt_template = template_obj
        else:
            prompt_template = template_obj.get("template", "")

        # Fallback default
        if not prompt_template:
            prompt_template = """
你是一位洞察力极强的心理侧写师，擅长结合“行为数据”与“对话细节”捕捉人的真实心理状态。
请阅读以下【行为数据】与【群聊片段】，对标记为 [Target] 的用户进行深度侧写。

【参考资料：行为数据】
- 判定人设: {archetype}
- 纯爱值 (Simp): {s}/100（关联：主动投入）
- 存在感 (Vibe): {v}/100（关联：被动反馈）
- 败犬值 (Ick): {i}/100（关联：社交尴尬）
- 旧情指数 (Nostalgia): {n}/100（关联：破冰/历史）
- 行为统计: 发言 {msg_sent} 条，被回复 {reply_received} 次，撤回 {recall_count} 次。

【重点分析：近 20 条群聊片段】
{context_text}

【分析目标】
请结合数据与对话：数据揭示了其宏观社交地位，而对话揭示了其微观心理动态。

**重要要求：**
1. **必须引用原文**：在分析时，必须摘录 1-2 句用户的具体发言或交互细节作为佐证（例如：“当他说‘...’时...”）。
2. **挖掘潜台词**：不要只复述表面意思，要分析其背后的心理动机（如：防御机制、寻求认同、掩饰尴尬等）。

示例逻辑：
- 数据显示“纯爱值”高，且对话中他在 01:23 发言“晚安”却无人回复 -> 侧写重点应为“自我感动的独角戏”。
- 数据显示“败犬值”高，且对话中他撤回了一条关于 ACG 的发言 -> 侧写重点应为“因过度在意评价而畏手畏脚”。

请严格按以下格式输出 JSON 结构：
[DEEP_PSYCHE]
KEYWORDS: #关键词1 #关键词2 #关键词3
ANALYSIS: 一段深度心理侧写。语气要冷静、透彻，引用具体细节，像是在撰写一份绝密的心理评估报告。
"""

        try:
            prompt = prompt_template.format(**format_data)
        except Exception as e:
            logger.error(f"Failed to format deep dive prompt: {e}")
            return None

        try:
            response = await self.context.llm_generate(
                prompt=prompt, chat_provider_id=provider_id
            )
            text = response.completion_text

            # Try parsing as JSON first (robust handling)
            try:
                # Remove markdown code blocks if present
                clean_text = text.strip()
                if clean_text.startswith("```"):
                    clean_text = clean_text.strip("`")
                    if clean_text.startswith("json"):
                        clean_text = clean_text[4:]

                data_json = json.loads(clean_text)

                # Handle structure: {"DEEP_PSYCHE": {"KEYWORDS": ..., "ANALYSIS": ...}}
                if "DEEP_PSYCHE" in data_json:
                    root = data_json["DEEP_PSYCHE"]
                    keywords_str = root.get("KEYWORDS", "")
                    analysis_str = root.get("ANALYSIS", "")

                    # Parse keywords string "#tag1 #tag2" -> ["#tag1", "#tag2"]
                    if isinstance(keywords_str, str):
                        keywords = [
                            k.strip()
                            for k in keywords_str.split()
                            if k.strip().startswith("#")
                        ]
                    elif isinstance(keywords_str, list):
                        keywords = keywords_str
                    else:
                        keywords = []

                    logger.info(f"LLM Deep Dive Generated (JSON): {analysis_str}")
                    return {"keywords": keywords, "content": analysis_str}
            except json.JSONDecodeError:
                pass  # Fallback to text parsing
            except Exception as e:
                logger.warning(f"JSON parsing failed, trying text parse: {e}")

            # Fallback: Text Parsing for [DEEP_PSYCHE] format
            parts = text.split("[DEEP_PSYCHE]")
            if len(parts) < 2:
                # Try simple format if model ignored [DEEP_PSYCHE] tag
                if "KEYWORDS:" in text and "ANALYSIS:" in text:
                    raw_content = text
                else:
                    return None
            else:
                raw_content = parts[1].strip()

            lines = raw_content.split("\n")

            keywords = []
            analysis = ""

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.upper().startswith("KEYWORDS"):
                    # Handle "KEYWORDS: #tag1" or "KEYWORDS": "#tag1" (pseudo-json)
                    content_part = line.split(":", 1)[1].strip()
                    # Strip quotes if pseudo-json
                    content_part = content_part.strip('",')
                    tags = content_part.split(" ")
                    keywords = [t.strip() for t in tags if t.strip().startswith("#")]
                elif line.upper().startswith("ANALYSIS"):
                    content_part = line.split(":", 1)[1].strip()
                    analysis = content_part.strip('",')
                elif analysis:
                    # Append continuation lines to analysis
                    clean_line = line.strip('",')
                    analysis += " " + clean_line

            if keywords and analysis:
                logger.info(f"LLM Deep Dive Generated (Text): {analysis}")
                return {"keywords": keywords, "content": analysis}

            return None
        except Exception as e:
            logger.error(f"LLM Deep Dive failed: {e}")
            return None
