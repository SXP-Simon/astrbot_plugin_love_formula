import os
import logging
from astrbot.core.star.star import Star
from astrbot.core.star.context import Context
from astrbot.core.event.model.event import AstrMessageEvent, EventMessageType
from astrbot.core.event import filter
from astrbot.core.platform.start_types import NakalType

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
        if not daily_data:
            yield event.plain_result("今日暂无恋爱成分数据，请多发言后再试。")
            return

        # 2. Calculate Scores
        scores = LoveCalculator.calculate_scores(daily_data)

        # 3. Classify Archetype
        archetype_key, archetype_name = ArchetypeClassifier.classify(scores)

        # 4. LLM Analysis
        raw_data_dict = daily_data.model_dump()
        commentary = await self.llm.generate_commentary(
            scores["raw"], archetype_name, raw_data_dict
        )

        # 5. Render Image
        render_data = {
            "scores": scores,
            "archetype": archetype_name,
            "commentary": commentary,
            "user_id": user_id,
            "group_id": group_id,
        }

        try:
            image_path = await self.renderer.render(render_data)
            yield event.image_result(image_path)
        except Exception as e:
            logger.error(f"Render failed: {e}", exc_info=True)
            yield event.plain_result(f"生成失败: {e}")
