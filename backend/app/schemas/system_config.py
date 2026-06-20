"""系统参数配置 schemas (Story 4.4)。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ConfigItem(BaseModel):
    """单个配置项。"""
    config_key: str
    config_value: str
    description: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """更新配置请求。"""
    config_value: str


class ConfigChangeLogInfo(BaseModel):
    """配置变更日志。"""
    id: int
    admin_id: int
    config_key: str
    old_value: Optional[str] = None
    new_value: str
    created_at: datetime


class ConfigListResponse(BaseModel):
    """配置列表响应。"""
    configs: list[ConfigItem]


class ConfigChangeLogListResponse(BaseModel):
    """变更日志列表响应。"""
    logs: list[ConfigChangeLogInfo]
