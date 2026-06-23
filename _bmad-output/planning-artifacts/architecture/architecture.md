---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-user-salse-2026-06-11/prd.md
  - d:/user-salse/需求说明.md
  - d:/user-salse/用户旅途说明.md
workflowType: 'architecture'
project_name: 'user-salse'
user_name: 'Lenovo'
date: '2026-06-11'
updated: '2026-06-21'
lastStep: 8
status: 'complete'
completedAt: '2026-06-21'
---

# Architecture Decision Document

_本文档基于 PRD v2（2026-06-21 修订）更新。_

## Project Context Analysis

### Requirements Overview

**Functional Requirements:** 25 FRs 分为 10 个功能模块：

- 代理/经销商认证（FR-1~4）：邮箱+验证码登录、推荐码生成（持久码）、超管创建种子用户、不支持开放注册
- 角色与支付（FR-5~7）：支付决定角色（888/5000/10000）、线下支付审核、可售额度管理
- 推荐码与团队（FR-8~10）：关系记录（5000/10000建团队关系，888仅佣金关系）、下级树、上级链
- License与额度销售（FR-11~12）：场景A额度销售（不产生佣金）、场景B在线支付（产生佣金）
- 佣金计算与收益（FR-13~15）：可配置佣金规则、收益展示、长期奖励（仅直接下级）
- License 对接（FR-16~17）：License 生成、验证接口（供业务系统调用），激活时绑定业务系统用户
- 提现工单（FR-18~19）：提现申请、工单管理
- 管理员后台（FR-20~23）：用户管理、支付审核、数据看板、参数配置
- 消息通知（FR-24）：通知
- 支付小闭环（FR-25）：在线支付888/5000/10000，生成License，可选填推荐码计算佣金
- 系统对接说明（§4.10）：License Code 对接，激活时绑定业务系统用户标识，不做 SSO

**Non-Functional Requirements:** 4 个 NFR：

- NFR-1: 佣金记账幂等性（基于业务 ID 去重）
- NFR-2: 审计日志（所有金额变动可追溯，不可删除）
- NFR-3: 推荐码安全性（HMAC 防篡改签名）
- NFR-4: License 安全性（防伪造、不绑定邮箱、激活时绑定业务系统用户、一次性使用）

### Technical Constraints & Dependencies

- **前端简化**: 移除微信小程序，改为 user-web (React+Vite) + admin-web (Ant Design Pro) + payment-app (React+Vite) 三端
- **用户体系独立**: 分销系统仅代理/经销商/管理员，终端用户在业务系统
- **邮箱服务**: 需第三方 SMTP/邮件 API（如阿里云邮件推送、SendGrid）
- **在线支付**: 支付小闭环App，支持888/5000/10000三档
- **License 对接**: 通过 License Code 与业务系统对接，激活时绑定业务系统用户标识
- **支付路径**: 线上支付小闭环 + 线下管理员审核
- **配置热更新**: 佣金参数管理员可配，修改仅对新业务生效

### Cross-Cutting Concerns Identified

1. **树形数据查询性能** — 团队树无限深度，佣金沿链追溯，需预计算聚合或闭包表
2. **佣金幂等性** — 每笔记账需基于唯一业务 ID 去重，防止重复计算
3. **审计完整性** — 金额变动全链路日志，不可篡改
4. **分销端认证** — user-web 邮箱+验证码 JWT + admin-web 账号密码 JWT
5. **推荐码安全** — 服务端签名 + 持久码，解析验证，防篡改
6. **License 安全** — 不绑定邮箱，激活时绑定业务系统用户，一次性使用，接口鉴权

## Starter Template Evaluation

### Primary Technology Domain

全栈多端应用：Python REST API + 用户 Web 端 + 支付小闭环 Web 端 + 管理后台 Web 端

### Technology Stack Decisions

| 层 | 技术选型 | 版本 |
|---|---------|------|
| 后端框架 | FastAPI | latest |
| ORM | SQLAlchemy 2.0 | latest |
| 数据库迁移 | Alembic | latest |
| 数据库 | MySQL 8.0 | 8.0+ |
| 用户 Web 端 | React + Vite | React 19, Vite 5.x |
| 用户 Web UI | Ant Design (antd) | v6 |
| 管理后台框架 | Ant Design Pro | v6 |
| 管理后台构建 | Umi Max 4 (Turbopack) | 4.x |
| 前后端语言 | Python 3.12+ / TypeScript 5.x | — |
| 邮件服务 | 阿里云邮件推送 / SendGrid | — |

### Selected Starters

#### Backend: FastAPI Standard Project Structure

**Rationale:** FastAPI 无官方 CLI，采用 2026 年社区标准分层架构。路由 (routers) → 服务 (services) → 数据访问 (models) 三层分离。

**Project Structure:**
```
backend/
├── app/
│   ├── main.py
│   ├── core/          # config, security, database
│   ├── api/v1/        # routers by module
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   └── services/      # business logic
├── alembic/
└── pyproject.toml
```

#### User Web: React 19 + Vite 5 + Ant Design v6

**Rationale:** 移除微信小程序，改用通用 Web 端。React 19 + Vite 5 提供快速开发和构建体验，Ant Design v6 提供完整组件库。用户通过浏览器访问，无需微信生态依赖。

**Init Command:**
```bash
npm create vite@latest user-web -- --template react-ts
cd user-web && npm install antd @ant-design/icons react-router-dom
```

**Architectural Decisions:**
- **Language & Runtime:** React 19 + TypeScript 5.x
- **Styling:** Ant Design v6 + CSS Modules
- **Build Tooling:** Vite 5 (esbuild)
- **Routing:** react-router-dom v6
- **State Management:** @tanstack/react-query (服务端状态) + Zustand (客户端状态)
- **Code Quality:** Biome (lint + format)

#### Payment App: React 19 + Vite 5 + Ant Design v6

