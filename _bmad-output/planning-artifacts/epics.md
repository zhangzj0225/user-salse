---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-user-salse-2026-06-11/prd.md
  - _bmad-output/planning-artifacts/architecture.md
status: complete
completedAt: '2026-06-11'
---

# user-salse - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for user-salse, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**认证与注册 (Auth & Registration)**
FR-1: 微信授权登录 — 用户打开小程序后，通过微信一键授权登录，获取 OpenID 和头像昵称
FR-2: 手机号绑定 — 用户在注册流程中绑定手机号，系统验证唯一性
FR-3: 邀请码填写与角色解析 — 用户手动输入邀请码，系统解析并展示目标角色、准入费用和权益说明，用户确认后进入注册。无邀请码时以普通用户身份注册

**邀请码 (Invite Codes)**
FR-4: 个人邀请码生成（含目标角色选择）— 代理/经销商选择目标角色生成含角色信息的邀请码，普通用户生成通用推荐码。邀请码含 HMAC 防篡改签名

**角色准入 (Role & Entry)**
FR-5: 准入申请 — 角色由邀请码确定，系统自动生成待审核准入记录
FR-6a: 准入审核与角色激活 — 管理员确认收款 → 角色变更为代理/经销商 → 分配账号额度（代理22个/经销商11个）。支持拒绝并填写原因
FR-6b: 准入首次奖励记账 — 角色激活后，系统自动沿上级链记账首次奖励（幂等：business_id = "entry_{user_id}"）
FR-7a: 账号额度查看 — 用户查看剩余额度和已销售记录，额度耗尽时不可继续销售
FR-7b: 额度补购申请 — 额度耗尽后提交补购申请（指定数量）
FR-7c: 额度补购审核（管理员）— 管理员查看补购申请列表，确认收款后追加额度，支持拒绝

**邀请链与团队 (Invite Chain & Team)**
FR-8: 邀请关系记录 — 注册时记录上下级关系（上级ID、下级ID、邀请码、时间），关系不可删除或修改
FR-9: 我的团队（下级树）— 查看直接下级列表，点击展开间接下级，展示昵称、角色、注册时间、下级数量、团队总人数
FR-10: 我的上级链条 — 从当前用户向上追溯到根节点，展示每级昵称和角色

**账号销售 (Account Sales)**
FR-11: 账号销售记录 — 录入客户手机号（短信验证），消耗额度，自动记账自销佣金 + 上级提成
FR-12: 普通用户推荐购买 — 通过邀请码注册的被推荐人购买账号后，普通用户获得推荐返佣

**佣金与收益 (Commission & Earnings)**
FR-13: 佣金规则配置（管理员可配）— 按角色和场景的默认佣金规则自动记账，所有参数管理员可修改。修改仅对新业务生效（需快照或版本化）
FR-14: 我的收益 — 区分记账余额（待提现）和已提现金额，展示收益明细（金额、类型、来源、时间），支持按类型筛选
FR-15: 长期奖励记账 — 按团队业绩（含全部下级）和配置比例逐级向上记账，结算周期管理员可配。⚠️ 风险：递归链计算 + APScheduler 脆弱性，需幂等 checkpoint（business_id = "settle_{user_id}_{YYYYMM}"）

**提现工单 (Withdrawal Tickets)**
FR-16: 提现申请 — 填写金额和收款信息，校验最低提现额，生成工单，展示预计处理时效。提交后冻结对应金额
FR-17: 工单管理（管理员）— 查看/筛选工单，确认打款或拒绝（填写原因）。拒绝时解冻对应金额退回用户余额

**管理员后台 (Admin Backend)**
FR-18: 用户管理 — 管理员查看用户列表（分页、搜索、角色筛选），查看用户详情（基本信息、上级、团队、收益）
FR-19: 运营数据看板 — 展示总用户数、各角色数量、今日新增、今日销售额、待处理工单数（仅数字卡片，今日=自然日 00:00~此刻）
FR-20: 系统参数配置 — 管理员配置准入费、账号定价、配额、佣金比例/金额、结算周期、最低提现额，记录变更日志

