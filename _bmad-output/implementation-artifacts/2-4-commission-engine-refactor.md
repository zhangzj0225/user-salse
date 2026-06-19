---
story_id: "2.4"
story_key: "2-4-commission-engine-refactor"
epic: "2"
title: "佣金引擎重构"
status: "done"
created: "2026-06-19"
---

# Story 2.4: 佣金引擎重构

## User Story

As a 开发者,
I want 重构佣金引擎以支持场景 A/B 分离和 4 角色佣金规则,
So that 额度销售不产生佣金，推荐充值才产生佣金，且佣金计算基于数据库配置。

## Business Context

PRD v2 将佣金模型从单一场景拆分为：
- **场景 A（额度销售）**：代理/经销商消耗额度为客户开通 888 会员，**不产生佣金**
- **场景 B（推荐充值）**：下级自己充值，**产生佣金**

场景 B 佣金包含三类：
1. **首次奖励**：上级角色 × 下级充值金额 → 查表得固定金额
2. **后续收益**：代理→经销商关系，经销商推荐他人充 888，代理获 133.2 元/笔
3. **长期奖励**：仅直接下级全部收入 × 比例（延后到 Epic 5 实现，本 Story 只需预留接口）

角色体系为 4 角色：普通用户(user)、888会员(member)、经销商(distributor)、代理(agent)。

## Acceptance Criteria

### AC1: CommissionEngine.calculate() 实现场景 B 首次奖励

**Given** 下级 B（上级 A）充值 888/5000/10000
**When** 调用 `engine.calculate_first_reward(parent_user_id=A, recharge_amount=888)`
**Then** 查 A 的角色（agent/distributor/member/user）
**And** 查 commission_configs 获取 `role=A.role, scene=recharge_{amount}` 的配置
**And** 返回 `{"amount": config.reward_value, "commission_type": "first_reward", "business_id": "recharge_{recharge_id}"}`
**And** 普通用户/888会员推荐的人充 5000/10000 时返回 None（无配置 = 无佣金）

### AC2: CommissionEngine.calculate_followup_reward() 实现后续收益

**Given** 经销商 B（上级 A 是代理）推荐的下下级 C 充值 888
**When** 调用 `engine.calculate_followup_reward(agent_id=A, distributor_id=B, recharge_id=C_recharge_id)`
**Then** 查 commission_configs 获取 `role=agent, scene=followup_reward` 的配置（133.2 元）
**And** 返回 `{"amount": 133.2, "commission_type": "followup_reward", "business_id": "recharge_{C_recharge_id}_followup_{A_id}"}`
**And** 仅当 A.role == "agent" 且 B.role == "distributor" 时才计算，否则返回 None

### AC3: CommissionEngine.calculate_long_term_reward() 预留接口

**Given** 需要长期奖励的接口骨架
**When** 调用 `engine.calculate_long_term_reward(user_id=A, period="2026-06")`
**Then** 返回 `NotImplementedError`（Epic 5 Story 5.1 实现）
**And** 方法签名已定义，供 Epic 5 调用

### AC4: get_config() 从数据库读取配置

**Given** commission_configs 表已有 11 条种子数据
**When** 调用 `engine.get_config(role="agent", scene="recharge_888")`
**Then** 返回 CommissionConfig 对象（reward_type="fixed", reward_value=488.40）
**And** 配置不存在时返回 None（不抛异常，由调用方判断）

### AC5: 场景 A 不产生佣金

**Given** 代理/经销商用额度销售（场景 A）
**When** 调用佣金引擎
**Then** 不产生任何 CommissionRecord
**And** 场景 A 的佣金计算在调用方（Story 3.7）处理，佣金引擎不提供场景 A 的计算方法

### AC6: record() 保持幂等保护

**Given** 已有 record_commission() 函数和 CommissionEngine.record() 方法
**When** 相同 business_id 重复调用
**Then** 返回 None，不创建重复记录
**And** 现有测试全部通过

### AC7: process_recharge() 集成方法

**Given** 管理员批准了一笔充值
**When** 调用 `engine.process_recharge(recharge_id, recharger_user_id, amount)`
**Then** 查找充值人的直接上级（parent_id）
**And** 若上级存在：计算并记账首次奖励（AC1）
**And** 若上级是代理且充值人是经销商：不在此处处理后续收益（后续收益在经销商的**下级**充值时触发，见 AC2）
**And** 普通用户/888会员推荐的人充 5000/10000：get_config 返回 None，跳过记账
**And** 无上级（parent_id is None）：跳过所有佣金记账
**And** 所有记账使用幂等保护