**Rationale:** 支付小闭环独立应用，支持888/5000/10000在线支付。与 user-web 技术栈一致，便于复用组件和工具函数。支付成功后回调后端生成 License，可选填推荐码计算佣金。

**Init Command:**
```bash
npm create vite@latest payment-app -- --template react-ts
cd payment-app && npm install antd @ant-design/icons react-router-dom
```

**Architectural Decisions:**
- **Language & Runtime:** React 19 + TypeScript 5.x
- **Styling:** Ant Design v6 + CSS Modules
- **Build Tooling:** Vite 5 (esbuild)
- **Routing:** react-router-dom v6
- **State Management:** @tanstack/react-query (服务端状态) + Zustand (客户端状态)
- **Code Quality:** Biome (lint + format)

#### Admin Web: Ant Design Pro v6

**Rationale:** 38k+ GitHub Stars，企业级中后台标准。v6 基于 React 19 + Ant Design 6 + Umi Max 4 (Turbopack)，构建速度提升 42%。

**Init Command:**
```bash
git clone https://github.com/ant-design/ant-design-pro.git admin-web
cd admin-web && npm run simple
```

**Architectural Decisions Provided:**
- **Language & Runtime:** React 19 + TypeScript 5.x
- **Styling:** Tailwind CSS v4 + antd-style (CSS-in-JS) + CSS Modules
- **Build Tooling:** Umi Max 4 (Turbopack), 42% faster builds
- **Routing:** Umi Max 约定式路由 + 权限路由
- **State Management:** @tanstack/react-query (服务端状态) + Umi Max model (客户端状态)
- **Code Quality:** Biome (lint + format)

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- 用户关系数据模型：邻接表 (parent_id)，不限深度但佣金仅查直接下级
- 推荐码设计：Base62 编码 + HMAC-SHA256 签名，**持久码，1人1码，支付时选填**
- 分销端认证：user-web 邮箱+验证码 JWT + admin-web 账号密码 JWT
- API 风格：RESTful，版本化路径 `/api/v1/`
- 佣金引擎：事件驱动 + 参数表 + 幂等键，**场景A不产生佣金，场景B产生佣金**
- License 对接：生成 + 验证接口，不绑定邮箱，激活时绑定业务系统用户，一次性使用

**Important Decisions (Shape Architecture):**
- 部署架构：单机部署，FastAPI + MySQL + Nginx
- 佣金参数：数据库配置表，管理员可配，仅对新业务生效

**Deferred Decisions (Post-MVP):**
- Docker 容器化
- CI/CD 流水线
- 水平扩展 / 负载均衡

### Data Architecture

#### Decision 1: 用户关系模型 — 邻接表 (parent_id)

**选择:** 邻接表，每行存储 `parent_id` 指向直接上级。

**理由:** 用户关系深度不限，但佣金计算仅基于直接下级（不穿透更深层级），邻接表查询直接下级只需 `WHERE parent_id = ?`，查询上级链最多 N 次回溯（N=层级深度），无需闭包表的额外复杂度。

**核心表结构:**