**消息通知 (Notifications — 嵌入各 Epic，非独立)**
FR-21: 订阅消息 — 下级注册、佣金入账、工单状态变更、准入审核通过时推送微信订阅消息

### NonFunctional Requirements

NFR-1: 佣金记账幂等性 — 每笔记账基于唯一 business_id 去重，使用 INSERT ON DUPLICATE KEY 或 SELECT FOR UPDATE
NFR-2: 审计日志 — 所有金额变动操作记录完整审计日志（操作人、类型、变更前后值、业务ID），不可删除
NFR-3: 邀请码安全性 — HMAC-SHA256 签名防篡改，密钥仅服务端持有，支持 key_version 密钥轮换

### Additional Requirements

- 项目初始化：Taro 4.x 小程序 + Ant Design Pro v6 管理后台 + FastAPI 后端
- 数据库迁移：12 张表（users, admin_users, invite_codes, sales, sms_records, quota_purchases, commission_configs, commission_records, tickets, audit_logs, config_change_logs, notification_logs）
- 种子数据：管理员账号创建脚本 + 10 条佣金配置 SQL
- 短信服务集成：阿里云 SMS / 腾讯云 SMS SDK（需指定模板 ID）
- APScheduler 定时任务：长期奖励月度/周度结算（⚠️ 已知风险：进程重启丢失状态，多 worker 重复执行；缓解：business_id 幂等）
- 双端 JWT 认证中间件：小程序端 (type=wechat) + 管理后台 (type=admin)
- HMAC 邀请码签名：Base62 编码 + HMAC-SHA256[:16]
- 幂等性保护：commission_records.business_id UNIQUE 约束
- 审计日志中间件：全局拦截金额变动操作
- 分页默认值：page_size=20, max_page_size=100
- 余额状态机：记账余额 → 提现冻结 → 打款确认(扣减) 或 拒绝(解冻退回)

### UX Design Requirements

（无 UX Design 文档）

### FR Coverage Map

| FR | Epic | Story | 简述 |
|----|------|-------|------|
| FR-1 | Epic 5 | 5.1 | 微信授权登录（最后对接） |
| FR-2 | Epic 5 | 5.1 | 手机号绑定（最后对接） |
| FR-3 | Epic 2 | 2.1 | 邀请码填写与角色解析 |
| FR-4 | Epic 2 | 2.2 | 个人邀请码生成 |
| FR-5 | Epic 2 | 2.3 | 准入申请 |
| FR-6a | Epic 2 | 2.3 | 准入审核与角色激活 |
| FR-6b | Epic 2 | 2.4 | 准入首次奖励记账 |
| FR-7a | Epic 2 | 2.5 | 账号额度查看 |
| FR-7b | Epic 2 | 2.6 | 额度补购申请 |
| FR-7c | Epic 2 | 2.6 | 额度补购审核（管理员） |
| FR-8 | Epic 2 | 2.1 | 邀请关系记录 |
| FR-9 | Epic 2 | 2.7 | 我的团队（下级树） |
| FR-10 | Epic 2 | 2.7 | 我的上级链条 |
| FR-11 | Epic 2 | 2.8a | 账号销售记录 |
| FR-12 | Epic 2 | 2.8b | 普通用户推荐购买 |
| FR-13 | Epic 2 | 2.9a | 佣金规则配置 |
| FR-14 | Epic 2 | 2.10 | 我的收益 |
| FR-16 | Epic 2 | 2.11 | 提现申请 |
| FR-17 | Epic 2 | 2.12 | 工单管理（管理员） |
| FR-18 | Epic 3 | 3.1 | 用户管理 |
| FR-19 | Epic 3 | 3.2 | 运营数据看板 |
| FR-20 | Epic 3 | 3.3 | 系统参数配置 |
| FR-15 | Epic 4 | 4.1 | 长期奖励记账 |
| FR-21 | Epic 4 | 4.2 | 订阅消息 |
| NFR-1 | Epic 2 | 2.9d | 佣金记账幂等性 |
| NFR-2 | Epic 2 | 2.9e | 审计日志 |
| NFR-3 | Epic 2 | 2.2 | 邀请码安全性 |

