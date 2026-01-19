import time
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.tables import LoveDailyRef, MessageOwnerIndex, UserCooldown
from .database import DBManager


class LoveRepo:
    """数据仓库，封装所有的数据库交互逻辑"""

    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    async def get_or_create_daily_ref(
        self, session: AsyncSession, group_id: str, user_id: str
    ) -> LoveDailyRef:
        """获取或创建今日的数据记录"""
        today = date.today()
        stmt = select(LoveDailyRef).where(
            LoveDailyRef.date == today,
            LoveDailyRef.group_id == group_id,
            LoveDailyRef.user_id == user_id,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            record = LoveDailyRef(
                date=today, group_id=group_id, user_id=user_id, updated_at=time.time()
            )
            session.add(record)
            # Flush 以确保如果需要立即获取 ID，但在 commit 时也会处理
            await session.flush()

        return record

    async def update_msg_stats(
        self, group_id: str, user_id: str, text_len: int, image_count: int = 0
    ):
        """更新消息统计数据 (发送数、字数、图片数)"""
        async with self.db.get_session() as session:
            record = await self.get_or_create_daily_ref(session, group_id, user_id)
            record.msg_sent += 1
            record.text_len_total += text_len
            record.image_sent += image_count
            record.updated_at = time.time()
            session.add(record)

    async def save_message_index(self, message_id: str, group_id: str, user_id: str):
        """保存消息 ID 与发送者的映射，用于后续的异步交互归因 (如 Reaction)"""
        async with self.db.get_session() as session:
            idx = MessageOwnerIndex(
                message_id=message_id,
                group_id=group_id,
                user_id=user_id,
                timestamp=time.time(),
            )
            session.add(idx)

    async def get_message_owner(self, message_id: str) -> MessageOwnerIndex | None:
        async with self.db.get_session() as session:
            stmt = select(MessageOwnerIndex).where(
                MessageOwnerIndex.message_id == message_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_interaction_sent(
        self,
        group_id: str,
        user_id: str,
        poke: int = 0,
        reply: int = 0,
        reaction: int = 0,
        recall: int = 0,
    ):
        """更新主动交互计数"""
        async with self.db.get_session() as session:
            record = await self.get_or_create_daily_ref(session, group_id, user_id)
            record.poke_sent += poke
            record.reply_sent += reply
            record.reaction_sent += reaction
            record.recall_count += recall
            record.updated_at = time.time()
            session.add(record)

    async def update_interaction_received(
        self,
        group_id: str,
        user_id: str,
        poke: int = 0,
        reply: int = 0,
        reaction: int = 0,
    ):
        async with self.db.get_session() as session:
            record = await self.get_or_create_daily_ref(session, group_id, user_id)
            record.poke_received += poke
            record.reply_received += reply
            record.reaction_received += reaction
            record.updated_at = time.time()
            session.add(record)

    async def update_behavior_stats(
        self, group_id: str, user_id: str, topic_inc: int = 0, repeat_inc: int = 0
    ):
        """更新高级行为指标 (话题、复读)"""
        async with self.db.get_session() as session:
            record = await self.get_or_create_daily_ref(session, group_id, user_id)
            record.topic_count += topic_inc
            record.repeat_count += repeat_inc
            record.updated_at = time.time()
            session.add(record)

    async def get_today_data(self, group_id: str, user_id: str) -> LoveDailyRef | None:
        return await self.get_data_by_date(group_id, user_id, date.today())

    async def get_data_by_date(
        self, group_id: str, user_id: str, target_date: date
    ) -> LoveDailyRef | None:
        """获取指定日期的数据"""
        async with self.db.get_session() as session:
            stmt = select(LoveDailyRef).where(
                LoveDailyRef.date == target_date,
                LoveDailyRef.group_id == group_id,
                LoveDailyRef.user_id == user_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def apply_honor_bonus(self, group_id: str, honor_data: dict) -> int:
        """根据群荣誉信息发放初始点数，返回同步的荣誉数量"""
        if not honor_data:
            return 0

        honor_count = 0
        async with self.db.get_session() as session:
            # 1. 龙王 (Talkative) - 活跃度与存在感双高
            talkative = honor_data.get("talkative", {})
            if talkative:
                uid = str(talkative.get("user_id"))
                if uid:
                    ref = await self.get_or_create_daily_ref(session, group_id, uid)
                    ref.msg_sent += 20  # 虚拟发言数，提升分值
                    ref.reply_received += 5
                    ref.updated_at = time.time()
                    honor_count += 1

            # 2. 表演者 (Performer) - 存在感高
            performers = honor_data.get("performer", [])
            for p in performers:
                uid = str(p.get("user_id"))
                if uid:
                    ref = await self.get_or_create_daily_ref(session, group_id, uid)
                    ref.reply_received += 10
                    ref.updated_at = time.time()
                    honor_count += 1

            # 3. 快乐源泉 (Emotion) - 白月光值高
            emotions = honor_data.get("emotion", [])
            for e in emotions:
                uid = str(e.get("user_id"))
                if uid:
                    ref = await self.get_or_create_daily_ref(session, group_id, uid)
                    ref.image_sent += 5
                    ref.topic_count += 2
                    ref.updated_at = time.time()
                    honor_count += 1
        return honor_count

    async def check_and_update_cooldown(self, user_id: str, cooldown_sec: int) -> int:
        """检查并更新冷却时间。返回 0 表示通过并已更新；返回正数表示剩余秒数"""
        now = time.time()
        async with self.db.get_session() as session:
            stmt = select(UserCooldown).where(UserCooldown.user_id == user_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                if now - record.last_rate_at < cooldown_sec:
                    return int(cooldown_sec - (now - record.last_rate_at))
                record.last_rate_at = now
            else:
                record = UserCooldown(user_id=user_id, last_rate_at=now)

            session.add(record)
            return 0
