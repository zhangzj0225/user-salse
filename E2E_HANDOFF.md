# 足球舆情分销系统 — E2E 测试交接文档

## 1. 系统架构

| 组件 | 技术栈 | 端口 | 目录 |
|------|--------|------|------|
| 后端 API | FastAPI + SQLAlchemy + SQLite | 8000 | `backend/` |
| 前端 Web | React 19 + Vite + Ant Design v6 | 5173 | `user-web/` |
| 定时任务 | APScheduler (后台进程) | — | `backend/app/services/scheduler_service.py` |

## 2. 环境变量

**后端** (`backend/.env`):
```env
ENV=dev
DATABASE_URL=sqlite:///./deploy_test.db
SECRET_KEY=deploy-test-secret-key-32bytes!!
INVITE_CODE_SECRET=deploy-test-invite-secret-ok
LICENSE_SECRET=deploy-test-license-secret-ok
LICENSE_API_KEY=deploy-test-license-api-key
AUTH_MODE=mock
CORS_ORIGINS=http://localhost:5173
```

**前端** (`user-web/.env`):
```env
VITE_API_PROXY=http://127.0.0.1:8000
```

**E2E 测试**（所有脚本从 `e2e_common.py` 读取，支持环境变量覆盖）:

| 变量 | 默认值 | 说明 |
|------|--------|------|
| E2E_API_BASE | http://127.0.0.1:8000 | 后端地址 |
| E2E_UI_BASE | http://localhost:5173 | 前端地址 |
| E2E_MOCK_CODE | 123456 | Mock 验证码 |
| E2E_ADMIN_USER | admin | 管理员用户名 |
| E2E_ADMIN_PASS | admin123 | 管理员密码 |
| E2E_LICENSE_KEY | deploy-test-license-api-key | License API Key |
| DATABASE_URL | （必须设置） | 与运行中后端指向同一库 |

**Mock 模式**：验证码固定为 `123456`，无需真实邮件服务。

## 3. 启动命令

```bash
# 后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端
cd user-web
npx vite --host 0.0.0.0 --port 5173
```

## 4. 测试账号

| 角色 | 邮箱 | 密码/验证码 | 说明 |
|------|------|-----------|------|
| 管理员 | admin | admin123 | 后台全部权限 |
| 任意新用户 | 任意邮箱 | 123456 (mock) | AUTH_MODE=mock 时自动创建 |

## 5. 佣金规则速查（来自需求说明.md）

### 5.1 首次奖励（场景B：直接下级充值）

| 上级角色 | 下级充 888 | 下级充 5000 | 下级充 10000 |
|---------|-----------|------------|-------------|
| 代理 (55%) | 488.40 | 2750 | 5500 |
| 经销商 (40%) | 355.20 | 2000 | 4000 |
| 普通/会员 (20%) | 177.60 | **0** | **0** |

### 5.2 后续收益（仅代理→经销商链）

代理的直接下级经销商，每推荐 1 人充 888 → 代理获 **133.20 元/笔**。
- A(代理)→B(代理)→C(经销商)→D(用户充888) → B 获 133.20，**A 不获**（agent→agent 非 agent→distributor）

### 5.3 长期奖励（直接下级全部佣金 × 比例）

| 上级 | 下级 | 比例 |
|------|------|------|
| 代理 | 代理 | 5% |
| 代理 | 经销商 | **不适用**（133.20/笔替代） |
| 经销商 | 代理 | 4% |
| 经销商 | 经销商 | 4% |

### 5.4 场景A：额度销售

| 充值 | 角色 | 获额度 | 产生佣金 |
|------|------|--------|---------|
| 10000 | 代理 | 22 | ❌ 不产生 |
| 5000 | 经销商 | 11 | ❌ 不产生 |
| 888 | 888会员 | 0 | ❌ 不产生 |

## 6. 核心 API 端点

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/send-email-code` | 发送验证码 `{email, scene}` |
| POST | `/api/v1/auth/login` | 用户登录 `{email, code}` |
| POST | `/api/v1/auth/register` | 用户注册 `{email, code, invite_code}` |
| POST | `/api/v1/auth/admin-login` | 管理员登录 `{username, password}` |

### 邀请码
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/invite-codes` | 生成邀请码（需 auth） |
| GET | `/api/v1/invite-codes` | 列出我的邀请码（需 auth） |

### 充值 + 审批
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/recharges` | 创建充值 `{amount: 888\|5000\|10000}` |
| POST | `/api/v1/admin/recharges/{id}/approve` | 管理员审批（触发角色升级+佣金） |

### 收益
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/users/me/earnings` | 收益汇总+明细 `?type=&limit=&offset=` |

### 提现
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/users/me/tickets` | 创建提现 `{amount, payment_method}` |
| POST | `/api/v1/admin/tickets/{id}/approve` | 审批打款 |
| POST | `/api/v1/admin/tickets/{id}/reject` | 拒绝工单 |

### 团队
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/users/me/team` | 我的下级树 |
| GET | `/api/v1/users/me/upstream` | 我的上级链路 |

