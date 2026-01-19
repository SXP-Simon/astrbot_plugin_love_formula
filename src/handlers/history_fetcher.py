import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.star.context import Context


class OneBotAdapter:
    """
    用于与 OneBot V11 API 交互以获取历史记录的适配器。
    """

    def __init__(self, context: Context, config: dict):
        self.context = context
        self.config = config
        self.history_count = config.get("analyze_history_count", 50)
        self.filter_users = [str(u) for u in config.get("filter_users", [])]

    async def fetch_context(
        self, event: AstrMessageEvent, target_user_id: str
    ) -> list[dict]:
        """
        获取最近的群聊消息并将其格式化为连续的对话上下文。

        Args:
            event: 当前消息事件（用于访问平台适配器）。
            target_user_id: 需要标记为 [Target] 的目标用户 ID。

        Returns:
            list[dict]: [{'time': str, 'role': str, 'nickname': str, 'content': str}, ...]
        """
        # 确保我们在群聊环境中
        if not event.message_obj.group_id:
            logger.warning("OneBotAdapter: 非群聊消息，无法获取历史记录。")
            return []

        group_id = event.message_obj.group_id

        # 尝试从事件或上下文中获取 OneBot 适配器
        # 注意：AstrBot 抽象了平台，但为了获取历史记录，我们可能 needing 原始 API 访问。
        # 此实现假设底层平台兼容 OneBot V11。

        raw_history = []
        try:
            # 尝试 1: Context.get_action (如果平台已实现)
            # 标准 OneBot V11 API: get_group_msg_history
            # 我们从事件中访问平台实例。
            platform = event.platform
            if not platform:
                logger.error("OneBotAdapter: 事件中未找到平台实例。")
                return []

            # 构建 get_group_msg_history 的参数
            # 部分实现使用 'get_group_msg_history'，其他使用 'get_history_msg'
            params = {
                "group_id": int(group_id) if str(group_id).isdigit() else group_id,
                "count": self.history_count,
            }

            logger.debug(f"正在获取群 {group_id} 的历史记录, 数量={self.history_count}")

            # 使用平台特定的调用方法。
            # 尝试从事件中访问 bot 对象。
            # 使用平台特定的调用方法。
            # 尝试从事件中访问 bot 对象。
            bot = getattr(event, "bot", None)

            resp = None
            success = False

            # Strategy 1: Direct Adapter Call (Unpacked) - Most likely correct for OneBot/CQHttp
            # This bypasses AstrBot's wrapper which might incorrectly pack kwargs into a dict
            if (
                not success
                and bot
                and hasattr(bot, "api")
                and hasattr(bot.api, "call_action")
            ):
                try:
                    resp = await bot.api.call_action("get_group_msg_history", **params)
                    success = True
                except Exception as e:
                    logger.warning(
                        f"OneBotAdapter: Strategy 1 (api.call_action) failed: {e}"
                    )

            # Strategy 2: AstrBot Universal Call (Unpacked)
            if not success and bot and hasattr(bot, "call_api"):
                try:
                    resp = await bot.call_api("get_group_msg_history", **params)
                    success = True
                except Exception as e:
                    logger.warning(
                        f"OneBotAdapter: Strategy 2 (bot.call_api unpacked) failed: {e}"
                    )

            # Strategy 3: AstrBot Universal Call (Packed Dictionary)
            if not success and bot and hasattr(bot, "call_api"):
                try:
                    resp = await bot.call_api("get_group_msg_history", params)
                    success = True
                except Exception as e:
                    logger.warning(
                        f"OneBotAdapter: Strategy 3 (bot.call_api packed) failed: {e}"
                    )

            if not resp and self.context:
                # Last resort: Try accessing bot via context global
                global_bot = self.context.get_bot()
                if global_bot and hasattr(global_bot, "call_api"):
                    try:
                        resp = await global_bot.call_api(
                            "get_group_msg_history", params
                        )
                    except Exception:
                        pass

            if not resp:
                logger.warning("OneBotAdapter: 获取历史记录失败或未找到 API。")
                return []

            messages = resp.get("messages", [])
            if not messages:
                logger.warning("OneBotAdapter: API 未返回任何消息。")
                return []

            raw_history = messages

        except Exception as e:
            logger.error(f"OneBotAdapter: 获取历史记录时出错: {e}")
            return []

        # 获取机器人自身的 ID，用于后续过滤
        # 使用 set 来存储可能的 ID，增加容错性
        black_list_ids = set()
        if hasattr(event, "self_id") and event.self_id:
            black_list_ids.add(str(event.self_id))

        bot = getattr(event, "bot", None)
        if bot:
            for attr in ["self_id", "qq", "user_id"]:
                val = getattr(bot, attr, None)
                if val:
                    black_list_ids.add(str(val))

        # 构建最终过滤名单
        black_list = set(self.filter_users) | black_list_ids
        logger.debug(
            f"[HistoryFetcher] Bot Self ID Detection: {black_list_ids}, Target: {target_user_id}"
        )

        # 处理并清理数据
        dialogue_context = []

        for msg in raw_history:
            sender = msg.get("sender", {})
            sender_id = str(sender.get("user_id", ""))
            nickname = sender.get("nickname", "Unknown")

            # 1. 过滤掉黑名单中的用户 (机器人 or 用户手动配置的过滤对象)
            if sender_id in black_list:
                continue

            # 2. 确定逻辑角色
            role = "[Target]" if sender_id == str(target_user_id) else "[Other]"

            # 获取内容 (简单的文本提取)
            # 消息可能是字典、字符串或片段列表
            content = self._extract_text(msg.get("message", ""))

            if not content:
                continue

            # 时间格式化
            ts = msg.get("time", time.time())
            time_str = time.strftime("%H:%M", time.localtime(ts))

            dialogue_context.append(
                {
                    "time": time_str,
                    "role": role,
                    "nickname": nickname,
                    "user_id": sender_id,
                    "content": content,
                }
            )

        return dialogue_context

    def _extract_text(self, message_chain) -> str:
        """从消息链中提取纯文本的辅助函数。"""
        text_parts = []

        if isinstance(message_chain, str):
            return message_chain

        if isinstance(message_chain, list):
            for segment in message_chain:
                type_ = segment.get("type")
                data = segment.get("data", {})

                if type_ == "text":
                    text_parts.append(data.get("text", ""))
                elif type_ == "face":
                    text_parts.append("[表情]")
                elif type_ == "image":
                    text_parts.append("[图片]")
                elif type_ == "at":
                    text_parts.append(f"@{data.get('qq', 'User')}")

        return "".join(text_parts).strip()
