# Story 1.4: 佣金引擎骨架与认证策略

Status: review

## Story

As a 开发者,
I want 搭建佣金引擎骨架和 AUTH_MODE 策略模式,
so that Epic 2 的佣金相关 Story 有可依赖的基础架构。

## Acceptance Criteria

1. `services/commission_service.py` 包含 `CommissionEngine` 类骨架（calculate → record → log 流水线）
2. `services/commission_service.py` 包含 `record_commission(user_id, amount, type, source_user_id, business_id)` 方法（含 INSERT ON DUPLICATE KEY 幂等保护）
3. `core/security.py` 包含 `get_auth_service()` 工厂函数，根据 `AUTH_MODE` 返回 MockAuthService 或 WechatAuthService
4. `services/audit_service.py` 包含 `log(action, operator_type, target_type, target_id, old_value, new_value, business_id)` 方法
5. 以上骨架可通过单元测试验证（无需完整业务逻辑）

## Tasks / Subtasks

- [x] Task 1: 创建 CommissionEngine 骨架 (AC: 1)
  - [x] 创建 `backend/app/services/commission_service.py`
  - [x] 定义 `CommissionEngine` 类，包含三个空方法骨架：
    - `calculate(user_id, scene, context)` — 返回占位 dict
    - `record(user_id, amount, commission_type, source_user_id, business_id, db)` — 调用 record_commission
    - `log_audit(...)` — 调用 audit_service.log
  - [x] 类初始化接收 db session

- [x] Task 2: 实现 record_commission 幂等保护 (AC: 2)
  - [x] 在 `commission_service.py` 中实现 `record_commission(user_id, amount, commission_type, source_user_id, business_id, db)` 函数
  - [x] 使用 INSERT ... ON DUPLICATE KEY UPDATE 或事务内 SELECT + INSERT 实现幂等
  - [x] business_id 已存在时返回 None（不重复记账）
  - [x] 成功时返回 CommissionRecord 实例

- [x] Task 3: 确认 get_auth_service 工厂函数 (AC: 3)
  - [x] 确认 `backend/app/services/auth_service.py` 中 `get_auth_service()` 已存在
  - [x] 验证 `AUTH_MODE=mock` → MockAuthService, `AUTH_MODE=wechat` → WechatAuthService
  - [x] 无需新增代码，仅确认现有实现满足需求

- [x] Task 4: 创建 AuditService (AC: 4)
  - [x] 创建 `backend/app/services/audit_service.py`
  - [x] 实现 `AuditService.log(action, operator_type, target_type, target_id, old_value, new_value, business_id, db)` 方法
  - [x] 写入 audit_logs 表
  - [x] old_value / new_value 以 JSON 字符串存储

- [x] Task 5: 编写单元测试 (AC: 5)
  - [x] `tests/test_commission_service.py` — 测试 record_commission 幂等（相同 business_id 不重复插入）
  - [x] `tests/test_audit_service.py` — 测试 AuditService.log 写入 audit_logs 表
  - [x] `tests/test_auth_service.py` — 已有 get_auth_service 测试，确认通过

## Dev Notes

### 当前代码状态

**`backend/app/services/`** — 仅有 `auth_service.py` 和 `__init__.py`。需新增 `commission_service.py` 和 `audit_service.py`。

**`backend/app/services/auth_service.py`** — `get_auth_service()` 已存在（第 105-108 行），根据 `settings.AUTH_MODE` 返回对应服务。**Task 3 无需新增代码。**

**`backend/app/models/`** — 已有 User, SmsRecord, AdminUser。需确认 `commission_records` 和 `audit_logs` 表已在 Alembic 迁移中定义。

**`backend/app/core/security.py`** — 已有 `create_access_token`, `decode_access_token`, `get_current_user`, `get_current_admin`。JWT 中间件完整。

### 架构要求

**分层架构：** routers → services → models。CommissionEngine 和 AuditService 属于 services 层，被 API routers 调用。

**数据库表（已在 001_create_all_tables.py 中定义）：**

```sql
-- commission_records
CREATE TABLE commission_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    commission_type VARCHAR(32) NOT NULL COMMENT 'first_reward|sale_commission|team_bonus|recommend',
    source_user_id INT COMMENT '来源用户ID',
    business_id VARCHAR(128) NOT NULL UNIQUE COMMENT '幂等键',
    status VARCHAR(16) DEFAULT 'booked',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- audit_logs
CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(64) NOT NULL,
    operator_type VARCHAR(32) NOT NULL COMMENT 'system|admin|user',
    operator_id INT,
    target_type VARCHAR(32) NOT NULL,
    target_id INT,
    old_value JSON,
    new_value JSON,
    business_id VARCHAR(128),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 关键实现细节

**幂等保护模式：**
```python
def record_commission(user_id, amount, commission_type, source_user_id, business_id, db):
    # SQLite 兼容方案：先查后插（事务内）
    existing = db.query(CommissionRecord).filter(
        CommissionRecord.business_id == business_id
    ).first()
    if existing:
        return None  # 幂等：已存在，不重复记账
    
    record = CommissionRecord(
        user_id=user_id,
        amount=amount,
        commission_type=commission_type,
        source_user_id=source_user_id,
        business_id=business_id,
    )
    db.add(record)
    db.flush()
    return record
```

**注意：** MySQL 生产环境使用 `INSERT ... ON DUPLICATE KEY UPDATE`，SQLite 测试环境使用 SELECT + INSERT 事务方案。两者均满足幂等要求。

**AuditService 签名：**
```python
class AuditService:
    @staticmethod
    def log(action, operator_type, target_type, target_id, old_value, new_value, business_id, db):
        import json
        entry = AuditLog(
            action=action,
            operator_type=operator_type,
            target_type=target_type,
            target_id=target_id,
            old_value=json.dumps(old_value) if old_value else None,
            new_value=json.dumps(new_value) if new_value else None,
            business_id=business_id,
        )
        db.add(entry)
        db.flush()
        return entry
```

### 测试要求

- 使用 SQLite 内存数据库（conftest.py 已配置）
- 测试幂等：两次调用 record_commission 相同 business_id，第二次返回 None
- 测试 AuditService.log 正确写入 audit_logs 表
- 确认 get_auth_service 测试通过（已有 test_auth_service.py）

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/commission_service.py` | NEW | CommissionEngine 骨架 + record_commission |
| `backend/app/services/audit_service.py` | NEW | AuditService.log |
| `backend/app/models/commission_record.py` | NEW | CommissionRecord ORM |
| `backend/app/models/audit_log.py` | NEW | AuditLog ORM |
| `backend/app/models/__init__.py` | UPDATE | 导出新模型 |
| `backend/tests/test_commission_service.py` | NEW | 幂等测试 |
| `backend/tests/test_audit_service.py` | NEW | 审计日志测试 |
| `backend/tests/conftest.py` | UPDATE | 导入新模型 |

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

## Change Log

## Status

ready-for-dev
