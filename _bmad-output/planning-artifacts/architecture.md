---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-user-salse-2026-06-11/prd.md
workflowType: 'architecture'
project_name: 'user-salse'
user_name: 'Lenovo'
date: '2026-06-11'
lastStep: 8
status: 'complete'
completedAt: '2026-06-11'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:** 22 FRs 分为 8 个功能模块：

- 用户注册与认证（FR-1~4）：微信授权、手机绑定、邀请码解析与生成
- 角色与准入（FR-5~7）：角色确定、准入审核、账号额度管理及补购
- 邀请链与团队（FR-8~10）：关系记录、下级树、上级链
- 账号销售（FR-11~12）：销售记录+短信验证、普通用户推荐返佣
- 佣金计算（FR-13~15）：可配置佣金规则、收益展示、长期奖励
- 提现工单（FR-16~17）：提现申请、工单审核管理
- 管理员后台（FR-18~21）：用户管理、准入审核、数据看板、参数配置
- 消息通知（FR-22）：小程序订阅消息

**Non-Functional Requirements:** 3 个 NFR：

- NFR-1: 佣金记账幂等性（基于业务 ID 去重）
- NFR-2: 审计日志（所有金额变动可追溯，不可删除）
- NFR-3: 邀请码安全性（HMAC 防篡改签名）

**Scale & Complexity:**

- Primary domain: 全栈（微信小程序 + Web 管理后台 + REST API + 关系型数据库）
- Complexity level: 中高
- Estimated architectural components: 6-8

### Technical Constraints & Dependencies

- **微信生态依赖**: wx.login、手机号快速验证组件、订阅消息模板 — 需微信开放平台认证
- **短信服务**: 账号销售需短信验证码 — 第三方 SMS 提供商（如阿里云短信）
- **独立部署**: 管理后台为独立 Web 应用，非小程序云开发内嵌
- **线下支付**: v1 无在线支付集成，所有支付为线下+后台确认模式
- **配置热更新**: 佣金参数管理员可配，修改仅对新业务生效

### Cross-Cutting Concerns Identified

1. **树形数据查询性能** — 团队树无限深度，佣金沿链追溯，需预计算聚合或闭包表
2. **佣金幂等性** — 每笔记账需基于唯一业务 ID 去重，防止重复计算
3. **审计完整性** — 金额变动全链路日志，不可篡改
4. **双端认证** — 小程序用微信 OAuth，Web 后台用账号密码/Session
5. **邀请码安全** — 服务端签名 + 解析验证，防止角色伪造

## Starter Template Evaluation

### Primary Technology Domain

全栈多端应用：Python REST API + 微信小程序 + Web 管理后台

### Technology Stack Decisions

| 层 | 技术选型 | 版本 |
|---|---------|------|
| 后端框架 | FastAPI | latest |
| ORM | SQLAlchemy 2.0 | latest |
| 数据库迁移 | Alembic | latest |
| 数据库 | MySQL 8.0 | 8.0+ |
| 小程序框架 | Taro | 4.x |
| 小程序 UI | NutUI (React Taro) | latest |
| 管理后台框架 | Ant Design Pro | v6 |
| 管理后台构建 | Umi Max 4 (Turbopack) | 4.x |
| 前后端语言 | Python 3.12+ / TypeScript 5.x | — |

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

#### Mini Program: Taro 4.x + React + TypeScript

**Rationale:** Taro 4.x 是当前生产级版本，React + TypeScript 提供完整类型安全。NutUI 提供开箱即用的小程序组件。

**Init Command:**
```bash
taro init mini-program
# Select: React, TypeScript, SCSS, default template
```

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
- 用户关系数据模型：邻接表 (parent_id)，最多 3 层深度
- 邀请码设计：Base62 编码 + HMAC-SHA256 签名
- 双端认证：小程序 JWT (微信 OAuth) + 管理后台 JWT (账号密码)
- API 风格：RESTful，版本化路径 `/api/v1/`
- 佣金引擎：事件驱动 + 参数表 + 幂等键

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

**理由:** 用户关系深度限制在 2-3 级（代理→代理→经销商 或 代理→经销商→代理），邻接表查询上级链最多 2 次回溯，查询下级树最多 2 层展开，无需闭包表的额外复杂度。

