# Story 1.3: 管理员登录

Status: review

## Story

As a 管理员,
I want 通过账号密码登录管理后台,
so that 可以管理用户、审核准入、处理工单。

## Acceptance Criteria

1. 管理员账号已通过种子数据创建
2. 管理员在后台登录页输入用户名和密码
3. 系统验证凭据，签发 JWT（sub=admin_id, type=admin）
4. 后续请求携带 JWT 可访问 `/api/v1/admin/*` 接口
5. 小程序端 JWT（type=wechat）无法访问管理后台接口
6. 密码错误时返回 401

## Tasks / Subtasks

- [x] Task 1: 创建 AdminUser ORM 模型 (AC: 1)
  - [x] 创建 `backend/app/models/admin_user.py` — AdminUser 模型（映射 admin_users 表）
  - [x] 更新 `backend/app/models/__init__.py` — 导出 AdminUser

- [x] Task 2: 创建管理员认证服务 (AC: 2,3,6)
  - [x] 在 `backend/app/services/auth_service.py` 添加 `AdminAuthService` 类
  - [x] `authenticate(username, password, db)` — bcrypt 验证密码 → 签发 JWT（type=admin）
  - [x] 用户不存在时返回 401
  - [x] 密码错误时返回 401

- [x] Task 3: 创建管理员登录路由 (AC: 2,3,6)
  - [x] 在 `backend/app/api/v1/auth.py` 添加 POST /api/v1/auth/admin-login
  - [x] 接收 {username, password} → 调用 AdminAuthService → 返回 JWT + 管理员信息
  - [x] 密码错误时返回 401

- [x] Task 4: 创建管理员权限中间件 (AC: 4,5)
  - [x] 在 `backend/app/core/security.py` 添加 `get_current_admin` 依赖
  - [x] 验证 JWT type == "admin"
  - [x] type != "admin" 时返回 403（小程序 token 无法访问）
  - [x] 创建受保护的测试端点 GET /api/v1/admin/me 验证管理员认证链路

## Dev Notes

### 当前代码状态

**backend/app/core/security.py** — 已有 `create_access_token(subject, role, token_type)`, `decode_access_token(token)`, `get_current_user`（验证 JWT + 查询 User 表）。需要添加 `get_current_admin`（验证 JWT type=="admin" + 查询 admin_users 表）。

**backend/app/services/auth_service.py** — 已有 `AuthService` ABC, `MockAuthService`, `WechatAuthService`, `get_auth_service()`。需要添加 `AdminAuthService`。

**backend/app/api/v1/auth.py** — 已有 POST /send-sms, POST /login。需要添加 POST /admin-login。

**backend/app/main.py** — 已有 auth router。需要添加 admin 受保护端点。

**admin_users 表结构（来自 001_create_all_tables.py）：**
```sql
admin_users (
    id INTEGER PK AUTO_INCREMENT,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(32) DEFAULT 'admin',
    created_at DATETIME DEFAULT NOW()
)
```

**种子数据** — `scripts/create_admin.py` 已创建管理员账号（bcrypt 哈希密码）。

### 架构要求

- **JWT Payload:** `{"sub": str(admin_id), "role": "admin", "type": "admin", "iat": ..., "exp": ...}`
- **权限隔离:** `get_current_user` 用于小程序端（type=wechat），`get_current_admin` 用于管理后台（type=admin）
- **API 响应格式:** `{"data": {...}}`

### AdminAuthService 实现

```python
class AdminAuthService:
    def authenticate(self, username: str, password: str, db: Session) -> tuple[AdminUser, str]:
        from app.models.admin_user import AdminUser
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if not admin or not pwd_context.verify(password, admin.password_hash):
            raise ValueError("Invalid credentials")

        token = create_access_token(subject=admin.id, role="admin", token_type="admin")
        return admin, token
```

### get_current_admin 实现

```python
def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("type") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    admin = db.query(AdminUser).filter(AdminUser.id == int(payload["sub"])).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")
    return admin
```

### API 端点

```
POST /api/v1/auth/admin-login
  Request:  {"username": "admin", "password": "mypassword"}
  Response: {"data": {"token": "eyJ...", "admin": {"id": 1, "username": "admin"}}}

GET /api/v1/admin/me
  Headers:  Authorization: Bearer eyJ... (type=admin)
  Response: {"data": {"id": 1, "username": "admin"}}
```

### 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/admin_user.py` | NEW | AdminUser ORM 模型 |
| `backend/app/models/__init__.py` | UPDATE | 导出 AdminUser |
| `backend/app/services/auth_service.py` | UPDATE | 添加 AdminAuthService |
| `backend/app/api/v1/auth.py` | UPDATE | 添加 POST /admin-login |
| `backend/app/core/security.py` | UPDATE | 添加 get_current_admin |
| `backend/app/main.py` | UPDATE | 添加 GET /api/v1/admin/me |

### 注意事项

- **不要创建独立的 admin schema 文件**，AdminInfo 放在 schemas/auth.py 中
- **AdminUser 和 User 是独立的表**，管理员不是小程序用户
- **get_current_admin 验证 type=="admin"**，小程序 JWT（type=wechat）会被 403 拒绝
- **密码使用 bcrypt 验证**，与 create_admin.py 脚本一致
- **AdminAuthService 不需要继承 AuthService ABC**，因为管理员认证流程与用户认证完全不同

### References

- [Source: Epics §Story 1.3] — 验收标准
- [Source: Architecture §Authentication & Security] — 双端 JWT 认证方案
- [Source: Architecture §Data Architecture] — admin_users 表结构
- [Source: Story 1.2 Completion Notes] — 当前代码状态

## Dev Agent Record

### Agent Model Used

Claude-4.5-Opus

### Debug Log References

### Completion Notes List

- Task 1: 创建 `models/admin_user.py`（AdminUser ORM），更新 `models/__init__.py`
- Task 2: 在 `services/auth_service.py` 添加 `AdminAuthService`（bcrypt 直接调用，非 passlib）
- Task 3: 在 `api/v1/auth.py` 添加 POST /admin-login（AdminLoginRequest + AdminInfo schema）
- Task 4: 在 `core/security.py` 添加 `get_current_admin`（验证 type=="admin"，否则 403），在 `main.py` 添加 GET /api/v1/admin/me
- 附加：更新 `scripts/create_admin.py` 使用 bcrypt 直接调用
- 附加：创建 `tests/test_admin_auth.py`（4 个单元测试）和 `tests/test_admin_api.py`（8 个集成测试）

### File List

- backend/app/models/admin_user.py (NEW)
- backend/app/models/__init__.py (UPDATE)
- backend/app/services/auth_service.py (UPDATE)
- backend/app/api/v1/auth.py (UPDATE)
- backend/app/core/security.py (UPDATE)
- backend/app/main.py (UPDATE)
- backend/scripts/create_admin.py (UPDATE)
- backend/tests/test_admin_auth.py (NEW)
- backend/tests/test_admin_api.py (NEW)
- backend/tests/conftest.py (UPDATE)
