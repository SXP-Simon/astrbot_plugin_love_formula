import os
from astrbot.core.log import LogManager
from astrbot.core.star import Star
from astrbot.core.star.context import Context
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import CustomFilter, EventMessageType
from astrbot.core.config import AstrBotConfig

from .src.persistence.database import DBManager
from .src.persistence.repo import LoveRepo
from .src.handlers.message_handler import MessageHandler
from .src.handlers.notice_handler import NoticeHandler
from .src.analysis.calculator import LoveCalculator
from .src.analysis.classifier import ArchetypeClassifier
from .src.analysis.llm_analyzer import LLMAnalyzer
from .src.visual.theme_manager import ThemeManager
from .src.visual.renderer import LoveRenderer

logger = LogManager.GetLogger("astrbot_plugin_love_formula")


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
        commentary = "获取失败"
        if self.config.get("enable_llm_commentary", True):
            raw_data_dict = daily_data.model_dump()
            # 如果配置了 provider_id 则传入

            provider_id = self.config.get("llm_provider_id", "")
            commentary = await self.llm.generate_commentary(
                scores["raw"], archetype_name, raw_data_dict, provider_id=provider_id
            )
        else:
            commentary = "LLM点评已关闭。"

        # 5. 渲染图片
        logger.debug(f"准备渲染图片，Archetype: {archetype_name}, Scores: {scores}")

        theme = self.config.get("theme", "galgame")

        # 构造符合模板要求的数据结构
        # Template expects: avatar_url, user_name, title, score, metrics, comment, generated_time
        sender = event.message_obj.sender
        user_name = sender.nickname if sender else f"用户{user_id}"
        # 尝试构建头像 URL (OneBot V11 风格)
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"

        from datetime import datetime

        render_data = {
            "user_name": user_name,
            "user_id": user_id,
            "avatar_url": avatar_url,
            "title": archetype_name,  # 使用人设作为 title
            "score": int(
                (scores["simp"] + scores["vibe"] + scores["ick"]) / 3
            ),  # 计算总分
            "metrics": {
                "舔狗值": scores["simp"],
                "魅力值": scores["vibe"],
                "下头值": scores["ick"],
                "纯爱度": scores.get("pure_love", 0),  # 假设 calculator 返回了这些
                "发言数": raw_data_dict.get("msg_sent", 0),
            },
            "comment": commentary,
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        logger.debug(f"Render Data: {render_data}")

        try:
            image_path = await self.renderer.render(render_data, theme_name=theme)
            logger.info(f"图片渲染成功: {image_path}")
            yield event.image_result(image_path)
        except Exception as e:
            logger.error(f"Render failed: {e}", exc_info=True)
            yield event.plain_result(f"生成失败: {e}")
