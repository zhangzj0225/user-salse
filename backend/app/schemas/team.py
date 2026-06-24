"""团队树与上级链相关 Pydantic schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TeamNode(BaseModel):
    """下级树节点。"""
    user_id: int
    email: str
    nickname: Optional[str] = None
    role: str
    created_at: datetime
    direct_downline_count: int
    children: list["TeamNode"] = Field(default_factory=list)


class UpstreamNode(BaseModel):
    """上级链节点。"""
    user_id: int
    email: str
    nickname: Optional[str] = None
    role: str
    level: int  # 距当前用户的层级（1=直接上级）


class TeamTreeResponse(BaseModel):
    """团队树响应。"""
    total_count: int
    root: TeamNode


class UpstreamChainResponse(BaseModel):
    """上级链响应。"""
    chain: list[UpstreamNode]
