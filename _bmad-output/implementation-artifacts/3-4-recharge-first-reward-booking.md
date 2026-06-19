---
story_id: "3.4"
story_key: "3-4-recharge-first-reward-booking"
epic: "Epic 3 — 核心业务闭环"
epic_id: "3"
title: "充值首次奖励记账"
status: "ready-for-dev"
priority: "high"
depends_on:
  - "2-4-commission-engine-refactor (CommissionEngine.process_recharge 已实现 + migration 004 种子数据已创建)"
  - "3-3-recharge-application-and-review (approve_recharge 调用 process_recharge，是集成入口)"
blocks:
  - "3-8-recharge-commission-scenario-b (场景 B 完整佣金依赖种子数据正确)"
  - "3-10-earnings-dashboard (收益展示依赖正确的佣金记录)"
---

# Story 3.4: 充值首次奖励记账

## User Story

As a 系统,
I want 在充值确认后自动记账上级的首次奖励,
So that 上级能实时看到推荐收益。

## Acceptance Criteria

- **AC1（查配置记账）**: 管理员批准了用户 B 的充值（B 通过 A 的邀请码注册），充值确认完成后，系统查 `commission_configs` 获取规则（`role=A 的角色`, `scene=recharge_{B 的充值金额}`）
- **AC2（首次奖励记账）**: 记账首次奖励：`business_id = "recharge_{B 的 recharge_id}"`, `amount = config.reward_value`
- **AC3（佣金记录与审计）**: 佣金记录 `type=first_reward`，写入 `audit_logs`（action=`commission_create`）
- **AC4（无佣金场景）**: 普通用户/888 会员推荐的人充 5000/10000 不产生佣金（`commission_configs` 表中无对应配置，`get_config` 返回 None）
- **AC5（幂等保护）**: 同一笔充值不会重复记账（`business_id` UNIQUE 约束 + 预查机制）
- **AC6（后续收益 — 已由 Story 2.4 实现）**: 充 888 时，若充值人上级是经销商、经销商上级是代理，代理获得 133.2 元/笔后续收益（`scene=followup_reward`, `business_id = "recharge_{recharge_id}_followup_{agent_id}"`）

## Technical Requirements

### 核心说明：本 Story 的职责边界

