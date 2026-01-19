from astrbot.api.event import AstrMessageEvent

from ..analysis.collectors.ick_collector import IckCollector
from ..analysis.collectors.nostalgia_collector import NostalgiaCollector
from ..analysis.collectors.simp_collector import SimpCollector
from ..analysis.collectors.vibe_collector import VibeCollector
from ..persistence.repo import LoveRepo


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
        group_id = str(event.message_obj.group_id)
        user_id = str(event.message_obj.sender.user_id)
        msg_id = str(event.message_obj.message_id)

        # 0. 去重检查 (防止重复处理同一条消息导致虚假复读)
        if await self.repo.get_message_owner(msg_id):
            return

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

    async def backfill_from_history(self, group_id: str, messages: list[dict]):
        """从历史记录中回填今日数据，仅处理基础指标与话题"""
        from datetime import date

        today = date.today()

        # 按照时间从小到大排序
        sorted_messages = sorted(messages, key=lambda x: x.get("time", 0))

        # 记录每位用户的统计
        group_last_time = 0
        user_history_text = {}  # {user_id: last_text} 用于回填中的复读判定
        stats = {
            "msg_count": 0,
            "image_count": 0,
            "topic_count": 0,
            "repeat_count": 0,
            "reply_count": 0,
            "at_count": 0,
        }

        for msg in sorted_messages:
            msg_time = msg.get("time", 0)
            # 仅处理今天的消息
            import datetime

            dt = datetime.datetime.fromtimestamp(msg_time)
            if dt.date() != today:
                continue

            msg_id = str(msg.get("message_id", ""))
            if not msg_id:
                continue

            # 检查是否已处理过
            if await self.repo.get_message_owner(msg_id):
                # 如果已存在，更新上下文时间但跳过统计
                group_last_time = msg_time
                continue

            user_id = str(msg.get("sender", {}).get("user_id", ""))
            if not user_id:
                continue

            # 1. 提取内容与交互信息
            raw_message = msg.get("message", "")
            text_content = ""
            current_images = 0
            reply_target_msg_id = None
            at_targets = []

            if isinstance(raw_message, str):
                text_content = raw_message
            elif isinstance(raw_message, list):
                for seg in raw_message:
                    s_type = seg.get("type", "")
                    s_data = seg.get("data", {})
                    if s_type == "text":
                        text_content += s_data.get("text", "")
                    elif s_type == "image":
                        current_images += 1
                    elif s_type == "reply":
                        reply_target_msg_id = str(s_data.get("id"))
                    elif s_type == "at":
                        at_qq = s_data.get("qq")
                        if at_qq:
                            at_targets.append(str(at_qq))

            # 2. 判定话题与复读 (Nos & Ick)
            topic_inc = 0
            if (
                group_last_time > 0
                and (msg_time - group_last_time) > self.nos_col.TOPIC_THRESHOLD
            ):
                topic_inc = 1
            elif group_last_time == 0:
                topic_inc = 1

            last_text = user_history_text.get(user_id, "")
            repeat_inc = 1 if text_content and text_content == last_text else 0
            user_history_text[user_id] = text_content

            # 3. 持久化与交互处理
            await self.repo.save_message_index(msg_id, group_id, user_id)
            await self.repo.update_msg_stats(
                group_id=group_id,
                user_id=user_id,
                text_len=len(text_content),
                image_count=current_images,
            )

            if topic_inc > 0 or repeat_inc > 0:
                await self.repo.update_behavior_stats(
                    group_id, user_id, topic_inc=topic_inc, repeat_inc=repeat_inc
                )
                stats["topic_count"] += topic_inc
                stats["repeat_count"] += repeat_inc

            # 历史交互归因
            if reply_target_msg_id:
                owner = await self.repo.get_message_owner(reply_target_msg_id)
                if owner and owner.user_id != user_id:
                    await self.repo.update_interaction_sent(group_id, user_id, reply=1)
                    await self.repo.update_interaction_received(
                        group_id, owner.user_id, reply=1
                    )
                    stats["reply_count"] += 1

            for at_target in at_targets:
                if at_target != user_id:
                    # 将 @ 提及回填为基础互动点数 (Vibe)
                    await self.repo.update_interaction_received(
                        group_id, at_target, reply=0
                    )
                    stats["at_count"] += 1

            # 更新统计
            stats["msg_count"] += 1
            stats["image_count"] += current_images
            group_last_time = msg_time

        # 更新类静态上下文（防止回填后立即说话判定错误）
        if group_last_time > 0:
            MessageHandler._group_last_msg_time[group_id] = group_last_time

        # 同步各用户的最后文本到内存缓存，用于接下来的实时判定
        if group_id not in MessageHandler._user_last_msg_text:
            MessageHandler._user_last_msg_text[group_id] = {}

        for uid, last_txt in user_history_text.items():
            MessageHandler._user_last_msg_text[group_id][uid] = last_txt

        return stats