> **编号说明:** PRD 中 FR-19（准入审核）已合并入 FR-6a / Story 2.3，导致后续 FR 编号前移一位：PRD FR-20→Epic FR-19（运营看板），PRD FR-21→Epic FR-20（参数配置），PRD FR-22→Epic FR-21（订阅消息）。功能无遗漏。

## Epic List

### Epic 1: 项目骨架与 Mock 认证
搭建三端项目骨架、数据库、Mock 认证（手机号+验证码），让后续业务开发无需等待微信对接。JWT subject 使用 user_id，openid 改为 NULLABLE，通过 AUTH_MODE 环境变量切换 mock/wechat。
**包含:** 三端脚手架、12 表迁移（openid NULLABLE）、种子数据、Mock 登录 API、JWT 中间件、管理员登录、佣金引擎骨架、AUTH_MODE 策略模式、审计日志骨架
**Stories:** 4

### Epic 2: 核心业务闭环
完整的业务链路：用户注册 → 邀请码生成/解析 → 角色准入审核 → 团队树/上级链 → 账号销售（短信验证）→ 佣金自动记账（幂等+审计）→ 收益展示 → 提现工单。这是系统的核心价值。
**FRs covered:** FR-3,4,5,6a,6b,7a,7b,7c,8,9,10,11,12,13,14,16,17
**NFRs covered:** NFR-1, NFR-2, NFR-3
**Stories:** 17

### Epic 3: 管理员后台
管理员 Web 端：用户管理（列表/详情/搜索）、运营数据看板（数字卡片）、系统参数配置（佣金比例/准入费/配额等，含变更日志）。
**FRs covered:** FR-18, FR-19, FR-20
**Stories:** 3

### Epic 4: 长期奖励与通知
APScheduler 定时结算长期团队奖励（含幂等 checkpoint）；关键事件推送微信订阅消息。
**FRs covered:** FR-15, FR-21
**Stories:** 2

### Epic 5: 微信小程序对接
将 Mock 认证替换为真实微信 OAuth（wx.login + 手机号快速验证），开发小程序端 UI 页面。设置 `AUTH_MODE=wechat` 即可切换。
**FRs covered:** FR-1, FR-2
**Stories:** 3

---

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: 项目骨架与 Mock 认证

搭建三端项目骨架、数据库、Mock 认证（手机号+验证码），让后续业务开发无需等待微信对接。JWT subject 使用 user_id，openid 改为 NULLABLE，通过 AUTH_MODE 环境变量切换 mock/wechat。

### Story 1.1: 项目骨架初始化

As a 开发者,
I want 初始化三端项目骨架和数据库,
So that 后续功能开发有统一的基础架构。

**Acceptance Criteria:**

**Given** 空的项目目录
**When** 执行项目初始化
**Then** `backend/` 包含 FastAPI 项目结构（app/main.py, core/, api/v1/, models/, schemas/, services/）
**And** `mini-program/` 包含 Taro 4.x + React + TypeScript 项目
**And** `admin-web/` 包含 Ant Design Pro v6 项目
**And** Alembic 已初始化并包含 12 张表的迁移脚本（users.openid 为 NULLABLE）
**And** 种子数据迁移包含 1 个管理员账号和 10 条佣金配置 SQL
**And** `pyproject.toml` 包含 FastAPI, SQLAlchemy, Alembic, PyJWT, base62, APScheduler 等依赖
**And** `core/config.py` 包含 `AUTH_MODE` 配置项（默认 "mock"）

### Story 1.2: Mock 用户认证

As a 用户,
I want 通过手机号和验证码登录系统,
So that 无需等待微信对接即可使用系统全部功能。

**Acceptance Criteria:**

