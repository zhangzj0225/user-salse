# Story 1.1: 项目骨架初始化

Status: done

## Story

As a 开发者,
I want 初始化三端项目骨架和数据库,
so that 后续功能开发有统一的基础架构。

## Acceptance Criteria

1. `backend/` 包含 FastAPI 项目结构（app/main.py, core/, api/v1/, models/, schemas/, services/）
2. `mini-program/` 包含 Taro 4.x + React + TypeScript 项目
3. `admin-web/` 包含 Ant Design Pro v6 项目
4. Alembic 已初始化并包含 12 张表的迁移脚本（users.openid 为 NULLABLE）
5. 种子数据迁移包含 1 个管理员账号和 10 条佣金配置 SQL
6. `pyproject.toml` 包含 FastAPI, SQLAlchemy, Alembic, PyJWT, base62, APScheduler 等依赖
7. `core/config.py` 包含 `AUTH_MODE` 配置项（默认 "mock"）

## Tasks / Subtasks

- [x] Task 1: 创建项目根目录结构 (AC: 1,2,3)
  - [x] 创建 `user-salse/` 根目录
  - [x] 创建 `backend/`, `mini-program/`, `admin-web/` 三个子目录

- [x] Task 2: 初始化 FastAPI 后端项目 (AC: 1,6,7)
  - [x] 创建 `backend/pyproject.toml`，包含所有依赖
  - [x] 创建 `backend/app/main.py` — FastAPI 入口
  - [x] 创建 `backend/app/core/__init__.py`, `config.py`, `security.py`, `database.py`, `exceptions.py`
  - [x] 创建 `backend/app/api/__init__.py`, `backend/app/api/v1/__init__.py`
  - [x] 创建 `backend/app/models/__init__.py`
  - [x] 创建 `backend/app/schemas/__init__.py`
  - [x] 创建 `backend/app/services/__init__.py`
  - [x] `core/config.py` 包含 `AUTH_MODE: str = "mock"` 和 `DATABASE_URL`, `SECRET_KEY`, `JWT_ALGORITHM` 等配置项

- [x] Task 3: 初始化 Taro 小程序项目 (AC: 2)
  - [x] 手动创建 Taro 4.x + React + TypeScript + SCSS 项目骨架
  - [x] 确认 `src/app.config.ts` 基础配置正确

- [x] Task 4: 初始化 Ant Design Pro 管理后台 (AC: 3)
  - [x] 手动创建 Ant Design Pro v6 项目骨架（Umi Max 4）
  - [x] 配置路由：dashboard, users, approvals, tickets, config

- [x] Task 5: 数据库迁移 — 12 张表 DDL (AC: 4)
  - [x] 创建 Alembic 配置（alembic.ini, env.py）
  - [x] 编写迁移脚本 001_create_all_tables.py — 12 张表完整 DDL
  - [x] 编写迁移脚本 002_seed_commission_configs.py — 种子数据

- [x] Task 6: 种子数据 (AC: 5)
  - [x] 创建 `backend/scripts/create_admin.py` — 管理员账号创建脚本（bcrypt 哈希密码）
  - [x] 编写种子数据迁移（Alembic data migration），插入 10 条佣金配置

## Dev Notes

### 技术栈（来自 Architecture §Starter Template Evaluation）

| 层 | 技术 | 版本 |
|---|------|------|
| 后端框架 | FastAPI | latest |
| ORM | SQLAlchemy 2.0 | latest |
| 数据库迁移 | Alembic | latest |
| 数据库 | MySQL 8.0 | 8.0+ |
| 小程序框架 | Taro | 4.x |
| 小程序 UI | NutUI (React Taro) | latest |
| 管理后台 | Ant Design Pro | v6 |
| 管理后台构建 | Umi Max 4 (Turbopack) | 4.x |

### 关键架构决策

- **openid 为 NULLABLE**：`users.openid VARCHAR(64) UNIQUE NULL` — 支持 Mock 模式下用户无真实 openid（Mock 时用 `"mock_{phone}"` 填充）
- **AUTH_MODE 配置**：`core/config.py` 中 `AUTH_MODE: str = "mock"`，后续通过环境变量切换为 `"wechat"`
- **JWT subject 使用 user_id**：不是 openid，确保 Mock→微信切换时零代码改动
- **三层分层**：router → service → model，本 Story 只创建骨架目录，不实现业务逻辑
- **金额字段使用 DECIMAL**：`amount DECIMAL(12,2)` 和 `reward_value DECIMAL(10,4)`，避免浮点精度问题

### 命名规范（来自 Architecture §Implementation Patterns）

- 数据库表名：snake_case 复数 — `users`, `commission_records`
- 数据库列名：snake_case — `parent_id`, `created_at`
- Python 文件：snake_case — `user_service.py`
- Python 类：PascalCase — `UserService`
- 外键：`{referenced_table}_id` — `user_id`, `generator_id`

