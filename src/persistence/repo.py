import time
from datetime import date
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import CursorResult
from sqlalchemy import and_

from ..models.tables import LoveDailyRef, MessageOwnerIndex, UserCooldown
from .database import DBManager

class LoveRepo:
    """数据仓库，封装所有的数据库交互逻辑"""

    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    async def get_or_create_daily_ref(
        self,
        session: AsyncSession,
        group_id: str,
        user_id: str
    ) -> LoveDailyRef:
        """并发安全的 get_or_create"""
        today = date.today()

        stmt = select(LoveDailyRef).where(and_(
            LoveDailyRef.date == today,
            LoveDailyRef.group_id == group_id,
            LoveDailyRef.user_id == user_id,
        ))

        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            return record

        record = LoveDailyRef(
            date=today,
            group_id=group_id,
            user_id=user_id,
            updated_at=time.time(),
        )
        session.add(record)

        try:
            await session.flush()
            return record
        except IntegrityError:
            # 并发下被其他事务插入，重新读取
            result = await session.execute(stmt)
            return result.scalar_one()

    async def update_msg_stats(
        self,
        group_id: str,
        user_id: str,
        text_len: int,
        image_count: int = 0,
    ) -> None:
        """更新消息统计（原子 UPDATE，极高频）"""
        async with self.db.get_session() as session:
            stmt = (
                update(LoveDailyRef)
                .where(and_(
                    LoveDailyRef.date == date.today(),
                    LoveDailyRef.group_id == group_id,
                    LoveDailyRef.user_id == user_id,
                ))
                .values(
                    msg_sent=LoveDailyRef.msg_sent + 1,
                    text_len_total=LoveDailyRef.text_len_total + text_len,
                    image_sent=LoveDailyRef.image_sent + image_count,
                    updated_at=time.time(),
                )
            )
            result: CursorResult = await session.execute(stmt)
            if result.rowcount == 0:
                await self.get_or_create_daily_ref(session, group_id, user_id)
                await session.execute(stmt)

    async def update_interaction_sent(
        self,
        group_id: str,
        user_id: str,
        poke: int = 0,
        reply: int = 0,
        reaction: int = 0,
        recall: int = 0,
    ) -> None:
        async with self.db.get_session() as session:
            stmt = (
                update(LoveDailyRef)
                .where(and_(
                    LoveDailyRef.date == date.today(),
                    LoveDailyRef.group_id == group_id,
                    LoveDailyRef.user_id == user_id,
                ))
                .values(
                    poke_sent=LoveDailyRef.poke_sent + poke,
                    reply_sent=LoveDailyRef.reply_sent + reply,
                    reaction_sent=LoveDailyRef.reaction_sent + reaction,
                    recall_count=LoveDailyRef.recall_count + recall,
                    updated_at=time.time(),
                )
            )

            result: CursorResult = await session.execute(stmt)
            if result.rowcount == 0:
                await self.get_or_create_daily_ref(session, group_id, user_id)
                await session.execute(stmt)

    async def update_interaction_received(
        self,
        group_id: str,
        user_id: str,
        poke: int = 0,
        reply: int = 0,
        reaction: int = 0,
    ) -> None:
        async with self.db.get_session() as session:
            stmt = (
                update(LoveDailyRef)
                .where(and_(
                    LoveDailyRef.date == date.today(),
                    LoveDailyRef.group_id == group_id,
                    LoveDailyRef.user_id == user_id,
                ))
                .values(
                    poke_received=LoveDailyRef.poke_received + poke,
                    reply_received=LoveDailyRef.reply_received + reply,
                    reaction_received=LoveDailyRef.reaction_received + reaction,
                    updated_at=time.time(),
                )
            )

            result: CursorResult = await session.execute(stmt)
            if result.rowcount == 0:
                await self.get_or_create_daily_ref(session, group_id, user_id)
                await session.execute(stmt)

    async def update_behavior_stats(
        self,
        group_id: str,
        user_id: str,
        topic_inc: int = 0,
        repeat_inc: int = 0,
    ) -> None:
        async with self.db.get_session() as session:
            stmt = (
                update(LoveDailyRef)
                .where(and_(
                    LoveDailyRef.date == date.today(),
                    LoveDailyRef.group_id == group_id,
                    LoveDailyRef.user_id == user_id,
                ))
                .values(
                    topic_count=LoveDailyRef.topic_count + topic_inc,
                    repeat_count=LoveDailyRef.repeat_count + repeat_inc,
                    updated_at=time.time(),
                )
            )

            result = await session.execute(stmt)
            if result.rowcount == 0:
                await self.get_or_create_daily_ref(session, group_id, user_id)
                await session.execute(stmt)

    async def save_message_index(
        self,
        message_id: str,
        group_id: str,
        user_id: str,
    ) -> None:
        async with self.db.get_session() as session:
            session.add(
                MessageOwnerIndex(
                    message_id=message_id,
                    group_id=group_id,
                    user_id=user_id,
                    timestamp=time.time(),
                )
            )

    async def get_message_owner(
        self,
        message_id: str,
    ) -> Optional[MessageOwnerIndex]:
        async with self.db.get_session() as session:
            stmt = select(MessageOwnerIndex).where(and_(
                MessageOwnerIndex.message_id == message_id
            ))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_today_data(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional[LoveDailyRef]:
        return await self.get_data_by_date(
            group_id,
            user_id,
            date.today(),
        )

    async def get_data_by_date(
        self,
        group_id: str,
        user_id: str,
        target_date: date,
    ) -> Optional[LoveDailyRef]:
        async with self.db.get_session() as session:
            stmt = select(LoveDailyRef).where(and_(
                LoveDailyRef.date == target_date,
                LoveDailyRef.group_id == group_id,
                LoveDailyRef.user_id == user_id,
            ))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def apply_honor_bonus(
        self,
        group_id: str,
        honor_data: dict,
    ) -> int:
        async with self.db.get_session() as session:
            if not honor_data:
                return 0

            honor_count = 0

            async def apply(uid: str, **inc):
                nonlocal honor_count
                ref = await self.get_or_create_daily_ref(session, group_id, uid)
                for k, v in inc.items():
                    setattr(ref, k, getattr(ref, k) + v)
                ref.updated_at = time.time()
                honor_count += 1

            if talkative := honor_data.get("talkative"):
                uid = str(talkative.get("user_id"))
                if uid:
                    await apply(uid, msg_sent=20, reply_received=5)

            for p in honor_data.get("performer", []):
                uid = str(p.get("user_id"))
                if uid:
                    await apply(uid, reply_received=10)

            for e in honor_data.get("emotion", []):
                uid = str(e.get("user_id"))
                if uid:
                    await apply(uid, image_sent=5, topic_count=2)

            return honor_count

    async def check_and_update_cooldown(
        self,
        user_id: str,
        cooldown_sec: int,
    ) -> int:
        async with self.db.get_session() as session:
            now = time.time()

            stmt = select(UserCooldown).where(and_(UserCooldown.user_id == user_id))
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                elapsed = now - record.last_rate_at
                if elapsed < cooldown_sec:
                    return int(cooldown_sec - elapsed)
                record.last_rate_at = now
            else:
                session.add(UserCooldown(user_id=user_id, last_rate_at=now))

            return 0

    async def batch_backfill(
            self,
            group_id: str,
            msg_indexes: list[MessageOwnerIndex],
            msg_stats: dict[str, dict],
            behavior_stats: dict[str, dict],
            interaction_sent: dict[str, dict],
            interaction_received: dict[str, dict],
    ) -> None:
        """历史回填批量写入（单事务）"""
        async with self.db.get_session() as session:
            today = date.today()
            now = time.time()

            session.add_all(msg_indexes)

            all_users = {
                *msg_stats.keys(),
                *behavior_stats.keys(),
                *interaction_sent.keys(),
                *interaction_received.keys(),
            }

            for uid in all_users:
                await self.get_or_create_daily_ref(session, group_id, uid)

            for uid, v in msg_stats.items():
                await session.execute(
                    update(LoveDailyRef)
                    .where(and_(
                        LoveDailyRef.date == today,
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == uid,
                    ))
                    .values(
                        msg_sent=LoveDailyRef.msg_sent + v["msg"],
                        text_len_total=LoveDailyRef.text_len_total + v["text"],
                        image_sent=LoveDailyRef.image_sent + v["image"],
                        updated_at=now,
                    )
                )

            for uid, v in behavior_stats.items():
                await session.execute(
                    update(LoveDailyRef)
                    .where(and_(
                        LoveDailyRef.date == today,
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == uid,
                    ))
                    .values(
                        topic_count=LoveDailyRef.topic_count + v["topic"],
                        repeat_count=LoveDailyRef.repeat_count + v["repeat"],
                        updated_at=now,
                    )
                )

            for uid, v in interaction_sent.items():
                await session.execute(
                    update(LoveDailyRef)
                    .where(and_(
                        LoveDailyRef.date == today,
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == uid,
                    ))
                    .values(
                        reply_sent=LoveDailyRef.reply_sent + v.get("reply", 0),
                        updated_at=now,
                    )
                )

            for uid, v in interaction_received.items():
                await session.execute(
                    update(LoveDailyRef)
                    .where(and_(
                        LoveDailyRef.date == today,
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == uid,
                    ))
                    .values(
                        reply_received=LoveDailyRef.reply_received + v.get("reply", 0),
                        updated_at=now,
                    )
                )