**Given** 用户已安装小程序（或使用 API 测试工具）
**When** 用户输入手机号并获取验证码
**Then** 系统发送 6 位短信验证码（Mock 模式下直接返回 "123456"，无需真实短信）
**And** 用户输入验证码提交登录
**And** 系统创建/查找用户（openid = "mock_{phone}"），签发 JWT（sub=user_id, type=wechat）
**And** 后续请求携带 JWT 可访问受保护接口
**And** 设置 `AUTH_MODE=wechat` 后，同一登录端点切换到微信 OAuth 流程

### Story 1.3: 管理员登录

As a 管理员,
I want 通过账号密码登录管理后台,
So that 可以管理用户、审核准入、处理工单。

**Acceptance Criteria:**

**Given** 管理员账号已通过种子数据创建
**When** 管理员在后台登录页输入用户名和密码
**Then** 系统验证凭据，签发 JWT（sub=admin_id, type=admin）
**And** 后续请求携带 JWT 可访问 `/api/v1/admin/*` 接口
**And** 小程序端 JWT（type=wechat）无法访问管理后台接口
**And** 密码错误时返回 401

### Story 1.4: 佣金引擎骨架与认证策略

As a 开发者,
I want 搭建佣金引擎骨架和 AUTH_MODE 策略模式,
So that Epic 2 的佣金相关 Story 有可依赖的基础架构。

**Acceptance Criteria:**

**Given** 项目骨架已初始化
**When** 实现基础架构
**Then** `services/commission_service.py` 包含 `CommissionEngine` 类骨架（calculate → record → log 流水线）
**And** `services/commission_service.py` 包含 `record_commission(user_id, amount, type, source_user_id, business_id)` 方法（含 INSERT ON DUPLICATE KEY 幂等保护）
**And** `core/security.py` 包含 `get_auth_service()` 工厂函数，根据 `AUTH_MODE` 返回 MockAuthService 或 WechatAuthService
**And** `services/` 目录下创建 `audit_service.py`，包含 `log(action, operator_type, target_type, target_id, old_value, new_value, business_id)` 方法
**And** 以上骨架可通过单元测试验证（无需完整业务逻辑）

---

## Epic 2: 核心业务闭环

完整的业务链路：用户注册 → 邀请码生成/解析 → 角色准入审核 → 团队树/上级链 → 账号销售（短信验证）→ 佣金自动记账（幂等+审计）→ 收益展示 → 提现工单。

### Story 2.1: 用户注册与关系记录

As a 新用户,
I want 通过邀请码注册并自动确定角色,
So that 无需手动选择即可成为代理或经销商。

**Acceptance Criteria:**

**Given** 用户已通过 Mock 认证（手机号+验证码）
**When** 用户在注册流程中输入邀请码
**Then** 系统解析邀请码，展示目标角色、准入费用（从 commission_configs 读取）、获得账号数量、佣金规则概要
**And** 用户确认后，角色由邀请码确定（无需手动选择）
**And** 无邀请码时默认为普通用户
**And** 用户不能填写自己的邀请码
**And** 系统记录上下级关系：上级ID、下级ID、邀请码、创建时间（关系不可删除或修改）

### Story 2.2: 邀请码生成与验证

As a 代理/经销商,
I want 选择目标角色生成邀请码,
So that 可以发展下线代理或经销商。

**Acceptance Criteria:**

**Given** 用户已登录且角色为代理或经销商
**When** 用户在"邀请好友"页面选择"发展代理"或"发展经销商"
**Then** 系统生成邀请码：Base62(user_id:target_role) + "." + HMAC-SHA256[:16]
**And** 邀请码存入 invite_codes 表（含 key_version=1）
**And** 用户可复制邀请码分享给他人
**And** 普通用户仅生成通用推荐邀请码

**Given** 任意用户
**When** 调用邀请码验证接口，传入邀请码
**Then** 系统按 "." 拆分 payload 和 signature，重新计算 HMAC 比对
**And** 签名不匹配时返回 "邀请码无效"（code: INVALID_INVITE_CODE）
**And** 签名匹配时返回 generator_id 和 target_role
**And** 被篡改的邀请码解析失败