```sql
-- ============================================
-- 用户与认证
-- ============================================

-- 用户表（分销系统用户：代理/经销商，终端用户在业务系统）
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(128) UNIQUE NOT NULL,    -- 邮箱（唯一标识）
    password_hash VARCHAR(256),            -- 密码哈希（邮箱+验证码登录后可设置）
    nickname VARCHAR(64),
    avatar_url VARCHAR(256),
    role ENUM('distributor', 'agent') DEFAULT 'distributor', -- 2 角色：经销商/代理
    parent_id BIGINT,                      -- 直接上级（通过推荐码建立）
    referral_code VARCHAR(32) UNIQUE,      -- 个人推荐码（持久码，1人1码）
    referral_code_generated TINYINT(1) DEFAULT 0, -- 是否已生成推荐码
    account_quota INT DEFAULT 0,           -- 可售额度（代理22/经销商11/其他0）
    account_used INT DEFAULT 0,            -- 已使用额度
    status ENUM('pending', 'active', 'rejected') DEFAULT 'active',
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    FOREIGN KEY (parent_id) REFERENCES users(id)
);

-- 管理员用户表（独立于分销系统用户）
CREATE TABLE admin_users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(32) DEFAULT 'admin',
    created_at DATETIME DEFAULT NOW()
);

-- 邮箱验证码记录（替代短信验证码）
CREATE TABLE email_verification_codes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(128) NOT NULL,
    code VARCHAR(6) NOT NULL,
    scene VARCHAR(32) NOT NULL DEFAULT 'login', -- login, sale_verify
    verified TINYINT(1) DEFAULT 0,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    INDEX idx_email_scene_verified (email, scene, verified, expires_at)
);

-- ============================================
-- 推荐码
-- ============================================

-- 推荐码表（持久码，1人1码，可重复使用）
CREATE TABLE referral_codes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) UNIQUE NOT NULL,      -- 推荐码（持久码，含签名）
    user_id BIGINT NOT NULL UNIQUE,        -- 所属用户（1人1码）
    key_version INT DEFAULT 1,             -- HMAC 密钥版本（支持密钥轮换）
    is_active TINYINT(1) DEFAULT 1,        -- 是否有效（可停用）
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- 支付（场景B的核心事件源）
-- ============================================

-- 支付记录表（用户支付888/5000/10000，在线支付或线下审核）
CREATE TABLE payments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,                        -- 分销系统用户ID（5000/10000支付时创建，888为NULL）
    email VARCHAR(128) NOT NULL,           -- 支付者邮箱
    amount DECIMAL(10,2) NOT NULL,         -- 支付金额：888.00 / 5000.00 / 10000.00
    target_role ENUM('member_license', 'distributor', 'agent') NOT NULL, -- 888=仅License / 5000=经销商 / 10000=代理
    referral_code VARCHAR(64),             -- 推荐码（选填）
    channel ENUM('online', 'offline') DEFAULT 'online', -- 在线支付/线下审核
    status ENUM('pending', 'paid', 'failed', 'refunded') DEFAULT 'pending',
    payment_no VARCHAR(128),               -- 第三方支付流水号
    license_code VARCHAR(128),             -- 支付成功后生成的License
    reviewed_by BIGINT,                    -- 审核人（线下支付）
    reviewed_at DATETIME,
    reject_reason VARCHAR(256),
    redirect_url VARCHAR(512),             -- 支付成功回跳URL（在线支付）
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by) REFERENCES admin_users(id)
);

-- ============================================
-- 额度销售（场景A，不产生佣金）
-- ============================================

-- 账号销售记录（代理/经销商用额度销售给客户）
CREATE TABLE sales (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    seller_id BIGINT NOT NULL,             -- 销售人（代理/经销商）
    customer_email VARCHAR(128) NOT NULL,  -- 客户邮箱
    amount DECIMAL(10,2) NOT NULL DEFAULT 888.00,
    remark VARCHAR(256),
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (seller_id) REFERENCES users(id)
);

-- 账号额度补购记录
CREATE TABLE quota_purchases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- License 对接
-- ============================================

-- License 表（用户支付888后生成，供业务系统验证）
CREATE TABLE licenses (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(128) UNIQUE NOT NULL,     -- License Code（含防篡改签名）
    user_id BIGINT,                        -- 所属用户（888支付时为NULL，5000/10000为支付者）
    activated_user_id VARCHAR(128),        -- 业务系统用户标识（激活时绑定）
    activated_user_info JSON,              -- 业务系统用户信息
    source ENUM('payment', 'sale', 'role_builtin') NOT NULL, -- 来源：支付/额度销售/角色自带
    source_id BIGINT,                      -- 来源业务ID（payment_id 或 sale_id）
    status ENUM('unused', 'activated', 'expired') DEFAULT 'unused',
    activated_at DATETIME,                 -- 激活时间（业务系统验证后）
    expires_at DATETIME,                   -- 过期时间（可选）
    key_version INT DEFAULT 1,             -- HMAC 密钥版本
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- 佣金
-- ============================================

-- 佣金参数配置表（2角色，管理员可配）
CREATE TABLE commission_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    role ENUM('agent', 'distributor') NOT NULL,
    scene VARCHAR(32) NOT NULL,            -- first_reward_888, first_reward_5000, first_reward_10000, follow_up_888, team_bonus
    reward_type ENUM('fixed', 'percentage') NOT NULL,
    reward_value DECIMAL(10,4) NOT NULL,   -- 488.4000 或 0.0500
    updated_at DATETIME DEFAULT NOW(),
    UNIQUE KEY uk_role_scene (role, scene)
);

-- 佣金记录表（幂等：business_id UNIQUE）
CREATE TABLE commission_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,               -- 获得佣金的用户
    amount DECIMAL(12,2) NOT NULL,
    type ENUM('first_reward', 'follow_up', 'team_bonus', 'recommend') NOT NULL,
    source_user_id BIGINT,                 -- 来源下级
    business_id VARCHAR(64) UNIQUE NOT NULL, -- 幂等键: "payment_{id}_first" / "payment_{id}_follow" / "settle_{user_id}_{period}"
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- 提现工单
-- ============================================

CREATE TABLE tickets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    payment_method VARCHAR(256) NOT NULL,  -- 收款信息
    status ENUM('pending', 'paid', 'rejected') DEFAULT 'pending',
    reject_reason VARCHAR(256),
    processed_by BIGINT,                   -- 处理人（管理员 ID）
    processed_at DATETIME,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (processed_by) REFERENCES admin_users(id)
);

-- ============================================
-- 审计与日志
-- ============================================

-- 审计日志（NFR-2：不可删除）
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    operator_id BIGINT,
    operator_type ENUM('user', 'admin', 'system') NOT NULL,
    action VARCHAR(64) NOT NULL,           -- commission_create, ticket_status_change, config_update, payment_approve, license_activate
    target_type VARCHAR(32),               -- commission_record, ticket, user, config, license
    target_id BIGINT,
    old_value JSON,                        -- 变更前值
    new_value JSON,                        -- 变更后值
    business_id VARCHAR(64),               -- 关联业务 ID
    created_at DATETIME DEFAULT NOW()
);

-- 配置变更日志（FR-23：谁、何时、改了什么）
CREATE TABLE config_change_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    admin_id BIGINT NOT NULL,
    config_key VARCHAR(64) NOT NULL,
    old_value VARCHAR(256),
    new_value VARCHAR(256) NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (admin_id) REFERENCES admin_users(id)
);

-- ============================================
-- 通知
-- ============================================

-- 通知发送记录
CREATE TABLE notification_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(32) NOT NULL,       -- new_downline, commission_earned, ticket_status, payment_approved
    content JSON,                          -- 消息内容
    sent TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Authentication & Security

#### Decision 2: 分销端 JWT 认证

**User Web 端（邮箱+验证码）:**
1. 代理/经销商通过支付5000/10000创建账号，或超管直接创建
2. 登录：POST `/api/v1/auth/send-email-code` {email, scene: 'login'} → POST `/api/v1/auth/login` {email, code}
3. 超管创建：POST `/api/v1/admin/users/create` {email, role, referral_code?}

**Admin Web 端（账号密码）:**
1. POST `/api/v1/auth/admin-login` {username, password}
2. 后端验证 → 签发 JWT (type=admin)

**JWT Payload:**
```json
// 分销系统用户（代理/经销商）
{"sub": 123, "role": "agent", "type": "user", "exp": ...}

