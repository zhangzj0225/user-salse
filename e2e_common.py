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
# 加载后端 .env（确保密钥与运行中的后端一致）
# ═══════════════════════════════════════════════════════════════
# 测试脚本从项目根目录运行，而后端从 backend/ 运行并读取 backend/.env。
# 若不加载此文件，INVITE_CODE_SECRET 等密钥会使用默认值，导致 seed_user
# 生成的推荐码签名与后端不一致，后端验证时返回"推荐码无效"。
_env_file = os.path.join(_BACKEND_ROOT, ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#"):
                continue
            if "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

# 测试安全覆盖：强制 mock 认证 + dev 环境（不受 .env 中 AUTH_MODE=email 影响）
os.environ["ENV"] = "dev"
os.environ["AUTH_MODE"] = "mock"

# 确保 backend/ 在 sys.path 上（Config 中的 _resolve_payment_callback_secret 需要 import backend settings）
_ensure_backend_on_path()


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
    # 支付回调 HMAC 签名密钥（需与后端 PAYMENT_CALLBACK_SECRET 一致）
    # 优先级：E2E_PAYMENT_CALLBACK_SECRET > PAYMENT_CALLBACK_SECRET > 后端 settings 值
    # 不再硬编码默认值，从后端 config 读取以保持两端一致。
    @staticmethod
    def _resolve_payment_callback_secret():
        from app.core.config import settings as _be_settings
        return os.environ.get(
            "E2E_PAYMENT_CALLBACK_SECRET",
            os.environ.get("PAYMENT_CALLBACK_SECRET", _be_settings.PAYMENT_CALLBACK_SECRET),
        )

    PAYMENT_CALLBACK_SECRET = _resolve_payment_callback_secret()
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
    body = json.dumps(data).encode() if data is not None else None
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


def login_user(email):
    """冷启动登录（首次登录自动创建用户），返回 API 响应 dict。

    PRD v2: 注册接口已删除，login API 支持首次登录创建用户（mock 模式）。
    """
    return login_as(email)


# ═══════════════════════════════════════════════════════════════
# 推荐码 & 支付 Helpers（PRD v2）
# ═══════════════════════════════════════════════════════════════

def get_referral_code(t):
    """获取当前用户的持久推荐码（GET /api/v1/referral-code）。

    PRD v2: 推荐码为持久码，1人1码，替代旧的邀请码生成接口。
    """
    return api("GET", "/api/v1/referral-code", t=t)


def create_payment(email, amount, t, referral_code=None):
    """创建支付（POST /api/v1/payments/create）。

    PRD v2: 充值改为支付，请求体从 {amount} 改为 {email, amount, referral_code?}。
    推荐码选填，无推荐码=无佣金。

    Args:
        email: 支付用户邮箱
        amount: 支付金额
        t: Bearer token
        referral_code: 推荐码（选填）
    """
    body = {"email": email, "amount": amount}
    if referral_code:
        body["referral_code"] = referral_code
    return api("POST", "/api/v1/payments/create", body, t)


def approve_payment(pid, at):
    """管理员批准支付（POST /api/v1/admin/payments/{id}/approve）。"""
    return api("POST", f"/api/v1/admin/payments/{pid}/approve", data={}, t=at)


def reject_payment(pid, reason, at):
    """管理员拒绝支付（POST /api/v1/admin/payments/{id}/reject）。"""
    return api("POST", f"/api/v1/admin/payments/{pid}/reject",
               {"reject_reason": reason}, t=at)


def get_payments(t):
    """获取支付记录列表（GET /api/v1/payments）。"""
    return api("GET", "/api/v1/payments", t=t)


# ═══════════════════════════════════════════════════════════════
# 测试数据 Helpers
# ═══════════════════════════════════════════════════════════════

def test_email(prefix, n, ts=None):
    """生成唯一测试邮箱: {prefix}_{ts}_{n}@test.com（全小写，与后端 M1 一致）"""
    if ts is None:
        ts = str(int(time.time()))[-4:]
    return f"{prefix}_{ts}_{n}@test.com".lower()


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


def seed_user(email, parent_id, role="distributor", db=None):
    """直接 DB 插入用户（绕过登录流程），返回 {"id", "email", "referral_code"}。
    
    PRD v2: 角色只有 distributor 和 agent，默认 distributor。
    创建 ReferralCode 记录（使用后端密钥签名），使推荐码可通过 API 验证。
    """
    _ensure_backend_on_path()
    from app.models.user import User
    from app.models.referral_code import ReferralCode
    from app.core.security import generate_invite_code

    own_db = db is None
    if own_db:
        db = get_backend_session()

    email = email.strip().lower()
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u)
    db.flush()
    rc_code = generate_invite_code(u.id)
    u.referral_code = rc_code
    u.referral_code_generated = 1
    db.add(ReferralCode(code=rc_code, user_id=u.id, key_version=1, is_active=1))
    if own_db:
        db.commit()
        uid = u.id
        db.close()
    else:
        uid = u.id
    return {"id": uid, "email": email, "referral_code": rc_code}


