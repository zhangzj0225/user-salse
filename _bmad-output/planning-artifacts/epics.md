---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-user-salse-2026-06-11/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture.md
  - d:/user-salse/需求说明.md
  - d:/user-salse/用户旅途说明.md
status: in-progress
completedAt: '2026-06-18'
updated: '2026-06-21'
---

# user-salse - Epic Breakdown

## Overview

本文档基于 PRD v2（2026-06-21 修订）和架构文档 v2 更新。核心变更：取消开放注册改为仅代理/经销商/管理员、邀请码改为推荐码（持久码）、佣金2档（去掉20%档）、License不绑定邮箱激活时绑定业务系统用户、新增支付小闭环App、超管创建种子用户、两系统用户独立。

## Requirements Inventory

### Functional Requirements（PRD v2, 25 FRs）

**代理/经销商认证 (FR-1~4)**
FR-1: 邮箱验证码登录 — 不提供注册页面，不创建新用户
FR-2: 邮箱即分销系统账号标识 — 终端用户在业务系统有独立账号，不在分销系统注册
FR-3: 推荐码 — 持久码，1人1码，支付时选填，HMAC签名
FR-4: 推荐码生成 — 代理/经销商创建时自动生成1个持久推荐码

**角色与支付 (FR-5~7)**
FR-5: 在线支付（场景B入口）— 支付小闭环页面，888/5000/10000三档
FR-6: 线下支付审核（管理员后台）— 管理员确认线下收款，可手动填写推荐码
FR-7: 可售额度管理 — 代理22个/经销商11个，额度耗尽可申请补购

**推荐链与团队 (FR-8~10)**
FR-8: 推荐关系记录 — 5000/10000建团队关系，888仅佣金关系不建团队关系
FR-9: 我的团队（下级树）— 仅含代理/经销商
FR-10: 我的上级链条 — 追溯到根节点

**License与额度销售 (FR-11~12)**
FR-11: 额度销售生成License（场景A）— 消耗1额度，生成未激活License，不绑定用户
FR-12: 在线支付生成License（场景B）— 888生成License，5000/10000创建账号+额度+License+推荐码

**佣金计算与收益 (FR-13~15)**
FR-13: 佣金规则配置 — 2档（55%/40%），无推荐码=无佣金，后续收益133.2元/笔
FR-14: 我的收益 — 记账余额+已提现+明细
FR-15: 长期奖励记账 — 代理→代理5%，经销商→代理/经销商4%，代理→经销商不适用

**License对接 (FR-16~17)**
FR-16: License生成 — 不绑定邮箱，激活时绑定业务系统用户标识
FR-17: License验证接口 — 供业务系统调用，验证+激活，API Key鉴权

**提现工单 (FR-18~19)**
FR-18: 提现申请 — 金额校验、冻结余额、生成工单
FR-19: 工单管理（管理员）— 确认打款或拒绝

**管理员后台 (FR-20~23)**
FR-20: 用户管理+创建种子用户 — 列表、搜索、角色筛选、详情、超管直接创建种子用户
FR-21: 支付审核 — 待审核列表、批准/拒绝
FR-22: 运营数据看板 — 数字卡片（含在线支付数据）
FR-23: 系统参数配置 — 所有参数可配，变更日志

**消息通知 (FR-24)**
FR-24: 通知 — 下级支付、佣金入账、工单状态、支付审核通过、种子用户创建

**在线支付小闭环 (FR-25)**
FR-25: 支付小闭环 — 独立支付页面，微信/支付宝扫码，888/5000/10000三档

### NonFunctional Requirements

NFR-1: 佣金记账幂等性 — business_id UNIQUE
NFR-2: 审计日志 — 不可删除
NFR-3: 推荐码安全性 — HMAC-SHA256 签名，持久码防篡改
NFR-4: License 安全性 — 防伪造、一次性使用、激活时绑定业务系统用户