### Story 2.3: 准入审核与角色激活

As a 管理员,
I want 审核用户的准入申请并确认收款,
So that 用户角色生效并获得账号额度。

**Acceptance Criteria:**

**Given** 用户已提交准入申请（状态为 pending）
**When** 管理员在后台查看待审核列表，点击"批准"
**Then** 用户角色变更为代理或经销商
**And** 代理获得 22 个账号额度，经销商获得 11 个（额度值从 commission_configs 读取）
**And** 用户状态变更为 active
**And** 写入 audit_logs（action=entry_approve）
**And** 批准后同步调用 Story 2.4 的首次奖励记账（CommissionEngine.create_first_reward）

**Given** 管理员拒绝申请
**When** 填写拒绝原因并提交
**Then** 用户状态变更为 rejected，拒绝原因可见

### Story 2.4: 准入首次奖励记账

As a 系统,
I want 在角色激活后自动记账上级的首次奖励,
So that 上级能实时看到发展下线的收益。

**Acceptance Criteria:**

**Given** 管理员批准了用户 B 的准入申请（B 通过 A 的邀请码注册）
**When** 角色激活完成（由 Story 2.3 触发）
**Then** CommissionEngine 查 commission_configs 获取对应规则（role=A的角色, scene=recruit_{B的角色}）
**And** 记账首次奖励：business_id = "entry_{B的user_id}", amount = config.reward_value
**And** 佣金记录 type=first_reward，写入 audit_logs
**And** 同一笔准入不会重复记账（business_id UNIQUE 约束）
**And** 金额从配置读取，不硬编码（如 agent+recruit_agent=5500, agent+recruit_distributor=2750 等）

### Story 2.5: 账号额度查看

As a 代理/经销商,
I want 查看我的剩余账号额度,
So that 知道还能销售多少个账号。

**Acceptance Criteria:**

**Given** 用户已登录且角色为代理或经销商
**When** 用户进入"我的账号"页面
**Then** 展示剩余额度（account_quota - account_used）和已销售记录列表
**And** 额度为 0 时显示"额度已用完，请申请补购"
**And** 普通用户不显示此页面

### Story 2.6: 额度补购

As a 代理/经销商,
I want 额度耗尽后申请补购,
So that 可以继续销售账号。

**Acceptance Criteria:**

**Given** 用户额度已耗尽（account_quota - account_used = 0）
**When** 用户点击"申请补购"，输入补购数量并提交
**Then** 系统生成补购申请记录（quota_purchases，状态 pending）

**Given** 管理员在后台查看补购申请列表
**When** 管理员确认收款并批准
**Then** 用户额度追加对应数量
**And** 管理员可拒绝并填写原因

### Story 2.7: 团队树与上级链

As a 用户,
I want 查看我的下级团队树和上级链条,
So that 了解我的团队结构和我在体系中的位置。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 用户进入"我的团队"页面
**Then** 展示直接下级列表（昵称、角色、注册时间、直接下级数量）
**And** 点击某下级可展开其直接下级（逐层展开）
**And** 展示团队总人数统计

**Given** 用户已登录
**When** 用户进入"我的上级"页面
**Then** 展示从当前用户向上追溯到根节点的完整链条（每级昵称、角色）
**And** 根节点用户显示"无上级"
**And** 链条按层级排序

### Story 2.8a: 账号销售（短信验证）

As a 代理/经销商,
I want 录入客户手机号并销售账号,
So that 消耗额度并获得佣金。

**Acceptance Criteria:**

**Given** 用户已登录且账号额度 > 0
**When** 用户输入客户手机号，点击"获取验证码"
**Then** 系统发送 6 位短信验证码（Mock 模式下直接返回 "123456"）
**And** 用户输入验证码并提交
**And** 验证码校验通过后，创建 sales 记录（seller_id, customer_phone, amount=888）
**And** 用户 account_used + 1
**And** 额度为 0 时不可提交
**And** 销售创建后同步调用 Story 2.9b 的佣金计算

