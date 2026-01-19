import time
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.tables import LoveDailyRef, MessageOwnerIndex
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
        async with self.db.get_session() as session:
            today = date.today()
            stmt = select(LoveDailyRef).where(
                LoveDailyRef.date == today,
                LoveDailyRef.group_id == group_id,
                LoveDailyRef.user_id == user_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