### FR Coverage Map

| FR | Epic | Story | 简述 |
|----|------|-------|------|
| — | Epic 1 | 1.1~1.4 | 项目骨架与 Mock 认证（已完成） |
| — | Epic 2 | 2.1~2.4 | 架构重构与模型迁移（已完成） |
| FR-1,2 | Epic 3 | 3.1 | 邮箱验证码登录（无注册） |
| FR-3,4 | Epic 3 | 3.2 | 推荐码生成与验证（持久码） |
| FR-5,6 | Epic 3 | 3.3 | 在线支付与线下审核（角色由支付决定） |
| FR-6 | Epic 3 | 3.4 | 支付首次奖励记账 |
| FR-7 | Epic 3 | 3.5 | 可售额度管理 |
| FR-8,9,10 | Epic 3 | 3.6 | 团队树与上级链（仅代理/经销商） |
| FR-11 | Epic 3 | 3.7 | 额度销售（场景A，不产生佣金） |
| FR-12,13 | Epic 3 | 3.8 | 推荐支付佣金（场景B，2档） |
| FR-13,NFR-1,2 | Epic 3 | 3.9 | 佣金配置与幂等保护 |
| FR-14 | Epic 3 | 3.10 | 我的收益 |
| FR-16,17 | Epic 3 | 3.11 | License生成与验证（不绑定邮箱） |
| FR-18 | Epic 3 | 3.12 | 提现申请 |
| FR-19 | Epic 3 | 3.13 | 工单管理（管理员） |
| FR-20 | Epic 4 | 4.1 | 用户管理+创建种子用户 |
| FR-21 | Epic 4 | 4.2 | 支付审核（后台） |
| FR-22 | Epic 4 | 4.3 | 运营数据看板 |
| FR-23 | Epic 4 | 4.4 | 系统参数配置 |
| FR-15 | Epic 5 | 5.1 | 长期奖励定时结算 |
| FR-24 | Epic 5 | 5.2 | 消息通知 |
| FR-25 | Epic 7 | 7.1~7.3 | 支付小闭环App |
| FR-1~14,16,18 | Epic 6 | 6.1~6.5 | user-web 前端开发 |

## Epic List

### Epic 1: 项目骨架与 Mock 认证 (DONE — 需重构)
搭建三端项目骨架、数据库、Mock 认证（手机号+验证码）。已完成 4 个 Story，80 个测试通过。因 PRD v2 变更（邮箱注册、移除小程序、License 对接），需在 Epic 2 中重构。
**Stories:** 4 (all done)

### Epic 2: 架构重构与模型迁移 (NEW)
将 Epic 1 的代码重构为 PRD v2 架构：数据库模型重构（email 替代 phone、新增 licenses/recharges 表、邀请码统一类型、佣金配置 4 角色）、认证模块重构（邮箱+验证码）、前端架构调整（移除 mini-program、新增 user-web）、佣金引擎重构（场景 A/B）。
**Stories:** 4

### Epic 3: 核心业务闭环 (UPDATED for v2)
完整的业务链路：邮箱登录（无注册）→ 推荐码生成/验证（持久码）→ 支付审核（角色由支付决定）→ 团队树/上级链（仅代理/经销商）→ 额度销售（场景A）→ 推荐支付佣金（场景B，2档）→ License生成与验证（不绑定邮箱）→ 收益展示 → 提现工单。
**FRs covered:** FR-1~14, 16~19
**NFRs covered:** NFR-1, NFR-2, NFR-3, NFR-4
**Stories:** 13

### Epic 4: 管理员后台 (UPDATED for v2)
管理员 Web 端：用户管理+创建种子用户、支付审核、运营数据看板（含在线支付）、系统参数配置。
**FRs covered:** FR-20, 21, 22, 23
**Stories:** 4

