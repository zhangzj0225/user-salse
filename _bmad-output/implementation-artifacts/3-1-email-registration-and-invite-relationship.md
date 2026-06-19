---
story_id: "3.1"
story_key: "3-1-email-registration-and-invite-relationship"
epic: "3"
title: "邮箱注册与邀请码关系建立"
status: "ready-for-dev"
created: "2026-06-19"
---

# Story 3.1: 邮箱注册与邀请码关系建立

## User Story

As a 新用户,
I want 通过邮箱和邀请码注册,
So that 进入系统并建立上下级关系。

## Business Context

Story 2.2 已实现注册基础流程（邮箱+验证码+邀请码校验+上下级关系+邀请码标记已使用）。本 Story 补充两个缺失的 AC：防止自推荐和注册后自动生成个人邀请码。

## Acceptance Criteria

### AC1-AC4, AC6: 已在 Story 2.2 实现（无需改动）

- AC1: 系统验证邮箱验证码 ✅
- AC2: 系统验证邀请码有效性（存在 + 未使用）✅
- AC3: 注册成功后建立上下级关系（上级 = 邀请码生成者）✅
- AC4: 邀请码标记为已使用，不可再用 ✅
- AC6: 新用户角色为普通用户（充值后变更）✅

### AC5: 用户不能填写自己的邀请码

**Given** 用户收到邀请码
**When** 用户输入的邀请码的生成者邮箱与注册邮箱相同
**Then** 系统拒绝注册，返回"不能使用自己的邀请码"

### AC7: 系统自动生成个人邀请码

**Given** 用户注册成功
**When** 用户创建完成
**Then** 系统自动生成个人邀请码：Base62(user_id) + "." + HMAC-SHA256[:16]
**And** 邀请码存入 invite_codes 表（generator_id = 新用户 ID）
**And** 用户记录的 invite_code 字段更新为生成的邀请码

## Technical Requirements

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/core/config.py` | UPDATE | 新增 `INVITE_CODE_SECRET` 配置项 |
| `backend/app/services/invite_service.py` | NEW | 邀请码生成与验证服务 |
| `backend/app/services/auth_service.py` | UPDATE | register() 添加自推荐检查 + 自动生成邀请码 |
| `backend/tests/test_auth_service.py` | UPDATE | 新增 AC5 + AC7 测试 |
| `backend/tests/test_invite_service.py` | NEW | 邀请码生成测试 |

### 邀请码格式

```
Base62(user_id) + "." + HMAC-SHA256(secret + user_id)[:16]
```

示例：用户 ID=1 → `1.a3b2c1d4e5f6a7b8`

### INVITE_CODE_SECRET

- 默认值：`"invite-secret-change-me"`
- 生产环境通过环境变量配置
- 与 JWT SECRET_KEY 独立

### 自推荐检查逻辑

在 `register()` 中，查到邀请码后，检查 `ic.generator` 的 email 是否等于注册邮箱：
```python
if ic.generator.email == email:
    raise ValueError("不能使用自己的邀请码")
```
