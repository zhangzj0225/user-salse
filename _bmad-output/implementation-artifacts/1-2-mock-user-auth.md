# Story 1.2: Mock 用户认证

Status: done

## Story

As a 用户,
I want 通过手机号和验证码登录系统,
so that 无需等待微信对接即可使用系统全部功能。

## Acceptance Criteria

1. 用户输入手机号并获取验证码（Mock 模式下直接返回 "123456"，无需真实短信）
2. 用户输入验证码提交登录
3. 系统创建/查找用户（openid = "mock_{phone}"），签发 JWT（sub=user_id, type=wechat）
4. 后续请求携带 JWT 可访问受保护接口
5. 设置 `AUTH_MODE=wechat` 后，同一登录端点切换到微信 OAuth 流程

## Tasks / Subtasks

- [x] Task 1: 创建 User ORM 模型 (AC: 3)
  - [x] 创建 `backend/app/models/user.py` — User 模型（映射 users 表）
  - [x] 创建 `backend/app/models/__init__.py` — 导出所有模型

- [x] Task 2: 创建认证 Schema (AC: 1,2,3)
  - [x] 创建 `backend/app/schemas/auth.py` — LoginRequest, LoginResponse, TokenResponse
  - [x] LoginRequest: phone (str), sms_code (str), invite_code (Optional[str])
  - [x] LoginResponse: token (str), user (UserInfo)

- [x] Task 3: 创建 Mock 认证服务 (AC: 1,2,3,5)
  - [x] 创建 `backend/app/services/auth_service.py` — MockAuthService 类
  - [x] `send_sms_code(phone)` — Mock 模式返回 "123456"，存入 sms_records 表
  - [x] `verify_sms_code(phone, code)` — 校验验证码（5 分钟有效期）
  - [x] `authenticate(phone, sms_code, invite_code?)` — 创建/查找用户 → 签发 JWT
  - [x] 用户不存在时创建：openid="mock_{phone}", role="user", status="active"
  - [x] 用户已存在时直接登录
  - [x] 预留 WechatAuthService 接口（AUTH_MODE=wechat 时使用）

- [x] Task 4: 创建认证路由 (AC: 1,2,3)
  - [x] 创建 `backend/app/api/v1/auth.py` — POST /api/v1/auth/login
  - [x] 接收 LoginRequest → 调用 auth_service.authenticate() → 返回 JWT + 用户信息
  - [x] 验证码错误时返回 400（code: INVALID_SMS_CODE）
  - [x] 手机号格式不合法时返回 422

- [x] Task 5: 创建 JWT 认证依赖 (AC: 4)
  - [x] 在 `backend/app/core/security.py` 添加 `get_current_user` 依赖函数
  - [x] 从 Authorization header 提取 Bearer token
  - [x] 调用 decode_access_token 解析 JWT
  - [x] 从数据库查询用户，注入到路由处理函数
  - [x] token 无效/过期时返回 401

- [x] Task 6: 注册路由到 main.py (AC: 4)
  - [x] 在 `backend/app/main.py` 中 include auth router
  - [x] 创建受保护的测试端点 GET /api/v1/users/me 验证 JWT 认证链路

## Dev Notes

### 当前代码状态（Story 1.1 产物）

**backend/app/main.py** — FastAPI 入口，已有 CORS、异常处理器、/health 端点、startup 事件。需要添加 auth router。

**backend/app/core/security.py** — 已有 `create_access_token(subject, role, token_type)` 和 `decode_access_token(token)`。需要添加 `get_current_user` 依赖。

**backend/app/core/config.py** — `AUTH_MODE: Literal["mock", "wechat"] = "mock"`。已有 `DATABASE_URL`, `SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`。

**backend/app/core/database.py** — 已有 `engine`, `SessionLocal`, `Base`, `get_db()`。`Base` 是所有 ORM 模型的基类。

**users 表结构（来自 001_create_all_tables.py）：**
```sql
users (
    id BIGINT PK AUTO_INCREMENT,
    openid VARCHAR(64) UNIQUE NULL,
    phone VARCHAR(11) UNIQUE NULL,
    nickname VARCHAR(64) NULL,
    avatar_url VARCHAR(256) NULL,
    role ENUM('user','distributor','agent') DEFAULT 'user',
    parent_id BIGINT NULL FK→users.id,
    invite_code VARCHAR(32) UNIQUE NULL,
    account_quota INT DEFAULT 0,
    account_used INT DEFAULT 0,
    status ENUM('pending','active','rejected') DEFAULT 'pending',
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
)
```

**sms_records 表结构：**
```sql
sms_records (
    id BIGINT PK AUTO_INCREMENT,
    phone VARCHAR(11) NOT NULL,
    code VARCHAR(6) NOT NULL,
    scene VARCHAR(32) DEFAULT 'sale_verify',
    verified BOOLEAN DEFAULT 0,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT NOW()
)
```

### 架构要求（来自 Architecture §Authentication & Security）

