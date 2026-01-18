from astrbot.core.log import LogManager
from ..persistence.repo import LoveRepo

logger = LogManager.GetLogger("astrbot_plugin_love_formula")


class NoticeHandler:
    """通知事件处理器，负责处理戳一戳、表情回应和撤回等通知"""

    def __init__(self, repo: LoveRepo):
        self.repo = repo

    async def handle_notice(self, event_data: dict):
        """
        处理来自 NapCat/OneBot V11 的原始通知事件
        """
        post_type = event_data.get("post_type")
        if post_type != "notice":
            return

        notice_type = event_data.get("notice_type")
        sub_type = event_data.get("sub_type")

        group_id = str(event_data.get("group_id", ""))
        user_id = str(event_data.get("user_id", ""))  # 操作者

        if not group_id:
            return

        # 1. 戳一戳 (Poke)
        if notice_type == "notify" and sub_type == "poke":
            target_id = str(event_data.get("target_id", ""))
            # 发送者戳了目标
            await self.repo.update_interaction_sent(group_id, user_id, poke=1)
            await self.repo.update_interaction_received(group_id, target_id, poke=1)

        # 2. 表情回应 (Reaction / Group Emoji Like)
        elif notice_type == "group_msg_emoji_like":
            message_id = str(event_data.get("message_id", ""))
            # 操作者对消息做出了回应

            # 查找该消息的发送者
            msg_idx = await self.repo.get_message_owner(message_id)
            if msg_idx:
                author_id = msg_idx.user_id
                # 操作者发送了回应 -> 作者收到了回应
                await self.repo.update_interaction_sent(group_id, user_id, reaction=1)
                await self.repo.update_interaction_received(
                    group_id, author_id, reaction=1
                )
            else:
                logger.debug(f"未知消息的表情回应: {message_id}")

        # 3. 消息撤回 (Recall)
        elif notice_type == "group_recall":
            # 操作者撤回了消息
            await self.repo.update_interaction_sent(group_id, user_id, recall=1)
