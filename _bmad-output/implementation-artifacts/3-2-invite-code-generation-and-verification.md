---
story_id: "3.2"
story_key: "3-2-invite-code-generation-and-verification"
epic: "Epic 3 — 核心业务闭环"
title: "邀请码生成与验证"
status: "ready-for-dev"
priority: "high"
---

# Story 3.2: 邀请码生成与验证

## User Story

As a 任意用户,
I want 生成统一类型的邀请码,
So that 推荐他人注册。

## Acceptance Criteria

- **AC1**: 用户已登录（任意角色），调用生成接口，返回 Base62(user_id).HMAC-SHA256[:16] 格式邀请码
- **AC2**: 邀请码存入 invite_codes 表（generator_id = 当前用户，无 target_role）
- **AC3**: 用户可生成多个未使用的邀请码（每次调用生成一个新码）
- **AC4**: 邀请码一次性使用，使用后 used_by/used_at 被设置，不可再用
- **AC5**: 验证接口：输入邀请码，HMAC 签名不匹配返回错误，匹配返回 generator_id
- **AC6**: 用户可查看自己生成的所有邀请码及其使用状态
- **AC7**: 生成邀请码需要 user token（admin token 不可调用）

## Technical Requirements

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/invite_service.py` | NEW | 邀请码生成、验证、列表服务 |
| `backend/app/schemas/invite_code.py` | NEW | 请求/响应 schema |
| `backend/app/api/v1/invite_codes.py` | NEW | API 端点 |
| `backend/app/main.py` | UPDATE | 注册路由 |
| `backend/tests/test_invite_service.py` | NEW | 服务层测试 |
| `backend/tests/test_invite_api.py` | NEW | API 层测试 |

### API 端点

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/v1/invite-codes` | user token | 生成邀请码 |
| GET | `/api/v1/invite-codes` | user token | 查看自己的邀请码列表 |
| POST | `/api/v1/invite-codes/verify` | 无 | 验证邀请码签名 |

### 邀请码验证逻辑

1. 解析邀请码格式：`{base62_user_id}.{hmac_hex[:16]}`
2. 从 base62 部分解码出 user_id
3. 用 `INVITE_CODE_SECRET` 重新计算 HMAC-SHA256[:16]
4. 比较签名：不匹配返回错误，匹配返回 `{ valid: true, generator_id: user_id }`
