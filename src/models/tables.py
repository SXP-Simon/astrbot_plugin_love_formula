from datetime import date as DateType
from typing import Optional
from sqlmodel import Field, SQLModel


class LoveDailyRef(SQLModel, table=True):
    """每日恋爱成分指标快照，存储每个用户在群组中的各项互动数据"""

    __tablename__ = "love_daily_ref"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    date: DateType = Field(index=True)
    group_id: str = Field(index=True)
    user_id: str = Field(index=True)

    # 文字指标
    msg_sent: int = Field(default=0)
    text_len_total: int = Field(default=0)

    # 互动指标
    reply_sent: int = Field(default=0)
    reply_received: int = Field(default=0)
    poke_sent: int = Field(default=0)
    poke_received: int = Field(default=0)
    reaction_sent: int = Field(default=0)
    reaction_received: int = Field(default=0)

    # 负面指标
    recall_count: int = Field(default=0)

    # 多媒体/梗图指标
    image_sent: int = Field(default=0)

    updated_at: float = Field(default=0.0)  # 更新时间戳


class MessageOwnerIndex(SQLModel, table=True):
    """消息归属索引，用于将后续的 Reaction 归因到具体的发送者"""

    __tablename__ = "message_owner_index"
    __table_args__ = {"extend_existing": True}

    message_id: str = Field(primary_key=True)
    user_id: str
    group_id: str
    timestamp: float  # 时间戳