> ⚠️ **关键**: `CommissionEngine.process_recharge()` 已在 Story 2.4 完整实现（含首次奖励 + 后续收益计算）。`commission_configs` 种子数据已由 migration 004 创建。本 Story 的职责是：
> 1. **验证种子数据正确性** — 确保 migration 004 的 11 条配置与 PRD 规则一致
> 2. **编写集成测试** — 通过 `RechargeService.approve_recharge()` → `CommissionEngine.process_recharge()` 端到端验证 AC
> 3. **不重新实现** `process_recharge` 或佣金计算逻辑

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/alembic/versions/004_seed_commission_configs_v2.py` | VERIFY | 种子数据迁移已存在（Story 2.4 创建），本 Story 验证 11 条配置与 PRD 一致 |
| `backend/tests/test_commission_seed_data.py` | NEW | 种子数据一致性测试：验证 11 条配置值与 PRD 规则匹配，防止测试 helper 与 migration 数据漂移 |
| `backend/tests/test_recharge_commission_integration.py` | NEW | 集成测试：通过 `approve_recharge` → `process_recharge` 端到端验证首次奖励记账 |

> **注意**: `backend/app/services/commission_service.py`（Story 2.4）、`backend/app/models/commission_config.py`（Story 2.1）、`backend/app/services/recharge_service.py`（Story 3.3）已存在且无需修改。`backend/tests/test_commission_service.py` 已有完整的 CommissionEngine 单元测试（直接调用 process_recharge），本 Story 新增集成测试层（通过 approve_recharge 间接调用）。

### 种子数据结构（migration 004）

`commission_configs` 表共 11 条配置，覆盖首次奖励（8 条）、后续收益（1 条）、长期奖励（2 条，Epic 5 使用）：

#### 首次奖励（scene = `recharge_{amount}`）

| role | scene | reward_type | reward_value | 说明 |
|------|-------|-------------|--------------|------|
| agent | recharge_888 | fixed | 488.4000 | 代理推荐的人充 888 |
| agent | recharge_5000 | fixed | 2750.0000 | 代理推荐的人充 5000 |
| agent | recharge_10000 | fixed | 5500.0000 | 代理推荐的人充 10000 |
| distributor | recharge_888 | fixed | 355.2000 | 经销商推荐的人充 888 |
| distributor | recharge_5000 | fixed | 2000.0000 | 经销商推荐的人充 5000 |
| distributor | recharge_10000 | fixed | 4000.0000 | 经销商推荐的人充 10000 |
| member | recharge_888 | fixed | 177.6000 | 888会员推荐的人充 888 |
| user | recharge_888 | fixed | 177.6000 | 普通用户推荐的人充 888 |

#### 后续收益（scene = `followup_reward`）

| role | scene | reward_type | reward_value | 说明 |
|------|-------|-------------|--------------|------|
| agent | followup_reward | fixed | 133.2000 | 代理的直接下级经销商推荐他人充 888 |

#### 长期奖励（scene = `team_bonus`，Epic 5 使用）

| role | scene | reward_type | reward_value | 说明 |
|------|-------|-------------|--------------|------|
| agent | team_bonus | percentage | 0.0500 | 代理→代理 5% |
| distributor | team_bonus | percentage | 0.0400 | 经销商→代理/经销商 4% |

#### 无佣金场景（刻意不创建配置）

| 上级角色 | 充值金额 | 原因 |
|---------|---------|------|
| user | 5000 | 普通用户推荐充 5000 不产生佣金 |
| user | 10000 | 普通用户推荐充 10000 不产生佣金 |
| member | 5000 | 888会员推荐充 5000 不产生佣金 |
| member | 10000 | 888会员推荐充 10000 不产生佣金 |

> `get_config(role, scene)` 查不到配置时返回 `None`，`calculate_first_reward` 返回 `None`，`process_recharge` 跳过记账。

### 佣金配置表结构（`commission_configs`）

```sql
CREATE TABLE commission_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role ENUM('user', 'member', 'distributor', 'agent') NOT NULL,
    scene VARCHAR(32) NOT NULL,
    reward_type ENUM('fixed', 'percentage') NOT NULL,
    reward_value DECIMAL(10, 4) NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (role, scene)
);
```

- `role` + `scene` 联合唯一约束（`uq_commission_configs_role_scene`）
- `reward_value` 精度 DECIMAL(10,4)：固定金额存完整值（488.4000），比例存小数（0.0500）

### business_id 格式

| 佣金类型 | business_id 格式 | 示例 |
|---------|-----------------|------|
| 首次奖励 | `recharge_{recharge_id}` | `recharge_100` |
| 后续收益 | `recharge_{recharge_id}_followup_{agent_id}` | `recharge_400_followup_5` |

## Developer Context

### 架构合规要求

1. **三层分层**: 本 Story 不新增 service/router，仅新增测试文件。测试遵循 `conftest.py` 的 `db_session`（SQLite 内存 + 事务回滚）fixture。
2. **种子数据一致性**: 测试中使用的 `_seed_commission_configs(db)` helper（`test_commission_service.py` 已定义）必须与 migration 004 的数据一致。本 Story 新增数据一致性测试锁定此契约。
3. **事务约定**: `process_recharge` 只 flush 不 commit，由 `approve_recharge` 末尾统一 commit。集成测试必须验证 commit 后佣金记录持久化。

### 已有代码模式（必须遵循）

#### CommissionEngine.process_recharge()（已实现，Story 2.4）

```python
# backend/app/services/commission_service.py
class CommissionEngine:
    def __init__(self, db: Session): ...

    def get_config(self, role: str, scene: str) -> CommissionConfig | None:
        """从数据库读取佣金配置。配置不存在返回 None。"""

    def calculate_first_reward(
        self, parent_user_id: int, recharge_amount: int, recharge_id: int,
        source_user_id: int | None = None,
    ) -> dict | None:
        """计算首次奖励。scene = f"recharge_{recharge_amount}"。
        无配置返回 None（普通用户/888会员 × 5000/10000）。"""

    def calculate_followup_reward(
        self, recharge_id: int, recharger_user_id: int,
    ) -> dict | None:
        """计算后续收益。仅充 888 且链路 C→B(经销商)→A(代理) 时触发。
        scene = "followup_reward", role = "agent"。"""

    def process_recharge(
        self, recharge_id: int, recharger_user_id: int, amount: int,
    ) -> list[CommissionRecord]:
        """充值确认后的佣金处理（首次奖励 + 后续收益）。
        ⚠️ 只 flush 不 commit，调用方必须 commit。
        ⚠️ amount 必须是 int（非 float/bool），且与 recharges 记录一致。"""

    def record(
        self, user_id: int, amount: Decimal, commission_type: str,
        source_user_id: int | None, business_id: str,
    ) -> CommissionRecord | None:
        """记账（幂等：business_id UNIQUE + 预查 + IntegrityError 降级）。"""
