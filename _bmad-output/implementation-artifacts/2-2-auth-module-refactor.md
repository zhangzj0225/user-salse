---
story_id: "2.2"
story_key: "2-2-auth-module-refactor"
epic: "2"
title: "认证模块重构"
status: "done"
created: "2026-06-18"
---

# Story 2.2: 认证模块重构

## User Story

As a 开发者,
I want 将认证模块从手机号改为邮箱+验证码，并实现邀请码注册流程,
So that 匹配 PRD v2 的注册方式和邀请码必填逻辑。

## Business Context

Story 2.1 已完成数据库模型重构（phone→email, EmailVerificationCode 表, InviteCode 表）。本 Story 在此基础上实现完整的认证流程：邮箱验证码发送、邀请码注册（必填）、邮箱登录。

关键变化：注册时邀请码必填，登录时邀请码选填。注册会建立上下级关系并标记邀请码已使用。

## Acceptance Criteria

### AC1: 发送邮箱验证码 — register 场景

**Given** 用户在注册页面输入邮箱
**When** 调用 `POST /api/v1/auth/send-email-code` with `{"email": "new@example.com", "scene": "register"}`
**Then** 返回 200，Mock 模式下返回 `{"data": {"message": "验证码已发送", "code": "123456"}}`
**And** 数据库创建 EmailVerificationCode 记录（scene="register"）

### AC2: 邀请码注册 — 成功

**Given** 用户已有注册验证码，且有有效邀请码
**When** 调用 `POST /api/v1/auth/register` with `{"email": "new@example.com", "code": "123456", "invite_code": "ABC123.SIG"}`
**Then** 返回 200，包含 token 和 user 信息
**And** 创建 User 记录（email, role="user", status="active", parent_id=邀请码生成者ID）
**And** InviteCode 记录标记 used_by=new_user_id, used_at=now
**And** EmailVerificationCode 标记 verified=True
**And** JWT payload: sub=user_id, role="user", type="user"

### AC3: 邀请码注册 — 邀请码必填

**Given** 用户尝试注册但不提供邀请码
**When** 调用 `POST /api/v1/auth/register` with `{"email": "new@example.com", "code": "123456"}`
**Then** 返回 422（Pydantic 验证失败，invite_code 必填）

### AC4: 邀请码注册 — 邀请码无效

**Given** 用户提供的邀请码不存在或已被使用
**When** 调用 `POST /api/v1/auth/register` with `{"email": "new@example.com", "code": "123456", "invite_code": "INVALID"}`
**Then** 返回 400，detail="邀请码无效或已被使用"

### AC5: 邀请码注册 — 邮箱已注册

**Given** 邮箱已存在用户记录
**When** 调用 `POST /api/v1/auth/register`
**Then** 返回 400，detail="该邮箱已注册"

### AC6: 邀请码注册 — 验证码错误

**Given** 用户提供的验证码不正确
**When** 调用 `POST /api/v1/auth/register`
**Then** 返回 400，detail="验证码错误或已过期"

### AC7: 邮箱登录 — 成功

**Given** 已注册用户
**When** 调用 `POST /api/v1/auth/login` with `{"email": "existing@example.com", "code": "123456"}`
**Then** 返回 200，包含 token 和 user 信息
**And** JWT payload: sub=user_id, role=user.role, type="user"

### AC8: 邮箱登录 — 未注册用户自动创建

**Given** 未注册用户通过登录入口进入
**When** 调用 `POST /api/v1/auth/login` with `{"email": "new@example.com", "code": "123456"}`
**Then** 返回 200，自动创建 User（无邀请码，无 parent_id）
**And** 这是为了保持登录流程的平滑体验（注册入口需邀请码，登录入口不需）

### AC9: 现有测试更新

**Given** Story 2.1 的 103 个测试
**When** 新增注册端点测试
**Then** 所有现有测试继续通过
**And** 新增测试覆盖 AC1-AC8 所有场景

## Developer Context

### 当前代码状态（Story 2.1 完成态）

**现有认证流程：**
- `POST /api/v1/auth/send-email-code` — 已实现，支持 scene 参数
- `POST /api/v1/auth/login` — 已实现，邮箱+验证码登录，自动创建用户
- `POST /api/v1/auth/admin-login` — 管理员登录（不变）

**现有代码分析：**

1. `auth_service.py` — `MockAuthService.authenticate()` 当前在登录时自动创建用户（不处理邀请码）。注释写 "invite_code will be processed in Story 3.1"。本 Story 需要把邀请码处理移到注册流程。

2. `schemas/auth.py` — `LoginRequest.invite_code` 是 `Optional[str]`。需要新增 `RegisterRequest` schema，其中 `invite_code` 必填。

