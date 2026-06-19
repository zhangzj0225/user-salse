---
story_id: "3.3"
story_key: "3-3-recharge-application-and-review"
epic: "Epic 3 — 核心业务闭环"
epic_id: "3"
title: "充值申请与审核"
status: "ready-for-dev"
priority: "high"
depends_on:
  - "3-4-recharge-first-reward-booking (佣金逻辑 — 3.3 只调用接口)"
  - "3-11-license-generation-and-verification (License 生成 — 3.3 只预留接口)"
blocks:
  - "3-5-quota-management (额度依赖充值确认后分配)"
  - "3-7-quota-sales-scenario-a (销售依赖额度)"
  - "4-2-recharge-review (后台审核页面对接)"
---

# Story 3.3: 充值申请与审核

## User Story

As a 用户,
I want 充值以获得更高角色,
So that 获得对应权益（额度 + License）。

## Acceptance Criteria

- **AC1（提交充值申请）**: 用户已登录（user token），选择充值金额（888/5000/10000）并提交，系统生成充值记录写入 `recharges` 表，状态为 `pending`，`target_role` 由金额自动映射（888→member, 5000→distributor, 10000→agent）
- **AC2（金额校验）**: 充值金额必须为 888/5000/10000 之一，其他金额返回 400 错误
- **AC3（充值独立）**: 各充值独立、不互斥。888 会员可再充 5000 成为经销商（不退 888），角色变更为最新充值对应角色，可售额度累加
- **AC4（查看充值记录）**: 用户可查看自己的充值记录列表，按创建时间倒序
- **AC5（管理员批准 — 角色变更）**: 管理员确认收款后批准充值，用户角色变更为充值金额对应角色（888→member, 5000→distributor, 10000→agent）
- **AC6（管理员批准 — 额度分配）**: 批准时代理获得 22 个额度，经销商获得 11 个额度，888 会员不获得额度。额度为累加（account_quota += 对应数量）
- **AC7（管理员批准 — License 预留）**: 批准时调用 License 生成接口（本 Story 仅预留 stub 调用点，实际 License Code 生成逻辑在 Story 3.11 实现）
- **AC8（管理员批准 — 佣金记账）**: 批准时调用 `CommissionEngine.process_recharge()` 记账直接上级的首次奖励（本 Story 仅调用接口，实际佣金计算逻辑在 Story 3.4 实现）
- **AC9（管理员拒绝）**: 管理员可拒绝充值申请并填写拒绝原因，状态变更为 `rejected`，用户角色和额度不变
- **AC10（状态机校验）**: 仅 `pending` 状态的充值可被批准/拒绝，已处理的充值重复操作返回 400 错误
- **AC11（审计日志）**: 批准和拒绝操作均写入 `audit_logs`（action=`recharge_approve` / `recharge_reject`）
- **AC12（权限控制）**: 提交充值、查看充值记录需 user token；审核操作（列表/批准/拒绝）需 admin token

## Technical Requirements

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/recharge_service.py` | NEW | 充值服务：创建申请、批准、拒绝、查询 |
| `backend/app/services/license_service.py` | NEW | License 服务 STUB：`generate_for_recharge()` 预留接口，实际生成在 Story 3.11 |
| `backend/app/schemas/recharge.py` | NEW | 充值请求/响应 Pydantic schemas |
| `backend/app/api/v1/recharges.py` | NEW | 用户端充值 API（POST/GET `/recharges`） |
| `backend/app/api/v1/admin.py` | NEW | 管理员端 API（GET `/admin/recharges`, POST approve/reject） |
| `backend/app/main.py` | UPDATE | 注册 `recharges_router` 和 `admin_router` |
| `backend/tests/test_recharge_service.py` | NEW | 服务层单元测试 |
| `backend/tests/test_recharge_api.py` | NEW | API 层集成测试 |

> **注意**: `backend/app/models/recharge.py`、`backend/app/models/user.py`、`backend/app/models/license.py` 已在 Story 2.1 创建，字段完整，本 Story 无需修改模型。`backend/app/services/commission_service.py` 已在 Story 2.4 创建，`CommissionEngine.process_recharge()` 接口可用。

### API 端点

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/v1/recharges` | user token | 提交充值申请 |
| GET | `/api/v1/recharges` | user token | 查看我的充值记录 |
| GET | `/api/v1/admin/recharges` | admin token | 充值审核列表（支持状态筛选） |
| POST | `/api/v1/admin/recharges/{id}/approve` | admin token | 批准充值 |
| POST | `/api/v1/admin/recharges/{id}/reject` | admin token | 拒绝充值（需传 reject_reason） |