### 后端目录结构（来自 Architecture §Project Structure）

```
backend/
├── app/
│   ├── main.py                  # FastAPI 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings（AUTH_MODE, DATABASE_URL, SECRET_KEY）
│   │   ├── security.py          # JWT 签发/验证（本 Story 仅骨架）
│   │   ├── database.py          # SQLAlchemy 引擎 + Session
│   │   └── exceptions.py        # 全局异常处理器（本 Story 仅骨架）
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   └── services/
│       └── __init__.py
├── alembic/
│   ├── env.py
│   ├── versions/                # 迁移脚本
│   └── alembic.ini
├── scripts/
│   └── create_admin.py
├── pyproject.toml
└── .env
```

### pyproject.toml 依赖清单

```toml
[project]
name = "user-salse-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]",
    "uvicorn[standard]",
    "sqlalchemy>=2.0",
    "alembic",
    "pymysql",
    "pyjwt",
    "passlib[bcrypt]",
    "pydantic-settings",
    "base62",
    "apscheduler",
]
```

### 注意事项

- **不要安装 Taro CLI 全局**：使用 `npx @tarojs/cli init` 避免版本冲突
- **Ant Design Pro 使用 `npm run simple`**：生成最小化模板，非完整 demo
- **Alembic 迁移需包含 downgrade**：确保可回滚
- **MySQL 需要预先创建数据库**：`CREATE DATABASE user_salse CHARACTER SET utf8mb4;`
- **.env 文件不提交到 Git**：包含 SECRET_KEY 等敏感信息

### References

- [Source: Architecture §Data Architecture] — 12 张表完整 DDL
- [Source: Architecture §Starter Template Evaluation] — 技术栈和初始化命令
- [Source: Architecture §Implementation Patterns] — 命名规范和分层规则
- [Source: Architecture §Project Structure] — 三端完整目录结构
- [Source: Architecture §Seed Data] — 管理员脚本和佣金配置 SQL
- [Source: Epics §Story 1.1] — 验收标准

## Dev Agent Record

### Agent Model Used

Claude-4.5-Opus

### Debug Log References

### Completion Notes List

- Task 1: 创建了三端根目录结构 backend/, mini-program/, admin-web/
- Task 2: 创建 FastAPI 后端项目骨架，包含 pyproject.toml（9 个依赖）、main.py（/health 端点）、core/（config/security/database/exceptions）、api/v1/、models/、schemas/、services/
- Task 3: 手动创建 Taro 4.x 小程序项目骨架（因 npx CLI 需要交互式输入），包含 package.json、tsconfig.json、app.tsx、app.config.ts、config/、pages/index/
- Task 4: 手动创建 Ant Design Pro v6 管理后台骨架（因 git clone 网络限制），包含 package.json、.umirc.ts（5 个路由 + API 代理）、5 个页面占位组件
- Task 5: 创建 Alembic 迁移 001_create_all_tables.py（12 张表完整 DDL，含 downgrade）和 002_seed_commission_configs.py（10 条佣金配置）
- Task 6: 创建 scripts/create_admin.py（bcrypt 密码哈希）和 .env 配置文件
- 附加：创建 .gitignore 和 README.md

### File List

- backend/pyproject.toml
- backend/app/main.py
- backend/app/core/__init__.py
- backend/app/core/config.py
- backend/app/core/security.py
- backend/app/core/database.py
- backend/app/core/exceptions.py
- backend/app/api/__init__.py
- backend/app/api/v1/__init__.py
- backend/app/models/__init__.py
- backend/app/schemas/__init__.py
- backend/app/services/__init__.py
- backend/alembic.ini
- backend/alembic/env.py
- backend/alembic/versions/001_create_all_tables.py
- backend/alembic/versions/002_seed_commission_configs.py
- backend/scripts/create_admin.py
- backend/.env
- mini-program/package.json
- mini-program/tsconfig.json
- mini-program/project.config.json
- mini-program/src/app.tsx
- mini-program/src/app.config.ts
- mini-program/src/app.scss
- mini-program/src/pages/index/index.tsx
- mini-program/src/pages/index/index.config.ts
- mini-program/config/index.ts
- mini-program/config/dev.ts
- mini-program/config/prod.ts
- admin-web/package.json
- admin-web/tsconfig.json
- admin-web/.umirc.ts
- admin-web/src/pages/dashboard/index.tsx
- admin-web/src/pages/users/index.tsx
- admin-web/src/pages/approvals/index.tsx
- admin-web/src/pages/tickets/index.tsx
- admin-web/src/pages/config/index.tsx
- .gitignore
- README.md
