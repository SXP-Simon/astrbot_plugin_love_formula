from datetime import date as DateType
from typing import Optional
from sqlmodel import Field, SQLModel


class LoveDailyRef(SQLModel, table=True):
    """每日恋爱成分指标快照"""

    __tablename__ = "love_daily_ref"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: DateType = Field(index=True)
    group_id: str = Field(index=True)
    user_id: str = Field(index=True)

    # Text Metrics
    msg_sent: int = Field(default=0)
    text_len_total: int = Field(default=0)

    # Interaction Metrics
    reply_sent: int = Field(default=0)
    reply_received: int = Field(default=0)
    poke_sent: int = Field(default=0)
    poke_received: int = Field(default=0)
    reaction_sent: int = Field(default=0)
    reaction_received: int = Field(default=0)

    # Negative Metrics
    recall_count: int = Field(default=0)

    # Meme/Nostalgia Metrics
    image_sent: int = Field(default=0)

    updated_at: float = Field(default=0.0)  # Timestamp


class MessageOwnerIndex(SQLModel, table=True):
    """消息归属索引，用于Reaction归因"""

    __tablename__ = "message_owner_index"

    message_id: str = Field(primary_key=True)
    user_id: str
    group_id: str
    timestamp: float  # 用于清理过期数据
