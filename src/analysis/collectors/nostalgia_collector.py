from astrbot.api.event import AstrMessageEvent

from .base import BaseCollector


class NostalgiaCollector(BaseCollector):
    """
    旧情/白月光领域采集器
    专门负责追踪：话题破冰、图片发送量等指标。
    """

    TOPIC_THRESHOLD = 900  # 15 分钟沉默视为新话题 (破冰)

    def collect(self, event: AstrMessageEvent, last_group_time: float) -> dict:
        """
        采集旧情指标。
        :param last_group_time: 本群最后一条消息的时间戳 (用于判定话题开启)
        """
        # 1. 采集图片发送
        image_count = 0
        for component in event.message_obj.message:
            if isinstance(component, dict) and component.get("type") == "image":
                image_count += 1
            elif hasattr(component, "type") and component.type == "image":
                image_count += 1

        # 2. 判定话题破冰 (Topic Initiation)
        current_time = __import__("time").time()
        is_topic = False
        if (
            last_group_time > 0
            and (current_time - last_group_time) > self.TOPIC_THRESHOLD
        ):
            is_topic = True

        return {
            "image_sent": image_count,
            "topic_inc": 1 if is_topic else 0,
            "current_time": current_time,
        }
