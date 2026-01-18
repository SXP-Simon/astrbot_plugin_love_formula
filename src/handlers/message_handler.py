from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Reply

from ..persistence.repo import LoveRepo


class MessageHandler:
    """消息处理器，负责监听和解析用户发送的聊天消息"""

    def __init__(self, repo: LoveRepo):
        self.repo = repo

    async def handle_message(self, event: AstrMessageEvent):
        """处理群消息事件"""

        logger.debug(
            f"[LoveFormula] handle_message 开始处理: {event.message_obj.message_id}"
        )

        # 仅处理群消息
        if not event.message_obj.group_id:
            logger.debug("非群消息，跳过。")
            return

        group_id = str(event.message_obj.group_id)
        user_id = str(event.message_obj.sender.user_id)
        message_id = str(event.message_obj.message_id)

        # 1. 保存消息索引 (用于 Reaction 归因)
        await self.repo.save_message_index(message_id, group_id, user_id)

        # 2. 内容分析
        text = event.message_str
        text_len = len(text)

        # 检查图片发送情况
        image_count = 0
        for component in event.message_obj.message:
            logger.debug(f"检查组件: {type(component)} -> {component}")
            if isinstance(component, dict) and component.get("type") == "image":
                image_count += 1
            elif hasattr(component, "type") and component.type == "image":  # 对象式访问
                image_count += 1

        # 检查回复 (引用) 情况
        reply_target_user_id = None
        for component in event.message_obj.message:
            # 检查 Reply 组件 (对象形式)
            if isinstance(component, Reply):
                logger.debug(
                    f"监听到回复组件 (对象): ID={getattr(component, 'id', '无')}, Sender={getattr(component, 'sender_id', '无')}"
                )
                # 优先获取 sender_id
                if (
                    hasattr(component, "sender_id")
                    and component.sender_id
                    and str(component.sender_id) != "0"
                ):
                    reply_target_user_id = str(component.sender_id)
                # 备选：根据 id (原消息 ID) 从索引查找发送者
                elif hasattr(component, "id") and component.id:
                    owner_idx = await self.repo.get_message_owner(str(component.id))
                    if owner_idx:
                        reply_target_user_id = owner_idx.user_id
                        logger.info(
                            f"通过索引查找成功: 原消息作者为 {reply_target_user_id}"
                        )
                break

            # 备选：兼容底层某些平台直接返回 Enum 字符串或 dict 的情况
            comp_type = ""
            if hasattr(component, "type"):
                comp_type = str(component.type).lower()
            elif isinstance(component, dict):
                comp_type = str(component.get("type", "")).lower()

            if "reply" in comp_type:
                logger.debug(f"监听到回复组件 (通用匹配): {component}")
                # ... 逻辑同上，但如果是 dict 需要特殊处理
                if isinstance(component, dict):
                    data = component.get("data", {})
                    sender_id = data.get("sender_id") or component.get("sender_id")
                    msg_id = data.get("id") or component.get("id")
                    if sender_id and str(sender_id) != "0":
                        reply_target_user_id = str(sender_id)
                    elif msg_id:
                        owner_idx = await self.repo.get_message_owner(str(msg_id))
                        if owner_idx:
                            reply_target_user_id = owner_idx.user_id
                else:
                    # 如果是对象但不是 Reply 子类 (虽然罕见)
                    if hasattr(component, "sender_id") and component.sender_id:
                        reply_target_user_id = str(component.sender_id)
                    elif hasattr(component, "id") and component.id:
                        owner_idx = await self.repo.get_message_owner(str(component.id))
                        if owner_idx:
                            reply_target_user_id = owner_idx.user_id
                break

        if reply_target_user_id:
            logger.debug(f"成功识别回复目标: {reply_target_user_id}")

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
