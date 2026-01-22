from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel


class DBManager:
    """数据库管理器，负责异步连接和会话管理"""

    def __init__(self, db_path: str):
        self.db_url = f"sqlite+aiosqlite:///{db_path}"

        # 创建异步引擎
        self.engine = create_async_engine(
            self.db_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=5,
        )

        # 创建会话工厂
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self):
        """初始化数据库，创建所有定义的表"""
        # 必须显式导入模型类，确保它们被注册到 SQLModel.metadata 中
        from ..models.tables import (  # noqa: F401
            LoveDailyRef,
            MessageOwnerIndex,
            UserCooldown,
        )

        # 1. 创建表
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

            def _needs_refresh(sync_conn):
                inspector = inspect(sync_conn)
                if "user_cooldown" not in inspector.get_table_names():
                    return True
                existing_columns = {col["name"] for col in inspector.get_columns("user_cooldown")}
                required_columns = set(UserCooldown.__table__.columns.keys())
                if existing_columns != required_columns:
                    return True
                return False

            needs_refresh = await conn.run_sync(_needs_refresh)
            if needs_refresh:
                await conn.run_sync(lambda sync_conn: UserCooldown.__table__.drop(sync_conn, checkfirst=True))
                await conn.run_sync(lambda sync_conn: UserCooldown.__table__.create(sync_conn, checkfirst=True))

        # 2. SQLite 优化 PRAGMA
        async with self.engine.connect() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=-20000"))
            await conn.execute(text("PRAGMA temp_store=MEMORY"))
            await conn.execute(text("PRAGMA mmap_size=134217728"))

            # 确认表名正确
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_message_id ON message_owner_index(message_id)")
            )

            await conn.execute(text("PRAGMA optimize"))

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """异步获取数据库会话的上下文管理器"""
        async with self.async_session() as session:
            async with session.begin():
                yield session
