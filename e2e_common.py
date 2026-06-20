"""E2E 测试共享模块 — 统一 API helpers、配置、DB 工具。

所有 E2E 脚本从此文件导入，避免 5 份重复代码。

环境变量覆盖（生产环境可通过 CI/系统环境切换，无需改代码）:
  E2E_API_BASE      — 后端 API 地址（默认 http://127.0.0.1:8000）
  E2E_UI_BASE       — 前端地址（默认 http://localhost:5173）
  E2E_MOCK_CODE     — Mock 验证码（默认 123456）
  E2E_ADMIN_USER    — 管理员用户名（默认 admin）
  E2E_ADMIN_PASS    — 管理员密码（默认 admin123）
  E2E_LICENSE_KEY   — License API Key（默认 deploy-test-license-api-key）
  E2E_OUTPUT_DIR    — 截图输出目录（默认 <项目根>/e2e_output）
  DATABASE_URL      — 后端 DB 连接（需与运行中的后端一致）
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# ═══════════════════════════════════════════════════════════════
# 路径解析（可移植 — 不依赖绝对路径）
# ═══════════════════════════════════════════════════════════════

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.join(_PROJECT_ROOT, "backend")


def _ensure_backend_on_path():
    """将 backend/ 目录加入 sys.path，确保可 import app.* 模块。"""
    if _BACKEND_ROOT not in sys.path:
        sys.path.insert(0, _BACKEND_ROOT)


# ═══════════════════════════════════════════════════════════════
# 配置（环境变量 → 默认值）
# ═══════════════════════════════════════════════════════════════

class Config:
    API_BASE_URL = os.environ.get("E2E_API_BASE", "http://127.0.0.1:8000")
    UI_BASE_URL = os.environ.get("E2E_UI_BASE", "http://localhost:5173")
    MOCK_CODE = os.environ.get("E2E_MOCK_CODE", "123456")
    ADMIN_USERNAME = os.environ.get("E2E_ADMIN_USER", "admin")
    ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASS", "admin123")
    LICENSE_API_KEY = os.environ.get("E2E_LICENSE_KEY", "deploy-test-license-api-key")
    E2E_OUTPUT_DIR = os.environ.get("E2E_OUTPUT_DIR", os.path.join(_PROJECT_ROOT, "e2e_output"))
    TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "15"))


# 确保 ENV=dev（避免 SEC-1 生产环境密钥校验拒绝启动）
os.environ.setdefault("ENV", "dev")
# 确保输出目录存在
os.makedirs(Config.E2E_OUTPUT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# HTTP Helpers
# ═══════════════════════════════════════════════════════════════

def api(method, path, data=None, t=None, timeout=None):
    """统一 HTTP API 调用。

    Args:
        method: HTTP 方法 (GET/POST/PUT)
        path: API 路径（如 "/api/v1/users/me"），自动拼接 BASE URL
        data: 请求体 dict（可选）
        t: Bearer token（可选）
        timeout: 超时秒数（默认 Config.TIMEOUT）

    Returns:
        dict: JSON 响应。HTTP 错误时返回 {"_e": status_code, "detail": "..."}
    """
    url = f"{Config.API_BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if t:
        headers["Authorization"] = f"Bearer {t}"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout or Config.TIMEOUT).read())
    except urllib.error.HTTPError as e:
        resp_body = json.loads(e.read() if e.fp else b"{}")
        return {"_e": e.code, "detail": resp_body.get("detail", str(e))}


def api_key(path, data):
    """带 X-API-Key 头的 API 调用（用于 License 验证等外部接口）。"""
    url = f"{Config.API_BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": Config.LICENSE_API_KEY,
        },
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=Config.TIMEOUT).read())
    except urllib.error.HTTPError as e:
        return {"_e": e.code, "success": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# 断言 & 结果收集
# ═══════════════════════════════════════════════════════════════

_results = []


def results():
    """返回当前收集的测试结果列表。"""
    return _results


def chk(ok, desc):
    """断言一条测试结果，收集到全局 results 列表。"""
    tag = "PASS" if ok else "FAIL"
    _results.append(f"{tag}: {desc}")
    print(f"  {tag}: {desc}" if ok else f"  *** {tag}: {desc}")
    return ok


def skip_msg(desc):
    """记录一条 SKIP 消息。"""
    _results.append(f"SKIP: {desc}")
    print(f"  SKIP: {desc}")


def warn_msg(desc):
    """记录一条 WARN 消息。"""
    _results.append(f"WARN: {desc}")
    print(f"  WARN: {desc}")


def summary():
    """打印测试汇总。"""
    passed = sum(1 for r in _results if "PASS" in r)
    failed = sum(1 for r in _results if "FAIL" in r)
    skipped = sum(1 for r in _results if "SKIP" in r)
    warned = sum(1 for r in _results if "WARN" in r)
    print(f"\n{'=' * 60}")
    for r in _results:
        print(f"  {r}")
    print(f"\n  PASS={passed} FAIL={failed} SKIP={skipped} WARN={warned} TOTAL={len(_results)}")
    return passed, failed


# ═══════════════════════════════════════════════════════════════
# 认证 Helpers
# ═══════════════════════════════════════════════════════════════

def login_as(email):
    """冷启动登录（自动发送验证码 + 登录），返回 API 响应 dict。"""
    api("POST", "/api/v1/auth/send-email-code", {"email": email, "scene": "login"})
    return api("POST", "/api/v1/auth/login", {"email": email, "code": Config.MOCK_CODE})


def admin_login():
    """管理员登录，返回 {"token": str}。"""
    resp = api("POST", "/api/v1/auth/admin-login",
               {"username": Config.ADMIN_USERNAME,
                "password": Config.ADMIN_PASSWORD})
    return {"token": resp["data"]["token"]}


def register_user(email, invite_code):
    """注册新用户（自动发送验证码 + 注册），返回 API 响应 dict。"""
    api("POST", "/api/v1/auth/send-email-code", {"email": email, "scene": "register"})
    return api("POST", "/api/v1/auth/register",
               {"email": email, "code": Config.MOCK_CODE, "invite_code": invite_code})


# ═══════════════════════════════════════════════════════════════
# 测试数据 Helpers
# ═══════════════════════════════════════════════════════════════

def test_email(prefix, n, ts=None):
    """生成唯一测试邮箱: {prefix}_{ts}_{n}@test.com"""
    if ts is None:
        ts = str(int(time.time()))[-4:]
    return f"{prefix}_{ts}_{n}@test.com"


def make_ts():
    """生成 4 位时间戳后缀（同脚本内多次调用复用同一个值）。"""
    return str(int(time.time()))[-4:]


# ═══════════════════════════════════════════════════════════════
# 数据库 Helpers（直接访问 backend DB）
# ═══════════════════════════════════════════════════════════════

def get_backend_session():
    """获取 backend 数据库 Session（自动注入 sys.path）。"""
    _ensure_backend_on_path()
    from app.core.database import get_session_local
    return get_session_local()()


def seed_user(email, parent_id, role="user", db=None):
    """直接 DB 插入用户（绕过注册流程），返回 {"id", "email", "invite_code"}。"""
    _ensure_backend_on_path()
    from app.models.user import User
    from app.models.invite_code import InviteCode
    from app.core.security import generate_invite_code

    own_db = db is None
    if own_db:
        db = get_backend_session()

    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    ic = generate_invite_code(u.id)
    u.invite_code = ic
    db.add(InviteCode(code=ic, generator_id=u.id, key_version=1))
    if own_db:
        db.commit()
        uid, uic = u.id, ic
        db.close()
    else:
        uid, uic = u.id, ic
    return {"id": uid, "email": email, "invite_code": uic}


def seed_users(names_parents, ts=None):
    """批量种子用户。

    Args:
        names_parents: [(name, parent_name|None), ...]  如 [("A", None), ("B", "A")]
        ts: 时间戳后缀

    Returns:
        dict: {name: {"id", "email", "invite_code"}}
    """
    _ensure_backend_on_path()
    from app.models.user import User
    from app.models.invite_code import InviteCode
    from app.core.security import generate_invite_code

    if ts is None:
        ts = make_ts()
    db = get_backend_session()
    info = {}
    for name, parent_name in names_parents:
        email = test_email(f"seed", name, ts)
        parent_id = info[parent_name]["id"] if parent_name else None
        u = User(email=email, role="user", status="active", parent_id=parent_id)
        db.add(u)
        db.flush()
        code = generate_invite_code(u.id)
        u.invite_code = code
        db.add(InviteCode(code=code, generator_id=u.id, key_version=1))
        info[name] = {"email": email, "id": u.id, "invite_code": code}
    db.commit()
    db.close()
    return info