### 销售
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sales` | 消耗额度销售 `{customer_email, verification_code}` |

### 管理后台
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/dashboard` | 运营看板 |
| GET | `/api/v1/admin/users?role=&limit=&offset=` | 用户列表 |
| GET | `/api/v1/admin/recharges?status=pending` | 待审充值 |
| GET | `/api/v1/admin/tickets?status=pending` | 待审工单 |
| GET | `/api/v1/admin/configs` | 系统配置 |

## 7. 测试脚本

所有脚本从 `e2e_common.py` 导入公共模块，不再硬编码路径/密码/URL。

### 运行方式
```bash
# 必须设置 DATABASE_URL（与后端 .env 一致）
set DATABASE_URL=sqlite:///./backend/deploy_test.db

# 深层分销链 (19/19)
python chain_e2e.py

# 缺口覆盖 (31/31)
python e2e_gap_cover.py

# 全功能回归 (30/30)
python e2e_full_flow.py

# 可见浏览器测试（PRD v2 已删除 — 基于已废弃的注册/充值 API）
# python visible_e2e.py     — 已删除
# python visible_e2e_full.py — 已删除
```

## 8. Playwright 配置

- 安装：`pip install playwright && python -m playwright install chromium`
- 可见模式：`headless=False, slow_mo=400`
- 截图输出：`d:/user-salse/e2e_output/`
- **关键技巧**：切账号前需 `localStorage.clear()` + 重新导航，否则 token 残留导致自动重定向

## 9. 已知限制

| 问题 | 说明 | 影响 |
|------|------|------|
| SQLite 锁 | API 服务器和测试脚本并发写时锁冲突 | 额度销售测试偶发失败，用 headless 单独测试可绕过 |
| 验证码重试 | MockAuthService 的 send-email-code + register 跨 HTTP 请求偶发丢记录 | 用 login(冷启动) 代替 register，或用 SQLAlchemy 直接创建用户设 parent_id |
| /users/me 不含 quota | quota 需单独调 `/api/v1/quota` | 取额度用 `/quota` 端点 |

## 10. 需求覆盖率

| 需求场景 | 测试 | 状态 |
|---------|------|:--:|
| 邀请码注册→建立上下级 | S4 (Playwright 浏览器) | ✅ |
| 充值 888→会员+License | S1/S2 | ✅ |
| 充值 5000→经销商+11额度 | S4 | ✅ |
| 充值 10000→代理+22额度 | S1 (chain) | ✅ |
| 角色不降级 | S3 | ✅ |
| 首次奖励比率矩阵 | S6 (9种组合) | ✅ |
| 零佣金路径 | S6c | ✅ |
| 后续收益 agent→distributor | S2/S4/S6 | ✅ |
| 长期奖励 | S7 (需当月数据) | ⚠️ |
| 额度销售零佣金 | S5 (30/30), S8 (chain) | ⚠️ SQLite |
| 提现+余额冻结 | S8 | ✅ |
| 邀请码防重/防自推荐 | S9 | ✅ |
| 通知 | S8e | ✅ |

## 11. 数据库重建

```bash
cd backend
del deploy_test.db
python -c "import os; os.environ['ENV']='dev'; import app.models; from app.core.database import Base, get_session_local, get_engine; Base.metadata.create_all(get_engine()); db=get_session_local()(); from app.models.commission_config import CommissionConfig; from app.models.admin_user import AdminUser; from decimal import Decimal; import bcrypt; db.add_all([CommissionConfig(role='agent',scene='recharge_888',reward_type='fixed',reward_value=Decimal('488.40')),CommissionConfig(role='agent',scene='recharge_5000',reward_type='fixed',reward_value=Decimal('2750.00')),CommissionConfig(role='agent',scene='recharge_10000',reward_type='fixed',reward_value=Decimal('5500.00')),CommissionConfig(role='agent',scene='followup_reward',reward_type='fixed',reward_value=Decimal('133.20')),CommissionConfig(role='agent',scene='team_bonus',reward_type='percentage',reward_value=Decimal('0.05')),CommissionConfig(role='distributor',scene='recharge_888',reward_type='fixed',reward_value=Decimal('355.20')),CommissionConfig(role='distributor',scene='recharge_5000',reward_type='fixed',reward_value=Decimal('2000.00')),CommissionConfig(role='distributor',scene='recharge_10000',reward_type='fixed',reward_value=Decimal('4000.00')),CommissionConfig(role='distributor',scene='team_bonus',reward_type='percentage',reward_value=Decimal('0.04')),CommissionConfig(role='member',scene='recharge_888',reward_type='fixed',reward_value=Decimal('177.60')),CommissionConfig(role='user',scene='recharge_888',reward_type='fixed',reward_value=Decimal('177.60'))]); pwh=bcrypt.hashpw(b'admin123',bcrypt.gensalt()).decode(); db.add(AdminUser(username='admin',password_hash=pwh,role='super_admin')); db.commit(); db.close(); print('DB seeded')"
```