### Epic 5: 长期奖励与通知 (UPDATED for v2)
APScheduler 定时结算长期团队奖励（仅直接下级，代理→经销商不适用）；关键事件推送通知。
**FRs covered:** FR-15, 24
**Stories:** 2

### Epic 6: user-web 前端开发 (UPDATED for v2)
React + Vite 用户端 Web 应用：登录（无注册）、首页、团队、收益、额度销售、License、提现。
**Stories:** 5

### Epic 7: 支付小闭环App (NEW)
独立部署的 React + Vite 支付页面，对接微信/支付宝扫码支付。支持888/5000/10000三档。
**FRs covered:** FR-25, FR-5（在线支付部分）
**Stories:** 3

---

## Epic 1: 项目骨架与 Mock 认证 (DONE)

> 已完成。4 个 Story，80 个测试通过。因 PRD v2 变更，部分代码需在 Epic 2 中重构。

### Story 1.1: 项目骨架初始化 (DONE)
### Story 1.2: Mock 用户认证 (DONE)
### Story 1.3: 管理员登录 (DONE)
### Story 1.4: 佣金引擎骨架与认证策略 (DONE)

---

## Epic 2: 架构重构与模型迁移 (NEW)

将 Epic 1 的代码重构为 PRD v2 架构。

### Story 2.1: 数据库模型重构

As a 开发者,
I want 重构数据库模型以匹配 PRD v2,
So that 后续业务开发基于正确的数据结构。

**Acceptance Criteria:**

**Given** Epic 1 已完成的数据库迁移
**When** 执行模型重构
**Then** `users` 表：`phone` → `email`，`openid` 字段移除，`role` 枚举增加 `member`（888会员）
**And** `invite_codes` 表：移除 `target_role` 字段，邀请码为统一类型
**And** 新增 `recharges` 表（user_id, amount, status, reviewed_by, reviewed_at）
**And** 新增 `licenses` 表（user_id, code, email, activated, activated_at）
**And** `commission_configs` 表：`role` 枚举增加 `member`，新增场景 `recharge_888/recharge_5000/recharge_10000`
**And** `commission_records` 表：`type` 枚举增加 `followup_reward`（后续收益）
**And** 移除 `quota_purchases` 表（改为 recharges 统一管理）
**And** Alembic 迁移脚本可正确执行（upgrade + downgrade）
**And** 种子数据更新：4 角色佣金配置 + 管理员账号

### Story 2.2: 认证模块重构

As a 开发者,
I want 将认证模块从手机号改为邮箱+验证码,
So that 匹配 PRD v2 的注册方式。

**Acceptance Criteria:**

**Given** Epic 1 的 Mock 认证（手机号+验证码）
**When** 重构认证模块
**Then** `POST /api/v1/auth/send-email-code` — 发送邮箱验证码（Mock 模式返回 "123456"）
**And** `POST /api/v1/auth/register` — 邮箱+验证码+邀请码（必填）注册
**And** `POST /api/v1/auth/login` — 邮箱+验证码登录
**And** 注册时邀请码必填，无邀请码不可注册
**And** 注册时建立上下级关系，邀请码标记为已使用
**And** JWT payload 中 `sub` = user_id，`type` = "user"
**And** 移除 `AUTH_MODE` 环境变量和微信 OAuth 相关代码
**And** 现有测试更新为邮箱场景，全部通过

### Story 2.3: 前端架构调整

As a 开发者,
I want 移除 mini-program 并创建 user-web,
So that 匹配 PRD v2 的双 Web 端架构。

**Acceptance Criteria:**

**Given** Epic 1 的 mini-program 目录
**When** 执行前端架构调整
**Then** 删除 `mini-program/` 目录
**And** 创建 `user-web/` 目录，初始化 React + Vite + TypeScript 项目
**And** `user-web/` 包含基础项目结构（src/, public/, vite.config.ts, package.json）
**And** `admin-web/` 保持不变（Ant Design Pro v6）
**And** `backend/` 保持不变（FastAPI）
**And** 根目录 README 更新项目结构说明