### Story 2.8b: 普通用户推荐返佣

As a 普通用户,
I want 通过我的邀请码推荐他人购买账号,
So that 获得推荐返佣。

**Acceptance Criteria:**

**Given** 用户 C（普通用户）的邀请码被 D 注册时使用
**When** D 通过任意代理/经销商购买了账号（触发 Story 2.8a 的销售流程）
**Then** CommissionEngine 查 commission_configs（role=user, scene=recommend）
**And** 记账 C 的推荐返佣：business_id = "recommend_{D的user_id}", amount = config.reward_value（默认 177.60）
**And** 佣金记录 type=recommend，写入 audit_logs
**And** 返佣记录在 C 的"我的收益"中可见

### Story 2.9a: 佣金配置 CRUD

As a 系统,
I want 从数据库读取佣金配置规则,
So that 佣金计算基于可配置的参数而非硬编码。

**Acceptance Criteria:**

**Given** 种子数据已包含 10 条佣金配置
**When** CommissionEngine 需要获取规则
**Then** 通过 `get_config(role, scene)` 方法查询 commission_configs 表
**And** 返回 reward_type（fixed/percentage）和 reward_value
**And** 配置不存在时抛出明确异常

### Story 2.9b: 自销佣金计算

As a 系统,
I want 在账号销售后自动记账销售人的自销佣金,
So that 销售人能实时看到自己的销售收益。

**Acceptance Criteria:**

**Given** 销售记录已创建（seller=B, B.role=distributor）
**When** 触发佣金计算
**Then** 查 commission_configs（role=distributor, scene=self_sell）获取 reward_value
**And** 记账 B 的自销佣金：business_id="sale_{sale_id}_self", amount=config.reward_value, type=sale_commission
**And** 金额从配置读取，不硬编码

### Story 2.9c: 上级链佣金追溯

As a 系统,
I want 沿上级链逐级记账各级上级的销售提成,
So that 整个链条上的上级都能获得对应收益。

**Acceptance Criteria:**

**Given** 销售记录已创建（seller=C，C.parent_id=B，B.parent_id=A）
**When** 触发佣金计算
**Then** 沿 parent_id 链向上追溯每一级上级
**And** 对每一级上级，查 commission_configs（role=上级角色, scene=downline_sell）
**And** 逐级记账：business_id="sale_{sale_id}_upstream_{上级ID}", amount=config.reward_value
**And** 链条有多级时（如 A→B→C），A 和 B 各获得对应提成
**And** 佣金链深度覆盖所有上级（FR-11 的"各级上级"）
**And** 根用户（parent_id=NULL）时，上级链为空，不产生任何上级提成记录

### Story 2.9d: 佣金记账幂等保护

As a 系统,
I want 每笔记账操作具有幂等性,
So that 同一笔业务不会产生重复佣金记录。

**Acceptance Criteria:**

**Given** 佣金记账请求（含 business_id）
**When** 执行记账操作
**Then** 使用 INSERT ON DUPLICATE KEY 或事务内 SELECT FOR UPDATE + INSERT
**And** business_id 已存在时跳过，不重复记账
**And** 并发场景下不会产生重复记录

### Story 2.9e: 佣金审计日志

As a 系统,
I want 每笔佣金记账自动写入审计日志,
So that 所有金额变动可追溯且不可删除。

**Acceptance Criteria:**

**Given** 佣金记账操作完成
**When** 写入 commission_records
**Then** 同步写入 audit_logs（operator_type=system, action=commission_create, target_type=commission_record, target_id, business_id）
**And** audit_logs 记录不可修改或删除
**And** 管理员可在后台查看审计日志

### Story 2.10: 我的收益（含余额状态机）

As a 用户,
I want 查看我的收益明细,
So that 清楚了解记账余额和已提现金额。

**Acceptance Criteria:**

