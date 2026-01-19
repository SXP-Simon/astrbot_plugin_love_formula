import time
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

from ..persistence.repo import LoveRepo
from ..analysis.collectors.simp_collector import SimpCollector
from ..analysis.collectors.vibe_collector import VibeCollector
from ..analysis.collectors.ick_collector import IckCollector
from ..analysis.collectors.nostalgia_collector import NostalgiaCollector


class MessageHandler:
    """消息处理器 (DDD)"""

    _group_last_msg_time = {}
    _user_last_msg_text = {}

    def __init__(self, repo: LoveRepo):
        self.repo = repo
        self.simp_col = SimpCollector()
        self.vibe_col = VibeCollector()
        self.ick_col = IckCollector()
        self.nos_col = NostalgiaCollector()

    async def handle_message(self, event: AstrMessageEvent):
        if not event.message_obj.group_id:
            return

        group_id = str(event.message_obj.group_id)
        user_id = str(event.message_obj.sender.user_id)

        # 1. 获取上下文状态
        last_group_time = MessageHandler._group_last_msg_time.get(group_id, 0)
        last_text = MessageHandler._user_last_msg_text.get(group_id, {}).get(
            user_id, ""
        )

        # 2. 领域数据采集 (判定逻辑已高度内聚于各自的 Collector)
        simp_m = self.simp_col.collect(event)
        vibe_m = self.vibe_col.collect(event)
        nos_m = self.nos_col.collect(event, last_group_time)
        ick_m = self.ick_col.collect_from_message(event, last_text)

        # 3. 结果状态回写
        MessageHandler._user_last_msg_text.setdefault(group_id, {})[user_id] = (
            event.message_str
        )
        MessageHandler._group_last_msg_time[group_id] = nos_m["current_time"]

        # 4. 业务逻辑编排与持有化
        await self.repo.save_message_index(simp_m["message_id"], group_id, user_id)

        # 更新判定指标 (Topic/Repeat)
        if nos_m["topic_inc"] > 0 or ick_m["repeat_inc"] > 0:
            await self.repo.update_behavior_stats(
                group_id, user_id, nos_m["topic_inc"], ick_m["repeat_inc"]
            )

        # 更新基础计分
        await self.repo.update_msg_stats(
            group_id=group_id,
            user_id=user_id,
            text_len=simp_m["text_len"],
            image_count=nos_m["image_sent"],
        )

        # 处理回复归因
        reply_target_id = vibe_m["reply_target_id"]
        if reply_target_id:
            final_target = reply_target_id
            if reply_target_id.startswith("MSG_REF:"):
                idx = await self.repo.get_message_owner(reply_target_id.split(":")[1])
                final_target = idx.user_id if idx else None

            if final_target:
                await self.repo.update_interaction_sent(group_id, user_id, reply=1)
                if final_target != user_id:
                    await self.repo.update_interaction_received(
                        group_id, final_target, reply=1
                    )