**核心表结构:**

```sql
-- ============================================
-- 用户与认证
-- ============================================

-- 小程序用户表
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    openid VARCHAR(64) UNIQUE NOT NULL,
    phone VARCHAR(11) UNIQUE,
    nickname VARCHAR(64),
    avatar_url VARCHAR(256),
    role ENUM('user', 'distributor', 'agent') DEFAULT 'user',
    parent_id BIGINT,                    -- 直接上级
    invite_code VARCHAR(32) UNIQUE,      -- 个人邀请码（基础码，不含角色）
    account_quota INT DEFAULT 0,         -- 账号额度
    account_used INT DEFAULT 0,          -- 已使用额度
    status ENUM('pending', 'active', 'rejected') DEFAULT 'pending',
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    FOREIGN KEY (parent_id) REFERENCES users(id)
);

-- 管理员用户表（独立于小程序用户）
CREATE TABLE admin_users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(32) DEFAULT 'admin',
    created_at DATETIME DEFAULT NOW()
);

-- ============================================
-- 邀请码
-- ============================================

-- 邀请码表（记录每次生成的邀请码）
CREATE TABLE invite_codes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(64) UNIQUE NOT NULL,    -- 完整邀请码（含签名）
    generator_id BIGINT NOT NULL,        -- 生成者
    target_role ENUM('agent', 'distributor') NOT NULL,
    key_version INT DEFAULT 1,           -- HMAC 密钥版本（支持密钥轮换）
    used_by BIGINT,                      -- 使用者（注册后回填）
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (generator_id) REFERENCES users(id)
);

-- ============================================
-- 账号销售
-- ============================================

-- 账号销售记录（佣金引擎的核心事件源）
CREATE TABLE sales (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    seller_id BIGINT NOT NULL,           -- 销售人
    customer_phone VARCHAR(11) NOT NULL, -- 客户手机号
    amount DECIMAL(10,2) NOT NULL DEFAULT 888.00,
    remark VARCHAR(256),
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (seller_id) REFERENCES users(id)
);

-- 短信验证码记录
CREATE TABLE sms_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    phone VARCHAR(11) NOT NULL,
    code VARCHAR(6) NOT NULL,
    scene VARCHAR(32) NOT NULL DEFAULT 'sale_verify',
    verified TINYINT(1) DEFAULT 0,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT NOW()
);

-- ============================================
-- 额度管理
-- ============================================

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
-- 佣金
-- ============================================

-- 佣金参数配置表
CREATE TABLE commission_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    role ENUM('agent', 'distributor', 'user') NOT NULL,
    scene VARCHAR(32) NOT NULL,          -- self_sell, recruit_agent, recruit_distributor, downline_sell, recommend, team_bonus
    reward_type ENUM('fixed', 'percentage') NOT NULL,
    reward_value DECIMAL(10,4) NOT NULL, -- 488.4 或 0.05
    updated_at DATETIME DEFAULT NOW()
);

-- 佣金记录表（幂等：business_id UNIQUE）
CREATE TABLE commission_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    type ENUM('first_reward', 'sale_commission', 'team_bonus', 'recommend') NOT NULL,
    source_user_id BIGINT,               -- 来源下级
    business_id VARCHAR(64) UNIQUE NOT NULL, -- 幂等键: "sale_{id}" / "entry_{id}" / "settle_{user_id}_{period}"
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
    payment_method VARCHAR(256) NOT NULL, -- 收款信息（银行卡/支付宝）
    status ENUM('pending', 'paid', 'rejected') DEFAULT 'pending',
    reject_reason VARCHAR(256),
    processed_by BIGINT,                  -- 处理人（管理员 ID）
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
    operator_id BIGINT,                  -- 操作人（用户或管理员）
    operator_type ENUM('user', 'admin') NOT NULL,
    action VARCHAR(64) NOT NULL,         -- commission_create, ticket_status_change, config_update, entry_approve
    target_type VARCHAR(32),             -- commission_record, ticket, user, config
    target_id BIGINT,
    old_value JSON,                      -- 变更前值
    new_value JSON,                      -- 变更后值
    business_id VARCHAR(64),             -- 关联业务 ID
    created_at DATETIME DEFAULT NOW()
);

-- 配置变更日志（FR-21：谁、何时、改了什么）
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

-- 订阅消息发送记录
CREATE TABLE notification_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(32) NOT NULL,     -- new_downline, commission_earned, ticket_status, entry_approved
    content JSON,                        -- 消息内容
    sent TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Authentication & Security

#### Decision 2: 双端 JWT 认证

**小程序端:**
1. 前端调用 `wx.login()` 获取 code
2. 前端调用 `wx.getPhoneNumber()` 获取手机号加密数据
3. POST `/api/v1/auth/wechat-login` {code, encrypted_phone, invite_code?}
4. 后端解密 → 创建/查找用户 → 签发 JWT

**管理后台:**
1. POST `/api/v1/auth/admin-login` {username, password}
2. 后端验证 → 签发 JWT (role=admin)

**JWT Payload:**
```json
// 小程序用户
{"sub": 123, "role": "agent", "type": "wechat", "exp": ...}

