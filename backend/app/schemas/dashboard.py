"""运营数据看板 schemas (Story 4.3)。"""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """运营看板数据。"""

    # 用户统计
    total_users: int
    agent_count: int
    distributor_count: int
    # 今日数据
    today_new_users: int
    today_payment_total: str
    # License 统计
    license_generated_count: int
    license_activated_count: int
    # 工单统计
    pending_ticket_count: int