**Given** 用户已登录
**When** 用户进入"我的收益"页面
**Then** 页面顶部展示：记账余额（待提现）、已提现总额、可用余额（= 记账余额 - 已冻结提现金额）
**And** "记账余额"使用账本图标 + 说明文字"此为记账金额，需提交工单提现"
**And** 收益明细按时间倒序排列
**And** 每条明细包含：金额、类型（首次奖励/账号提成/长期奖励/推荐返佣）、来源（下级昵称或账号销售）、时间
**And** 支持按类型筛选
**And** 余额状态机：记账余额 → 提现冻结（Story 2.11）→ 打款确认扣减 或 拒绝解冻退回（Story 2.12）

### Story 2.11: 提现申请

As a 用户,
I want 提交提现申请,
So that 将记账余额转为实际收款。

**Acceptance Criteria:**

**Given** 用户已登录且可用余额 >= 最低提现额（默认100元，从 commission_configs 读取）
**When** 用户填写提现金额和收款信息（银行卡/支付宝）并提交
**Then** 提现金额不能超过可用余额
**And** 生成工单（tickets 表，状态 pending），展示预计处理时效"通常 3 个工作日内处理"
**And** 对应金额从可用余额中冻结（不扣减记账余额，仅标记为冻结）
**And** 用户可查看工单列表（状态、提交时间、金额）
**And** 提现金额低于最低提现额时提示错误

### Story 2.12: 工单管理（管理员）

As a 管理员,
I want 审核提现工单并确认打款,
So that 用户能收到实际款项。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 管理员查看工单列表
**Then** 支持按状态筛选（待处理/已打款/已拒绝）
**And** 点击工单查看详情（申请人、金额、收款信息、佣金来源）

**Given** 管理员确认打款
**When** 点击"确认打款"
**Then** 工单状态变更为 paid，记录 processed_by 和 processed_at
**And** 冻结金额从记账余额中扣减，已提现总额增加
**And** 用户端同步更新状态，通过订阅消息通知

**Given** 管理员拒绝工单
**When** 填写拒绝原因并提交
**Then** 工单状态变更为 rejected
**And** 冻结金额解冻退回用户可用余额（记账余额不变）
**And** 用户端可见拒绝原因

---

## Epic 3: 管理员后台

管理员 Web 端：用户管理、运营数据看板、系统参数配置。

### Story 3.1: 用户管理

As a 管理员,
I want 查看和管理所有注册用户,
So that 了解平台用户全貌。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入用户管理页面
**Then** 用户列表分页展示（默认 page_size=20）
**And** 支持按手机号/昵称/邀请码搜索
**And** 支持按角色筛选（代理/经销商/普通用户）
**And** 点击用户查看详情：基本信息、上级信息、团队统计、收益汇总

### Story 3.2: 运营数据看板

As a 管理员,
I want 在首页查看核心运营数据,
So that 快速了解平台运营状况。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入首页
**Then** 展示数字卡片：总用户数、代理数、经销商数、普通用户数
**And** 展示：今日新增用户（自然日 00:00~此刻）
**And** 展示：今日销售额（自然日 00:00~此刻）
**And** 展示：待处理工单数
**And** 仅数字卡片 + 简单列表，不做复杂图表

### Story 3.3: 系统参数配置

As a 管理员,
I want 配置佣金比例和业务参数,
So that 业务规则可以灵活调整。

**Acceptance Criteria:**

**Given** 管理员已登录后台
**When** 进入系统配置页面
**Then** 可配置项包括：准入费金额（代理/经销商）、账号定价、账号配额（代理/经销商）、各角色各场景的佣金比例/金额、长期奖励结算周期、最低提现金额
**And** 修改后仅对新产生的业务生效，不影响历史记录
**And** 配置变更记录到 config_change_logs（谁、何时、改了什么、旧值、新值）

---

## Epic 4: 长期奖励与通知

APScheduler 定时结算长期团队奖励；关键事件推送微信订阅消息。