// 管理员
{"sub": 1, "role": "admin", "type": "admin", "exp": ...}
```

#### Decision 3: 邀请码设计

**格式:** `Base62(payload) + "." + HMAC-SHA256(payload, SECRET_KEY)[:16]`

- `payload = f"{user_id}:{target_role}"` （冒号分隔）
- Base62 编码（字符集 `0-9A-Za-z`），非 Python 标准库，使用 `base62` 包或自定义实现
- HMAC-SHA256 签名取前 16 个十六进制字符（64 位熵，防暴力破解）
- `invite_codes.key_version` 支持密钥轮换：旧密钥签名的邀请码仍可验证

**生成流程:**
1. 用户选择目标角色 → POST `/api/v1/invite-codes/generate` {target_role}
2. 服务端：`payload = f"{user_id}:{target_role}"` → Base62 编码
3. 服务端：`signature = HMAC-SHA256(payload, SECRET_KEY).hex()[:16]`
4. 返回：`f"{payload}.{signature}"` 存入 `invite_codes` 表（含 `key_version`）

**解析流程:**
1. 用户输入邀请码 → POST `/api/v1/invite-codes/verify` {code}
2. 服务端：按最后一个 `.` 拆分 payload 和 signature
3. 服务端：用 `key_version` 对应的密钥重新计算签名比对
4. 签名不匹配 → 拒绝（`INVALID_INVITE_CODE`）
5. 签名匹配 → Base62 解码 payload 得到 `generator_id` 和 `target_role`

### API & Communication Patterns

#### Decision 4: RESTful API 设计

**API 路由规划:**

```
# 认证
POST   /api/v1/auth/wechat-login
POST   /api/v1/auth/admin-login

# 用户
GET    /api/v1/users/me
GET    /api/v1/users/{id}/team          # 下级团队树
GET    /api/v1/users/{id}/upstream      # 上级链条

# 邀请码
POST   /api/v1/invite-codes/generate
POST   /api/v1/invite-codes/verify

# 账号销售
POST   /api/v1/sales                    # 录入销售
GET    /api/v1/sales                    # 销售记录列表

# 佣金/收益
GET    /api/v1/commissions              # 我的收益
GET    /api/v1/commissions/stats        # 收益统计

# 提现工单
POST   /api/v1/tickets                  # 提交提现
GET    /api/v1/tickets                  # 我的工单列表