### Story 2.4: 佣金引擎重构

As a 开发者,
I want 重构佣金引擎以支持场景 A/B 分离,
So that 额度销售不产生佣金，推荐充值才产生佣金。

**Acceptance Criteria:**

**Given** Epic 1 的佣金引擎骨架
**When** 重构佣金引擎
**Then** `CommissionEngine` 区分场景 A（额度销售，不产生佣金）和场景 B（推荐充值，产生佣金）
**And** 场景 B 首次奖励：根据上级角色 × 下级充值金额查表计算
**And** 场景 B 后续收益：代理→经销商关系，经销商推荐他人充 888，代理获 133.2 元/笔
**And** 长期奖励：仅直接下级全部收入 × 比例，代理→经销商不适用
**And** 普通用户/888 会员推荐的人充 5000/10000 不产生佣金
**And** `record_commission()` 方法保持幂等保护（business_id UNIQUE）
**And** 单元测试覆盖所有场景，全部通过

---

## Epic 3: 核心业务闭环 (UPDATED for v2)

完整的业务链路。

### Story 3.1: 邮箱验证码登录（无注册）

As a 代理/经销商,
I want 通过邮箱验证码登录分销系统,
So that 进入系统使用分销功能。

**Acceptance Criteria:**

**Given** 代理/经销商已有分销系统账号
**When** 用户输入邮箱，获取验证码，登录
**Then** 系统验证邮箱验证码
**And** 验证通过后签发 JWT，进入系统
**And** 不提供注册页面，不创建新用户
**And** 5000/10000支付成功后邮箱成为登录账号
**And** 超管创建种子用户后可登录
**And** 用户不能填写自己的推荐码

### Story 3.2: 推荐码生成与验证（持久码）

As a 代理/经销商,
I want 生成持久推荐码,
So that 推荐他人支付。

**Acceptance Criteria:**

**Given** 代理/经销商创建时
**When** 系统自动生成推荐码
**Then** 生成持久推荐码：Base62(user_id) + "." + HMAC-SHA256[:16]
**And** 推荐码存入 invite_codes 表（无 target_role）
**And** 代理/经销商创建时自动生成1个推荐码
**And** 推荐码可重复使用，不消耗
**And** 1人1码，持久有效
**And** 验证接口：签名不匹配返回错误，匹配返回 generator_id

### Story 3.3: 在线支付与线下审核

As a 用户,
I want 通过在线或线下支付获得对应权益,
So that 成为代理/经销商或获得License。

**Acceptance Criteria:**

**Given** 用户访问支付页面
**When** 用户选择支付金额（888/5000/10000）
**Then** 在线支付路径：通过支付小闭环页面完成支付
**And** 888支付不创建分销系统账号，仅生成License
**And** 5000支付创建经销商账号 + 11额度 + License + 推荐码
**And** 10000支付创建代理账号 + 22额度 + License + 推荐码

**Given** 管理员确认线下收款
**When** 批准支付
**Then** 管理员可手动填写推荐码
**And** 用户角色变更（5000→distributor, 10000→agent）
**And** 代理获得 22 个额度，经销商获得 11 个
**And** 系统自动生成 License
**And** 系统自动记账直接上级的首次奖励
**And** 管理员可拒绝并填写原因

### Story 3.4: 支付首次奖励记账

As a 系统,
I want 在支付确认后自动记账上级的首次奖励,
So that 上级能实时看到推荐收益。

**Acceptance Criteria:**

**Given** 管理员批准了用户 B 的支付（B 通过 A 的推荐码支付）
**When** 支付确认完成
**Then** 查 commission_configs 获取规则（role=A 的角色, scene=recharge_{B 的支付金额}）
**And** 记账首次奖励：business_id = "recharge_{B 的 recharge_id}", amount = config.reward_value
**And** 佣金记录 type=first_reward，写入 audit_logs
**And** 无推荐码=无佣金
**And** 同一笔支付不会重复记账（幂等）

