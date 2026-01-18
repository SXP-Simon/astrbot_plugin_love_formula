from astrbot.api.event import AstrMessageEvent
from ..persistence.repo import LoveRepo
from ..models.tables import LoveDailyRef


class MessageHandler:
    """消息处理器，负责监听和解析用户发送的聊天消息"""

    def __init__(self, repo: LoveRepo):
        self.repo = repo

    async def handle_message(self, event: AstrMessageEvent):
        """处理群消息事件"""
        # 仅处理群消息
        if not event.message_obj.group_id:
            return

        group_id = event.message_obj.group_id
        user_id = event.message_obj.sender.user_id
        message_id = event.message_obj.message_id

        # 1. 保存消息索引 (用于 Reaction 归因)
        await self.repo.save_message_index(message_id, group_id, user_id)

        # 2. 内容分析
        text = event.message_str
        text_len = len(text)

        # 检查图片发送情况
        image_count = 0
        for component in event.message_obj.message:
            if isinstance(component, dict) and component.get("type") == "image":
                image_count += 1
            elif hasattr(component, "type") and component.type == "image":  # 对象式访问
                image_count += 1

        # 检查回复 (引用) 情况
        reply_target_user_id = None
        for component in event.message_obj.message:
            # 检查 Reply 组件 (对象形式)
            if hasattr(component, "type") and str(component.type).lower() == "reply":
                # 找到 Reply 组件，获取原消息发送者 ID
                if hasattr(component, "sender_id"):
                    reply_target_user_id = str(component.sender_id)
                break
            # 检查 Reply 组件 (字典形式)
            if isinstance(component, dict) and component.get("type") == "reply":
                reply_target_user_id = str(component.get("sender_id", ""))
                break

        # 3. 更新每日统计
        await self.repo.update_msg_stats(
            group_id=group_id,
            user_id=user_id,
            text_len=text_len,
            image_count=image_count,
        )

        # 4. 更新回复统计
        if reply_target_user_id:
            # 发送者发送了回复
            await self.repo.update_interaction_sent(
                group_id=group_id,
                user_id=user_id,
                reply=1,
            )
            # 被回复者收到了回复 (且非自言自语)
            if reply_target_user_id != str(user_id):
                await self.repo.update_interaction_received(
                    group_id=group_id,
                    user_id=reply_target_user_id,
                    reply=1,
                )