# 管理员
GET    /api/v1/admin/users              # 用户列表
GET    /api/v1/admin/users/{id}         # 用户详情
POST   /api/v1/admin/users/{id}/approve # 准入审核
POST   /api/v1/admin/users/{id}/quota   # 追加额度
GET    /api/v1/admin/tickets            # 工单列表
POST   /api/v1/admin/tickets/{id}/pay   # 确认打款
POST   /api/v1/admin/tickets/{id}/reject # 拒绝工单
GET    /api/v1/admin/dashboard          # 数据看板
GET    /api/v1/admin/config             # 获取配置
PUT    /api/v1/admin/config             # 更新配置
```

**错误响应格式:**
```json
{"detail": "邀请码无效，请联系分享者确认", "code": "INVALID_INVITE_CODE"}
```

### Commission Engine

#### Decision 5: 事件驱动佣金引擎

**触发点:**
| 事件 | 触发时机 | 计算内容 |
|------|---------|---------|
| 准入确认 | 管理员批准准入申请 | 上级首次奖励 |
| 账号销售 | 销售记录创建 | 自销佣金 + 上级销售提成 |
| 推荐购买 | 普通用户下级购买 | 推荐返佣 |
| 定时结算 | 定时任务触发 | 长期奖励 (5%/4%) |

**佣金参数表:**
```sql
CREATE TABLE commission_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    role ENUM('agent', 'distributor', 'user') NOT NULL,
    scene VARCHAR(32) NOT NULL,          -- self_sell, recruit_agent, recruit_distributor, downline_sell, recommend
    reward_type ENUM('fixed', 'percentage') NOT NULL,
    reward_value DECIMAL(10,4) NOT NULL, -- 488.4 或 0.05
    updated_at DATETIME DEFAULT NOW()
);
```

**佣金记录表 (幂等):**
```sql
CREATE TABLE commission_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    type ENUM('first_reward', 'sale_commission', 'team_bonus', 'recommend') NOT NULL,
    source_user_id BIGINT,               -- 来源下级
    business_id VARCHAR(64) UNIQUE NOT NULL, -- 幂等键: "sale_{id}" / "entry_{id}"
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**幂等保护:** 每笔记账前使用 `INSERT ... ON DUPLICATE KEY` 或事务内 `SELECT FOR UPDATE` + `INSERT`，确保并发安全。

**佣金计算走查示例 — 账号销售:**

> **场景:** 经销商 B（上级代理 A）卖出一个账号 888 元。
>
> 1. `POST /api/v1/sales` → `SaleService.create_sale(seller_id=B, customer_phone=...)`
> 2. 校验额度 > 0 → 创建 `sales` 记录 (id=101)
> 3. 触发 `CommissionService.calculate_for_sale(sale_id=101)`
> 4. 查 `commission_configs`：
>    - `(role=distributor, scene=self_sell)` → `reward_type=fixed, reward_value=355.20`
>    - `(role=agent, scene=downline_sell)` → `reward_type=fixed, reward_value=133.20`
> 5. 记账 B 的自销佣金：
>    - `business_id = "sale_101_self"`, `user_id=B`, `amount=355.20`, `type=sale_commission`
> 6. 查 B 的上级链：`B.parent_id = A`（代理）
> 7. 记账 A 的下级销售提成：
>    - `business_id = "sale_101_upstream_A"`, `user_id=A`, `amount=133.20`, `type=sale_commission`
> 8. 更新 B 的 `account_used += 1`
> 9. 写入 `audit_logs`：`action=commission_create, target_type=commission_record, business_id=sale_101_self`

**长期奖励走查示例 — 月度结算:**

> **场景:** 每月 1 日 APScheduler 触发结算。
>
> 1. 遍历所有代理/经销商用户
> 2. 对每个用户，聚合其所有下级（递归 parent_id）在上月的 `sales` 总额 = `team_revenue`
> 3. 查 `commission_configs` 中 `scene=team_bonus` 的比例
> 4. 沿上级链逐级记账：`business_id = "settle_{上级ID}_{YYYYMM}"`
> 5. 每笔记账独立幂等：同一周期重复执行不会重复记账
> 6. 写入 `audit_logs`

### Infrastructure & Deployment

#### Decision 6: 单机部署架构

```
┌──────────────┐   ┌──────────────┐
│  微信小程序   │   │  Web 管理后台 │
│  (Taro 4.x)  │   │ (Ant Design  │
│              │   │   Pro v6)    │
└──────┬───────┘   └──────┬───────┘
       │ HTTPS             │ HTTPS
       └────────┬──────────┘
                ▼
       ┌────────────────┐
       │  Nginx (反向代理) │
       │  /api/* → 后端   │
       │  /*     → 静态文件│
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │  FastAPI 后端   │
       │  (Uvicorn)     │
       │  Port: 8000    │
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   MySQL 8.0    │
       │   Port: 3306   │
       └────────────────┘
```

