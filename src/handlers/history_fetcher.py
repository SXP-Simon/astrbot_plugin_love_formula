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
        # 1. 获取较大的消息池 (最大 300 条，或者历史配置的 5 倍)
        history_count = self.config.get("analyze_history_count", 50)
        pool_size = min(300, history_count * 5)
        raw_pool = await self.fetch_raw_group_history(event, count=pool_size)
        if not raw_pool:
            logger.warning("OneBotAdapter: 未能获取到任何历史消息池。")
            return []

        # 按照时间从旧到新排序
        raw_pool = sorted(raw_pool, key=lambda x: x.get("time", 0))

        # 2. 识别过滤名单与无效消息，预先构建“有效消息索引”
        black_list_ids = set()
        if hasattr(event, "self_id") and event.self_id:
            black_list_ids.add(str(event.self_id))
        bot_obj = getattr(event, "bot", None)
        if bot_obj:
            for attr in ["self_id", "qq", "user_id"]:
                val = getattr(bot_obj, attr, None)
                if val:
                    black_list_ids.add(str(val))
        black_list = set(self.filter_users) | black_list_ids

        # 预过滤：既要不在黑名单，也要有实际内容（文本/回复/@等）
        valid_indices = []
        target_str_id = str(target_user_id)
        for i, msg in enumerate(raw_pool):
            sender_id = str(msg.get("sender", {}).get("user_id", ""))

            # 黑名单过滤 (除非是目标用户自己，哪怕他是机器人也分析他)
            if sender_id in black_list and sender_id != target_str_id:
                continue

            # 内容过滤
            content = self._extract_text(msg.get("message", ""))
            if not content:
                continue

            valid_indices.append(i)

        # 3. 在有效消息中寻找“兴趣点” (Target 发言或被提及)
        interest_positions = []  # 在 valid_indices 列表中的索引
        for pos, original_idx in enumerate(valid_indices):
            msg = raw_pool[original_idx]
            sender_id = str(msg.get("sender", {}).get("user_id", ""))

            if sender_id == target_str_id:
                interest_positions.append(pos)
            else:
                interactions = self._extract_interactions(msg.get("message", []))
                if target_str_id in interactions.get("at_list", []):
                    interest_positions.append(pos)

        # 4. 提取窗口并合并 (基于有效消息的位置)
        window_size = self.config.get("context_window_size", 5)
        selected_valid_positions = set()

        for pos in interest_positions:
            start = max(0, pos - window_size)
            end = min(len(valid_indices), pos + window_size + 1)
            for j in range(start, end):
                selected_valid_positions.add(j)

        # 5. 兜底策略：补齐到 history_count
        if len(selected_valid_positions) < history_count:
            # 从有效消息末尾向前补
            for k in range(len(valid_indices) - 1, -1, -1):
                if len(selected_valid_positions) >= history_count:
                    break
                selected_valid_positions.add(k)

        # 6. 按时间顺序提取物理索引并格式化
        final_valid_positions = sorted(selected_valid_positions)

        # 结果可能仍超过 history_count (如果用户密集发言)，截断最近消息
        if len(final_valid_positions) > history_count:
            final_valid_positions = final_valid_positions[-history_count:]

        dialogue_context = []
        last_pos = -1

        for pos in final_valid_positions:
            original_idx = valid_indices[pos]

            # 检测逻辑索引（在有效消息流中的位置）上的跳变 (说明由于窗口限制跳过了部分有效对话)
            if last_pos != -1 and pos > last_pos + 1:
                dialogue_context.append(
                    {
                        "time": "...",
                        "role": "[System]",
                        "nickname": "System",
                        "content": "... (此处省略部分对话) ...",
                    }
                )

            msg = raw_pool[original_idx]
            sender = msg.get("sender", {})
            sender_id = str(sender.get("user_id", ""))
            nickname = sender.get("nickname", "Unknown")
            role = "[Target]" if sender_id == target_str_id else "[Other]"
            content = self._extract_text(msg.get("message", ""))

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
            last_pos = pos

        return dialogue_context

    async def fetch_raw_group_history(
        self, event: AstrMessageEvent, count: int = 100
    ) -> list[dict]:
        """
        获取原始群聊历史记录，不进行角色标记或过滤，用于数据回填。
        """
        if not event.message_obj.group_id:
            return []

        group_id = event.message_obj.group_id
        bot = getattr(event, "bot", None)
        params = {
            "group_id": int(group_id) if str(group_id).isdigit() else group_id,
            "count": count,
        }

        try:
            # 这里的策略与 fetch_context 类似，但更直接
            if bot and hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                resp = await bot.api.call_action("get_group_msg_history", **params)
                if resp:
                    return resp.get("messages", [])

            if bot and hasattr(bot, "call_api"):
                resp = await bot.call_api("get_group_msg_history", **params)
                if resp:
                    return resp.get("messages", [])
        except Exception as e:
            logger.warning(f"OneBotAdapter: 原始历史记录获取失败: {e}")

        return []

    async def fetch_group_honor(self, event: AstrMessageEvent) -> dict:
        """获取群荣誉信息 (龙王、群聊之星等)"""
        group_id = event.message_obj.group_id
        bot = getattr(event, "bot", None)
        if not bot:
            return {}

        params = {
            "group_id": int(group_id) if str(group_id).isdigit() else group_id,
            "type": "all",
        }
        try:
            if hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                resp = await bot.api.call_action("get_group_honor_info", **params)
                return resp if resp else {}
            if hasattr(bot, "call_api"):
                resp = await bot.call_api("get_group_honor_info", params)
                return resp if resp else {}
        except Exception as e:
            logger.warning(f"OneBotAdapter: 获取群荣誉失败: {e}")
        return {}

    async def fetch_group_member_list(self, event: AstrMessageEvent) -> list[dict]:
        """获取群成员列表数据"""
        group_id = event.message_obj.group_id
        bot = getattr(event, "bot", None)
        if not bot:
            return []

        params = {"group_id": int(group_id) if str(group_id).isdigit() else group_id}
        try:
            if hasattr(bot, "api") and hasattr(bot.api, "call_action"):
                resp = await bot.api.call_action("get_group_member_list", **params)
                return resp if resp else []
            if hasattr(bot, "call_api"):
                resp = await bot.call_api("get_group_member_list", params)
                return resp if resp else []
        except Exception as e:
            logger.warning(f"OneBotAdapter: 获取群成员列表失败: {e}")
        return []

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
                elif type_ == "reply":
                    # 识别回复段
                    text_parts.append("[回复]")

        return "".join(text_parts).strip()

    def _extract_interactions(self, message_chain) -> dict:
        """从消息链中提取交互信息 (回复、提及)"""
        interactions = {"reply_to": None, "at_list": []}
        if not isinstance(message_chain, list):
            return interactions

        for segment in message_chain:
            type_ = segment.get("type")
            data = segment.get("data", {})
            if type_ == "reply":
                interactions["reply_to"] = str(data.get("id"))  # 这是一个 message_id
            elif type_ == "at":
                at_qq = data.get("qq")
                if at_qq:
                    interactions["at_list"].append(str(at_qq))
        return interactions