### 请求/响应格式

**POST `/api/v1/recharges` 请求:**
```json
{"amount": 888}
```

**POST `/api/v1/recharges` 响应 (201):**
```json
{
  "data": {
    "id": 1,
    "user_id": 123,
    "amount": "888.00",
    "target_role": "member",
    "status": "pending",
    "reject_reason": null,
    "reviewed_by": null,
    "reviewed_at": null,
    "created_at": "2026-06-19T10:00:00+08:00"
  }
}
```

**GET `/api/v1/recharges` 响应:**
```json
{
  "data": [/* RechargeInfo 列表 */],
  "total": 5
}
```

**GET `/api/v1/admin/recharges?status=pending` 响应:**
```json
{
  "data": [/* RechargeInfo 列表（含用户邮箱） */],
  "total": 10
}
```

**POST `/api/v1/admin/recharges/{id}/reject` 请求:**
```json
{"reject_reason": "未收到款项"}
```

### 核心业务规则

#### 金额→角色→额度映射

```python
VALID_RECHARGE_AMOUNTS = (888, 5000, 10000)

AMOUNT_ROLE_MAP = {
    888: "member",
    5000: "distributor",
    10000: "agent",
}

AMOUNT_QUOTA_MAP = {
    888: 0,    # 888 会员不获得可售额度
    5000: 11,  # 经销商获得 11 个
    10000: 22, # 代理获得 22 个
}
```

#### 批准流程（approve_recharge）

```
1. 查找 recharge 记录，不存在 → 404
2. 校验 recharge.status == "pending"，否则 → 400 "充值已处理"
3. 查找充值用户 User
4. 更新用户角色：user.role = AMOUNT_ROLE_MAP[int(recharge.amount)]
5. 累加额度：user.account_quota += AMOUNT_QUOTA_MAP[int(recharge.amount)]
   （累加而非覆盖，因为"各充值独立不互斥"）
6. 更新充值记录：status="approved", reviewed_by=admin_id, reviewed_at=now
7. 调用 License 生成（stub）：
   license_service.generate_for_recharge(
       user_id=user.id, email=user.email,
       recharge_id=recharge.id, target_role=user.role, db=db
   )
8. 调用佣金记账：
   engine = CommissionEngine(db)
   engine.process_recharge(
       recharge_id=recharge.id,
       recharger_user_id=user.id,
       amount=int(recharge.amount),
   )
   ⚠️ process_recharge 只 flush 不 commit，调用方必须 commit
9. 写入审计日志：AuditService.log(action="recharge_approve", ...)
10. db.commit()
11. 返回更新后的充值记录
```

#### 拒绝流程（reject_recharge）

```
1. 查找 recharge 记录，不存在 → 404
2. 校验 recharge.status == "pending"，否则 → 400 "充值已处理"
3. 更新充值记录：status="rejected", reject_reason=reason, reviewed_by=admin_id, reviewed_at=now
4. 写入审计日志：AuditService.log(action="recharge_reject", ...)
5. db.commit()
6. 返回更新后的充值记录
```

## Developer Context

### 架构合规要求

1. **三层分层**: router（`api/v1/`）→ service（`services/`）→ model（`models/`）。router 只做参数提取和响应返回，业务逻辑在 service 层。
2. **API 响应格式**: 统一 `{"data": ...}` 成功格式，错误用 `{"detail": "...", "code": "..."}`。当前项目通过 `core/exceptions.py` 的全局异常处理器统一处理，router 层用 `HTTPException` 抛出。
3. **金额传输**: amount 在 API 层用整数（888/5000/10000），数据库 DECIMAL(10,2)。响应序列化时 Pydantic 会转为字符串 `"888.00"`。
4. **命名规范**: Python snake_case（变量/函数/文件），PascalCase（类）。API 路径 kebab-case 复数。
5. **JSON 字段**: 后端与前端统一 snake_case（如 `target_role`、`reject_reason`）。

### 已有代码模式（必须遵循）