```

#### CommissionConfig 模型（`backend/app/models/commission_config.py`，已存在，无需修改）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| role | Enum(user/member/distributor/agent) | 角色 |
| scene | String(32) | 场景：recharge_888/recharge_5000/recharge_10000/followup_reward/team_bonus |
| reward_type | Enum(fixed/percentage) | 奖励类型 |
| reward_value | DECIMAL(10,4) | 奖励值（固定金额或比例） |
| updated_at | DateTime | 更新时间（自动） |
| | UniqueConstraint | (role, scene) 联合唯一 |

#### RechargeService.approve_recharge()（已实现，Story 3.3）

```python
# backend/app/services/recharge_service.py
# approve_recharge 流程中调用佣金记账：
engine = CommissionEngine(db)
records = engine.process_recharge(
    recharge_id=recharge.id,
    recharger_user_id=user.id,
    amount=int(recharge.amount),  # DECIMAL → int
)
# ⚠️ 不在此 commit，由 approve_recharge 末尾统一 commit
```

#### record_commission 幂等机制（已实现）

```python
# 幂等三层保护：
# 1. 预查：db.query(CommissionRecord).filter(business_id == ...).first()
# 2. UNIQUE 约束：commission_records.business_id UNIQUE
# 3. IntegrityError 降级：并发竞态时 rollback + 重查返回 None
```

### 关键依赖接口

#### _seed_commission_configs 测试 helper（`test_commission_service.py` 已定义）

```python
def _seed_commission_configs(db):
    """Seed the 11 commission configs matching migration 004."""
    configs = [
        ("agent", "recharge_888", "fixed", 488.40),
        ("agent", "recharge_5000", "fixed", 2750.00),
        ("agent", "recharge_10000", "fixed", 5500.00),
        ("agent", "followup_reward", "fixed", 133.20),
        ("agent", "team_bonus", "percentage", 0.05),
        ("distributor", "recharge_888", "fixed", 355.20),
        ("distributor", "recharge_5000", "fixed", 2000.00),
        ("distributor", "recharge_10000", "fixed", 4000.00),
        ("distributor", "team_bonus", "percentage", 0.04),
        ("member", "recharge_888", "fixed", 177.60),
        ("user", "recharge_888", "fixed", 177.60),
    ]
    for role, scene, rtype, rval in configs:
        db.add(CommissionConfig(role=role, scene=scene, reward_type=rtype, reward_value=rval))
    db.flush()
