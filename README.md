# user-salse

足球舆情分销系统 — 销售奖励模型与分销管理平台。

## 项目结构

- `backend/` — Python FastAPI 后端（SQLAlchemy + Alembic + JWT 认证）
- `user-web/` — React 19 + Vite 5 用户端 Web 应用（邮箱注册/登录、团队、收益、充值、提现）
- `admin-web/` — Ant Design Pro v6 管理后台（用户管理、充值审核、运营看板、系统配置）

## 快速开始

### 后端

```bash
cd backend
pip install -e .
alembic upgrade head
python scripts/create_admin.py --username admin --password yourpassword
uvicorn app.main:app --reload
```

### 用户端 Web

```bash
cd user-web
npm install
npm run dev
```

开发服务器运行在 http://localhost:5173，API 请求自动代理到 http://localhost:8000。

### 管理后台

```bash
cd admin-web
npm install
npm run dev
```

## 技术栈

| 端 | 框架 | 版本 |
|----|------|------|
| 后端 | FastAPI + SQLAlchemy | Python 3.14 |
| 用户端 | React + Vite + Ant Design | React 19, Vite 5, antd v6 |
| 管理后台 | Ant Design Pro (Umi) | antd v6 |
| 数据库 | SQLite (开发) / PostgreSQL (生产) | — |

## 角色体系

| 角色 | 准入门槛 | 获赠可售额度 |
|------|---------|------------|
| 代理 | 10000 元 | 22 个 888 会员账号 |
| 经销商 | 5000 元 | 11 个 888 会员账号 |
| 888 会员 | 888 元 | — |
| 普通用户 | 无 | — |

## 佣金模型

- **场景 A（额度销售）**：代理/经销商消耗额度为客户开通 888 会员，不产生佣金
- **场景 B（推荐充值）**：下级自己充值，产生佣金（首次奖励 + 后续收益 + 长期奖励）

详细规则见 [需求说明.md](需求说明.md) 和 [用户旅途说明.md](用户旅途说明.md)。