### AC8: 单元测试覆盖所有场景

**Given** 佣金引擎重构完成
**When** 运行测试
**Then** 覆盖以下场景：
- 首次奖励：4 角色 × 3 充值金额（agent/distributor 有 3 种，member/user 只有 888）
- 后续收益：代理→经销商 133.2 元，其他关系返回 None
- 幂等保护：重复 business_id 不重复记账
- get_config：存在/不存在的配置
- process_recharge：有上级/无上级/无配置/代理+经销商
- 长期奖励：返回 NotImplementedError
**And** 全部测试通过

## Technical Requirements

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/commission_service.py` | UPDATE | 重构 CommissionEngine，新增 calculate_first_reward / calculate_followup_reward / calculate_long_term_reward / get_config / process_recharge |
| `backend/tests/test_commission_service.py` | UPDATE | 新增测试覆盖 AC1-AC8，保留现有幂等测试 |

### 佣金规则参考（种子数据 004_seed_commission_configs_v2.py）

| role | scene | reward_type | reward_value | 说明 |
|------|-------|------------|-------------|------|
| agent | recharge_888 | fixed | 488.40 | 代理推荐充 888 |
| agent | recharge_5000 | fixed | 2750.00 | 代理推荐充 5000 |
| agent | recharge_10000 | fixed | 5500.00 | 代理推荐充 10000 |
| agent | followup_reward | fixed | 133.20 | 代理从经销商下级获得 |
| agent | team_bonus | percentage | 0.05 | 长期奖励（Epic 5） |
| distributor | recharge_888 | fixed | 355.20 | 经销商推荐充 888 |
| distributor | recharge_5000 | fixed | 2000.00 | 经销商推荐充 5000 |
| distributor | recharge_10000 | fixed | 4000.00 | 经销商推荐充 10000 |
| distributor | team_bonus | percentage | 0.04 | 长期奖励（Epic 5） |
| member | recharge_888 | fixed | 177.60 | 888会员推荐充 888 |
| user | recharge_888 | fixed | 177.60 | 普通用户推荐充 888 |

### business_id 命名规则

| 佣金类型 | business_id 格式 | 示例 |
|---------|-----------------|------|
| first_reward | `recharge_{recharge_id}` | `recharge_42` |
| followup_reward | `recharge_{recharge_id}_followup_{agent_id}` | `recharge_42_followup_7` |
| team_bonus (Epic 5) | `settle_{user_id}_{YYYYMM}` | `settle_7_202606` |

### 关键设计决策

1. **场景 A 不进入佣金引擎** — 额度销售在 Story 3.7 的 SaleService 中处理，不调用 CommissionEngine
2. **process_recharge 只处理首次奖励** — 后续收益在经销商的下级充值时触发（需要额外判断链路），本 Story 只提供 `calculate_followup_reward()` 方法供 Story 3.8 调用
3. **长期奖励延后** — `calculate_long_term_reward()` 只提供签名，Epic 5 实现
4. **get_config 返回 None 而非抛异常** — 普通用户充 5000/10000 无配置是正常业务逻辑，返回 None 让调用方跳过

### 现有代码保护

- `record_commission()` 函数保持不变（已测试，幂等）
- `CommissionEngine.record()` 方法保持不变（委托给 record_commission）
- `CommissionEngine.log_audit()` 方法保持不变
- 现有 9 个测试必须全部通过

## Architecture Compliance

- 使用 SQLAlchemy ORM 查询 commission_configs
- 错误消息使用中文（对齐 PRD）
- 审计日志通过 AuditService.log() 写入
- 幂等保护通过 business_id UNIQUE 约束

## Testing Requirements

- 测试框架：pytest + SQLite in-memory
- 测试文件：`backend/tests/test_commission_service.py`
- 保留现有 TestRecordCommission 和 TestCommissionEngine 类
- 新增测试类：TestCalculateFirstReward, TestCalculateFollowupReward, TestGetConfig, TestProcessRecharge

## Previous Story Intelligence

- Story 2.1 已完成数据库模型重构，commission_configs 表有 11 条种子数据
- Story 2.2 已完成认证模块重构，User 模型有 parent_id 字段用于查上级
- 现有 `record_commission()` 函数已有幂等保护，无需重新实现
- CommissionEngine.calculate() 当前是 NotImplementedError，需要替换为真实实现