```

> 本 helper 与 migration 004 数据必须完全一致。Story 3.4 新增数据一致性测试锁定此契约。

### 依赖关系说明

#### 与 Story 2.4（佣金引擎重构）的关系

- **Story 2.4 的职责**: 实现 `CommissionEngine`（process_recharge、calculate_first_reward、calculate_followup_reward、record_commission）+ 创建 migration 004 种子数据。
- **Story 3.4 的职责**: 验证 migration 004 种子数据正确性 + 编写集成测试证明 AC 满足。
- **解耦方式**: 引擎和种子数据已就绪，3.4 是验证层，不修改引擎代码。

#### 与 Story 3.3（充值申请与审核）的关系

- **Story 3.3 的职责**: `approve_recharge` 中调用 `CommissionEngine.process_recharge()`，触发佣金记账流程。
- **Story 3.4 的职责**: 确保种子数据正确，使 `process_recharge` 内部能查到规则并记账。佣金金额正确性由 3.4 保证。
- **解耦方式**: `process_recharge` 接口已实现，内部查表无配置时返回空列表（幂等无操作）。3.3 测试只验证"调用了接口、无异常"，不验证佣金金额。3.4 的集成测试验证佣金金额正确。
- **顺序**: 3.3 和 3.4 可并行开发。3.3 不阻塞于 3.4。

#### 与 Story 3.8（推荐充值佣金场景 B）的关系

- Story 3.8 是场景 B 的完整实现（首次奖励 + 后续收益 + 审计），依赖 3.4 种子数据正确。
- 3.4 的后续收益测试为 3.8 提供基础。

#### 与 Story 3.9（佣金配置与幂等保护）的关系

- Story 3.9 关注 `get_config` 查询接口 + 幂等保护机制（已在 Story 2.4 实现）。
- 3.4 关注种子数据值正确性 + 端到端 AC 验证。两者互补。

### 注意事项

1. **不重新实现 process_recharge**: 该方法已在 Story 2.4 完整实现并通过单元测试。3.4 仅验证种子数据 + 集成测试。
2. **migration 004 已存在**: 创建于 2026-06-18（Story 2.4），down_revision='003'，链路 001→002→003→004→005 完整。3.4 验证其数据正确性，不新建迁移。
3. **测试 helper 数据漂移风险**: `_seed_commission_configs` 与 migration 004 必须一致。数据一致性测试锁定此契约，防止后续修改时漂移。
4. **amount 类型一致性**: `process_recharge` 要求 amount 为 int。`approve_recharge` 传参 `int(recharge.amount)`（DECIMAL→int）。
5. **后续收益触发条件**: 仅充 888 且链路 C→B(经销商)→A(代理) 时触发。充 5000/10000 不触发后续收益。
6. **幂等 business_id**: 首次奖励 `recharge_{id}`，后续收益 `recharge_{id}_followup_{agent_id}`。UNIQUE 约束保证不重复。

## Testing Requirements

### 测试框架

- 使用 pytest，遵循 `conftest.py` 中的 `db_session`（SQLite 内存 + 事务回滚）和 `client`（TestClient + DB 覆盖）fixture。
- 测试文件参考 `test_commission_service.py` 的组织方式（class 分组、`_seed_commission_configs` helper、`_make_user` helper）。
- 已有 `test_commission_service.py` 覆盖 CommissionEngine 单元测试（process_recharge 直接调用），本 Story 新增集成测试（通过 approve_recharge 间接调用）。

### 种子数据一致性测试（`test_commission_seed_data.py`）必须覆盖

| 测试用例 | 验证点 |
|---------|--------|
| test_seed_configs_count | `_seed_commission_configs` 写入 11 条配置 |
| test_first_reward_configs_match_prd | 首次奖励 8 条配置值与 PRD 一致（agent 488.4/2750/5500, distributor 355.2/2000/4000, member 177.6, user 177.6） |
| test_followup_reward_config_matches_prd | 后续收益配置 (agent, followup_reward, fixed, 133.20) |
| test_team_bonus_configs_match_prd | 长期奖励配置 (agent 5%, distributor 4%) |
| test_no_config_for_user_member_high_amount | user/member × recharge_5000/10000 无配置（get_config 返回 None） |
| test_seed_helper_matches_migration_004 | `_seed_commission_configs` 数据与 migration 004 的 bulk_insert 数据一致 |

### 集成测试（`test_recharge_commission_integration.py`）必须覆盖

| 测试用例 | 验证点 |
|---------|--------|
| test_approve_recharge_888_agent_parent_commission | 代理上级 + 充 888 → 首次奖励 488.40，business_id=`recharge_{id}`，type=first_reward |
| test_approve_recharge_5000_agent_parent_commission | 代理上级 + 充 5000 → 首次奖励 2750.00 |
| test_approve_recharge_10000_agent_parent_commission | 代理上级 + 充 10000 → 首次奖励 5500.00 |
| test_approve_recharge_888_distributor_parent_commission | 经销商上级 + 充 888 → 首次奖励 355.20 |
| test_approve_recharge_888_member_parent_commission | 888会员上级 + 充 888 → 首次奖励 177.60 |
| test_approve_recharge_888_user_parent_commission | 普通用户上级 + 充 888 → 首次奖励 177.60 |
| test_approve_recharge_5000_user_parent_no_commission | 普通用户上级 + 充 5000 → 无佣金记录（AC4） |
| test_approve_recharge_10000_member_parent_no_commission | 888会员上级 + 充 10000 → 无佣金记录（AC4） |
| test_approve_recharge_writes_audit_log | 佣金记账写入 audit_logs（action=commission_create）（AC3） |
| test_approve_recharge_idempotent | 同一笔充值重复批准不产生重复佣金（状态机拦截 + business_id 幂等）（AC5） |
| test_approve_recharge_888_followup_reward | C→B(经销商)→A(代理) + 充 888 → 首次奖励(给B 355.20) + 后续收益(给A 133.20)（AC6） |
| test_approve_recharge_5000_no_followup | 充 5000 不触发后续收益（仅有首次奖励） |
