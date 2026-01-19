from astrbot.api.event import AstrMessageEvent

from .base import BaseCollector


class SimpCollector(BaseCollector):
    """
    纯爱值领域采集器
    专门负责追踪：主动发言频率、戳一戳、小作文长度等指标。
    """

    def collect(self, event: AstrMessageEvent) -> dict:
        text = event.message_str
        return {
            "msg_sent": 1,
            "text_len": len(text),
            "message_id": str(event.message_obj.message_id),
        }

    def collect_notice(self, event_data: dict) -> dict:
        """采集主动交互（戳一戳）"""
        notice_type = event_data.get("notice_type")
        sub_type = event_data.get("sub_type")
        is_poke = notice_type == "notify" and sub_type == "poke"
        return {
            "poke_sent": 1 if is_poke else 0,
            "target_id": event_data.get("target_id"),
        }
