---
story_id: "2.1"
story_key: "2-1-database-model-refactor"
epic: "2"
title: "数据库模型重构"
status: "review"
created: "2026-06-18"
---

# Story 2.1: 数据库模型重构

## User Story

As a 开发者,
I want 重构数据库模型以匹配 PRD v2,
So that 后续业务开发基于正确的数据结构。

## Business Context

PRD v2 进行了重大架构调整：邮箱注册替代微信 OAuth、邀请码统一类型、角色由充值决定、新增 License 对接、佣金场景 A/B 分离。Epic 1 的数据库模型需要全面重构。

## Acceptance Criteria

### AC1: users 表重构

**Given** Epic 1 已完成的 users 表（含 phone, openid, 3 角色）
**When** 执行模型重构
**Then** `users` 表：`phone` → `email`（VARCHAR(128), UNIQUE, NOT NULL）
**And** 移除 `openid` 字段
**And** `role` 枚举增加 `member`（4 角色：user, member, distributor, agent）
**And** `status` 默认值从 `pending` 改为 `active`（注册即 active）
**And** 新增 `password_hash` 字段（VARCHAR(256), nullable）

### AC2: invite_codes 表重构

**Given** Epic 1 的 invite_codes 表含 `target_role` 字段
**When** 执行模型重构
**Then** 移除 `target_role` 字段（邀请码统一类型）
**And** 新增 `used_at` 字段（DATETIME, nullable）

### AC3: 新增 email_verification_codes 表

**Given** 需要邮箱验证码替代短信验证码
**When** 创建新表
**Then** 创建 `email_verification_codes` 表（email, code, scene, verified, expires_at）
**And** 添加复合索引 `idx_email_scene_verified (email, scene, verified, expires_at)`

### AC4: 新增 recharges 表

**Given** 需要充值记录表
**When** 创建新表
**Then** 创建 `recharges` 表（user_id, amount, target_role, status, reject_reason, reviewed_by, reviewed_at）
**And** `target_role` ENUM('member', 'distributor', 'agent')
**And** `status` ENUM('pending', 'approved', 'rejected')

### AC5: 新增 licenses 表

**Given** 需要 License 对接舆情系统
**When** 创建新表
**Then** 创建 `licenses` 表（code, user_id, email, source, source_id, status, activated_at, expires_at, key_version）
**And** `code` VARCHAR(128), UNIQUE, NOT NULL
**And** `source` ENUM('recharge', 'sale', 'role_builtin')
**And** `status` ENUM('unused', 'activated', 'expired')

### AC6: commission_configs 表重构

**Given** Epic 1 的 commission_configs 表（3 角色，旧场景）
**When** 执行模型重构
**Then** `role` 枚举增加 `member`
**And** 场景更新为：`recharge_888`, `recharge_5000`, `recharge_10000`, `followup_reward`, `team_bonus`
**And** 保留 UNIQUE 约束 `(role, scene)`

### AC7: commission_records 表重构

**Given** Epic 1 的 commission_records 表
**When** 执行模型重构
**Then** `type` 枚举增加 `followup_reward`（后续收益）
**And** 保留 `business_id` UNIQUE 约束

### AC8: sales 表重构

**Given** Epic 1 的 sales 表使用 `customer_phone`
**When** 执行模型重构
**Then** `customer_phone` → `customer_email`（VARCHAR(128)）

### AC9: 移除旧表

**Given** Epic 1 的 sms_records 和 quota_purchases 表
**When** 执行模型重构
**Then** 移除 `sms_records` 表（被 email_verification_codes 替代）
**And** 移除 `quota_purchases` 表（补购改为 recharges 统一管理）

### AC10: 种子数据更新

**Given** Epic 1 的 10 条佣金配置种子数据
**When** 更新种子数据
**Then** 种子数据更新为 4 角色佣金配置：
- agent: recharge_888=488.40, recharge_5000=2750.00, recharge_10000=5500.00, followup_reward=133.20, team_bonus=0.05
- distributor: recharge_888=355.20, recharge_5000=2000.00, recharge_10000=4000.00, team_bonus=0.04
- member: recharge_888=177.60
- user: recharge_888=177.60

