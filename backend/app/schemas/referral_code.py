"""推荐码相关 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel


class ReferralCodeResponse(BaseModel):
    """推荐码响应（持久码，不记录使用情况）。"""

    code: str
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
