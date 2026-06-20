import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.invite_codes import router as invite_codes_router
from app.api.v1.recharges import router as recharges_router
from app.api.v1.admin import router as admin_router
from app.api.v1.quota import router as quota_router
from app.api.v1.team import router as team_router
from app.api.v1.sales import router as sales_router
from app.api.v1.earnings import router as earnings_router
from app.api.v1.license import router as license_router
from app.api.v1.tickets import router as tickets_router
from app.core.config import settings, validate_security_secrets
from app.core.exceptions import global_exception_handler
from app.core.security import get_current_admin, get_current_user
from app.models.admin_user import AdminUser
from app.models.user import User
from app.schemas.auth import AdminInfo, UserInfo

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="user-salse API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Exception, global_exception_handler)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(invite_codes_router, prefix="/api/v1")
app.include_router(recharges_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(quota_router, prefix="/api/v1")
app.include_router(team_router, prefix="/api/v1")
app.include_router(sales_router, prefix="/api/v1")
app.include_router(earnings_router, prefix="/api/v1")
app.include_router(license_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    # SEC-1: 生产环境启动校验密钥非默认值，dev 仅警告
    validate_security_secrets()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/users/me", response_model=dict)
def get_me(current_user: User = Depends(get_current_user)):
    return {"data": UserInfo.model_validate(current_user).model_dump()}


@app.get("/api/v1/admin/me", response_model=dict)
def admin_me(current_admin: AdminUser = Depends(get_current_admin)):
    return {"data": AdminInfo.model_validate(current_admin).model_dump()}