// 管理员
{"sub": 1, "role": "admin", "type": "admin", "exp": ...}
```

#### Decision 3: 推荐码设计（持久码）

**格式:** `Base62(payload) + "." + HMAC-SHA256(payload, SECRET_KEY)[:16]`

- `payload = f"{user_id}"` （1人1码，无随机nonce）
- **持久码，可重复使用** — 每次支付时验证有效性
- Base62 编码（字符集 `0-9A-Za-z`），使用 `base62` 包
- HMAC-SHA256 签名取前 16 个十六进制字符（64 位熵）
- `referral_codes.key_version` 支持密钥轮换

**生成流程:**
1. 用户请求获取推荐码 → GET `/api/v1/referral-code`
2. 服务端：`payload = f"{user_id}"` → Base62 编码
3. 服务端：`signature = HMAC-SHA256(payload, SECRET_KEY).hex()[:16]`
4. 返回：`f"{payload}.{signature}"` 存入 `referral_codes` 表（含 `key_version`，1人1码）

**解析流程:**
1. 支付时选填推荐码 → POST `/api/v1/payments/create` {amount, referral_code?}
2. 服务端：按最后一个 `.` 拆分 payload 和 signature
3. 服务端：重新计算签名比对
4. 签名不匹配 → 拒绝（`INVALID_REFERRAL_CODE`）
5. 签名匹配 → Base62 解码 payload 得到 `user_id`
6. 校验推荐码有效（`is_active = 1`）
7. 推荐码可重复使用，每次支付时验证有效性，不标记已使用

#### Decision 4: License 设计

**格式:** `Base62(payload) + "." + HMAC-SHA256(payload, LICENSE_SECRET)[:16]`

- `payload = f"{payment_id}:{source}"` （不含email）
- License 不绑定邮箱，生成时为 unused 状态
- 一次性使用，激活后标记为 `activated`，激活时绑定业务系统用户
- 验证接口需 API Key 鉴权（供业务系统调用）

**生成时机:**
- 支付 888 → 仅生成 License（source=payment，user_id 为 NULL）
- 支付 5000 → 经销商，生成 License（source=role_builtin）
- 支付 10000 → 代理，生成 License（source=role_builtin）
- 额度销售（场景A）→ 客户获得 License（source=sale）

**验证接口:**
- POST `/api/v1/license/verify` {code} （需 API Key）→ 返回 {valid, status, license_info}
- POST `/api/v1/license/activate` {code, business_user_id, business_user_info} （需 API Key）→ 标记为 activated + 绑定业务系统用户
- 验证逻辑：License 存在 + 状态为 unused
- 激活通过：标记为 activated，绑定 `activated_user_id` 和 `activated_user_info`，返回成功
- 验证失败：返回具体错误

### API & Communication Patterns

#### Decision 5: RESTful API 设计

**API 路由规划:**

```
# 认证
POST   /api/v1/auth/send-email-code     # 发送邮箱验证码
POST   /api/v1/auth/login               # 登录（邮箱+验证码）
POST   /api/v1/auth/admin-login         # 管理员登录

# 用户
GET    /api/v1/users/me                  # 我的信息
GET    /api/v1/users/me/team             # 我的团队（下级树）
GET    /api/v1/users/me/upstream         # 我的上级链条
GET    /api/v1/users/me/license          # 我的 License

# 推荐码
GET    /api/v1/referral-code             # 获取我的持久推荐码

# 支付
POST   /api/v1/payments/create           # 创建支付订单（选填推荐码）
GET    /api/v1/payments                  # 我的支付记录
POST   /api/v1/payments/callback         # 支付回调（第三方）
GET    /api/v1/payments/{id}/status      # 查询支付状态

# 额度销售（场景A）
POST   /api/v1/sales                     # 额度销售（消耗额度）
GET    /api/v1/sales                     # 销售记录列表
POST   /api/v1/quota-purchases           # 申请补购额度

# 佣金/收益
GET    /api/v1/commissions               # 我的收益明细
GET    /api/v1/commissions/stats         # 收益统计

# 提现工单
POST   /api/v1/tickets                   # 提交提现
GET    /api/v1/tickets                   # 我的工单列表

# License 验证（供业务系统调用，需 API Key）
POST   /api/v1/license/verify            # 验证 License
POST   /api/v1/license/activate          # 激活 License（绑定业务系统用户）