### AC11: 迁移脚本可执行

**Given** Alembic 迁移脚本
**When** 执行 `alembic upgrade head`
**Then** 所有表创建成功，种子数据插入成功
**And** 执行 `alembic downgrade base` 可完整回滚

## Developer Context

### 当前代码状态（Epic 1 完成态）

**现有模型文件：**
- `backend/app/models/user.py` — User ORM（phone, openid, 3 角色）
- `backend/app/models/sms_record.py` — SmsRecord ORM
- `backend/app/models/admin_user.py` — AdminUser ORM
- `backend/app/models/commission_record.py` — CommissionRecord ORM
- `backend/app/models/audit_log.py` — AuditLog ORM
- `backend/app/models/__init__.py` — 导出所有模型

**现有迁移：**
- `001_create_all_tables.py` — 12 张表
- `002_seed_commission_configs.py` — 10 条种子数据

**现有测试：** 80 个测试（test_security, test_auth_service, test_schemas, test_auth_api, test_conftest）

### 重构策略

由于是开发早期、无生产数据，采用 **新建迁移脚本（003）替代修改 001/002** 的策略：
1. 新增 `003_refactor_models_v2.py` 迁移脚本
2. 在 upgrade 中：drop 旧表 → create 新表
3. 在 downgrade 中：drop 新表 → recreate 旧表（保持对称）
4. 新增 `004_seed_commission_configs_v2.py` 种子数据迁移
5. 删除旧的 `sms_record.py` 模型文件
6. 新增 `email_verification_code.py`, `recharge.py`, `license.py`, `invite_code.py`, `sale.py`, `ticket.py` 模型文件

### 需要新建的模型文件

| 文件 | ORM 类 | 说明 |
|------|--------|------|
| `models/email_verification_code.py` | EmailVerificationCode | 邮箱验证码 |
| `models/invite_code.py` | InviteCode | 邀请码（统一类型） |
| `models/recharge.py` | Recharge | 充值记录 |
| `models/sale.py` | Sale | 额度销售记录 |
| `models/license.py` | License | License Code |
| `models/ticket.py` | Ticket | 提现工单 |
| `models/config_change_log.py` | ConfigChangeLog | 配置变更日志 |
| `models/notification_log.py` | NotificationLog | 通知日志 |

### 需要修改的模型文件

| 文件 | 变更 |
|------|------|
| `models/user.py` | phone→email, 移除 openid, role 加 member, status 默认 active, 加 password_hash |
| `models/commission_record.py` | type 加 followup_reward |
| `models/audit_log.py` | 无变更 |
| `models/admin_user.py` | 无变更 |
| `models/__init__.py` | 更新导出列表 |

### 需要删除的模型文件

| 文件 | 原因 |
|------|------|
| `models/sms_record.py` | 被 email_verification_code.py 替代 |

### 数据库表结构完整定义

参考架构文档 `_bmad-output/planning-artifacts/architecture/architecture.md` 的 "Data Architecture" 章节。

**关键表结构变更摘要：**

```python
# users 表变更
email = Column(String(128), unique=True, nullable=False)  # 替代 phone
# openid 字段移除
password_hash = Column(String(256), nullable=True)  # 新增
role = Column(Enum("user", "member", "distributor", "agent"), ...)  # 加 member
status = Column(Enum("pending", "active", "rejected"), server_default="active", ...)  # 默认 active

# invite_codes 表变更
# target_role 字段移除
used_at = Column(DateTime, nullable=True)  # 新增

# 新增 email_verification_codes 表
# 字段: id, email, code, scene, verified, expires_at, created_at
# 索引: idx_email_scene_verified (email, scene, verified, expires_at)

# 新增 recharges 表
# 字段: id, user_id, amount, target_role, status, reject_reason, reviewed_by, reviewed_at, created_at

# 新增 licenses 表
# 字段: id, code, user_id, email, source, source_id, status, activated_at, expires_at, key_version, created_at

# commission_configs 表变更
# role 枚举加 member
# scene 更新为: recharge_888, recharge_5000, recharge_10000, followup_reward, team_bonus

# commission_records 表变更
# type 枚举加 followup_reward

# sales 表变更
# customer_phone → customer_email (VARCHAR(128))
```