### Story 3.5: 可售额度管理

As a 代理/经销商,
I want 查看和管理我的可售额度,
So that 知道还能销售多少个账号。

**Acceptance Criteria:**

**Given** 用户已登录且角色为代理或经销商
**When** 用户进入"我的额度"页面
**Then** 展示剩余额度和已销售记录
**And** 额度为 0 时显示"申请补购"
**And** 补购通过支付申请（充 10000 追加 22 个，充 5000 追加 11 个）

### Story 3.6: 团队树与上级链

As a 代理/经销商,
I want 查看我的团队树和上级链条,
So that 了解团队结构。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 进入"我的团队"页面
**Then** 展示直接下级列表（昵称、角色、注册时间、下级数量）
**And** 逐层展开，不限深度
**And** 展示团队总人数
**And** 仅含代理/经销商

**Given** 用户已登录
**When** 进入"我的上级"页面
**Then** 展示从当前用户到根节点的完整链条
**And** 根节点显示"无上级"

### Story 3.7: 额度销售（场景 A）

As a 代理/经销商,
I want 用额度为客户生成License,
So that 客户获得 License。

**Acceptance Criteria:**

**Given** 用户已登录且额度 > 0
**When** 用户录入客户邮箱，确认销售
**Then** 消耗 1 个额度
**And** 生成未激活License，不绑定用户
**And** 客户邮箱保留但不创建分销系统账号
**And** 不建立上下级关系
**And** 不产生任何佣金
**And** 额度为 0 时不可提交

### Story 3.8: 推荐支付佣金（场景B，2档）

As a 系统,
I want 在下级支付时自动记账佣金,
So that 上级获得推荐收益。

**Acceptance Criteria:**

**Given** 下级 B（上级 A）支付 888/5000/10000
**When** 支付确认完成
**Then** 查 commission_configs 获取 A 的首次奖励规则（2档：55%/40%）
**And** 记账 A 的首次奖励（business_id = "recharge_{id}"）
**And** 无推荐码=无佣金
**And** 后续收益：若 A 是代理、B 是经销商，B 每次推荐他人充 888，A 获得 133.2 元/笔
**And** 后续收益 business_id = "recharge_{下下级支付id}_followup_{A的ID}"
**And** 所有佣金幂等保护
**And** 写入审计日志

### Story 3.9: 佣金配置与幂等保护

As a 系统,
I want 从数据库读取佣金配置并保证幂等,
So that 佣金计算基于可配置参数且不重复。

**Acceptance Criteria:**

**Given** 种子数据包含 2 档佣金配置（代理55%/经销商40%）
**When** CommissionEngine 获取规则
**Then** `get_config(role, scene)` 查询 commission_configs 表
**And** 配置不存在时抛出明确异常
**And** 每笔记账使用 business_id 幂等键
**And** 并发场景下不产生重复记录

### Story 3.10: 我的收益

As a 用户,
I want 查看我的收益明细,
So that 了解记账余额和提现情况。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 进入"我的收益"页面
**Then** 展示：记账余额（待提现）、已提现总额、可用余额
**And** 收益明细按时间倒序
**And** 每条明细包含：金额、类型、来源、时间
**And** 支持按类型筛选

### Story 3.11: License 生成与验证

As a 系统,
I want 生成 License 并提供验证接口,
So that 业务系统可验证用户会员状态。

**Acceptance Criteria:**

**Given** 用户支付确认后
**When** 角色变更完成
**Then** 系统自动生成 License Code，不绑定邮箱
**And** License 含防篡改签名
**And** 用户可在"我的"页面查看 License

**Given** 业务系统调用验证接口
**When** 传入 License Code + 业务系统用户标识
**Then** 验证：License 存在 + 未激活
**And** 验证通过：返回成功
**And** 验证失败：返回具体错误
**And** 接口需鉴权（API Key）