3. `api/v1/auth.py` — 需要新增 `POST /api/v1/auth/register` 端点。

4. `InviteCode` 模型已有 `used_by` 和 `used_at` 字段，用于标记已使用。

5. `User` 模型已有 `parent_id` 字段，用于建立上下级关系。

### 需要新建的文件

无。所有修改都在现有文件上。

### 需要修改的文件

| 文件 | 变更 |
|------|------|
| `schemas/auth.py` | 新增 `RegisterRequest` schema（invite_code 必填） |
| `services/auth_service.py` | 新增 `register()` 方法；`authenticate()` 保留为登录（自动创建用户，不处理邀请码） |
| `api/v1/auth.py` | 新增 `POST /api/v1/auth/register` 端点 |
| `tests/test_auth_api.py` | 新增注册端点测试 |
| `tests/test_auth_service.py` | 新增 register() 方法测试 |

### API 端点定义

```
POST /api/v1/auth/register
Body: {"email": "user@example.com", "code": "123456", "invite_code": "ABC123.SIG"}
Response 200: {"data": {"token": "...", "user": {...}}}
Response 400: {"detail": "邀请码无效或已被使用" / "该邮箱已注册" / "验证码错误或已过期"}
Response 422: Pydantic 验证失败
```

### 关键实现逻辑

#### register() 方法流程

```python
def register(self, email, code, invite_code, db):
    # 1. 验证邮箱验证码（scene="register"）
    record = db.query(EmailVerificationCode).filter(
        email == email, scene == "register", verified == False,
        expires_at > now
    ).first()
    if not record or record.code != code:
        raise ValueError("验证码错误或已过期")

    # 2. 检查邮箱是否已注册
    if db.query(User).filter(User.email == email).first():
        raise ValueError("该邮箱已注册")

    # 3. 验证邀请码（有效且未使用）
    invite = db.query(InviteCode).filter(
        InviteCode.code == invite_code,
        InviteCode.used_by == None
    ).first()
    if not invite:
        raise ValueError("邀请码无效或已被使用")

    # 4. 创建用户
    user = User(email=email, role="user", status="active", parent_id=invite.generator_id)
    db.add(user)
    db.flush()

    # 5. 标记邀请码已使用
    invite.used_by = user.id
    invite.used_at = now

    # 6. 标记验证码已验证
    record.verified = True

    db.commit()

    # 7. 签发 JWT
    token = create_access_token(subject=user.id, role="user", token_type="user")
    return user, token
```

#### authenticate() 方法（登录，保持现有逻辑）

登录流程不处理邀请码，自动创建用户（无 parent_id）。这与注册流程分离：
- 注册：必须邀请码，建立上下级关系
- 登录：无邀请码，无上下级关系（自由用户）

### 测试要求

**新增测试（test_auth_service.py）：**
- `TestMockAuthServiceRegister` 类
  - test_register_creates_user_with_parent
  - test_register_marks_invite_code_used
  - test_register_marks_email_verified
  - test_register_raises_on_invalid_invite_code
  - test_register_raises_on_used_invite_code
  - test_register_raises_on_existing_email
  - test_register_raises_on_wrong_code
  - test_register_raises_on_expired_code

**新增测试（test_auth_api.py）：**
- `TestRegister` 类
  - test_returns_200_with_token_and_user
  - test_returns_422_without_invite_code
  - test_returns_400_on_invalid_invite_code
  - test_returns_400_on_existing_email
  - test_returns_400_on_wrong_code

## Tasks

1. 在 `schemas/auth.py` 新增 `RegisterRequest` schema（invite_code 必填）
2. 在 `auth_service.py` 新增 `register()` 方法到 `AuthService` 抽象类和 `MockAuthService`
3. 在 `api/v1/auth.py` 新增 `POST /api/v1/auth/register` 端点
4. 在 `test_auth_service.py` 新增 `TestMockAuthServiceRegister` 测试类（8 个测试）
5. 在 `test_auth_api.py` 新增 `TestRegister` 测试类（5 个测试）
6. 运行 `pytest` 确保全部通过

## Dependencies

- Story 2.1 已完成（数据库模型、EmailVerificationCode、InviteCode 表）
- 无外部依赖

## Definition of Done

- [ ] RegisterRequest schema 创建（invite_code 必填）
- [ ] register() 方法实现（含邀请码验证、用户创建、关系建立）
- [ ] POST /api/v1/auth/register 端点实现
- [ ] test_auth_service.py 新增 8 个注册测试
- [ ] test_auth_api.py 新增 5 个注册 API 测试
- [ ] 所有现有测试（103 个）继续通过
- [ ] 新增测试（13 个）通过
- [ ] `pytest` 全部通过（116+）