# 管理员
GET    /api/v1/admin/users               # 用户列表
GET    /api/v1/admin/users/{id}          # 用户详情
POST   /api/v1/admin/users/create        # 超管创建种子用户
GET    /api/v1/admin/payments            # 支付审核列表
POST   /api/v1/admin/payments/{id}/approve   # 批准支付
POST   /api/v1/admin/payments/{id}/reject    # 拒绝支付
GET    /api/v1/admin/tickets             # 工单列表
POST   /api/v1/admin/tickets/{id}/pay    # 确认打款
POST   /api/v1/admin/tickets/{id}/reject # 拒绝工单
GET    /api/v1/admin/dashboard           # 数据看板
GET    /api/v1/admin/config              # 获取配置
PUT    /api/v1/admin/config              # 更新配置
```

**错误响应格式:**
```json
{"detail": "推荐码无效，请联系分享者确认", "code": "INVALID_REFERRAL_CODE"}
```

### Commission Engine

#### Decision 6: 事件驱动佣金引擎（场景A/B 分离）

**核心原则:**
- **场景 A（额度销售）→ 不产生佣金**，成本已在准入费中
- **场景 B（在线支付）→ 产生佣金**，按规则记账给直接上级
- **无推荐码=无佣金**，平台收全款

**触发点:**
| 事件 | 触发时机 | 计算内容 |
|------|---------|---------|
| 支付确认 | 在线支付成功或管理员批准支付 | 上级首次奖励 + 代理→经销商后续收益 |
| 定时结算 | APScheduler 定时触发 | 长期奖励（5%/4%，仅直接下级） |

**佣金参数表种子数据:**
```sql
INSERT INTO commission_configs (role, scene, reward_type, reward_value) VALUES
-- 首次奖励（场景B，下级支付时直接上级获得）
('agent', 'first_reward_888', 'fixed', 488.40),       -- 代理推荐的人支付888
('agent', 'first_reward_5000', 'fixed', 2750.00),     -- 代理推荐的人支付5000
('agent', 'first_reward_10000', 'fixed', 5500.00),    -- 代理推荐的人支付10000
('agent', 'follow_up_888', 'fixed', 133.20),          -- 代理的下级经销商推荐的人支付888
('agent', 'team_bonus', 'percentage', 0.05),          -- 代理→代理 长期奖励5%
('distributor', 'first_reward_888', 'fixed', 355.20), -- 经销商推荐的人支付888
('distributor', 'first_reward_5000', 'fixed', 2000.00),
('distributor', 'first_reward_10000', 'fixed', 4000.00),
('distributor', 'team_bonus', 'percentage', 0.04);    -- 经销商→代理/经销商 长期奖励4%
```

**佣金规则说明:**

1. **首次奖励（场景B）:**
   - 下级支付 888：上级是代理→488.4，经销商→355.2
   - 下级支付 5000：上级是代理→2750，经销商→2000
   - 下级支付 10000：上级是代理→5500，经销商→4000
   - **无推荐码=无佣金**，平台收全款

2. **后续收益（仅代理→经销商）:**
   - 代理的直接下级经销商，每次推荐他人支付 888（场景B），代理获得 133.2 元/笔

3. **长期奖励（定期结算，仅限直接下级全部收入×比例）:**
   - 代理→代理：5%
   - 代理→经销商：不适用（已由 133.2 元/笔替代）
   - 经销商→代理：4%
   - 经销商→经销商：4%

**"全部收入"定义:** 直接下级获得的所有佣金总和，包括首次奖励 + 后续收益 + 长期奖励。

**幂等保护:** 每笔记账前使用 `business_id` UNIQUE 约束 + `INSERT ... ON DUPLICATE KEY`，确保并发安全。

**佣金计算走查示例 — 支付确认（场景B）:**

> **场景:** 用户 B（上级是代理 A，使用 A 的推荐码）支付 888 元获得 License。
>
> 1. 支付成功 → `PaymentService.confirm(payment_id=101)`
> 2. 生成 License（B 不创建分销系统账号）
> 3. 触发 `CommissionService.calculate_for_payment(payment_id=101)`
> 4. 查支付时的推荐码 → 解码得到上级 A（代理）
> 5. 查 `commission_configs`：`(role=agent, scene=first_reward_888)` → `fixed, 488.40`
> 6. 记账 A 的首次奖励：
>    - `business_id = "payment_101_first"`, `user_id=A`, `amount=488.40`, `type=first_reward`
> 7. 写入 `audit_logs`：`action=commission_create, business_id=payment_101_first`

**佣金计算走查示例 — 后续收益（代理→经销商）:**

> **场景:** 经销商 D（上级是代理 A）推荐的人 C（使用 D 的推荐码）支付 888 元。
>
> 1. C 的支付成功 → 触发首次奖励给 D（355.20 元）
> 2. 查 D 的上级：`D.parent_id = A`（代理），D 的角色是 `distributor`
> 3. 查 `commission_configs`：`(role=agent, scene=follow_up_888)` → `fixed, 133.20`
> 4. 记账 A 的后续收益：
>    - `business_id = "payment_{C的payment_id}_follow"`, `user_id=A`, `amount=133.20`, `type=follow_up`
> 5. 写入 `audit_logs`

**长期奖励走查示例 — 月度结算:**

> **场景:** 每月 1 日 APScheduler 触发结算。
>
> 1. 遍历所有代理/经销商用户
> 2. 对每个用户 U，查其所有直接下级
> 3. 对每个直接下级 D，聚合 D 在上月的 `commission_records` 总额 = `D_income`
> 4. 查 `commission_configs` 中 U 的 `team_bonus` 比例
> 5. 特殊处理：如果 U 是代理、D 是经销商 → 跳过（已由 133.2 替代）
> 6. 记账：`business_id = "settle_{U_id}_{YYYYMM}_{D_id}"`, `amount = D_income × 比例`
> 7. 幂等：同一周期重复执行不会重复记账

### Infrastructure & Deployment

#### Decision 7: 单机部署架构

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  User Web    │   │  Admin Web   │   │ Payment App  │
│  (React+Vite)│   │ (Ant Design  │   │ (React+Vite) │
│              │   │   Pro v6)    │   │              │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │ HTTPS             │ HTTPS             │ HTTPS
       └────────┬──────────┘────────────┬─────┘
                ▼                       │
       ┌────────────────┐               │
       │  Nginx (反向代理) │               │
       │  /api/* → 后端   │               │
       │  /*     → 静态文件│               │
       └───────┬────────┘               │
               │                        │
       ┌───────▼────────┐               │
       │  FastAPI 后端   │◄──────────────┘
       │  (Uvicorn)     │  支付回调
       │  Port: 8000    │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   MySQL 8.0    │
       │   Port: 3306   │
       └────────────────┘
```

- User Web、Admin Web 和 Payment App 均构建为静态文件，由 Nginx 托管
- Payment App 负责在线支付小闭环（888/5000/10000），支付成功后回调后端生成 License
- 定时任务（长期奖励结算）使用 APScheduler 内嵌在 FastAPI 进程中
- **APScheduler 风险:** 进程重启丢失任务状态；多 worker 部署时任务重复执行。缓解措施：长期奖励结算使用 `business_id = "settle_{user_id}_{YYYYMM}_{downline_id}"` 保证幂等

### Seed Data

**管理员引导:** 首次部署时通过脚本创建初始管理员账号：
```bash
python scripts/create_admin.py --username admin --password <secure_password>
```

**推荐码种子数据:** 超管创建种子用户后，系统自动为代理/经销商生成持久推荐码（1人1码），存入 `referral_codes` 表。