#### Service 层模式（参考 `invite_service.py`、`auth_service.py`）

```python
"""充值服务。"""
import logging
from sqlalchemy.orm import Session
from app.models.recharge import Recharge

logger = logging.getLogger(__name__)

class RechargeService:
    """充值申请、审核服务。"""

    def create_recharge(self, user_id: int, amount: int, db: Session) -> Recharge:
        ...

    def approve_recharge(self, recharge_id: int, admin_id: int, db: Session) -> Recharge:
        ...

    def reject_recharge(self, recharge_id: int, admin_id: int, reason: str, db: Session) -> Recharge:
        ...

    def list_user_recharges(self, user_id: int, db: Session) -> list[Recharge]:
        ...

    def list_pending_recharges(self, db: Session, status: str | None = None) -> list[Recharge]:
        ...


def get_recharge_service() -> RechargeService:
    return RechargeService()
```

#### Router 层模式（参考 `invite_codes.py`、`auth.py`）

```python
"""充值 API 端点。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin
from app.models.user import User
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/recharges", tags=["recharges"])

@router.post("", response_model=dict)
def create_recharge_endpoint(
    request: CreateRechargeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: RechargeService = Depends(get_recharge_service),
):
    ...
    return {"data": RechargeInfo.model_validate(recharge).model_dump()}
```

#### Schema 层模式（参考 `schemas/invite_code.py`、`schemas/auth.py`）

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class CreateRechargeRequest(BaseModel):
    amount: int = Field(..., description="充值金额：888/5000/10000")

class RechargeInfo(BaseModel):
    id: int
    user_id: int
    amount: str  # DECIMAL 序列化为字符串
    target_role: str
    status: str
    reject_reason: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class RejectRechargeRequest(BaseModel):
    reject_reason: str = Field(..., min_length=1, max_length=256)
```

#### main.py 路由注册（UPDATE）

在 `main.py` 中添加：
```python
from app.api.v1.recharges import router as recharges_router
from app.api.v1.admin import router as admin_router

