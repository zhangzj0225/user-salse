"""Schemas package - Pydantic models for request/response validation."""

from app.schemas.admin_user import (
    AdminUserInfo,
    UserDetail,
    UserListResponse,
)
from app.schemas.auth import (
    AdminInfo,
    LoginRequest,
    LoginResponse,
    SendEmailCodeRequest,
    UserInfo,
)
from app.schemas.dashboard import DashboardStats
from app.schemas.earnings import (
    EarningsListResponse,
    EarningsRecord,
    EarningsSummary,
)
from app.schemas.license import (
    LicenseActivateRequest,
    LicenseInfo,
    LicenseVerifyRequest,
    LicenseVerifyResponse,
)
from app.schemas.payment import (
    PaymentApproveRequest,
    PaymentCreateRequest,
    PaymentResponse,
    PaymentStatusResponse,
)
from app.schemas.quota import (
    QuotaInfo,
    SalesRecord,
)
from app.schemas.referral_code import ReferralCodeResponse
from app.schemas.sale import (
    SellAccountRequest,
    SellAccountResponse,
)
from app.schemas.system_config import (
    ConfigChangeLogInfo,
    ConfigChangeLogListResponse,
    ConfigItem,
    ConfigListResponse,
    ConfigUpdateRequest,
)
from app.schemas.team import (
    TeamNode,
    TeamTreeResponse,
    UpstreamChainResponse,
    UpstreamNode,
)
from app.schemas.ticket import (
    AdminTicketInfo,
    AdminTicketListResponse,
    CreateTicketRequest,
    CreateTicketResponse,
    RejectTicketRequest,
    TicketActionResponse,
    TicketInfo,
    TicketListResponse,
)

__all__ = [
    # admin_user
    "AdminUserInfo",
    "UserDetail",
    "UserListResponse",
    # auth
    "AdminInfo",
    "LoginRequest",
    "LoginResponse",
    "SendEmailCodeRequest",
    "UserInfo",
    # dashboard
    "DashboardStats",
    # earnings
    "EarningsListResponse",
    "EarningsRecord",
    "EarningsSummary",
    # license
    "LicenseActivateRequest",
    "LicenseInfo",
    "LicenseVerifyRequest",
    "LicenseVerifyResponse",
    # payment
    "PaymentApproveRequest",
    "PaymentCreateRequest",
    "PaymentResponse",
    "PaymentStatusResponse",
    # quota
    "QuotaInfo",
    "SalesRecord",
    # referral_code
    "ReferralCodeResponse",
    # sale
    "SellAccountRequest",
    "SellAccountResponse",
    # system_config
    "ConfigChangeLogInfo",
    "ConfigChangeLogListResponse",
    "ConfigItem",
    "ConfigListResponse",
    "ConfigUpdateRequest",
    # team
    "TeamNode",
    "TeamTreeResponse",
    "UpstreamChainResponse",
    "UpstreamNode",
    # ticket
    "AdminTicketInfo",
    "AdminTicketListResponse",
    "CreateTicketRequest",
    "CreateTicketResponse",
    "RejectTicketRequest",
    "TicketActionResponse",
    "TicketInfo",
    "TicketListResponse",
]