**佣金配置种子数据 (Alembic 迁移):**
```sql
INSERT INTO commission_configs (role, scene, reward_type, reward_value) VALUES
('agent', 'first_reward_888', 'fixed', 488.40),
('agent', 'first_reward_5000', 'fixed', 2750.00),
('agent', 'first_reward_10000', 'fixed', 5500.00),
('agent', 'follow_up_888', 'fixed', 133.20),
('agent', 'team_bonus', 'percentage', 0.05),
('distributor', 'first_reward_888', 'fixed', 355.20),
('distributor', 'first_reward_5000', 'fixed', 2000.00),
('distributor', 'first_reward_10000', 'fixed', 4000.00),
('distributor', 'team_bonus', 'percentage', 0.04);
```

### Decision Impact Analysis

**Implementation Sequence:**
1. 数据库表结构 → Alembic 迁移（含种子数据）— **13 张表**
2. 认证模块（邮箱+验证码登录 + 管理员登录 + 超管创建种子用户）
3. 推荐码生成/解析（持久码，1人1码）+ 用户关系建立（支付时选填）
4. 支付小闭环（在线支付888/5000/10000）+ 支付回调 + License 生成
5. 线下支付审核 + 角色变更
6. 额度销售（场景A）+ 佣金记账（场景B，含幂等保护）
7. 团队树 + 上级链查询
8. License 验证/激活接口（供业务系统调用，激活时绑定业务系统用户）
9. 收益展示 + 提现工单
10. 管理后台 API
11. 定时任务（长期奖励，含幂等 checkpoint）
12. 通知

**Cross-Component Dependencies:**
- 佣金引擎依赖用户关系表（查直接上级）和佣金参数表
- License 生成依赖支付确认或额度销售
- License 验证/激活接口依赖 API Key 鉴权
- 提现工单依赖佣金记录表（余额 = sum(佣金) - sum(已提现)）
- 管理后台所有操作依赖认证中间件（JWT + type=admin）
- 推荐码解析依赖 HMAC 签名校验，支付时验证有效性

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Database Naming Conventions:**
- 表名：snake_case 复数 — `users`, `commission_records`, `referral_codes`, `payments`
- 列名：snake_case — `parent_id`, `created_at`
- 外键：`{referenced_table}_id` — `user_id`, `reviewed_by`
- 索引：`idx_{table}_{column}` — `idx_users_email`

**API Naming Conventions:**
- 路径：kebab-case 复数 — `/referral-codes`, `/commission-records`, `/payments`
- 参数：snake_case — `?user_id=1&page_size=20`
- 版本前缀：`/api/v1/`

**Code Naming Conventions:**

| 语言 | 变量/函数 | 类/组件 | 文件 |
|------|----------|---------|------|
| Python | snake_case: `get_user_team()` | PascalCase: `UserService` | snake_case: `user_service.py` |
| TypeScript | camelCase: `getUserTeam()` | PascalCase: `TeamTree` | PascalCase: `TeamTree.tsx` |

### Structure Patterns

**Backend (FastAPI) Organization:**
```
app/
├── api/v1/           # 路由层 — 只做参数提取和响应返回
│   ├── auth.py
│   ├── users.py
│   ├── referral_codes.py
│   ├── payments.py
│   ├── sales.py
│   ├── commissions.py
│   ├── tickets.py
│   ├── license.py
│   └── admin.py
├── services/         # 业务逻辑层 — 所有业务判断
│   ├── user_service.py
│   ├── referral_service.py
│   ├── payment_service.py
│   ├── commission_service.py
│   ├── sale_service.py
│   ├── license_service.py
│   ├── ticket_service.py
│   └── email_service.py
├── models/           # SQLAlchemy ORM 模型
├── schemas/          # Pydantic 请求/响应模型
└── core/             # 配置、安全、数据库连接
```

**分层规则:**
- **router** → 只做参数提取、调用 service、返回响应。不写业务逻辑。
- **service** → 承载所有业务逻辑，可调用多个 model。不直接操作 HTTP。
- **model** → 只做数据库 CRUD，不包含业务判断。

**User Web (React+Vite) Organization:**
```
src/
├── pages/            # 页面（按功能模块）
│   ├── login/        # 邮箱+验证码登录
│   ├── home/         # 首页（数据概览）
│   ├── referral/     # 推荐码（获取我的持久推荐码）
│   ├── team/         # 我的团队（下级树）
│   ├── upstream/     # 我的上级链条
│   ├── sale/         # 额度销售录入（场景A）
│   ├── pay/          # 支付页面（在线支付888/5000/10000）
│   ├── earnings/     # 我的收益（记账余额 + 明细）
│   ├── tickets/      # 提现工单（申请 + 列表）
│   ├── license/      # 我的 License
│   └── profile/      # 我的（个人信息、推荐码、额度）
├── components/       # 公共组件
├── services/         # API 调用封装
├── stores/           # 状态管理（Zustand）
└── utils/            # 工具函数
```

**Admin Web (Ant Design Pro) Organization:**
```
src/
├── pages/
│   ├── dashboard/    # 数据看板
│   ├── users/        # 用户列表 + 详情 + 创建种子用户
│   ├── payments/     # 支付审核
│   ├── tickets/      # 工单管理
│   └── config/       # 系统参数配置
├── services/         # API 调用（@tanstack/react-query）
└── components/       # 公共组件
```

### Format Patterns

**API Response Formats:**

```json
// 单条数据成功
{"data": {"id": 1, "nickname": "张三"}, "message": "ok"}

// 列表数据
{"data": [...], "total": 100, "page": 1, "page_size": 20}

// 错误
{"detail": "推荐码无效，请联系分享者确认", "code": "INVALID_REFERRAL_CODE"}
```

**Data Exchange Formats:**
- JSON 字段：后端与前端统一使用 snake_case（如 `referral_code`、`parent_id`）。后端 Pydantic 未配置 alias，前端直接以 snake_case 传输，避免转换层不一致
- 时间：ISO 8601 字符串 `"2026-06-18T16:00:00+08:00"`
- 金额：字符串（避免浮点精度问题）`"488.40"`
- 布尔：`true` / `false`