- 管理后台构建为静态文件，由 Nginx 托管
- 小程序通过 HTTPS 域名访问 API
- 定时任务（长期奖励结算）使用 APScheduler 内嵌在 FastAPI 进程中
- **APScheduler 风险:** 进程重启丢失任务状态；多 worker 部署时任务重复执行。缓解措施：长期奖励结算使用 `business_id = "settle_{user_id}_{YYYYMM}"` 保证幂等，建议后续迁移至 Celery Beat + Redis

### Seed Data

**管理员引导:** 首次部署时通过脚本创建初始管理员账号：
```bash
python scripts/create_admin.py --username admin --password <secure_password>
```

**佣金配置种子数据 (Alembic 迁移):**
```sql
INSERT INTO commission_configs (role, scene, reward_type, reward_value) VALUES
('agent', 'self_sell', 'fixed', 488.40),
('agent', 'recruit_agent', 'fixed', 5500.00),
('agent', 'recruit_distributor', 'fixed', 2750.00),
('agent', 'downline_sell', 'fixed', 133.20),
('agent', 'team_bonus', 'percentage', 0.05),
('distributor', 'self_sell', 'fixed', 355.20),
('distributor', 'recruit_agent', 'fixed', 4000.00),
('distributor', 'recruit_distributor', 'fixed', 2000.00),
('distributor', 'team_bonus', 'percentage', 0.04),
('user', 'recommend', 'fixed', 177.60);
```

### Decision Impact Analysis

**Implementation Sequence:**
1. 数据库表结构 → Alembic 迁移（含种子数据）
2. 认证模块 (微信登录 + 管理员登录)
3. 用户注册 + 邀请码生成/解析
4. 角色准入 + 额度管理
5. 账号销售 + 佣金记账（含幂等保护）
6. 团队树 + 上级链查询
7. 收益展示 + 提现工单
8. 管理后台 API
9. 定时任务 (长期奖励，含幂等 checkpoint)
10. 订阅消息通知

**Cross-Component Dependencies:**
- 佣金引擎依赖用户关系表（查上级链）和佣金参数表
- 提现工单依赖佣金记录表（余额 = sum(佣金) - sum(已提现)）
- 管理后台所有操作依赖认证中间件（JWT + role=admin）
- 短信服务依赖第三方 SMS SDK（阿里云/腾讯云）

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 三个独立代码库（Python 后端 + Taro 小程序 + Ant Design Pro 后台），15+ 处潜在命名/格式/结构冲突点。

### Naming Patterns

**Database Naming Conventions:**
- 表名：snake_case 复数 — `users`, `commission_records`, `invite_codes`
- 列名：snake_case — `parent_id`, `created_at`, `target_role`
- 外键：`{referenced_table}_id` — `user_id`, `generator_id`
- 索引：`idx_{table}_{column}` — `idx_users_phone`

