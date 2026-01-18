import os

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import CustomFilter, EventMessageType
from astrbot.core.config import AstrBotConfig
from astrbot.core.star import Star
from astrbot.core.star.context import Context

from .src.analysis.calculator import LoveCalculator
from .src.analysis.classifier import ArchetypeClassifier
from .src.analysis.llm_analyzer import LLMAnalyzer
from .src.handlers.message_handler import MessageHandler
from .src.handlers.notice_handler import NoticeHandler
from .src.persistence.database import DBManager
from .src.persistence.repo import LoveRepo
from .src.visual.renderer import LoveRenderer
from .src.visual.theme_manager import ThemeManager


class NoticeFilter(CustomFilter):
    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        if not event.message_obj.raw_message:
            return False
        raw = event.message_obj.raw_message
        if isinstance(raw, dict):
            return raw.get("post_type") == "notice"
        return False


class LoveFormulaPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

        # 1. 初始化持久层
        db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "love_formula.db"
        )
        self.db_mgr = DBManager(db_path)
        self.repo = LoveRepo(self.db_mgr)

        # 2. 初始化处理器和逻辑

        self.msg_handler = MessageHandler(self.repo)
        self.notice_handler = NoticeHandler(self.repo)
        self.theme_mgr = ThemeManager(os.path.dirname(os.path.abspath(__file__)))
        self.renderer = LoveRenderer(context, self.theme_mgr)
        self.llm = LLMAnalyzer(context)

    async def init(self):
        """AstrBot 调用的异步初始化方法"""
        await self.db_mgr.init_db()
        logger.info("LoveFormula DB initialized.")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """处理群消息监听"""
        logger.debug(
            f"[LoveFormula] on_group_message 触发: {event.message_obj.message_id}"
        )
        await self.msg_handler.handle_message(event)

    @filter.custom_filter(NoticeFilter)
    async def on_notice(self, event: AstrMessageEvent):
        """
        处理 Notice 事件 (OneBot V11)。
        注意：逻辑取决于 AstrBot 如何封装 notice 事件。
        假设 event.raw_data 包含 OneBot 负载。
        """
        if hasattr(event, "message_obj") and event.message_obj.raw_message:
            await self.notice_handler.handle_notice(event.message_obj.raw_message)

    @filter.command("今日人设")
    async def cmd_love_profile(self, event: AstrMessageEvent):
        """生成每日恋爱成分分析报告"""
        group_id = event.message_obj.group_id
        user_id = event.message_obj.sender.user_id

        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        # 1. 获取数据

        daily_data = await self.repo.get_today_data(group_id, user_id)

        # 检查配置中的阈值

        min_msg = self.config.get("min_msg_threshold", 3)
        if not daily_data or daily_data.msg_sent < min_msg:
            yield event.plain_result(
                f"你今天太沉默了（发言少于{min_msg}条），甚至无法测算出恋爱成分。"
            )
            return

        # 2. 计算分数

        scores = LoveCalculator.calculate_scores(daily_data)

        # 3. 归类人设

        archetype_key, archetype_name = ArchetypeClassifier.classify(scores)

        # 4. LLM 分析
        # 4. LLM 分析 (获取判词和诊断)
        llm_result = {"comment": "获取失败", "diagnostics": []}
        raw_data_dict = (
            daily_data.model_dump()
        )  # Ensure raw_data_dict is available for metrics
        if self.config.get("enable_llm_commentary", True):
            provider_id = self.config.get("llm_provider_id", "")
            # 注意: 现在 generate_commentary 返回的是字典 {"comment": "...", "diagnostics": [...]}
            llm_result = await self.llm.generate_commentary(
                scores, archetype_name, raw_data_dict, provider_id=provider_id
            )
        else:
            llm_result["comment"] = "LLM点评已关闭。"

        # 5. 组装诊断叙事 (如果 LLM 没给，就用内置逻辑 fallback)
        if not llm_result.get("diagnostics"):
            logic_insights = self._generate_diagnostic_insights(
                scores, raw_data_dict, archetype_key
            )
        else:
            logic_insights = llm_result["diagnostics"]

        # 6. 构造渲染数据
        # Template expects: avatar_url, user_name, title, score, metrics, logic_insights, comment, generated_time
        sender = event.message_obj.sender
        user_name = sender.nickname if sender else f"用户{user_id}"
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        from datetime import datetime

        render_data = {
            "user_name": user_name,
            "user_id": user_id,
            "avatar_url": avatar_url,
            "title": archetype_name,
            "score": int((scores["simp"] + scores["vibe"] + scores["ick"]) / 3),
            "metrics": {
                "舔狗值": f"{scores['simp']}%",
                "魅力值": f"{scores['vibe']}%",
                "下头值": f"{scores['ick']}%",
                "互动频率": f"{raw_data_dict.get('msg_sent', 0)}条/日",
                "平均字数": f"{int(raw_data_dict.get('text_len_total', 0) / raw_data_dict.get('msg_sent', 1)) if raw_data_dict.get('msg_sent', 0) > 0 else 0}字",
            },
            "logic_insights": logic_insights,
            "comment": llm_result.get("comment", "获取失败"),
            "equation": self._construct_latex_equation(scores, raw_data_dict),
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        logger.debug(f"Render Data: {render_data}")

        # 7. 渲染图片
        theme = self.config.get("theme", "galgame")
        try:
            image_path = await self.renderer.render(render_data, theme_name=theme)
            logger.info(f"图片渲染成功: {image_path}")

            # Convert to Base64 to avoid "rich media transfer failed" error
            import base64

            with open(image_path, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode()

            from astrbot.core.message.components import Image

            yield event.chain_result([Image.fromBase64(b64_str)])
        except Exception as e:
            logger.error(f"Render failed: {e}", exc_info=True)
            yield event.plain_result(f"生成失败: {e}")

    def _construct_latex_equation(self, scores: dict, raw: dict) -> str:
        """构造 LaTeX 数学公式"""
        # S = (msg * 1.0 + poke * 2.0 + avg_len * 0.05)
        # V = (reply * 3.0 + reaction * 2.0 + poke_recv * 2.0)
        # I = (recall * 5.0)
        s_raw = scores["raw"]["simp"]
        v_raw = scores["raw"]["vibe"]
        i_raw = scores["raw"]["ick"]

        # 构造一个展示核心逻辑的算式
        latex = r"L = \sigma("
        latex += rf"{s_raw:.1f} \cdot S_{{imp}} + "
        latex += rf"{v_raw:.1f} \cdot V_{{ibe}} - "
        latex += rf"{i_raw:.1f} \cdot I_{{ck}}"
        latex += r") \approx "  # Wait, render_data is local to handle_message

        # Re-calculating score for the string is redundant, let's just make it a clean formula
        score = int((scores["simp"] + scores["vibe"] + scores["ick"]) / 3)
        return rf"f(S, V, I) = \text{{norm}}({s_raw:.1f}, {v_raw:.1f}, {i_raw:.1f}) \Rightarrow {score}\%"

    def _generate_diagnostic_insights(
        self, scores: dict, raw_data: dict, archetype_key: str
    ) -> list:
        """生成叙事性的行为诊断报告"""
        insights = []

        # 1. 舔狗值诊断 (S)
        msg_sent = raw_data.get("msg_sent", 0)
        poke_sent = raw_data.get("poke_sent", 0)
        if scores["simp"] > 60:
            insights.append(
                f"主动付出判定: 你今日发送了 {msg_sent} 条消息并主动‘戳了戳’他人 {poke_sent} 次。这种高频的单向互动大幅推高了你的‘舔狗值’，反映出你强烈的社交欲望。"
            )
        else:
            insights.append(
                "社交投入判定: 你今日的发言频率与互动强度适中，处于健康的社交平衡区间，没有表现出过度的低姿态倾向。"
            )

        # 2. 魅力值诊断 (V)
        reply_recv = raw_data.get("reply_received", 0)
        reaction_recv = raw_data.get("reaction_received", 0)
        if scores["vibe"] > 60:
            insights.append(
                f"吸引力判定: 你的言论引发了群友的广泛关注。收到了 {reply_recv} 次回复和 {reaction_recv} 次表情回应。这表明你今天的发言质量极高，是群内的社交核心。"
            )
        elif scores["vibe"] < 20:
            insights.append(
                f"存在感判定: 群友对你的回应较少（仅 {reply_recv} 次回复）。建议通过发送有趣的表情包或参与热门话题来提升你的存在感。"
            )
        else:
            insights.append(
                "反馈能量判定: 你的发言获得了一定程度的反馈，社交磁场保持稳定。"
            )

        # 3. 下头值诊断 (I)
        recall = raw_data.get("recall_count", 0)
        if recall > 0:
            insights.append(
                f"社交稳定性判定: 你今日撤回了 {recall} 条消息。在社交模型中，频繁撤回被视为‘犹豫’或‘不确定性’，每撤回一条会显著增加你的‘下头值’({LoveCalculator.W_RECALL}分/条)。"
            )

        # 4. 人设由来
        insights.append(
            f"人设达成逻辑: 基于上述数据，{self._get_archetype_reason(archetype_key, scores)}"
        )

        return insights

    def _get_archetype_reason(self, key: str, scores: dict) -> str:
        """根据 Key 返回判定理由"""
        reasons = {
            "THE_SIMP": f"由于你的投入({scores['simp']}%)远高于群友对你的反馈({scores['vibe']}%)，满足了‘沸羊羊’判定门槛。",
            "THE_PLAYER": f"因为你只需较低的投入就能换取极高的群友反馈({scores['vibe']}%)，表现出典型的‘海王’特征。",
            "HIMBO": f"虽然你的魅力值({scores['vibe']}%)很高，但撤回行为带来的下头值({scores['ick']}%)让你的表现显得矛盾而迷人。",
            "IDOL": f"你几乎不主动付出({scores['simp']}%)却依然保有一定的群友关注，这种高冷姿态符合‘男神/女神’的设定。",
            "NPC": "你今日的各项交互数据均处于极低水平，系统判定你正在群内‘潜水’观望。",
            "NORMAL": "各项指标分布均匀，没有极端异常的数据表现，是一个平稳社交的普通群友。",
        }
        return reasons.get(key, "数据分布符合该人设的特征判定区间。")