### Process Patterns

**Error Handling:**
- 后端：全局异常处理器捕获所有异常，统一返回 `{"detail": "...", "code": "..."}`
- User Web：每个 API 调用包裹 try-catch，错误提示用 Ant Design `message.error()`
- Admin Web：@tanstack/react-query 的 `onError` 回调 + Ant Design `message.error()`

**幂等性保护:**
- 所有佣金记账操作使用 `business_id` 作为幂等键
- 数据库 `UNIQUE` 约束 + 应用层 `INSERT IGNORE` 或先查后插

### Enforcement Guidelines

**All AI Agents MUST:**
1. 遵循上述命名规范，不得使用其他风格
2. 后端严格遵循 router → service → model 分层，不得跨层调用
3. API 响应使用统一格式 `{"data": ...}` 或 `{"detail": ..., "code": ...}`
4. 所有金额字段使用字符串传输，避免浮点精度问题
5. 佣金记账必须包含 `business_id` 幂等键
6. **场景 A（额度销售）不产生佣金记账**
7. **场景 B（在线支付）才产生佣金记账**
8. License 生成时不绑定邮箱，激活时绑定业务系统用户标识

## Project Structure & Boundaries

### Complete Project Directory Structure

```
user-salse/                          # 项目根目录
├── backend/                         # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口，注册路由和中间件
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings 配置
│   │   │   ├── security.py          # JWT 签发/验证、推荐码 HMAC、License HMAC
│   │   │   ├── database.py          # SQLAlchemy 引擎 + Session
│   │   │   └── exceptions.py        # 全局异常处理器
│   │   ├── api/v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # 邮箱验证码登录、管理员登录
│   │   │   ├── users.py             # 用户信息、团队树、上级链、License
│   │   │   ├── referral_codes.py    # 推荐码获取（持久码，1人1码）
│   │   │   ├── payments.py          # 支付创建、支付记录、回调、状态查询
│   │   │   ├── sales.py             # 额度销售录入（场景A）
│   │   │   ├── commissions.py       # 收益明细、统计
│   │   │   ├── tickets.py           # 提现申请、工单列表
│   │   │   ├── license.py           # License 验证/激活接口（供业务系统调用）
│   │   │   └── admin.py             # 用户管理、支付审核、配置、看板、创建种子用户
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py              # User ORM
│   │   │   ├── admin_user.py        # AdminUser ORM
│   │   │   ├── email_verification.py # EmailVerificationCode ORM
│   │   │   ├── referral_code.py     # ReferralCode ORM
│   │   │   ├── payment.py           # Payment ORM
│   │   │   ├── sale.py              # Sale ORM
│   │   │   ├── license.py           # License ORM
│   │   │   ├── commission.py        # CommissionRecord + CommissionConfig ORM
│   │   │   ├── ticket.py            # Ticket ORM
│   │   │   └── audit_log.py         # AuditLog + ConfigChangeLog ORM
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # 登录请求/响应
│   │   │   ├── user.py              # 用户请求/响应
│   │   │   ├── referral_code.py     # 推荐码请求/响应
│   │   │   ├── payment.py           # 支付请求/响应
│   │   │   ├── sale.py              # 销售请求/响应
│   │   │   ├── license.py           # License 请求/响应
│   │   │   ├── commission.py        # 佣金请求/响应
│   │   │   └── ticket.py            # 工单请求/响应
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── user_service.py      # 用户管理、角色管理
│   │       ├── referral_service.py  # 推荐码生成/解析、关系建立
│   │       ├── payment_service.py   # 支付创建 + 回调处理 + 审核
│   │       ├── commission_service.py # 佣金计算引擎（场景B）
│   │       ├── sale_service.py      # 额度销售（场景A）+ 额度管理
│   │       ├── license_service.py   # License 生成 + 验证/激活
│   │       ├── ticket_service.py    # 提现工单
│   │       └── email_service.py     # 邮件发送（验证码、通知）
│   ├── alembic/                     # 数据库迁移
│   │   └── versions/                # 迁移脚本
│   ├── scripts/
│   │   └── create_admin.py          # 管理员账号创建脚本
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_referral_codes.py
│   │   ├── test_payments.py
│   │   ├── test_commissions.py
│   │   ├── test_license.py
│   │   └── test_tickets.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env
│
├── user-web/                        # React + Vite 用户端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── login/               # 邮箱+验证码登录
│   │   │   ├── home/                # 首页（数据概览）
│   │   │   ├── referral/            # 推荐码（获取我的持久推荐码）
│   │   │   ├── team/                # 我的团队（下级树）
│   │   │   ├── upstream/            # 我的上级链条
│   │   │   ├── sale/                # 额度销售录入（场景A）
│   │   │   ├── pay/                 # 支付页面（在线支付888/5000/10000）
│   │   │   ├── earnings/            # 我的收益（记账余额 + 明细）
│   │   │   ├── tickets/             # 提现工单（申请 + 列表）
│   │   │   ├── license/             # 我的 License
│   │   │   └── profile/             # 我的（个人信息、推荐码、额度）
│   │   ├── components/
│   │   ├── services/
│   │   ├── stores/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
│
├── payment-app/                     # React + Vite 支付小闭环
│   ├── src/
│   │   ├── pages/
│   │   │   ├── checkout/            # 支付确认页（888/5000/10000）
│   │   │   ├── result/              # 支付结果页
│   │   │   └── referral/            # 推荐码选填
│   │   ├── components/
│   │   ├── services/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
│
└── admin-web/                       # Ant Design Pro v6 管理后台
    ├── config/
    │   └── proxy.ts                 # API 代理配置
    ├── src/
    │   ├── app.tsx                  # 运行时配置（权限、请求）
    │   ├── pages/
    │   │   ├── dashboard/           # 数据看板
    │   │   ├── users/               # 用户列表 + 详情 + 创建种子用户
    │   │   ├── payments/            # 支付审核
    │   │   ├── tickets/             # 工单管理
    │   │   └── config/              # 系统参数配置
    │   ├── services/
    │   └── components/
    ├── package.json
    └── .umirc.ts
```

