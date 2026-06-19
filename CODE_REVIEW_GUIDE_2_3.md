# Code Review Guide — Epic 2 全部完成

## 概览

Epic 2（架构重构与模型迁移）4 个 Story 全部完成。本文档汇总各 Story 的实现内容和 review 修复，供快速 review。

## Commit 历史

| Commit | Story | 内容 |
|--------|-------|------|
| `ead4d8d` | 2.2 | 认证模块 review 修复（行锁/IntegrityError/中文消息/审计日志/DRY） |
| `36a2791` | 2.4 | 佣金引擎重构（场景 A/B 分离 + 4 角色佣金规则） |
| `550d8ff` | 2.4 | 同伴 review 修复（金钱链路正确性 C1-C9） |
| `3688ca3` | 2.3 | 前端架构调整（删除 mini-program + 创建 user-web） |
| `13b7b36` | 2.3 | 前端 review 修复（7 项问题） |

## Story 2.3 前端架构调整 — Review 修复说明（commit `13b7b36`）

### 🔴 必须修复（已修复）

| # | 问题 | 修复方式 | 文件 |
|---|------|---------|------|
| 1 | 登录页"获取验证码"按钮取值错误 — `onSearch` 收到的是验证码框的值而非邮箱，认证主流程完全不可用 | `Form.useForm()` + `form.getFieldValue("email")` 读取邮箱字段 | `login/index.tsx` |

### 🟡 应该修复（已修复）

| # | 问题 | 修复方式 | 文件 |
|---|------|---------|------|
| 3 | API 错误处理不健壮 — 422 校验错误渲染为 `[object Object]`，网络错误无提示 | 422 数组取首条 `msg`；无 response 时 fallback "网络异常，请稍后重试" | `api.ts` |
| 4 | 响应拦截器 `return response.data` 破坏 TypeScript 类型安全 | 新增 `request<T>()` typed helper，`auth.ts` 使用泛型调用 | `api.ts`, `auth.ts` |
| 5 | 倒计时定时器泄漏 + Tab 间状态共享 + 可重复触发 | `useEffect` cleanup 清理 `clearInterval`；login/register 各自独立 countdown 状态；倒计时期间 `disabled={true}` | `login/index.tsx` |
| 6 | antd 静态 `message` 脱离 ConfigProvider 上下文 | `main.tsx` 包裹 `<AntdApp>`；`App.tsx` 用 `App.useApp()` 获取 message 实例注入到 API 错误处理器 | `main.tsx`, `App.tsx`, `api.ts` |
| 7 | Biome 已声明依赖但未配置 | 新增 `biome.json`；`package.json` 添加 `lint`/`format` 脚本 | `biome.json`, `package.json` |

### 🔵 建议改进（已修复）

| # | 问题 | 修复方式 |
|---|------|---------|
| 9 | 已登录用户仍可访问 /login | `LoginPage` 内 `useEffect` 检测 token 后 `navigate("/")` |
| 12 | 缺 public/ 目录 | 创建 `public/.gitkeep` |

### 未修复（延后到 Epic 6）

| # | 问题 | 延后原因 |
|---|------|---------|
| 2 | JWT 存 localStorage 暴露于 XSS | 架构未规定 token 存储方式，生产前评估 httpOnly cookie |
| 8 | 路由守卫不解析 exp | 401 兜底已覆盖安全性，体验优化延后 |
| 10 | 组件文件名 index.tsx 与 PascalCase 规范不符 | 常见约定，骨架阶段不改 |
| 11 | 样式用内联 style | Epic 6 迁移到 CSS Modules |
| 13 | dayjs / @ant-design/icons 已装未用 | 骨架阶段正常 |

## Story 2.4 佣金引擎重构 — 同伴 Review 修复说明（commit `550d8ff`）

同伴在 review 中做了 9 项修复（C1-C9），全部合理：

| # | 改动 | 说明 |
|---|------|------|
| C1 | 事务约定：flush 不 commit，docstring 明确 + 测试锁定 | 防止调用方忘记 commit 导致静默丢账 |
| C3 | `record_commission` IntegrityError 捕获 → 幂等降级 | 修复了我标记为延后的 MF-1 TOCTOU 竞态 |
| C4 | amount 与 recharge 记录一致性校验 | 查 recharges 表校验，不信任调用方 |
| C5 | 后续收益仅在充 888 时触发 | 在 process_recharge 内集成，减少调用方复杂度 |
| C6 | `calculate_followup_reward` 签名重构 | 改为 `recharge_id + recharger_user_id`，引擎内部反查链路 |
| C8 | `source_user_id` 改为真实充值人 C | 收益明细展示来源用户，不是中间经销商 |
| C9 | float 金额类型拒绝 | `isinstance(amount, int)` 防止 888.0 绕过校验 |
| Decimal | 金额类型从 float → Decimal | 架构要求避免浮点精度问题 |
| SF-3 | `calculate_first_reward` source_user_id 参数 | 方法自包含，调用方无需额外设置 |

## 验证方法

```bash
# 后端测试
cd backend
python -m pytest tests/ -v
# 预期: 162 passed

# 前端 TypeScript 编译
cd user-web
npx tsc --noEmit
# 预期: 无错误

# 前端构建
npx vite build
# 预期: 构建成功

# Biome lint
npx biome lint src/
```

## Epic 2 完成状态

| Story | 状态 | 测试数 |
|-------|------|--------|
| 2.1 数据库模型重构 | done | — |
| 2.2 认证模块重构 | done | — |
| 2.3 前端架构调整 | done | tsc + vite build 通过 |
| 2.4 佣金引擎重构 | done | 162 backend tests |

## 文档与实现的偏差（记录备查）

1. 架构文档 `architecture.md:390` 写发送验证码端点为 `POST /api/v1/auth/send-code`，实际实现为 `/auth/send-email-code`
2. 架构文档声称"Pydantic alias 自动转换为 camelCase"，实际后端接收 snake_case（`invite_code`），前端匹配了实际行为
3. 以上均为文档 stale，建议后续更新架构文档