### 种子数据（4 角色，14 条配置）

```python
COMMISSION_CONFIGS_SEED = [
    # agent (代理)
    {"role": "agent", "scene": "recharge_888", "reward_type": "fixed", "reward_value": 488.40},
    {"role": "agent", "scene": "recharge_5000", "reward_type": "fixed", "reward_value": 2750.00},
    {"role": "agent", "scene": "recharge_10000", "reward_type": "fixed", "reward_value": 5500.00},
    {"role": "agent", "scene": "followup_reward", "reward_type": "fixed", "reward_value": 133.20},
    {"role": "agent", "scene": "team_bonus", "reward_type": "percentage", "reward_value": 0.05},
    # distributor (经销商)
    {"role": "distributor", "scene": "recharge_888", "reward_type": "fixed", "reward_value": 355.20},
    {"role": "distributor", "scene": "recharge_5000", "reward_type": "fixed", "reward_value": 2000.00},
    {"role": "distributor", "scene": "recharge_10000", "reward_type": "fixed", "reward_value": 4000.00},
    {"role": "distributor", "scene": "team_bonus", "reward_type": "percentage", "reward_value": 0.04},
    # member (888会员)
    {"role": "member", "scene": "recharge_888", "reward_type": "fixed", "reward_value": 177.60},
    # user (普通用户)
    {"role": "user", "scene": "recharge_888", "reward_type": "fixed", "reward_value": 177.60},
]
```

### 测试要求

**必须更新的测试：**
- `tests/conftest.py` — 更新 fixture 适配新表结构
- `tests/test_security.py` — 更新 User 创建（email 替代 phone）
- `tests/test_auth_service.py` — 更新 MockAuthService（email 替代 phone）
- `tests/test_schemas.py` — 更新 schema（email 替代 phone）
- `tests/test_auth_api.py` — 更新 API 测试（email 替代 phone）

**新增测试：**
- `tests/test_models.py` — 验证所有新模型可正确创建/查询
- 验证 email_verification_codes, recharges, licenses, invite_codes（无 target_role）表

**测试原则：** 避免"为了通过而通过"的代码逻辑。测试应验证真实的业务约束（如 email 唯一性、role 枚举值、business_id 幂等性）。

## Tasks

1. 创建新模型文件（8 个）
2. 修改现有模型文件（user.py, commission_record.py, __init__.py）
3. 删除 sms_record.py
4. 创建 003_refactor_models_v2.py 迁移脚本（drop 旧表 → create 新表）
5. 创建 004_seed_commission_configs_v2.py 种子数据迁移
6. 更新 tests/conftest.py 适配新表结构
7. 更新现有测试（5 个文件）适配 email 字段
8. 新增 tests/test_models.py 验证新模型
9. 运行 `alembic upgrade head` 和 `alembic downgrade base` 验证迁移
10. 运行 `pytest` 确保所有测试通过

## Dependencies

- Epic 1 已完成（数据库迁移 001/002 可正常执行）
- 无外部依赖（纯数据库重构）

## Definition of Done

- [ ] 所有新模型文件创建完成
- [ ] 现有模型文件修改完成
- [ ] sms_record.py 已删除
- [ ] 迁移脚本 003/004 可正确执行（upgrade + downgrade）
- [ ] 种子数据 11 条佣金配置插入成功
- [ ] 所有现有测试更新并通过
- [ ] 新增 test_models.py 测试通过
- [ ] `pytest` 全部通过（含新测试）