**Given** 业务系统调用激活接口
**When** 传入 License Code + 业务系统用户标识
**Then** 激活 License，绑定业务系统用户标识
**And** 激活后不可重复激活
**And** 接口需鉴权（API Key）

### Story 3.12: 提现申请

As a 用户,
I want 提交提现申请,
So that 将记账余额转为实际收款。

**Acceptance Criteria:**

**Given** 用户可用余额 >= 最低提现额（默认 100 元）
**When** 用户填写金额和收款信息并提交
**Then** 生成工单（状态 pending），冻结对应金额
**And** 用户可查看工单列表
**And** 提现金额超过可用余额或低于最低额时提示错误

### Story 3.13: 工单管理（管理员）

As a 管理员,
I want 审核提现工单,
So that 用户能收到款项。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 查看工单列表
**Then** 支持按状态筛选
**And** 确认打款后状态变更为 paid，冻结金额扣减
**And** 拒绝时填写原因，金额解冻退回

---

## Epic 4: 管理员后台 (UPDATED for v2)

### Story 4.1: 用户管理+创建种子用户

As a 管理员,
I want 查看和管理所有用户并创建种子用户,
So that 了解平台用户全貌并初始化分销网络。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入用户管理页面
**Then** 列表分页展示（page_size=20）
**And** 支持按邮箱/昵称搜索
**And** 支持按角色筛选（代理/经销商）
**And** 点击用户查看详情：基本信息、上级、团队统计、收益汇总

**Given** 超管已登录后台
**When** 创建种子用户
**Then** 指定邮箱 + 角色 + 可选推荐码
**And** 跳过支付流程，自动分配额度（代理22个/经销商11个）
**And** 自动生成 License + 推荐码
**And** 种子用户创建后可登录

### Story 4.2: 支付审核

As a 管理员,
I want 审核用户的线下支付申请,
So that 确认收款后角色生效。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入支付审核页面
**Then** 待审核列表按申请时间排序
**And** 批准后自动触发角色变更、额度分配、License 生成、上级佣金记账
**And** 管理员可手动填写推荐码
**And** 支持拒绝并填写原因

### Story 4.3: 运营数据看板

As a 管理员,
I want 查看核心运营数据,
So that 了解平台状况。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入首页
**Then** 展示：总用户数、代理数、经销商数
**And** 展示：今日新增用户、今日支付总额（含在线支付）
**And** 展示：今日License生成数、激活数
**And** 展示：待处理工单数
**And** 仅数字卡片，不做复杂图表

### Story 4.4: 系统参数配置

As a 管理员,
I want 配置系统参数,
So that 业务规则可灵活调整。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入系统配置页面
**Then** 可配置：支付金额、可售额度、佣金比例/金额、结算周期、最低提现金额
**And** 修改仅对新业务生效
**And** 配置变更记录到 config_change_logs

---

## Epic 5: 长期奖励与通知 (UPDATED for v2)

### Story 5.1: 长期奖励定时结算

As a 系统,
I want 按周期自动结算长期奖励,
So that 上级持续获得下级收益提成。

**Acceptance Criteria:**

**Given** APScheduler 已配置结算周期（默认每月 1 日）
**When** 定时任务触发
**Then** 遍历所有代理/经销商用户
**And** 对每个用户，聚合其**直接下级**在上周期的全部收入总和
**And** 查 commission_configs 获取比例
**And** 代理→代理：5%，经销商→代理：4%，经销商→经销商：4%
**And** 代理→经销商：不适用（已由 133.2 元/笔替代）
**And** 仅限直接下级，不穿透更深层级
**And** 幂等保护：business_id = "settle_{user_id}_{YYYYMM}"

### Story 5.2: 消息通知

