import os

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import CustomFilter, EventMessageType
from astrbot.core.config import AstrBotConfig
from astrbot.core.message.components import At, Image
from astrbot.core.star import Star
from astrbot.core.star.context import Context

from .src.analysis.calculator import LoveCalculator
from .src.analysis.classifier import ArchetypeClassifier
from .src.analysis.llm_analyzer import LLMAnalyzer
from .src.handlers.history_fetcher import OneBotAdapter
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

        # 1. 确定持久化存储路径
        from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

        # 插件数据目录: data/plugin_data/astrbot_plugin_love_formula/
        data_dir = os.path.join(
            get_astrbot_plugin_data_path(), "astrbot_plugin_love_formula"
        )
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        db_path = os.path.join(data_dir, "love_formula.db")

        # 迁移逻辑: 如果旧路径存在数据库，则移动到新路径
        old_db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "love_formula.db"
        )
        if os.path.exists(old_db_path) and not os.path.exists(db_path):
            try:
                import shutil

                shutil.move(old_db_path, db_path)
            except Exception:
                pass  # 如果移动失败，则按新路径初始化，由 DBManager 处理

        self.db_mgr = DBManager(db_path)
        self.repo = LoveRepo(self.db_mgr)

        # 2. 初始化处理器和逻辑

        self.msg_handler = MessageHandler(self.repo)
        self.notice_handler = NoticeHandler(self.repo)
        self.history_fetcher = OneBotAdapter(context, config)
        self.theme_mgr = ThemeManager(os.path.dirname(os.path.abspath(__file__)))
        self.renderer = LoveRenderer(context, self.theme_mgr)
        self.llm = LLMAnalyzer(context, self.config)
        self.calculator = LoveCalculator()
        self.classifier = ArchetypeClassifier()

    async def init(self):
        """AstrBot 调用的异步初始化方法"""
        await self.db_mgr.init_db()
        logger.info("LoveFormula DB initialized.")

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """处理群消息监听"""
        if not self._is_group_allowed(event.message_obj.group_id):
            return

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
        nickname = event.message_obj.sender.nickname

        # 0. 检查是否为指定分析（被 at 的人）
        targeted_user_id = None
        targeted_nickname = None

        for component in event.message_obj.message:
            if isinstance(component, At):
                targeted_user_id = str(component.qq)
                # 尝试获取 被 at 人的昵称，如果获取不到则使用默认
                targeted_nickname = (
                    getattr(component, "display", None) or f"用户{targeted_user_id}"
                )
                break

        if targeted_user_id:
            user_id = targeted_user_id
            nickname = targeted_nickname

        if not group_id:
            yield event.plain_result("请在群聊中使用此指令。")
            return

        # 1. 获取数据回溯
        if not self._is_group_allowed(group_id):
            yield event.plain_result("此群未启用恋爱分析功能。")
            return

        # 尝试获取昨日得分作为白月光值
        from datetime import date, timedelta

        yesterday = date.today() - timedelta(days=1)
        yesterday_data = await self.repo.get_data_by_date(group_id, user_id, yesterday)
        yesterday_score = 0
        if yesterday_data:
            y_scores = self.calculator.calculate_scores(yesterday_data)
            yesterday_score = y_scores.get("score", 0)
            logger.debug(f"Yesterday score for {user_id}: {yesterday_score}")

        daily_data = await self.repo.get_today_data(group_id, user_id)

        # 检查配置中的阈值
        min_msg = self.config.get("min_msg_threshold", 3)
        if not daily_data or daily_data.msg_sent < min_msg:
            prefix = (
                "你" if user_id == event.message_obj.sender.user_id else f"{nickname}"
            )
            yield event.plain_result(
                f"{prefix}今天太沉默了（发言少于{min_msg}条），甚至无法测算出恋爱成分。"
            )
            return

        # 2. 计算分数
        scores = self.calculator.calculate_scores(
            daily_data, yesterday_score=yesterday_score
        )

        # 3. 归类人设

        archetype_key, archetype_name = ArchetypeClassifier.classify(scores)

        # 4. LLM 分析 (获取判词和诊断) - Data Driven
        llm_result = {"comment": "获取失败", "diagnostics": []}
        deep_dive_result = None

        raw_data_dict = daily_data.model_dump()

        if self.config.get("enable_llm_commentary", True):
            # 获取对应的 Provider ID
            global_provider = self.config.get("llm_provider_id", "")
            commentary_provider = (
                self.config.get("commentary_provider_id", "") or global_provider
            )
            deep_dive_provider = (
                self.config.get("deep_dive_provider_id", "") or global_provider
            )

            # 4.1 Basic Commentary (No Context)
            llm_result = await self.llm.generate_commentary(
                scores, archetype_name, raw_data_dict, provider_id=commentary_provider
            )

            # 4.2 Deep Dive (Context Driven)
            if self.config.get("enable_history_analysis", True):
                try:
                    chat_context = await self.history_fetcher.fetch_context(
                        event, user_id
                    )
                    if chat_context:
                        deep_dive_result = await self.llm.generate_deep_dive(
                            scores,
                            archetype_name,
                            raw_data_dict,
                            chat_context,
                            provider_id=deep_dive_provider,
                        )
                except Exception as e:
                    logger.warning(f"Failed to fetch/analyze chat history: {e}")
            else:
                logger.debug("History analysis disabled by config.")
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
        user_name = nickname if nickname else f"用户{user_id}"
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        from datetime import datetime

        render_data = {
            "user_name": user_name,
            "user_id": user_id,
            "avatar_url": avatar_url,
            "title": archetype_name,
            "score": scores.get("score", 0),
            "metrics": {
                "纯爱值": f"{scores['simp']}%",
                "存在感": f"{scores['vibe']}%",
                "败犬值": f"{scores['ick']}%",
                "白月光指数": f"{scores['nostalgia']}%",
                "营业频率": f"{raw_data_dict.get('msg_sent', 0)}条/日",
                "小作文功率": f"{int(raw_data_dict.get('text_len_total', 0) / raw_data_dict.get('msg_sent', 1)) if raw_data_dict.get('msg_sent', 0) > 0 else 0}字/条",
            },
            "logic_insights": logic_insights,
            "comment": llm_result.get("comment", "获取失败"),
            "equation": self._construct_latex_equation(scores, raw_data_dict),
            "deep_dive": deep_dive_result,
            "generated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        logger.debug(f"Render Data: {render_data}")

        # 7. 渲染图片
        theme = self.config.get("theme", "galgame")
        try:
            image_path = await self.renderer.render(render_data, theme_name=theme)
            logger.info(f"图片渲染成功: {image_path}")

            try:
                # 1. 优先尝试本地路径直接发送 (性能更好，减少内存占用)
                yield event.chain_result([Image.fromFileSystem(image_path)])
            except Exception as path_err:
                logger.warning(f"路径发送失败，尝试 Base64 回退: {path_err}")
                # 2. 回退到 Base64 方式 (规避部分平台富媒体传输失败问题)
                import base64

                with open(image_path, "rb") as f:
                    b64_str = base64.b64encode(f.read()).decode()

                yield event.chain_result([Image.fromBase64(b64_str)])
        except Exception as e:
            logger.error(f"Render failed: {e}", exc_info=True)
            yield event.plain_result(f"生成失败: {e}")

    def _construct_latex_equation(self, scores: dict, raw_data: dict) -> str:
        """根据公式生成 LaTeX 字符串"""
        # J_{love} = \int_{today} e^{-rt} \cdot [Vibe + \beta Nostalgia - \lambda Ick - c \cdot Simp] \, dt
        return (
            r"J_{love} = \int_{today} e^{-rt} \cdot [Vibe + \beta Nostalgia - \lambda Ick - c \cdot Simp] \, dt \Rightarrow "
            + f"{scores['score']}\\%"
        )

    def _generate_diagnostic_insights(
        self, scores: dict, raw_data: dict, archetype_key: str
    ) -> list:
        """生成叙事性的行为诊断报告"""
        insights = []

        # 1. 纯爱值诊断 (S)
        msg_sent = raw_data.get("msg_sent", 0)
        poke_sent = raw_data.get("poke_sent", 0)
        if scores["simp"] > 60:
            insights.append(
                f"【纯爱处刑】本席在群聊底层逻辑中发现了该成员疯狂倾倒的 {msg_sent} 条情感垃圾，甚至还厚着脸皮‘戳了戳’他人 {poke_sent} 次。这种自我感动式的卑微热情，是纯度 100% 的败犬预备役。"
            )
        else:
            insights.append(
                "【投入判定】该成员今日的表现尚算理智，没在群里表现出那种令人掩面的‘舔狗’狂热，社交尊严保持得非常得体。"
            )

        # 2. 存在感诊断 (V)
        reply_recv = raw_data.get("reply_received", 0)
        reaction_recv = raw_data.get("reaction_received", 0)
        if scores["vibe"] > 60:
            insights.append(
                f"【公敌警告】被告今日的存在感已然失控。引发了 {reply_recv} 次回复和 {reaction_recv} 次表情回应，这股‘现充’的统治力已经严重干扰了本庭的秩序。"
            )
        elif scores["vibe"] < 20:
            insights.append(
                f"【空气系处分】本席几乎无法在数据流中捕捉该受众的波长。仅仅被回复了 {reply_recv} 次，这种透明度堪比 Galgame 里的背景板，建议通过梗图或‘白月光’式发言换取一点施舍。"
            )
        else:
            insights.append(
                "【社交观测】其发言虽然平稳，但缺乏致命的吸引力。群友们对其回应保持在一个‘礼貌但不热烈’的安全距离。"
            )

        # 3. 败犬与白月光诊断 (I / N)
        recall = raw_data.get("recall_count", 0)
        repeat = raw_data.get("repeat_count", 0)
        topic = raw_data.get("topic_count", 0)
        if recall > 0 or repeat > 0:
            msg = f"【败犬修正】本席捕捉到该成员在社交战场上的拙劣逃避——撤回了 {recall} 条信息"
            if repeat > 0:
                msg += f"并伴随 {repeat} 次复读机式的刷屏自毁"
            msg += "。每一步都在无情推高其败犬值，那是属于失败者的滑稽谢幕。"
            insights.append(msg)

        if topic > 0:
            insights.append(
                f"【角色复辟】对方在今日开启了 {topic} 次全新话题，通过‘破冰’行为强行夺回了焦点。这种‘白月光’般的领导力，正在修复其逐渐透明的身影。"
            )

        # 4. 人设由来
        insights.append(
            f"【最终判词】综上所述，{self._get_archetype_reason(archetype_key, scores)}"
        )

        return insights

    def _get_archetype_reason(self, key: str, scores: dict) -> str:
        """根据 Key 返回判定理由"""
        reasons = {
            "THE_SIMP": f"由于你的投入({scores['simp']}%)远高于群友对你的反馈({scores['vibe']}%)，本庭认定你是那种只会一厢情愿透支热情的‘纯爱劳模’。",
            "THE_PLAYER": f"因为你只需较低的投入就能换取极高的群友反馈({scores['vibe']}%)，你是典型的社交霸凌者，也就是所谓的‘现充现行犯’。",
            "HIMBO": f"虽然你的存在感({scores['vibe']}%)很高，但撤回或刷屏带来的败犬臭味({scores['ick']}%)让你的光芒显得滑稽而苍白。",
            "IDOL": f"你几乎不主动营业({scores['simp']}%)却依然保有极高的关注度，这种高冷且傲慢的姿态，确实符合‘群内偶像’的恶劣本质。",
            "NPC": "你各项维度均已归零，系统判定你只是本群的一块‘空气背景板’，毫无审判交互的必要。",
            "NORMAL": "各项指标分布极其平庸，没有能够引起本庭注意的闪光点或污点，老老实实做个普通路人吧。",
        }
        return reasons.get(key, "数据分布符合该人设的特征判定区间。")

    def _is_group_allowed(self, group_id: int | str | None) -> bool:
        """检查群组是否在黑白名单允许范围内"""
        if not group_id:
            return True  # 私聊通常不限制，或者由其他逻辑处理

        mode = self.config.get("group_list_mode", "none")
        if mode == "none":
            return True

        group_list = self.config.get("group_list", [])
        group_id_str = str(group_id)

        if mode == "whitelist":
            return group_id_str in group_list
        if mode == "blacklist":
            return group_id_str not in group_list

        return True