### Architectural Boundaries

**API Boundaries:**
- User Web 端：仅可访问 `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/referral-code`, `/api/v1/payments/*`, `/api/v1/sales/*`, `/api/v1/commissions/*`, `/api/v1/tickets/*`
- Payment App 端：可访问 `/api/v1/payments/create`, `/api/v1/payments/callback`, `/api/v1/payments/{id}/status`, `/api/v1/referral-code`
- Admin Web 端：可访问全部 API（含 `/api/v1/admin/*`）
- 业务系统：仅可访问 `/api/v1/license/verify` 和 `/api/v1/license/activate`（需 API Key）
- 认证中间件根据 JWT `type` 字段（`user` / `admin`）区分权限

**Service Boundaries:**
- `commission_service.py` 是核心引擎，被 `payment_service.py`（支付确认时触发）、定时任务调用
- `license_service.py` 被 `payment_service.py`（支付确认）和 `sale_service.py`（额度销售）调用
- 各 service 之间通过依赖注入获取，不直接实例化

**Data Boundaries:**
- `payments` 表是场景B佣金引擎的事件源，不可删除
- `sales` 表是场景A的记录（不触发佣金），不可删除
- `audit_logs` 表仅追加，不可修改或删除
- `commission_records` 通过 `business_id` UNIQUE 约束保证幂等
- `licenses` 通过 `code` UNIQUE 约束 + 状态机保证一次性使用
- `referral_codes` 表为持久码，1人1码，可重复使用

### Requirements to Structure Mapping

| FR 模块 | 后端 | User Web 页面 | Admin Web 页面 |
|---------|------|-------------|---------------|
| 代理/经销商认证 (FR-1~4) | `auth.py`, `user_service.py`, `referral_service.py`, `email_service.py` | `login/`, `referral/` | — |
| 角色与支付 (FR-5~7) | `payments.py`, `payment_service.py`, `admin.py` | `pay/`, `profile/` | `payments/` |
| 推荐码与团队 (FR-8~10) | `users.py` | `team/`, `upstream/` | `users/` |
| License与额度销售 (FR-11~12) | `sales.py`, `sale_service.py`, `commission_service.py` | `sale/` | — |
| 佣金与收益 (FR-13~15) | `commissions.py`, `commission_service.py` | `earnings/` | — |
| License 对接 (FR-16~17) | `license.py`, `license_service.py` | `license/` | — |
| 提现工单 (FR-18~19) | `tickets.py`, `ticket_service.py` | `tickets/` | `tickets/` |
| 管理员后台 (FR-20~23) | `admin.py` | — | `dashboard/`, `users/`, `config/` |
| 消息通知 (FR-24) | `email_service.py` | 全局 | — |
| 支付小闭环 (FR-25) | `payments.py`, `payment_service.py` | `pay/` (Payment App) | — |
| 幂等性 (NFR-1) | `commission_service.py` | — | — |
| 审计日志 (NFR-2) | `audit_log.py` (全局中间件) | — | — |
| 推荐码安全 (NFR-3) | `security.py`, `referral_service.py` | — | — |
| License 安全 (NFR-4) | `security.py`, `license_service.py` | — | — |

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** 所有技术选型兼容，无冲突。FastAPI + SQLAlchemy + MySQL 是成熟的 Python 后端组合；React 19 + Vite 5 + Ant Design v6 是现代 Web 前端方案；Ant Design Pro v6 + Umi Max 4 是企业级中后台标准；Payment App 复用 user-web 技术栈实现支付小闭环。JWT 分销端认证通过 `type` 字段区分权限，与 API 边界设计一致。

**Pattern Consistency:** 三层分层（router→service→model）在目录结构和 API 设计中保持一致。命名规范覆盖数据库、API、Python、TypeScript 四个领域，无冲突。

**Structure Alignment:** 项目结构完全支持所有架构决策。13 张表覆盖所有业务实体（新增 referral_codes、payments，移除 invite_codes、recharges），35+ 个 API 端点覆盖所有功能模块，三端目录结构与 FR 映射表一一对应。

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:** 25/25 FRs 全部覆盖（100%）。每个 FR 模块均有对应的后端路由、服务层、前端页面。

**Non-Functional Requirements Coverage:** 4/4 NFRs 全部覆盖（100%）。

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified (用户体系独立、在线支付、License 对接、场景A/B 分离)
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified (移除小程序，改为 user-web + admin-web + payment-app 三端)
- [x] Integration patterns defined (License Code 对接)
- [x] Performance considerations addressed

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Key Changes from v1 (2026-06-21 修订):**
1. 移除微信小程序（Taro），改为 user-web (React+Vite) + admin-web (Ant Design Pro) + payment-app (React+Vite) 三端
2. **取消开放注册**：分销系统仅代理/经销商/管理员，终端用户在业务系统
3. **邀请码→推荐码**：一次性→持久码，1人1码，支付时选填（非注册时），仅代理和经销商持有
4. **佣金2档**：去掉20%档（user/member），仅保留55%(代理)和40%(经销商)，无推荐码=无佣金
5. **License不绑定邮箱**：生成时不绑定，激活时绑定业务系统用户标识
6. **超管创建种子用户**：不再冷启动登录创建
7. **新增支付小闭环App**：支持888/5000/10000在线支付
8. **两系统用户独立**：通过License验证API对接
9. 数据库表变更：invite_codes → referral_codes，recharges → payments（13张表不变，表名替换）
10. API路由更新：删除 register，invite-codes → referral-code，recharges → payments，新增 license/activate、admin/users/create