As a 用户,
I want 在关键事件发生时收到通知,
So that 不错过重要信息。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 以下事件发生时
**Then** 下级支付（有人通过你的推荐码支付）→ 推送通知
**And** 佣金入账 → 推送通知（含金额和类型）
**And** 工单状态变更 → 推送通知
**And** 支付审核通过 → 推送通知
**And** 种子用户创建通知（含登录引导）→ 推送通知
**And** 通知记录写入 notification_logs

---

## Epic 6: user-web 前端开发 (UPDATED for v2)

React + Vite 用户端 Web 应用。

### Story 6.1: user-web 项目初始化与登录

As a 用户,
I want 在 Web 端登录,
So that 使用系统功能。

**Acceptance Criteria:**

**Given** user-web 项目已初始化（Story 2.3）
**When** 用户访问 user-web
**Then** 展示登录页（邮箱+验证码）
**And** 不展示注册页
**And** 登录后进入首页
**And** 调用后端 API（Epic 3 开发的接口）

### Story 6.2: 首页与个人中心

As a 用户,
I want 查看首页概览和个人信息,
So that 了解基本数据。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 进入首页
**Then** 展示角色、额度、收益摘要
**And** 进入"我的"页面可查看个人信息、推荐码、License

### Story 6.3: 团队与收益页面

As a 用户,
I want 查看团队和收益,
So that 了解团队结构和收益情况。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 进入"我的团队"页面
**Then** 展示下级团队树（逐层展开）
**And** 进入"我的上级"页面展示上级链条
**And** 进入"我的收益"页面展示余额和明细

### Story 6.4: 额度销售页面

As a 代理/经销商,
I want 销售账号生成License,
So that 为客户提供License。

**Acceptance Criteria:**

**Given** 代理/经销商已登录
**When** 进入"额度销售"页面
**Then** 代理/经销商可录入客户邮箱生成License
**And** 消耗1个额度

### Story 6.5: 提现工单页面

As a 用户,
I want 提交提现申请,
So that 将收益转为实际收款。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 进入"提现"页面
**Then** 可填写金额和收款信息提交提现
**And** 可查看提现工单列表和状态

---

## Epic 7: 支付小闭环App (NEW)

独立部署的 React + Vite 支付页面，对接微信/支付宝扫码支付。

### Story 7.1: payment-app 初始化与支付页面

As a 终端用户,
I want 在支付页面完成在线支付,
So that 获得License或成为代理/经销商。

**Acceptance Criteria:**

**Given** payment-app 项目已初始化
**When** 用户访问 /pay?amount=888&referral=XXX&redirect=YYY
**Then** 展示支付页面：金额、邮箱输入框、推荐码输入框（选填）
**And** 调用后端创建支付订单 API
**And** 展示微信/支付宝扫码二维码
**And** 支付成功后展示License Code
**And** 支付成功后邮件发送License Code
**And** 提供"返回业务系统"按钮（带redirect参数+License Code）
**And** redirect参数白名单校验

### Story 7.2: 支付回调处理

As a 系统,
I want 处理支付回调并触发后续业务,
So that 支付成功后自动完成权益分配。

**Acceptance Criteria:**

**Given** 微信/支付宝回调到达
**When** 回调验签通过
**Then** 888支付：生成License + 邮件发送 + 计算佣金（如有推荐码）
**And** 5000支付：创建经销商账号 + 11额度 + License + 推荐码 + 计算佣金
**And** 10000支付：创建代理账号 + 22额度 + License + 推荐码 + 计算佣金
**And** 幂等保护：同一支付订单不重复处理
**And** 回调返回 success 给支付平台

### Story 7.3: 支付状态查询

As a 终端用户,
I want 查询支付状态,
So that 确认支付是否成功。

**Acceptance Criteria:**

**Given** 用户已发起支付
**When** 调用支付状态查询 API
**Then** 返回支付状态（pending/paid/failed）
**And** 支付成功时返回License Code
**And** 支付失败时提供重试入口