app.include_router(recharges_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
```

### 关键依赖接口

#### CommissionEngine.process_recharge()（已实现，Story 2.4）

```python
# backend/app/services/commission_service.py
class CommissionEngine:
    def __init__(self, db: Session): ...

    def process_recharge(
        self,
        recharge_id: int,
        recharger_user_id: int,
        amount: int,  # 必须是 int 类型，888/5000/10000
    ) -> list[CommissionRecord]:
        """
        充值确认后的佣金处理（首次奖励 + 后续收益）。
        ⚠️ 事务约定：本方法只 flush 不 commit。调用方必须在同一事务内
        于本方法返回后调用 db.commit()，否则佣金记录随 session 关闭回滚丢失。
        ⚠️ amount 必须是 int（非 float/bool），且与 recharges 记录一致。
        内部会校验 amount 与 recharges 表记录一致。
        """
```

**调用方式（在 approve_recharge 中）:**
```python
from app.services.commission_service import CommissionEngine

engine = CommissionEngine(db)
records = engine.process_recharge(
    recharge_id=recharge.id,
    recharger_user_id=user.id,
    amount=int(recharge.amount),  # DECIMAL → int
)
# ⚠️ 不要在此 commit，由 approve_recharge 末尾统一 commit
```

> **注意（与 Story 3.4 的关系）**: `process_recharge` 内部通过 `commission_configs` 表查询佣金规则。Story 3.4 负责确保佣金配置种子数据正确写入。在 Story 3.3 实现时，若 `commission_configs` 表中无对应配置，`process_recharge` 会返回空列表（无佣金记录），不影响充值审批流程本身。Story 3.3 的测试应验证"调用了 process_recharge"而非"佣金金额正确"。

#### LicenseService STUB（本 Story 创建）

```python
"""License 生成与验证服务。

⚠️ 本文件为 Story 3.3 创建的 STUB。实际 License Code 生成逻辑
（HMAC 签名、防篡改）在 Story 3.11 实现。
"""
import logging
from sqlalchemy.orm import Session
from app.models.license import License

logger = logging.getLogger(__name__)

class LicenseService:
    def generate_for_recharge(
        self,
        user_id: int,
        email: str,
        recharge_id: int,
        target_role: str,
        db: Session,
    ) -> License | None:
        """充值确认后生成 License。

        STUB：Story 3.3 仅预留调用点，实际 License 生成在 Story 3.11。
        当前实现仅记录日志，不创建 License 记录。
        """
        # TODO: Story 3.11 — 实现 License Code 生成（HMAC 签名 + 写入 licenses 表）
        # source 映射：888 → "recharge"，5000/10000 → "role_builtin"
        logger.info(
            "License generation stub (Story 3.11 will implement): "
            "user_id=%d recharge_id=%d target_role=%s",
            user_id, recharge_id, target_role,
        )
        return None


def get_license_service() -> LicenseService:
    return LicenseService()
```

> **License source 映射**（供 Story 3.11 实现时参考）:
> - 充值 888 → source="recharge"
> - 充值 5000 → source="role_builtin"
> - 充值 10000 → source="role_builtin"

#### AuditService.log()（已实现）

```python
# backend/app/services/audit_service.py
class AuditService:
    @staticmethod
    def log(
        action: str,           # "recharge_approve" / "recharge_reject"
        operator_type: str,    # "admin" / "system"
        target_type: str,      # "recharge"
        target_id: int | None, # recharge.id
        old_value: dict | None,
        new_value: dict | None,
        business_id: str | None,  # f"recharge_{recharge.id}"
        db: Session,
    ) -> AuditLog: ...
```

### 现有模型字段参考

#### Recharge 模型（`backend/app/models/recharge.py`，已存在，无需修改）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| user_id | Integer FK→users.id | 充值用户 |
| amount | DECIMAL(10,2) | 充值金额 888.00/5000.00/10000.00 |
| target_role | Enum(member/distributor/agent) | 充值目标角色 |
| status | Enum(pending/approved/rejected) | 审核状态，默认 pending |
| reject_reason | String(256) | 拒绝原因 |
| reviewed_by | Integer FK→admin_users.id | 审核管理员 |
| reviewed_at | DateTime | 审核时间 |
| created_at | DateTime | 创建时间 |

#### User 模型（`backend/app/models/user.py`，已存在，无需修改）

关键字段：`role`（Enum: user/member/distributor/agent）、`account_quota`（Int, 可售额度）、`account_used`（Int, 已使用额度）、`parent_id`（直接上级）、`email`（邮箱）。

#### License 模型（`backend/app/models/license.py`，已存在，无需修改）

关键字段：`code`（String UNIQUE）、`user_id`、`email`、`source`（Enum: recharge/sale/role_builtin）、`source_id`、`status`（Enum: unused/activated/expired）。

### 测试要求

#### 测试框架

- 使用 pytest，遵循 `conftest.py` 中的 `db_session`（SQLite 内存 + 事务回滚）和 `client`（TestClient + DB 覆盖）fixture。
- 认证 token 使用 `create_access_token(subject=user.id, role="user", token_type="user")` 和 `create_access_token(subject=admin.id, role="admin", token_type="admin")` 生成。
- 测试文件参考 `test_invite_api.py` 和 `test_invite_service.py` 的组织方式（class 分组）。

#### 服务层测试（`test_recharge_service.py`）必须覆盖

| 测试用例 | 验证点 |
|---------|--------|
| test_create_recharge_success | 888/5000/10000 各创建成功，status=pending，target_role 正确映射 |
| test_create_recharge_invalid_amount | 非 888/5000/10000 金额抛出 ValueError |
| test_approve_recharge_changes_role | 批准后 user.role 变更（888→member, 5000→distributor, 10000→agent） |
| test_approve_recharge_adds_quota | 批准后 account_quota 累加（22/11/0） |
| test_approve_recharge_independent | 888 会员再充 5000 → role=distributor, quota=0+11=11 |
| test_approve_recharge_calls_commission | 批准后调用 CommissionEngine.process_recharge（mock 或验证无异常） |
| test_approve_recharge_calls_license_stub | 批准后调用 LicenseService.generate_for_recharge（验证日志或不报错） |
| test_approve_recharge_writes_audit | audit_logs 表有 recharge_approve 记录 |
| test_approve_already_processed | 批准已 approved/rejected 的充值抛出 ValueError |
| test_reject_recharge_success | 拒绝后 status=rejected, reject_reason 已设置, 角色和额度不变 |
| test_reject_recharge_writes_audit | audit_logs 表有 recharge_reject 记录 |
| test_reject_already_processed | 拒绝已处理的充值抛出 ValueError |
| test_list_user_recharges | 只返回当前用户的充值记录，按时间倒序 |

#### API 层测试（`test_recharge_api.py`）必须覆盖

| 测试用例 | 验证点 |
|---------|--------|
| test_create_recharge_requires_auth | 无 token → 401 |
| test_create_recharge_success | 有 user token → 201, 返回充值记录 |
| test_create_recharge_invalid_amount | 金额非 888/5000/10000 → 400 |
| test_list_recharges_requires_auth | 无 token → 401 |
| test_list_recharges_returns_own | 只返回自己的充值记录 |
| test_admin_list_recharges_requires_admin | user token → 403 |
| test_admin_list_recharges_success | admin token → 200, 返回列表 |
| test_admin_list_recharges_filter_by_status | ?status=pending 筛选 |
| test_admin_approve_success | admin token → 200, status=approved |
| test_admin_approve_already_processed | 已处理 → 400 |
| test_admin_reject_success | admin token + reject_reason → 200, status=rejected |
| test_admin_reject_without_reason | 缺 reject_reason → 422 |
| test_admin_endpoints_require_admin_token | user token 调用 → 403 |

### 依赖关系说明

#### 与 Story 3.4（充值首次奖励记账）的关系

- **Story 3.3 的职责**: 在 `approve_recharge` 中调用 `CommissionEngine.process_recharge(recharge_id, recharger_user_id, amount)`，触发佣金记账流程。
- **Story 3.4 的职责**: 确保佣金配置种子数据正确（`commission_configs` 表），使 `process_recharge` 内部能查到规则并记账。佣金金额正确性由 3.4 保证。
- **解耦方式**: `process_recharge` 接口已实现（Story 2.4），内部查表无配置时返回空列表（幂等无操作）。3.3 测试只验证"调用了接口、无异常"，不验证佣金金额。
- **顺序**: 3.3 和 3.4 可并行开发。3.3 不阻塞于 3.4。

#### 与 Story 3.11（License 生成与验证）的关系

- **Story 3.3 的职责**: 创建 `LicenseService.generate_for_recharge()` stub 方法，在 `approve_recharge` 中调用。当前 stub 仅记录日志、不生成 License。
- **Story 3.11 的职责**: 实现 License Code 生成（HMAC-SHA256 签名 + 写入 `licenses` 表），实现验证接口。
- **解耦方式**: stub 方法签名已定义（`user_id, email, recharge_id, target_role, db`），Story 3.11 替换 stub 实现即可，不影响 3.3 的调用代码。

#### 与 Story 3.5（可售额度管理）的关系

- Story 3.5 依赖 3.3 批准充值后 `user.account_quota` 的正确累加。3.3 完成后 3.5 可直接读取 `account_quota` 和 `account_used`。

#### 与 Story 4.2（充值审核后台）的关系

- Story 4.2 是管理员 Web 前端页面，对接本 Story 的 admin API 端点（GET /admin/recharges, approve, reject）。

### 注意事项

1. **amount 类型一致性**: `Recharge.amount` 是 `DECIMAL(10,2)`，调用 `process_recharge` 时必须 `int(recharge.amount)` 转为 int。`process_recharge` 内部会校验入参 amount 与 recharges 表记录一致。
2. **额度累加而非覆盖**: `user.account_quota += AMOUNT_QUOTA_MAP[amount]`。因为"各充值独立不互斥"，888 会员（quota=0）再充 5000 后 quota=0+11=11。
3. **角色覆盖**: `user.role = AMOUNT_ROLE_MAP[amount]`。角色反映最新充值状态（888 会员充 5000 后 role=distributor）。
4. **事务边界**: `approve_recharge` 内的所有操作（角色变更、额度累加、状态更新、License stub、佣金记账、审计日志）必须在同一事务内，末尾统一 `db.commit()`。`process_recharge` 和 `AuditService.log` 只 flush 不 commit。
5. **admin.py 是新文件**: 当前项目无 `backend/app/api/v1/admin.py`，本 Story 创建。后续 Story 4.x 会在此文件追加更多管理员端点。
6. **License source 映射**: 供 Story 3.11 参考 — 充值 888 → source="recharge"，充值 5000/10000 → source="role_builtin"。