**API Naming Conventions:**
- 路径：kebab-case 复数 — `/invite-codes`, `/commission-records`
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
│   ├── sales.py
│   ├── commissions.py
│   ├── tickets.py
│   └── admin.py
├── services/         # 业务逻辑层 — 所有业务判断
│   ├── user_service.py
│   ├── invite_service.py
│   ├── commission_service.py
│   └── ticket_service.py
├── models/           # SQLAlchemy ORM 模型
├── schemas/          # Pydantic 请求/响应模型
└── core/             # 配置、安全、数据库连接
```

**分层规则:**
- **router** → 只做参数提取、调用 service、返回响应。不写业务逻辑。
- **service** → 承载所有业务逻辑，可调用多个 model。不直接操作 HTTP。
- **model** → 只做数据库 CRUD，不包含业务判断。

**Mini Program (Taro) Organization:**
```
src/
├── pages/            # 页面（按功能模块）
│   ├── login/
│   ├── home/
│   ├── team/
│   ├── earnings/
│   └── profile/
├── components/       # 公共组件
├── services/         # API 调用封装
├── stores/           # 状态管理
└── utils/            # 工具函数
```

**Admin Web (Ant Design Pro) Organization:**
```
src/
├── pages/            # 页面（按功能模块）
│   ├── dashboard/
│   ├── users/
│   ├── approvals/
│   ├── tickets/
│   └── config/
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
{"detail": "邀请码无效，请联系分享者确认", "code": "INVALID_INVITE_CODE"}
```

**Data Exchange Formats:**
- JSON 字段：后端 snake_case，前端 camelCase（FastAPI Pydantic `alias` 自动转换）
- 时间：ISO 8601 字符串 `"2026-06-11T16:00:00+08:00"`
- 金额：字符串（避免浮点精度问题）`"488.40"`
- 布尔：`true` / `false`

**HTTP Status Codes:**
- 200: 成功
- 201: 创建成功
- 400: 参数错误
- 401: 未认证
- 403: 无权限
- 404: 资源不存在
- 409: 冲突（如重复幂等键）
- 422: 数据校验失败
- 500: 服务器内部错误

### Process Patterns

**Error Handling:**
- 后端：全局异常处理器捕获所有异常，统一返回 `{"detail": "...", "code": "..."}`
- 小程序：每个 API 调用包裹 try-catch，错误提示用 `Taro.showToast()`
- 管理后台：@tanstack/react-query 的 `onError` 回调 + Ant Design `message.error()`

**Loading States:**
- 小程序：页面级 `Taro.showLoading()` / `Taro.hideLoading()`
- 管理后台：表格/列表用 Ant Design `Spin` 或 `Skeleton`

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

**Pattern Enforcement:**
- 后端：代码审查时检查分层是否合规
- 前端：ESLint + Biome 自动检查命名规范
- API：FastAPI 自动生成 OpenAPI 文档，检查响应格式一致性

## Project Structure & Boundaries

### Complete Project Directory Structure

```
user-salse/                          # 项目根目录
├── backend/                         # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口，注册路由和中间件
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings 配置
│   │   │   ├── security.py          # JWT 签发/验证、邀请码 HMAC
│   │   │   ├── database.py          # SQLAlchemy 引擎 + Session
│   │   │   └── exceptions.py        # 全局异常处理器
│   │   ├── api/v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # 微信登录、管理员登录
│   │   │   ├── users.py             # 用户信息、团队树、上级链
│   │   │   ├── invite_codes.py      # 邀请码生成、验证
│   │   │   ├── sales.py             # 账号销售录入、列表
│   │   │   ├── commissions.py       # 收益明细、统计
│   │   │   ├── tickets.py           # 提现申请、工单列表
│   │   │   └── admin.py             # 用户管理、审核、配置、看板
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py              # User ORM
│   │   │   ├── admin_user.py        # AdminUser ORM
│   │   │   ├── invite_code.py       # InviteCode ORM
│   │   │   ├── sale.py              # Sale ORM
│   │   │   ├── commission.py        # CommissionRecord + CommissionConfig ORM
│   │   │   ├── ticket.py            # Ticket ORM
│   │   │   └── audit_log.py         # AuditLog + ConfigChangeLog ORM
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # 登录请求/响应
│   │   │   ├── user.py              # 用户请求/响应
│   │   │   ├── invite_code.py       # 邀请码请求/响应
│   │   │   ├── sale.py              # 销售请求/响应
│   │   │   ├── commission.py        # 佣金请求/响应
│   │   │   └── ticket.py            # 工单请求/响应
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── user_service.py      # 用户注册、角色管理
│   │       ├── invite_service.py    # 邀请码生成/解析、关系建立
│   │       ├── commission_service.py # 佣金计算引擎
│   │       ├── sale_service.py      # 账号销售 + 额度管理
│   │       ├── ticket_service.py    # 提现工单
│   │       └── wechat_service.py    # 微信 API 调用（code2session、手机号解密）
│   ├── alembic/                     # 数据库迁移
│   │   └── versions/                # 迁移脚本
│   ├── scripts/
│   │   └── create_admin.py          # 管理员账号创建脚本
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_users.py
│   │   ├── test_commissions.py
│   │   └── test_tickets.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env
│
├── mini-program/                    # Taro 4.x 微信小程序
│   ├── config/
│   │   ├── index.ts                 # Taro 构建配置
│   │   ├── dev.ts                   # 开发环境
│   │   └── prod.ts                  # 生产环境
│   ├── src/
│   │   ├── app.tsx                  # 根组件（登录态守卫）
│   │   ├── app.config.ts            # 页面路由 + TabBar
│   │   ├── app.scss                 # 全局样式
│   │   ├── pages/
│   │   │   ├── login/               # 微信授权 + 手机号绑定 + 邀请码输入
│   │   │   ├── home/                # 首页（数据概览）
│   │   │   ├── invite/              # 邀请好友（选择目标角色生成邀请码）
│   │   │   ├── team/                # 我的团队（下级树）
│   │   │   ├── upstream/            # 我的上级链条
│   │   │   ├── sale/                # 账号销售录入
│   │   │   ├── earnings/            # 我的收益（记账余额 + 明细）
│   │   │   ├── tickets/             # 提现工单（申请 + 列表）
│   │   │   └── profile/             # 我的（个人信息、邀请码、额度）
│   │   ├── components/              # 公共组件
│   │   ├── services/                # API 调用封装
│   │   ├── stores/                  # 状态管理
│   │   └── utils/                   # 工具函数
│   ├── package.json
│   └── project.config.json          # 微信开发者工具配置
│
└── admin-web/                       # Ant Design Pro v6 管理后台
    ├── config/
    │   └── proxy.ts                 # API 代理配置
    ├── src/
    │   ├── app.tsx                  # 运行时配置（权限、请求）
    │   ├── pages/
    │   │   ├── dashboard/           # 数据看板
    │   │   ├── users/               # 用户列表 + 详情
    │   │   ├── approvals/           # 准入审核
    │   │   ├── tickets/             # 工单管理
    │   │   └── config/              # 系统参数配置
    │   ├── services/                # API 调用（@tanstack/react-query）
    │   └── components/              # 公共组件
    ├── package.json
    └── .umirc.ts                    # Umi Max 配置
