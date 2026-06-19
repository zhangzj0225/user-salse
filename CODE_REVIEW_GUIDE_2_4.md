# Story 2.4 佣金引擎重构 — Code Review 指南

## 变更概述

将佣金引擎从 `NotImplementedError` 骨架重构为完整实现，支持 PRD v2 的场景 A/B 分离和 4 角色佣金规则。

## 变更文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/commission_service.py` | UPDATE | 重构 CommissionEngine，新增 5 个方法 |
| `backend/tests/test_commission_service.py` | UPDATE | 新增 32 个测试（保留原 9 个） |

## 新增方法

| 方法 | AC | 说明 |
|------|-----|------|
| `get_config(role, scene)` | AC4 | 从 DB 读取佣金配置，不存在返回 None |
| `calculate_first_reward(parent_user_id, recharge_amount, recharge_id)` | AC1 | 场景 B 首次奖励，4 角色 × 3 金额查表 |
| `calculate_followup_reward(agent_id, distributor_id, recharge_id)` | AC2 | 后续收益，代理→经销商 133.2 元/笔 |
| `calculate_long_term_reward(user_id, period)` | AC3 | 长期奖励预留接口，抛 NotImplementedError |
| `process_recharge(recharge_id, recharger_user_id, amount)` | AC7 | 充值确认后集成方法：查上级 → 计算首次奖励 → 记账 |

## 佣金规则对照（PRD 对齐验证）

### 首次奖励（场景 B，下级充值时上级获得）

| 上级角色 | 下级充 888 | 下级充 5000 | 下级充 10000 |
|---------|-----------|------------|-------------|
| 代理 (agent) | 488.40 | 2750.00 | 5500.00 |
| 经销商 (distributor) | 355.20 | 2000.00 | 4000.00 |
| 888会员 (member) | 177.60 | 无（返回 None） | 无（返回 None） |
| 普通用户 (user) | 177.60 | 无（返回 None） | 无（返回 None） |

### 后续收益

| 关系 | 金额 | business_id 格式 |
|------|------|-----------------|
| 代理 ← 经销商的下级充 888 | 133.20 | `recharge_{id}_followup_{agent_id}` |

### 长期奖励（Epic 5 实现）

| 上级角色 | 下级角色 | 比例 |
|---------|---------|------|
| 代理 | 代理 | 5% |
| 经销商 | 代理/经销商 | 4% |
| 代理 | 经销商 | 不适用（已由 133.2 元/笔替代） |

## 关键设计决策

1. **场景 A 不进入佣金引擎** — 额度销售在 Story 3.7 的 SaleService 中处理
2. **`get_config` 返回 None 而非抛异常** — 普通用户充 5000/10000 无配置是正常业务逻辑
3. **`process_recharge` 只处理首次奖励** — 后续收益需额外判断链路，由 Story 3.8 调用 `calculate_followup_reward()`
4. **`amount` 入口校验** — `process_recharge` 校验 `amount in (888, 5000, 10000)`，非法值跳过

## Code Review 发现及修复

| # | 级别 | 问题 | 修复状态 |
|---|------|------|---------|
| MF-1 | 🔴 | `record_commission` TOCTOU 竞态（预存技术债） | 延后到 Story 3.9 |
| SF-1 | 🟡 | `process_recharge` 不校验 amount | ✅ 已修复 |
| SF-2 | 🟡 | amount 与 recharge_id 一致性 | ✅ 文档标注 |
| SF-3 | 🟡 | source_user_id 不一致 | ✅ 统一文档 |
| SF-4 | 🟡 | 日志触发懒加载 | ✅ 已修复 |
| SF-5 | 🟡 | member 充 10000 未测试 | ✅ 已补充 |
| SF-6 | 🟡 | 代理+经销商场景未测试 | ✅ 已补充 |
| SF-7 | 🟡 | 5000/10000 集成未测试 | ✅ 已补充 |
| NT-3 | 🔵 | user_id 断言缺失 | ✅ 已补充 |

## 测试覆盖

- **总计 154 个测试通过**（原 123 + 本次新增 31）
- 佣金引擎测试：41 个（原 9 + 新增 32）
- 覆盖：4 角色 × 3 金额、后续收益、幂等、get_config、process_recharge 全路径

## 验证命令

```bash
cd backend
python -m pytest tests/test_commission_service.py -v
python -m pytest tests/ --tb=short
```