### Story 4.1: 长期奖励定时结算

As a 系统,
I want 按周期自动结算长期团队奖励,
So that 上级能持续获得下级团队的业绩提成。

**Acceptance Criteria:**

**Given** APScheduler 已配置结算周期（默认每月 1 日）
**When** 定时任务触发
**Then** 遍历所有代理/经销商用户
**And** 对每个用户，聚合其所有下级（递归 parent_id）在上周期的 sales 总额 = team_revenue
**And** 查 commission_configs 中 scene=team_bonus 的比例
**And** 沿上级链逐级记账：business_id = "settle_{上级ID}_{YYYYMM}"
**And** 每笔记账独立幂等：同一周期重复执行不会重复记账
**And** 写入 audit_logs
**And** 结算周期可由管理员在后台配置（按月/按周/按天）

### Story 4.2: 订阅消息通知

As a 用户,
I want 在关键事件发生时收到通知,
So that 不错过重要信息。

**Acceptance Criteria:**

**Given** 用户已订阅消息
**When** 以下事件发生时
**Then** 下级注册 → 推送通知（含下级昵称）
**And** 佣金入账 → 推送通知（含金额和类型）
**And** 工单状态变更（已打款/已拒绝）→ 推送通知（含状态和金额）
**And** 准入审核通过 → 推送通知
**And** 通知记录写入 notification_logs

---

## Epic 5: 微信小程序对接

将 Mock 认证替换为真实微信 OAuth，开发小程序端 UI 页面。

### Story 5.1: 微信 OAuth 认证切换

As a 系统,
I want 将 Mock 认证切换为微信 OAuth,
So that 用户可以通过微信授权登录。

**Acceptance Criteria:**

**Given** 微信小程序已配置 AppID 和 Secret
**When** 设置 AUTH_MODE=wechat 并重启服务
**Then** POST /api/v1/auth/login 切换为微信 OAuth 流程
**And** 前端调用 wx.login() 获取 code → 后端 code2session 换取 openid
**And** 前端调用 getPhoneNumber 获取加密手机号 → 后端解密
**And** 创建/查找用户（openid 为真实微信 openid），签发 JWT（sub=user_id, type=wechat）
**And** 所有业务接口（Epic 2 开发的）无需任何代码改动

### Story 5.2: 小程序登录与首页

As a 用户,
I want 在小程序中完成微信登录并看到首页,
So that 可以进入系统并了解基本数据。

**Acceptance Criteria:**

**Given** 小程序已编译运行
**When** 用户打开小程序
**Then** 展示登录页（微信授权 + 手机号绑定 + 邀请码输入）
**And** 登录后进入首页（展示用户基本数据概览：角色、额度、收益摘要）
**And** 首页数据调用 Epic 2 后端 API

### Story 5.3: 小程序邀请与团队页面

As a 用户,
I want 在小程序中邀请好友和查看团队,
So that 可以发展下线和了解团队结构。

**Acceptance Criteria:**

**Given** 用户已登录小程序
**When** 进入"邀请好友"页面
**Then** 代理/经销商可选择目标角色生成邀请码并分享
**And** 普通用户可生成通用推荐码
**And** 进入"我的团队"页面可查看下级树（逐层展开）
**And** 进入"我的上级"页面可查看完整上级链条
**And** 各页面调用 Epic 2 后端 API

### Story 5.4: 小程序收益与个人中心

As a 用户,
I want 在小程序中查看收益和管理个人账户,
So that 可以了解收益情况和管理额度。

**Acceptance Criteria:**

**Given** 用户已登录小程序
**When** 进入"收益"页面
**Then** 展示记账余额、已提现总额、收益明细列表（支持筛选）
**And** 可提交提现申请（填写金额和收款信息）
**And** 可查看提现工单列表和状态
**And** 进入"我的"页面可查看个人信息、邀请码、账号额度
**And** 代理/经销商可进行账号销售（录入客户手机号+短信验证）
**And** 各页面调用 Epic 2 后端 API
