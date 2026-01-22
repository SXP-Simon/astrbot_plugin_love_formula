from astrbot.api.event import AstrMessageEvent

from ..analysis.collectors.ick_collector import IckCollector
from ..analysis.collectors.nostalgia_collector import NostalgiaCollector
from ..analysis.collectors.simp_collector import SimpCollector
from ..analysis.collectors.vibe_collector import VibeCollector
from ..models.tables import MessageOwnerIndex
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
        """从历史记录中回填今日数据（批量写入）"""
        from datetime import date, datetime

        today = date.today()
        sorted_messages = sorted(messages, key=lambda x: x.get("time", 0))

        # 提前收集 message_id，并批量查询已存在的 message
        all_msg_ids = [
            str(m.get("message_id"))
            for m in sorted_messages
            if m.get("message_id")
        ]
        existed_msg_ids = await self.repo.filter_existing_message_ids(all_msg_ids)

        group_last_time = 0
        user_history_text: dict[str, str] = {}

        # ===== 批量缓冲区 =====
        msg_indexes: list[MessageOwnerIndex] = []

        msg_stats: dict[str, dict] = {}
        behavior_stats: dict[str, dict] = {}
        interaction_sent: dict[str, dict] = {}
        interaction_received: dict[str, dict] = {}

        stats = {
            "msg_count": 0,
            "image_count": 0,
            "topic_count": 0,
            "repeat_count": 0,
            "reply_count": 0,
            "at_count": 0,
        }

        # 输入消息列表自身去重（防止历史数据本身重复）
        seen_msg_ids: set[str] = set()

        for msg in sorted_messages:
            msg_time = msg.get("time", 0)
            if datetime.fromtimestamp(msg_time).date() != today:
                continue

            msg_id = str(msg.get("message_id", ""))
            if not msg_id:
                continue

            # message_id 去重
            if msg_id in seen_msg_ids:
                continue
            seen_msg_ids.add(msg_id)

            # 使用批量查询结果判断是否已存在
            if msg_id in existed_msg_ids:
                group_last_time = msg_time
                continue

            user_id = str(msg.get("sender", {}).get("user_id", ""))
            if not user_id:
                continue

            raw_message = msg.get("message", "")
            text_content = ""
            image_count = 0
            reply_target_msg_id = None
            at_targets = []

            if isinstance(raw_message, str):
                text_content = raw_message
            elif isinstance(raw_message, list):
                for seg in raw_message:
                    t = seg.get("type")
                    d = seg.get("data", {})
                    if t == "text":
                        text_content += d.get("text", "")
                    elif t == "image":
                        image_count += 1
                    elif t == "reply":
                        reply_target_msg_id = str(d.get("id"))
                    elif t == "at":
                        if d.get("qq"):
                            at_targets.append(str(d["qq"]))

            # ===== 话题 / 复读 =====
            topic_inc = (
                1
                if group_last_time == 0
                   or (msg_time - group_last_time > self.nos_col.TOPIC_THRESHOLD)
                else 0
            )

            repeat_inc = (
                1
                if (text_content and user_history_text.get(user_id) == text_content)
                else 0
            )

            user_history_text[user_id] = text_content

            # ===== 累加基础统计 =====
            msg_stats.setdefault(user_id, {"msg": 0, "text": 0, "image": 0})
            msg_stats[user_id]["msg"] += 1
            msg_stats[user_id]["text"] += len(text_content)
            msg_stats[user_id]["image"] += image_count

            if topic_inc or repeat_inc:
                behavior_stats.setdefault(user_id, {"topic": 0, "repeat": 0})
                behavior_stats[user_id]["topic"] += topic_inc
                behavior_stats[user_id]["repeat"] += repeat_inc

            # ===== 消息索引 =====
            msg_indexes.append(
                MessageOwnerIndex(
                    message_id=msg_id,
                    group_id=group_id,
                    user_id=user_id,
                    timestamp=msg_time,
                )
            )

            # ===== 回复 / @ 交互 =====
            if reply_target_msg_id:
                owner = await self.repo.get_message_owner(reply_target_msg_id)
                if owner and owner.user_id != user_id:
                    interaction_sent.setdefault(user_id, {"reply": 0})
                    interaction_received.setdefault(owner.user_id, {"reply": 0})
                    interaction_sent[user_id]["reply"] += 1
                    interaction_received[owner.user_id]["reply"] += 1
                    stats["reply_count"] += 1

            for at_uid in at_targets:
                if at_uid != user_id:
                    interaction_received.setdefault(at_uid, {"reply": 0})
                    stats["at_count"] += 1

            stats["msg_count"] += 1
            stats["image_count"] += image_count
            stats["topic_count"] += topic_inc
            stats["repeat_count"] += repeat_inc
            group_last_time = msg_time

        # ===== 一次性写库 =====
        await self.repo.batch_backfill(
            group_id=group_id,
            msg_indexes=msg_indexes,
            msg_stats=msg_stats,
            behavior_stats=behavior_stats,
            interaction_sent=interaction_sent,
            interaction_received=interaction_received,
        )

        return stats
