from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Reply

from .base import BaseDataProvider


class MessageProvider(BaseDataProvider):
    """
    消息数据提供者 (Message Data Provider)
    负责从 AstrMessageEvent 中提取文本长度、图片数量、回复目标等。
    """

    def extract_metrics(self, event: AstrMessageEvent) -> dict:
        text = event.message_str
        message_id = str(event.message_obj.message_id)

        # 1. 图片统计
        image_count = 0
        for component in event.message_obj.message:
            # 兼容 dict 和对象
            if isinstance(component, dict) and component.get("type") == "image":
                image_count += 1
            elif hasattr(component, "type") and component.type == "image":
                image_count += 1

        # 2. 回复归因
        reply_target_id = self._find_reply_target(event)

        return {
            "message_id": message_id,
            "text_len": len(text),
            "text_content": text,
            "image_count": image_count,
            "reply_target_id": reply_target_id,
        }

    def _find_reply_target(self, event: AstrMessageEvent) -> str | None:
        """解析回复目标的逻辑模块化"""
        for component in event.message_obj.message:
            # A. Reply 组件对象
            if isinstance(component, Reply):
                if (
                    hasattr(component, "sender_id")
                    and component.sender_id
                    and str(component.sender_id) != "0"
                ):
                    return str(component.sender_id)
                elif hasattr(component, "id") and component.id:
                    # 如果只有消息 ID，可能需要外部（Repo）协助查找作者，
                    # 但 Provider 这里只负责提取已知字段。
                    # 让 Handler 根据 message_id 自行去 Repo 查。
                    return f"MSG_REF:{component.id}"

            # B. 原始 dict 或其他结构兼容
            comp_type = ""
            if hasattr(component, "type"):
                comp_type = str(component.type).lower()
            elif isinstance(component, dict):
                comp_type = str(component.get("type", "")).lower()

            if "reply" in comp_type:
                if isinstance(component, dict):
                    data = component.get("data", {})
                    sender_id = data.get("sender_id") or component.get("sender_id")
                    msg_id = data.get("id") or component.get("id")
                    if sender_id and str(sender_id) != "0":
                        return str(sender_id)
                    elif msg_id:
                        return f"MSG_REF:{msg_id}"
        return None