- **Mock 认证流程:** POST /api/v1/auth/login {phone, sms_code, invite_code?} → 验证 → 创建/查找用户 → JWT
- **JWT Payload:** `{"sub": user_id, "role": "agent", "type": "wechat", "iat": ..., "exp": ...}`
- **AUTH_MODE 切换:** MockAuthService 和 WechatAuthService 通过 AUTH_MODE 配置切换
- **JWT 中间件:** 从 Authorization: Bearer <token> 提取，验证后注入当前用户

### 策略模式实现

```python
# backend/app/services/auth_service.py

class AuthService(ABC):
    @abstractmethod
    def authenticate(self, phone: str, sms_code: str, invite_code: str | None, db: Session) -> tuple[User, str]:
        ...

class MockAuthService(AuthService):
    def send_sms_code(self, phone: str, db: Session) -> str:
        code = "123456"  # Mock 固定验证码
        # 存入 sms_records 表
        ...
    def authenticate(self, ...) -> tuple[User, str]:
        # 验证 SMS → 创建/查找用户 → 签发 JWT
        ...

class WechatAuthService(AuthService):
    # Story 5.1 实现，当前抛 NotImplementedError
    ...

def get_auth_service() -> AuthService:
    if settings.AUTH_MODE == "mock":
        return MockAuthService()
    return WechatAuthService()
```

### API 端点

```
POST /api/v1/auth/login
  Request:  {"phone": "13800138000", "sms_code": "123456", "invite_code": null}
  Response: {"data": {"token": "eyJ...", "user": {"id": 1, "phone": "138...", "role": "user", "nickname": null}}}

POST /api/v1/auth/send-sms
  Request:  {"phone": "13800138000"}
  Response: {"data": {"message": "验证码已发送"}}

GET /api/v1/users/me
  Headers:  Authorization: Bearer eyJ...
  Response: {"data": {"id": 1, "phone": "138...", "role": "user", ...}}
```

### 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/user.py` | NEW | User ORM 模型 |
| `backend/app/models/__init__.py` | UPDATE | 导出 User |
| `backend/app/schemas/auth.py` | NEW | LoginRequest, LoginResponse, SendSmsRequest |
| `backend/app/services/auth_service.py` | NEW | MockAuthService + 策略模式 |
| `backend/app/api/v1/auth.py` | NEW | POST /login, POST /send-sms |
| `backend/app/core/security.py` | UPDATE | 添加 get_current_user 依赖 |
| `backend/app/main.py` | UPDATE | include auth router |

### 注意事项

- **Mock 验证码固定为 "123456"**，任何手机号都可用此验证码登录
- **openid 格式为 "mock_{phone}"**，确保后续切换到微信时 openid 可被真实值替换
- **首次登录自动创建用户**，role 默认为 "user"，status 为 "active"（Mock 模式跳过准入审核）
- **JWT type 字段为 "wechat"**，即使 Mock 模式也保持一致，确保切换时零改动
- **不要创建独立的 user schema 文件**，UserInfo 放在 schemas/auth.py 中即可（后续 Story 会扩展）
- **验证码 5 分钟有效期**，存入 sms_records 表时设置 expires_at = now + 5min

### References

- [Source: Epics §Story 1.2] — 验收标准
- [Source: Architecture §Authentication & Security] — 双端 JWT 认证方案
- [Source: Architecture §API & Communication Patterns] — API 路由规划
- [Source: Architecture §Data Architecture] — users 和 sms_records 表结构
- [Source: Story 1.1 Completion Notes] — 当前代码状态

## Dev Agent Record

### Agent Model Used

Claude-4.5-Opus

### Debug Log References

### Completion Notes List

- Task 1: 创建 `models/user.py`（User ORM，映射 users 表全部字段，含 parent 自引用关系）和 `models/sms_record.py`（SmsRecord ORM）
- Task 2: 创建 `schemas/auth.py`（SendSmsRequest, LoginRequest, UserInfo, LoginResponse），手机号正则校验 `^1[3-9]\d{9}$`
- Task 3: 创建 `services/auth_service.py`（AuthService 抽象基类 + MockAuthService + WechatAuthService 骨架 + get_auth_service 工厂函数），Mock 验证码固定 "123456"，5 分钟有效期，首次登录自动创建用户
- Task 4: 创建 `api/v1/auth.py`（POST /send-sms, POST /login），统一响应格式 `{"data": {...}}`
- Task 5: 在 `core/security.py` 添加 `get_current_user` 依赖（HTTPBearer + JWT 解析 + 数据库查询），token 无效返回 401
- Task 6: 在 `main.py` 注册 auth router 和 GET /api/v1/users/me 受保护端点

### File List

- backend/app/models/user.py (NEW)
- backend/app/models/sms_record.py (NEW)
- backend/app/models/__init__.py (UPDATE)
- backend/app/schemas/auth.py (NEW)
- backend/app/services/auth_service.py (NEW)
- backend/app/api/v1/auth.py (NEW)
- backend/app/core/security.py (UPDATE)
- backend/app/main.py (UPDATE)
