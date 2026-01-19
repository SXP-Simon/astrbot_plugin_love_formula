from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Reply

from .base import BaseCollector


class VibeCollector(BaseCollector):
    """
    存在感领域采集器
    专门负责追踪：被回复、被贴贴、被戳一戳等受众反馈指标。
    """

    def collect(self, event: AstrMessageEvent) -> dict:
        """采集收到的互动"""
        reply_target_id = self._find_reply_target(event)
        return {"reply_target_id": reply_target_id}

    def collect_notice(self, event_data: dict) -> dict:
        """采集收到的通知互动 (贴贴, 戳戳)"""
        notice_type = event_data.get("notice_type")
        is_reaction = notice_type == "group_msg_emoji_like"

        return {
            "reaction_received": 1 if is_reaction else 0,
            "message_id": event_data.get("message_id"),
        }

    def _find_reply_target(self, event: AstrMessageEvent) -> str | None:
        """解析引用回复目标的逻辑"""
        for component in event.message_obj.message:
            if isinstance(component, Reply):
                if (
                    hasattr(component, "sender_id")
                    and component.sender_id
                    and str(component.sender_id) != "0"
                ):
                    return str(component.sender_id)
                elif hasattr(component, "id") and component.id:
                    return f"MSG_REF:{component.id}"

            # 兼容 dict
            if (
                isinstance(component, dict)
                and "reply" in str(component.get("type", "")).lower()
            ):
                data = component.get("data", {})
                sender_id = data.get("sender_id") or component.get("sender_id")
                msg_id = data.get("id") or component.get("id")
                if sender_id and str(sender_id) != "0":
                    return str(sender_id)
                elif msg_id:
                    return f"MSG_REF:{msg_id}"
        return None
