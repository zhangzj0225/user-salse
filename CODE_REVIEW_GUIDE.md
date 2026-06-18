# Code Review Guide — Story 2.1 数据库模型重构

> 本文档供代码审查者参考，说明本次提交的变更范围、审查重点和需求匹配验证清单。

## 提交信息

- **Commit**: `3223f50`
- **Story**: 2.1 数据库模型重构
- **测试**: 103 passed
- **文件变更**: 35 files changed, 3512 insertions(+), 916 deletions(-)

## 需求背景

PRD v2 进行了重大架构调整，本提交是重构的第一步——数据库模型层：

1. **邮箱注册替代微信 OAuth** — phone→email, 移除 openid
2. **邀请码统一类型** — 移除 target_role, 新增 used_at
3. **角色由充值决定** — 新增 member 角色（4 角色：user/member/distributor/agent）
4. **License 对接** — 新增 licenses 表，供舆情系统验证
5. **场景 A/B 分离** — 额度销售（场景A）不产生佣金，推荐充值（场景B）产生佣金
6. **长期奖励仅限直接下级** — 不穿透更深层级

## 审查重点

### 1. 数据库模型正确性

| 检查项 | 文件 | 预期 |
|--------|------|------|
| users.email UNIQUE NOT NULL | `models/user.py` | email 替代 phone |
| users.role 含 member | `models/user.py` | Enum: user, member, distributor, agent |
| users.status 默认 active | `models/user.py` | 注册即 active |
| invite_codes 无 target_role | `models/invite_code.py` | 统一类型邀请码 |
| invite_codes 有 used_at | `models/invite_code.py` | 一次性使用标记 |
| licenses.code UNIQUE | `models/license.py` | License 唯一 |
| commission_configs UNIQUE(role,scene) | `models/commission_config.py` | 防重复配置 |

### 2. 佣金配置种子数据

| 角色 | 场景 | 金额 | 来源 |
|------|------|------|------|
| agent | recharge_888 | 488.40 | 888×55% |
| agent | recharge_5000 | 2750.00 | 5000×55% |
| agent | recharge_10000 | 5500.00 | 10000×55% |
| agent | followup_reward | 133.20 | 888×15%（代理→经销商后续收益） |
| agent | team_bonus | 0.05 | 5%（仅推荐代理） |
| distributor | recharge_888 | 355.20 | 888×40% |
| distributor | recharge_5000 | 2000.00 | 5000×40% |
| distributor | recharge_10000 | 4000.00 | 10000×40% |
| distributor | team_bonus | 0.04 | 4%（推荐代理+经销商） |
| member | recharge_888 | 177.60 | 888×20% |
| user | recharge_888 | 177.60 | 888×20% |

### 3. 认证重构

| 检查项 | 预期 |
|--------|------|
| token_type | "user"（不再是 "wechat"） |
| AUTH_MODE | ["mock", "email"]（不再是 "wechat"） |
| WechatAuthService | 已重命名为 EmailAuthService |
| WECHAT_APPID/SECRET | 已从 config.py 移除 |
| SmsRecord | 已删除，替换为 EmailVerificationCode |

### 4. 迁移脚本对称性

| 检查项 | 预期 |
|--------|------|
| 003 upgrade | drop 旧表 → create 新表（13 张） |
| 003 downgrade | drop 新表 → recreate 旧表 |
| 004 upgrade | 插入 11 条种子数据 |
| 004 downgrade | 删除种子数据 |

## 需求匹配验证

### 与需求说明.md 对照

| 需求条目 | 代码实现 | 验证方法 |
|---------|---------|---------|
| 代理自销 888×55%=488.4 | commission_configs seed | 查 commission_configs 表 |
| 经销商自销 888×40%=355.2 | commission_configs seed | 查 commission_configs 表 |
| 普通用户推荐 888×20%=177.6 | commission_configs seed | 查 commission_configs 表 |
| 代理推荐代理 10000×55%=5500 | commission_configs seed | 查 commission_configs 表 |
| 经销商推荐代理 10000×40%=4000 | commission_configs seed | 查 commission_configs 表 |
| 代理发展经销商后续 133.2/个 | commission_configs seed (followup_reward) | 查 commission_configs 表 |
| 长期奖励仅限直接下级 | User.parent_id 单级 | 查 models/user.py |

### 与用户旅途说明.md 对照

| 旅途节点 | 代码实现 | 验证方法 |
|---------|---------|---------|
| 邀请码一次性使用 | InviteCode.used_by + used_at | 查 models/invite_code.py |
| 角色由充值决定 | Recharge.target_role (member/distributor/agent) | 查 models/recharge.py |
| License 对接舆情系统 | License 表 (code, user_id, email, source) | 查 models/license.py |

## 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|---------|
| test_security.py | 14 | JWT 创建/解码/验证 |
| test_auth_service.py | 15 | MockAuthService 发码/认证 |
| test_schemas.py | 10 | 请求/响应 schema 验证 |
| test_auth_api.py | 14 | 认证 API 端点 |
| test_admin_api.py | 8 | 管理员登录 API |
| test_models.py | 28 | 所有新模型 CRUD + 唯一性 |
| test_commission_service.py | 9 | 佣金引擎骨架 |
| test_audit_service.py | 3 | 审计日志 |
| test_conftest.py | 2 | 测试 fixtures |
| **合计** | **103** | — |

## 下一步计划

| Story | 内容 | 状态 |
|-------|------|------|
| 2.2 | 认证模块重构（邀请码注册流程） | ready-for-dev |
| 2.3 | 前端架构调整（移除小程序，创建 user-web） | backlog |
| 2.4 | 佣金引擎重构（场景 A/B 分离） | backlog |
