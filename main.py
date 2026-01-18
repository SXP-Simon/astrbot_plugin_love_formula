import os
import logging
from astrbot.core.star import Star
from astrbot.core.star.context import Context
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import EventMessageType

from .src.persistence.database import DBManager
from .src.persistence.repo import LoveRepo
from .src.handlers.message_handler import MessageHandler
from .src.handlers.notice_handler import NoticeHandler
from .src.analysis.calculator import LoveCalculator
from .src.analysis.classifier import ArchetypeClassifier
from .src.analysis.llm_analyzer import LLMAnalyzer
from .src.visual.theme_manager import ThemeManager
from .src.visual.renderer import LoveRenderer

logger = logging.getLogger("astrbot_plugin_love_formula")


class LoveFormulaPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

        # 1. Init Persistence
        db_path = os.path.join(context.plugin_data_dir, "love_formula.db")
        self.db_mgr = DBManager(db_path)
        self.repo = LoveRepo(self.db_mgr)

        # 2. Init Handlers & Logic
        self.msg_handler = MessageHandler(self.repo)
        self.notice_handler = NoticeHandler(self.repo)
        self.theme_mgr = ThemeManager(os.path.dirname(os.path.abspath(__file__)))
        self.renderer = LoveRenderer(context, self.theme_mgr)
        self.llm = LLMAnalyzer(context)

    async def init(self):
        """Async initialization called by AstrBot"""
        await self.db_mgr.init_db()
        logger.info("LoveFormula DB initialized.")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """Handle group messages"""
        await self.msg_handler.handle_message(event)

    @filter.platform_event_type("notice")
    async def on_notice(self, event: AstrMessageEvent):
        """
        Handle Notice events (OneBot V11).
        Note: logic depends on how AstrBot wraps notice events.
        Assuming event.raw_data contains the OneBot payload.
        """
        if hasattr(event, "message_obj") and event.message_obj.raw_data:
            await self.notice_handler.handle_notice(event.message_obj.raw_data)

    @filter.command("今日人设")
    async def cmd_love_profile(self, event: AstrMessageEvent):
        """Generate daily love analysis profile"""
        group_id = event.message_obj.group_id
        user_id = event.message_obj.sender.user_id

        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        # 1. Fetch Data
        daily_data = await self.repo.get_today_data(group_id, user_id)

        # Check threshold from config
        min_msg = self.config.get("min_msg_threshold", 3)
        if not daily_data or daily_data.msg_sent < min_msg:
            yield event.plain_result(
                f"你今天太沉默了（发言少于{min_msg}条），甚至无法测算出恋爱成分。"
            )
            return

        # 2. Calculate Scores
        scores = LoveCalculator.calculate_scores(daily_data)

        # 3. Classify Archetype
        archetype_key, archetype_name = ArchetypeClassifier.classify(scores)

        # 4. LLM Analysis
        commentary = "获取失败"
        if self.config.get("enable_llm_commentary", True):
            raw_data_dict = daily_data.model_dump()
            # Pass provider_id if configured
            provider_id = self.config.get("llm_provider_id", "")
            commentary = await self.llm.generate_commentary(
                scores["raw"], archetype_name, raw_data_dict, provider_id=provider_id
            )
        else:
            commentary = "LLM点评已关闭。"

        # 5. Render Image
        theme = self.config.get("theme", "galgame")
        render_data = {
            "scores": scores,
            "archetype": archetype_name,
            "commentary": commentary,
            "user_id": user_id,
            "group_id": group_id,
        }

        try:
            image_path = await self.renderer.render(render_data, theme_name=theme)
            yield event.image_result(image_path)
        except Exception as e:
            logger.error(f"Render failed: {e}", exc_info=True)
            yield event.plain_result(f"生成失败: {e}")
