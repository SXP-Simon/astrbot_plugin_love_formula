from astrbot.api.event import AstrMessageEvent

from .base import BaseCollector


class IckCollector(BaseCollector):
    """
    败犬值领域采集器
    专门负责追踪：复读刷屏、撤回行为等负面指标。
    """

    def collect_from_message(self, event: AstrMessageEvent, last_text: str) -> dict:
        """从消息流中采集"""
        text = event.message_str
        is_repeat = text and text == last_text
        return {
            "is_repeat": is_repeat,
            "repeat_inc": 1 if is_repeat else 0,
            "text": text,
        }

    def collect_from_notice(self, event_data: dict) -> dict:
        """从通知流中采集"""
        notice_type = event_data.get("notice_type")
        is_recall = notice_type == "group_recall"
        return {"is_recall": is_recall, "message_id": event_data.get("message_id")}

    def collect(self, event) -> dict:
        # 兼容不同类型的事件采集
        if isinstance(event, AstrMessageEvent):
            return {"type": "message"}
        return {"type": "notice"}