def seed_users(names_parents, ts=None):
    """批量种子用户。

    Args:
        names_parents: [(name, parent_name|None), ...]  如 [("A", None), ("B", "A")]
        ts: 时间戳后缀

    Returns:
        dict: {name: {"id", "email", "referral_code"}}

    不再创建 ReferralCode 记录 — 推荐码由后端在支付审批时生成。
    """
    _ensure_backend_on_path()
    from app.models.user import User
    from app.models.referral_code import ReferralCode
    from app.core.security import generate_invite_code

    if ts is None:
        ts = make_ts()
    db = get_backend_session()
    info = {}
    for name, parent_name in names_parents:
        email = test_email(f"seed", name, ts).lower()
        parent_id = info[parent_name]["id"] if parent_name else None
        u = User(email=email, role="distributor", status="active", parent_id=parent_id)
        db.add(u)
        db.flush()
        code = generate_invite_code(u.id)
        u.referral_code = code
        u.referral_code_generated = 1
        db.add(ReferralCode(code=code, user_id=u.id, key_version=1, is_active=1))
        info[name] = {"email": email, "id": u.id, "referral_code": code}
    db.commit()
    db.close()
    return info


def get_referral_code_str(t):
    """获取当前用户的持久推荐码字符串（便捷方法，从后端 API 获取）。

    替代旧 seed_user 中直接生成推荐码的方式，确保签名密钥与后端一致。
    """
    return api("GET", "/api/v1/referral-code", t=t)["data"]["code"]


# ═══════════════════════════════════════════════════════════════
# 支付回调签名 & 自定义 Header Helpers
# ═══════════════════════════════════════════════════════════════

def make_callback_signature(payment_id, payment_no):
    """计算支付回调 HMAC-SHA256 签名。

    签名算法: HMAC-SHA256("{payment_id}:{payment_no}", PAYMENT_CALLBACK_SECRET)
    与 backend/app/api/v1/payments.py:_verify_callback_signature 一致。
    """
    import hashlib
    import hmac
    payload = f"{payment_id}:{payment_no}"
    sig = hmac.new(
        Config.PAYMENT_CALLBACK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return sig


def api_with_headers(method, path, data=None, headers=None):
    """带自定义 headers 的 HTTP API 调用。

    用于需要自定义 Header（如 X-Signature、X-API-Key 不同值）的场景。
    与 api() 的区别：不会自动加 Authorization header，由调用方完全控制 headers。
    """
    url = f"{Config.API_BASE_URL}{path}"
    body = json.dumps(data).encode() if data is not None else None
    _headers = {"Content-Type": "application/json"}
    if headers:
        _headers.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=_headers)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=Config.TIMEOUT).read())
    except urllib.error.HTTPError as e:
        resp_body = json.loads(e.read() if e.fp else b"{}")
        return {"_e": e.code, "detail": resp_body.get("detail", str(e))}


# ═══════════════════════════════════════════════════════════════
# 管理员 Helpers
# ═══════════════════════════════════════════════════════════════

def admin_create_seed(email, role, at, referral_code=None):
    """管理员创建种子用户（POST /api/v1/admin/users/create）。

    PRD v2: 替代旧注册流程，管理员直接创建 agent/distributor。
    返回创建的用户信息 dict。
    """
    body = {"email": email, "role": role}
    if referral_code:
        body["referral_code"] = referral_code
    return api("POST", "/api/v1/admin/users/create", body, t=at)