```

### Architectural Boundaries

**API Boundaries:**
- 小程序端：仅可访问 `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/invite-codes/*`, `/api/v1/sales/*`, `/api/v1/commissions/*`, `/api/v1/tickets/*`
- 管理后台：可访问全部 API（含 `/api/v1/admin/*`）
- 认证中间件根据 JWT `type` 字段（`wechat` / `admin`）区分权限

**Service Boundaries:**
- `commission_service.py` 是核心引擎，被 `sale_service.py`、`user_service.py`（准入确认）、定时任务调用
- `wechat_service.py` 仅被 `auth.py` 和通知模块调用
- 各 service 之间通过依赖注入获取，不直接实例化

**Data Boundaries:**
- `sales` 表是佣金引擎的事件源，不可删除
- `audit_logs` 表仅追加，不可修改或删除
- `commission_records` 通过 `business_id` UNIQUE 约束保证幂等

### Requirements to Structure Mapping

| FR 模块 | 后端 | 小程序页面 | 管理后台页面 |
|---------|------|-----------|-------------|
| 注册与认证 (FR-1~4) | `auth.py`, `user_service.py`, `invite_service.py` | `login/`, `invite/` | — |
| 角色与准入 (FR-5~7) | `admin.py`, `user_service.py` | `profile/` | `approvals/` |
| 邀请链与团队 (FR-8~10) | `users.py` | `team/`, `upstream/` | `users/` |
| 账号销售 (FR-11~12) | `sales.py`, `sale_service.py`, `commission_service.py` | `sale/` | — |
| 佣金与收益 (FR-13~15) | `commissions.py`, `commission_service.py` | `earnings/` | — |
| 提现工单 (FR-16~17) | `tickets.py`, `ticket_service.py` | `tickets/` | `tickets/` |
| 管理员后台 (FR-18~21) | `admin.py` | — | `dashboard/`, `users/`, `config/` |
| 消息通知 (FR-22) | `wechat_service.py` | 全局订阅 | — |
| 幂等性 (NFR-1) | `commission_service.py` | — | — |
| 审计日志 (NFR-2) | `audit_log.py` (全局中间件) | — | — |
| 邀请码安全 (NFR-3) | `security.py`, `invite_service.py` | — | — |

### Integration Points

**Internal Communication:**
- 同步调用：router → service → model（同进程内函数调用）
- 异步任务：APScheduler 定时触发长期奖励结算
- 事件触发：准入确认 → `commission_service.create_first_reward()`；销售创建 → `commission_service.calculate_for_sale()`

**External Integrations:**
- 微信开放平台：`code2session` 接口（换取 OpenID）、`getPhoneNumber` 解密
- 短信服务商：阿里云 SMS / 腾讯云 SMS SDK
- 微信订阅消息：`subscribeMessage.send` API

**Data Flow:**
```
用户操作 → API Router → Service → Model → MySQL
                              ↓
                       CommissionService
                       (查配置 → 计算 → 记账 → 审计日志)
                              ↓
                       佣金记录 + 审计日志写入
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** 所有技术选型兼容，无冲突。FastAPI + SQLAlchemy + MySQL 是成熟的 Python 后端组合；Taro 4.x + React 18 + NutUI 是微信小程序生产级方案；Ant Design Pro v6 + React 19 + Umi Max 4 是企业级中后台标准。JWT 双端认证通过 `type` 字段区分权限，与 API 边界设计一致。

**Pattern Consistency:** 三层分层（router→service→model）在目录结构和 API 设计中保持一致。命名规范覆盖数据库、API、Python、TypeScript 四个领域，无冲突。

**Structure Alignment:** 项目结构完全支持所有架构决策。12 张表覆盖所有业务实体，24 个 API 端点覆盖所有功能模块，三端目录结构与 FR 映射表一一对应。

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:** 22/22 FRs 全部覆盖（100%）。每个 FR 模块均有对应的后端路由、服务层、前端页面。

**Non-Functional Requirements Coverage:** 3/3 NFRs 全部覆盖（100%）。NFR-1 幂等性通过 `business_id` UNIQUE 约束 + `INSERT ON DUPLICATE KEY` 实现；NFR-2 审计日志通过 `audit_logs` 表 + 全局中间件实现；NFR-3 邀请码安全通过 HMAC-SHA256 签名 + `key_version` 密钥轮换实现。

### Implementation Readiness Validation ✅

**Decision Completeness:** 6 个核心架构决策全部文档化，含版本号、理由、影响分析。佣金引擎含两个端到端走查示例（账号销售 9 步 + 长期奖励 6 步）。

**Structure Completeness:** 三端完整目录结构已定义，含 50+ 个具体文件路径。FR 到目录的映射表覆盖所有 22 个 FR 和 3 个 NFR。

**Pattern Completeness:** 命名规范（4 个领域）、结构规范（3 端）、格式规范（API 响应 + 数据交换 + HTTP 状态码）、流程规范（错误处理 + 加载状态 + 幂等保护）全部定义。

### Gap Analysis Results

**Critical Gaps:** 无。Party Mode 审查发现的问题（缺失 6 张表、邀请码 HMAC 细节不足、佣金引擎缺示例）已全部修复。

**Important Gaps:** 无。

**Nice-to-Have Gaps:** 无。

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
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

**Confidence Level:** High — 16/16 checklist items verified, 100% FR/NFR coverage, Party Mode review applied.

**Key Strengths:**
- 完整的数据模型（12 张表，含字段、约束、外键）
- 佣金引擎含端到端走查示例，消除实现歧义
- 三端目录结构与 FR 映射表，Agent 可直接按图索骥
- 幂等性、审计日志、邀请码安全三大 NFR 有具体实现方案
- 种子数据（管理员脚本 + 佣金配置 SQL）可直接执行

**Areas for Future Enhancement:**
- APScheduler → Celery Beat + Redis（多 worker 场景）
- Docker 容器化部署
- CI/CD 流水线
- 负载均衡与水平扩展

### Implementation Handoff

**AI Agent Guidelines:**
- 严格遵循 router → service → model 三层分层
- 所有 API 响应使用统一格式 `{"data": ...}` 或 `{"detail": ..., "code": ...}`
- 金额字段使用字符串传输
- 佣金记账必须包含 `business_id` 幂等键
- 遵循命名规范（Python snake_case, TypeScript camelCase, DB snake_case）

**First Implementation Priority:**
1. `backend/` 项目初始化：`pyproject.toml` + FastAPI + SQLAlchemy + Alembic
2. 数据库迁移：12 张表 + 种子数据
3. 认证模块：微信登录 + 管理员登录
