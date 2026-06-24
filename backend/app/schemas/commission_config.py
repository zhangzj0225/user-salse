from pydantic import BaseModel, Field
from typing import Optional

class CommissionConfigItem(BaseModel):
    id: int
    role: str
    scene: str
    reward_type: str
    reward_value: str

class CommissionConfigListResponse(BaseModel):
    configs: list[CommissionConfigItem]

class CommissionConfigUpdateRequest(BaseModel):
    reward_value: str = Field(..., min_length=1, max_length=32)
