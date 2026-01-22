import time
from datetime import date
from typing import cast

from sqlalchemy import and_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..models.tables import LoveDailyRef, MessageOwnerIndex, UserCooldown
from .database import DBManager


class LoveRepo:
    """数据仓库，封装所有的数据库交互逻辑"""

    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    async def get_or_create_daily_ref(
        self, session: AsyncSession, group_id: str, user_id: str
    ) -> LoveDailyRef:
        """并发安全的 get_or_create"""
        today = date.today()

        stmt = select(LoveDailyRef).where(
            and_(
                LoveDailyRef.date == today,
                LoveDailyRef.group_id == group_id,
                LoveDailyRef.user_id == user_id,
            )
        )

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
                .where(
                    and_(
                        LoveDailyRef.date == date.today(),
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == user_id,
                    )
                )
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
                .where(
                    and_(
                        LoveDailyRef.date == date.today(),
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == user_id,
                    )
                )
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
                .where(
                    and_(
                        LoveDailyRef.date == date.today(),
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == user_id,
                    )
                )
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
                .where(
                    and_(
                        LoveDailyRef.date == date.today(),
                        LoveDailyRef.group_id == group_id,
                        LoveDailyRef.user_id == user_id,
                    )
                )
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
    ) -> MessageOwnerIndex | None:
        async with self.db.get_session() as session:
            stmt = select(MessageOwnerIndex).where(
                and_(MessageOwnerIndex.message_id == message_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_today_data(
        self,
        group_id: str,
        user_id: str,
    ) -> LoveDailyRef | None:
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
    ) -> LoveDailyRef | None:
        async with self.db.get_session() as session:
            stmt = select(LoveDailyRef).where(
                and_(
                    LoveDailyRef.date == target_date,
                    LoveDailyRef.group_id == group_id,
                    LoveDailyRef.user_id == user_id,
                )
            )
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
                    ref = await self.get_or_create_daily_ref(session, group_id, uid)
                    ref.image_sent += 5
                    ref.topic_count += 2
                    ref.updated_at = time.time()
                    honor_count += 1
        return honor_count

    async def check_and_update_cooldown(
        self, user_id: str, group_id: str, cooldown_sec: int
    ) -> int:
        """检查并更新冷却时间（按群组隔离）。返回 0 表示通过并已更新；返回正数表示剩余秒数"""
        now = time.time()
        async with self.db.get_session() as session:
            stmt = select(UserCooldown).where(
                UserCooldown.user_id == user_id,
                UserCooldown.group_id == group_id,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                elapsed = now - record.last_rate_at
                if elapsed < cooldown_sec:
                    return int(cooldown_sec - elapsed)
                record.last_rate_at = now
            else:
                session.add(
                    UserCooldown(user_id=user_id, group_id=group_id, last_rate_at=now)
                )

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

            if msg_indexes:
                # 检查输入数据是否包含重复的 message_id
                unique_msgs = []
                seen_ids = set()
                for msg in msg_indexes:
                    if msg.message_id not in seen_ids:
                        seen_ids.add(msg.message_id)
                        unique_msgs.append(msg)
                msg_indexes = unique_msgs

                # 过滤已存在的 message_id
                msg_ids = [m.message_id for m in msg_indexes]
                message_id_col = cast(ColumnElement[str], MessageOwnerIndex.message_id)
                stmt = select(MessageOwnerIndex.message_id).where(
                    message_id_col.in_(msg_ids)
                )
                result = await session.execute(stmt)
                existed_ids = {row[0] for row in result.all()}
                msg_indexes = [
                    m for m in msg_indexes if m.message_id not in existed_ids
                ]

            if msg_indexes:
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
                    .where(
                        and_(
                            LoveDailyRef.date == today,
                            LoveDailyRef.group_id == group_id,
                            LoveDailyRef.user_id == uid,
                        )
                    )
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
                    .where(
                        and_(
                            LoveDailyRef.date == today,
                            LoveDailyRef.group_id == group_id,
                            LoveDailyRef.user_id == uid,
                        )
                    )
                    .values(
                        topic_count=LoveDailyRef.topic_count + v["topic"],
                        repeat_count=LoveDailyRef.repeat_count + v["repeat"],
                        updated_at=now,
                    )
                )

            for uid, v in interaction_sent.items():
                await session.execute(
                    update(LoveDailyRef)
                    .where(
                        and_(
                            LoveDailyRef.date == today,
                            LoveDailyRef.group_id == group_id,
                            LoveDailyRef.user_id == uid,
                        )
                    )
                    .values(
                        reply_sent=LoveDailyRef.reply_sent + v.get("reply", 0),
                        updated_at=now,
                    )
                )

            for uid, v in interaction_received.items():
                await session.execute(
                    update(LoveDailyRef)
                    .where(
                        and_(
                            LoveDailyRef.date == today,
                            LoveDailyRef.group_id == group_id,
                            LoveDailyRef.user_id == uid,
                        )
                    )
                    .values(
                        reply_received=LoveDailyRef.reply_received + v.get("reply", 0),
                        updated_at=now,
                    )
                )

    async def filter_existing_message_ids(
            self, message_ids: list[str]
    ) -> set[str]:
        """
        批量查询已存在的 message_id
        返回：已存在的 message_id 集合
        """
        if not message_ids:
            return set()

        async with self.db.get_session() as session:
            message_id_col = cast(ColumnElement[str], MessageOwnerIndex.message_id)
            stmt = select(MessageOwnerIndex.message_id).where(
                message_id_col.in_(message_ids)
            )
            result = await session.execute(stmt)
            return {row[0] for row in result.all()}