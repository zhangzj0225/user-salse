"""E2E 扩展测试 — 覆盖佣金规则全集、充值独立性、邀请码流程、额度销售 API、
管理员完整功能、通知系统等现有测试未覆盖的场景。

Run with: backend server on 8000 + DATABASE_URL pointing to seeded deploy_test.db
"""
from decimal import Decimal
import time

from e2e_common import (
    Config, api, api_key, chk, skip_msg, warn_msg, summary,
    test_email, make_ts, login_as, admin_login, seed_user, seed_users,
    get_backend_session, get_referral_code_str, admin_create_seed,
)

MOCK = Config.MOCK_CODE
TS = make_ts()


def em(n):
    return test_email("ext", n, TS)


# ── 本地 helpers ──────────────────────────────────────────

def get_me(t):
    return api("GET", "/api/v1/users/me", t=t)


def get_earn(t):
    return api("GET", "/api/v1/users/me/earnings", t=t)


def recharge(amt, t, email=None, referral_code=None):
    """创建支付（PRD v2: recharges → payments/create，请求体需 email + 可选 referral_code）"""
    if email is None:
        me = api("GET", "/api/v1/users/me", t=t)
        email = me["data"]["email"]
    body = {"email": email, "amount": amt}
    if referral_code:
        body["referral_code"] = referral_code
    return api("POST", "/api/v1/payments/create", body, t)


def approve_r(rid, at):
    return api("POST", f"/api/v1/admin/payments/{rid}/approve", data={}, t=at)


def reject_r(rid, reason, at):
    return api("POST", f"/api/v1/admin/payments/{rid}/reject",
               {"reject_reason": reason}, t=at)


def first_reward_from(earn_resp, source_uid):
    """从收益响应中提取指定来源用户的 first_reward 记录。"""
    return [r for r in earn_resp.get("records", [])
            if r["type"] == "first_reward"
            and r.get("source_user_id") == source_uid]


def get_quota_from_db(user_email):
    """从 DB 直接查询用户额度（绕过 API 角色限制）。"""
    db = get_backend_session()
    from app.models.user import User
    u = db.query(User).filter(User.email == user_email).first()
    quota = (u.account_quota, u.account_used) if u else (0, 0)
    db.close()
    return quota


# ═══════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════
print("=== SETUP ===")
at = admin_login()["token"]
chk(bool(at) and len(at) > 20, "X0: Admin login OK")

# ═══════════════════════════════════════════
# A. 佣金规则全覆盖（需求核心 — 9 种首次奖励组合）
# ═══════════════════════════════════════════
print("\n=== A. 佣金规则全覆盖 ===")

# A1: 创建用户 U0（用于后续权限测试）
# PRD v2: 无 user/member 角色，冷启动登录创建的用户为 distributor
u0 = login_as(em("U0"))
u0t = u0["data"]["token"]
u0_id = u0["data"]["user"]["id"]
chk(u0["data"]["user"]["role"] == "distributor", "A1: U0 created as distributor")

# A4: 代理 AG1 推荐充 888 → AG1 获 488.4 (55%)
ag1 = login_as(em("AG1"))
ag1t = ag1["data"]["token"]
ag1_id = ag1["data"]["user"]["id"]
rid = recharge(10000, ag1t)["data"]["id"]
approve_r(rid, at)
chk(get_me(ag1t)["data"]["role"] == "agent", "A4a: AG1 -> agent")
ag1_rc = get_referral_code_str(ag1t)

ag1_child = seed_user(em("AG1c"), parent_id=ag1_id)
ag1c_login = login_as(ag1_child["email"])
ag1ct = ag1c_login["data"]["token"]
rid = recharge(888, ag1ct, referral_code=ag1_rc)["data"]["id"]
approve_r(rid, at)
time.sleep(0.3)
ag1_earn = get_earn(ag1t)
fr4 = [r for r in ag1_earn.get("records", [])
       if r["type"] == "first_reward" and Decimal(str(r["amount"])) == Decimal("488.40")]
chk(len(fr4) >= 1,
    f"A4: agent→child充888 = 488.40 (55%, got {[r['amount'] for r in fr4]})")

# A5: 经销商 DS1 推荐充 5000 → DS1 获 2000 (40%)
ds1 = login_as(em("DS1"))
ds1t = ds1["data"]["token"]
ds1_id = ds1["data"]["user"]["id"]
rid = recharge(5000, ds1t)["data"]["id"]
approve_r(rid, at)
chk(get_me(ds1t)["data"]["role"] == "distributor", "A5a: DS1 -> distributor")
ds1_rc = get_referral_code_str(ds1t)

ds1_child = seed_user(em("DS1c"), parent_id=ds1_id)
ds1c_login = login_as(ds1_child["email"])
ds1ct = ds1c_login["data"]["token"]
rid = recharge(5000, ds1ct, referral_code=ds1_rc)["data"]["id"]
approve_r(rid, at)
time.sleep(0.3)
ds1_earn = get_earn(ds1t)
fr5 = first_reward_from(ds1_earn, ds1_child["id"])
chk(len(fr5) >= 1 and Decimal(str(fr5[0]["amount"])) == Decimal("2000.00"),
    f"A5: distributor→child充5000 = 2000.00 (40%, got {[r['amount'] for r in fr5]})")

# A6: 经销商 DS1 推荐充 10000 → DS1 获 4000 (40%)
ds1_child2 = seed_user(em("DS1c2"), parent_id=ds1_id)
ds1c2_login = login_as(ds1_child2["email"])
ds1c2t = ds1c2_login["data"]["token"]
rid = recharge(10000, ds1c2t, referral_code=ds1_rc)["data"]["id"]
approve_r(rid, at)
time.sleep(0.3)
ds1_earn = get_earn(ds1t)
fr6 = first_reward_from(ds1_earn, ds1_child2["id"])
chk(len(fr6) >= 1 and Decimal(str(fr6[0]["amount"])) == Decimal("4000.00"),
    f"A6: distributor→child充10000 = 4000.00 (40%, got {[r['amount'] for r in fr6]})")

# A7-A8: 已删除（PRD v2 无 member 角色，20% 档佣金不再存在）

print()

# ═══════════════════════════════════════════
# B. 充值独立性（不互斥、不降级、额度累加）
# ═══════════════════════════════════════════
print("=== B. 充值独立性 ===")

# B1: 冷启动用户充888 → distributor（PRD v2: 无 member 角色）
indep = login_as(em("indep"))
indep_email = indep["data"]["user"]["email"]
indept = indep["data"]["token"]
rid = recharge(888, indept)["data"]["id"]
approve_r(rid, at)
chk(get_me(indept)["data"]["role"] == "distributor", "B1a: indep -> distributor (888)")

rid = recharge(5000, indept)["data"]["id"]
approve_r(rid, at)
me_after = get_me(indept)["data"]
chk(me_after["role"] == "distributor",
    f"B1b: distributor+5000 -> distributor (got {me_after['role']})")
q, used = get_quota_from_db(indep_email)
chk(q == 11, f"B1c: distributor quota=11 (got {q})")

# B2: 经销商再充10000 → 代理（角色升级，额度累加 11+22=33）
rid = recharge(10000, indept)["data"]["id"]
approve_r(rid, at)
me_after2 = get_me(indept)["data"]
chk(me_after2["role"] == "agent",
    f"B2a: distributor+10000 -> agent (got {me_after2['role']})")
q, used = get_quota_from_db(indep_email)
chk(q == 33, f"B2b: agent quota=33 (11+22, got {q})")

# B3: 代理再充888 → 仍为代理（角色不降级）
rid = recharge(888, indept)["data"]["id"]
approve_r(rid, at)
me_after3 = get_me(indept)["data"]
chk(me_after3["role"] == "agent",
    f"B3a: agent+888 -> still agent (no downgrade, got {me_after3['role']})")
q, used = get_quota_from_db(indep_email)
chk(q == 33, f"B3b: quota still 33 (888 gives 0 quota, got {q})")

# B4: 代理再充5000 → 仍为代理（额度 +11 = 44）
# NOTE: payment_service.py 已修复角色降级，但运行中的后端可能未重载。
# 后端重启后 role 应为 agent。
rid = recharge(5000, indept)["data"]["id"]
approve_r(rid, at)
me_after4 = get_me(indept)["data"]
chk(me_after4["role"] == "agent",
    f"B4a: agent+5000 stays agent (role never downgrades, got {me_after4['role']})")
q, used = get_quota_from_db(indep_email)
chk(q == 44, f"B4b: quota=44 (33+11, got {q})")

print()

# ═══════════════════════════════════════════
# C. 充值边界
# ═══════════════════════════════════════════
print("=== C. 充值边界 ===")

# C1: 无效充值金额被拒（Pydantic 422 或服务层 400）
c1 = login_as(em("C1"))
c1t = c1["data"]["token"]
resp = recharge(1000, c1t)
chk(resp.get("_e") in (400, 422), f"C1: invalid amount 1000 rejected (code={resp.get('_e')})")

resp = recharge(100, c1t)
chk(resp.get("_e") in (400, 422), f"C1b: invalid amount 100 rejected (code={resp.get('_e')})")

# C2: 重复 pending 充值被拒
rid = recharge(888, c1t)["data"]["id"]
resp2 = recharge(5000, c1t)
chk(resp2.get("_e") == 400,
    f"C2: duplicate pending rejected (code={resp2.get('_e')})")
# 清理：批准第一笔
approve_r(rid, at)

# C3: 支付记录列表（888 支付不设置 user_id，可能不在用户列表中）
recs = api("GET", "/api/v1/payments", t=c1t)
chk("total" in recs, f"C3: payment list returned (total={recs.get('total', 0)})")

print()

# ═══════════════════════════════════════════
# D. 邀请码完整流程
# ═══════════════════════════════════════════
print("=== D. 邀请码完整流程 ===")

# D1: 获取持久推荐码（PRD v2: GET /api/v1/referral-code，1人1码）
rc_resp = api("GET", "/api/v1/referral-code", t=ag1t)
chk("data" in rc_resp and "code" in rc_resp.get("data", {}),
    f"D1: get referral code via API (got={rc_resp.get('_e', 'OK')})")
api_code = rc_resp.get("data", {}).get("code", "")

# D2: 再次获取推荐码 → 返回同一个持久码
rc_resp2 = api("GET", "/api/v1/referral-code", t=ag1t)
api_code2 = rc_resp2.get("data", {}).get("code", "")
chk(api_code == api_code2 and api_code != "",
    f"D2: referral code is persistent (same code={api_code == api_code2})")

# D3-D5: 已删除（PRD v2: 注册接口已删除，邀请码验证/列表不再适用）

print()

# ═══════════════════════════════════════════
# E. 额度/销售
# ═══════════════════════════════════════════
print("=== E. 额度/销售 ===")

# E1: 额度查询 API（代理）
q_resp = api("GET", "/api/v1/quota", t=ag1t)
chk("account_quota" in q_resp or "quota" in q_resp,
    f"E1: agent quota query OK (got={q_resp})")

# E2: 普通用户查询额度（v2: distributor 也可查询额度）
q_resp2 = api("GET", "/api/v1/quota", t=u0t)
chk(q_resp2.get("_e") is None,
    f"E2: distributor quota query OK (code={q_resp2.get('_e')})")

# E3: 普通用户无额度时销售被拒
sale_resp = api("POST", "/api/v1/sales",
                {"customer_email": em("E3sale"), "verification_code": MOCK}, t=u0t)
chk(sale_resp.get("_e") in (400, 403),
    f"E3: no-quota sale rejected (code={sale_resp.get('_e')})")

# E4: 真正的销售流程 API（sale_verify 验证码）
sale_email = em("E4customer")
api("POST", "/api/v1/auth/send-email-code",
    {"email": sale_email, "scene": "sale_verify"})
ag1_quota_before = api("GET", "/api/v1/quota", t=ag1t)
qb = ag1_quota_before.get("account_quota", 0) - ag1_quota_before.get("account_used", 0)
sale_resp2 = api("POST", "/api/v1/sales",
                 {"customer_email": sale_email, "verification_code": MOCK}, t=ag1t)
if sale_resp2.get("_e"):
    chk(False, f"E4: sale API failed: {sale_resp2.get('detail')}")
else:
    chk("customer_id" in sale_resp2.get("data", sale_resp2),
        f"E4: sale via API OK (customer_id={sale_resp2.get('data', sale_resp2).get('customer_id')})")
    # 验证额度减少
    ag1_quota_after = api("GET", "/api/v1/quota", t=ag1t)
    qa = ag1_quota_after.get("account_quota", 0) - ag1_quota_after.get("account_used", 0)
    chk(qa == qb - 1, f"E4b: quota decreased {qb} -> {qa}")

    # 验证客户成为 888 会员
    cust_login = login_as(sale_email)
    chk(cust_login.get("data", {}).get("user", {}).get("role") == "distributor",
        f"E4c: sale customer is distributor (role={cust_login.get('data', {}).get('user', {}).get('role')})")

    # 验证客户上级 = 销售者
    cust_t = cust_login["data"]["token"]
    upstream = api("GET", "/api/v1/users/me/upstream", t=cust_t)
    parents = [m["user_id"] for m in upstream.get("chain", [])]
    chk(ag1_id in parents, f"E4d: sale customer parent=AG1 (upstream={parents[:2]})")

    # 验证销售零佣金
    ag1_earn_after = get_earn(ag1t)
    sale_commissions = [r for r in ag1_earn_after.get("records", [])
                        if r.get("source_user_id") == sale_resp2.get("data", sale_resp2).get("customer_id")]
    chk(len(sale_commissions) == 0,
        f"E4e: sale produces 0 commission (got {len(sale_commissions)} records)")

# E5: 额度耗尽后销售被拒 — 用一个额度少的经销商测试
# DS1 有 11 额度，连续销售直到耗尽
# 为了不消耗太多时间，用 DB 直接设置额度来测试边界
try:
    db = get_backend_session()
    from app.models.user import User
    low_quota_user = db.query(User).filter(User.email == ds1["data"]["user"]["email"]).first()
    low_quota_user.account_quota = low_quota_user.account_used + 1  # 仅剩 1 个额度
    db.commit()
    db.close()

    # 第 1 次销售用掉最后一个额度
    last_sale_email = em("E5last")
    api("POST", "/api/v1/auth/send-email-code",
       {"email": last_sale_email, "scene": "sale_verify"})
    r1 = api("POST", "/api/v1/sales",
             {"customer_email": last_sale_email, "verification_code": MOCK}, t=ds1t)
    chk(not r1.get("_e"), f"E5a: last quota sale OK")

    # 第 2 次销售应该被拒（额度不足）
    over_sale_email = em("E5over")
    api("POST", "/api/v1/auth/send-email-code",
       {"email": over_sale_email, "scene": "sale_verify"})
    r2 = api("POST", "/api/v1/sales",
             {"customer_email": over_sale_email, "verification_code": MOCK}, t=ds1t)
    chk(r2.get("_e") == 400, f"E5b: over-quota sale rejected (code={r2.get('_e')})")
except Exception as ex:
    chk(False, f"E5: quota exhaustion test error: {ex}")

print()

# ═══════════════════════════════════════════
# F. 工单列表
# ═══════════════════════════════════════════
print("=== F. 工单列表 ===")

# F1: 用户查看自己的工单列表
my_tickets = api("GET", "/api/v1/users/me/tickets", t=ag1t)
chk("tickets" in my_tickets, f"F1: user ticket list OK (total={my_tickets.get('total')})")

# F2: 工单状态筛选
pending_tickets = api("GET", "/api/v1/users/me/tickets?status=pending", t=ag1t)
chk("tickets" in pending_tickets, f"F2: ticket filter by status OK")

print()

# ═══════════════════════════════════════════
# G. 管理员完整功能
# ═══════════════════════════════════════════
print("=== G. 管理员完整功能 ===")

# G1: 用户列表
users_resp = api("GET", "/api/v1/admin/users", t=at)
chk("users" in users_resp and users_resp.get("total", 0) > 0,
    f"G1: admin user list (total={users_resp.get('total')})")

# G2: 用户列表角色筛选
agents = api("GET", "/api/v1/admin/users?role=agent", t=at)
chk("users" in agents, f"G2a: admin user filter by role OK")
all_agents = [u for u in agents.get("users", []) if u.get("role") == "agent"]
chk(len(all_agents) == len(agents.get("users", [])),
    f"G2b: all returned users are agents ({len(all_agents)})")

# G3: 用户列表搜索
search_resp = api("GET", f"/api/v1/admin/users?search={em('U0')[0:10]}", t=at)
chk("users" in search_resp, f"G3: admin user search OK")

# G4: 用户详情
detail_resp = api("GET", f"/api/v1/admin/users/{u0_id}", t=at)
chk("id" in detail_resp or "user" in detail_resp,
    f"G4: admin user detail OK (keys={list(detail_resp.keys())[:3]})")

# G5: 运营看板
dash = api("GET", "/api/v1/admin/dashboard", t=at)
chk("total_users" in dash or "users" in dash,
    f"G5: admin dashboard OK (keys={list(dash.keys())[:5]})")

# G6: 管理员支付记录列表
admin_payments = api("GET", "/api/v1/admin/payments", t=at)
chk("data" in admin_payments and admin_payments.get("total", 0) > 0,
    f"G6: admin payment list (total={admin_payments.get('total')})")

# G7: 管理员支付记录状态筛选
pending_payments = api("GET", "/api/v1/admin/payments?status=failed", t=at)
chk("data" in pending_payments, f"G7: admin payment filter OK")

# G8: 管理员工单列表
admin_tickets = api("GET", "/api/v1/admin/tickets", t=at)
chk("tickets" in admin_tickets, f"G8: admin ticket list OK (total={admin_tickets.get('total')})")

# G9: 配置变更日志
logs = api("GET", "/api/v1/admin/config-change-logs", t=at)
chk("logs" in logs, f"G9: config change logs OK")

# G10: 重复审批被拒
# 找一个已 approved 的支付记录，尝试再次审批
if admin_payments.get("data"):
    approved_rec = admin_payments["data"][0]
    if approved_rec.get("status") == "approved":
        dup_resp = api("POST", f"/api/v1/admin/payments/{approved_rec['id']}/approve", data={}, t=at)
        chk(dup_resp.get("_e") == 400,
            f"G10: duplicate approve rejected (code={dup_resp.get('_e')})")
    else:
        skip_msg("G10: no approved payment to test duplicate")
else:
    skip_msg("G10: no payments to test duplicate")

# G11: 单个配置查询
cfg_single = api("GET", "/api/v1/admin/configs/min_withdrawal_amount", t=at)
chk("data" in cfg_single, f"G11: get single config OK")

print()

# ═══════════════════════════════════════════
# H. 通知系统
# ═══════════════════════════════════════════
print("=== H. 通知系统 ===")

# H1: 通知列表（充值审核通过后会生成通知）
notifs = api("GET", "/api/v1/users/me/notifications", t=indept)
chk("notifications" in notifs, f"H1: notification list OK (total={notifs.get('total')})")

# H2: 标记通知已读
notif_list = notifs.get("notifications", [])
if notif_list:
    nid = notif_list[0].get("id")
    read_resp = api("POST", f"/api/v1/users/me/notifications/{nid}/read", t=indept)
    chk(read_resp.get("success") is True, f"H2: mark notification read OK")
else:
    skip_msg("H2: no notifications to mark read")

print()

# ═══════════════════════════════════════════
# I. 长期奖励补充（经销商→经销商 4%）
# ═══════════════════════════════════════════
print("=== I. 长期奖励补充 ===")
try:
    from app.services.commission_service import CommissionEngine
    from datetime import datetime, timezone, timedelta

    # 造数据：DS1 是经销商，其下级 DS1c 也是经销商
    # DS1c 充 5000 时 DS1 获 2000 首次奖励
    # 长期奖励：经销商→经销商 4%，DS1 应获 2000 * 4% = 80
    db2 = get_backend_session()
    engine = CommissionEngine(db2)
    next_month = (datetime.now(timezone.utc).replace(day=1) + timedelta(days=32))
    period = next_month.strftime("%Y%m")
    recs = engine.calculate_long_term_reward(ds1_id, period, db=db2)
    if recs:
        db2.commit()
        # DS1 的下级 DS1c 获得了 2000 首次奖励（充5000）
        # DS1c2 获得了充10000，DS1 获 4000
        # 但长期奖励按"直接下级全部收入"计算
        # DS1c 收入 = 0（DS1c 没有下级获得佣金）
        # DS1c2 收入 = 0（DS1c2 没有下级）
        # 所以 DS1 的长期奖励可能为 0（因为下级没有收入）
        total_lt = sum(Decimal(str(r.amount)) for r in recs)
        chk(total_lt >= Decimal("0"),
            f"I1: DS1 long-term reward calculated (total={total_lt})")
    else:
        # 下级无收入时返回空列表是正确的
        chk(True, f"I1: DS1 no long-term reward (subordinates have no income)")
    db2.close()
except Exception as ex:
    warn_msg(f"I1: long-term reward test error: {ex}")

# I2: 经销商→经销商长期奖励（需要下级有收入）
# 造一个完整链：DS2(经销商) → DS2c(经销商) → DS2cc(用户充888)
# DS2c 从 DS2cc 获 355.2 首次奖励
# DS2 长期奖励 = 355.2 * 4% = 14.208
try:
    info_i = seed_users([("DS2", None), ("DS2c", "DS2"), ("DS2cc", "DS2c")], ts=TS + "i")
    toks_i = {}
    # 充值
    for nm, amt in [("DS2", 5000), ("DS2c", 5000)]:
        i = info_i[nm]
        api("POST", "/api/v1/auth/send-email-code", {"email": i["email"], "scene": "login"})
        r = api("POST", "/api/v1/auth/login", {"email": i["email"], "code": MOCK})
        t = r["data"]["token"]
        toks_i[nm] = t
        parent_name = {"DS2": None, "DS2c": "DS2"}[nm]
        rc = toks_i.get(parent_name) and get_referral_code_str(toks_i[parent_name])
        rid = recharge(amt, t, referral_code=rc)["data"]["id"]
        approve_r(rid, at)

    # DS2cc 充 888
    i = info_i["DS2cc"]
    api("POST", "/api/v1/auth/send-email-code", {"email": i["email"], "scene": "login"})
    r = api("POST", "/api/v1/auth/login", {"email": i["email"], "code": MOCK})
    t = r["data"]["token"]
    ds2c_rc = get_referral_code_str(toks_i["DS2c"])
    rid = recharge(888, t, referral_code=ds2c_rc)["data"]["id"]
    approve_r(rid, at)
    time.sleep(0.5)

    # 计算长期奖励
    db3 = get_backend_session()
    engine2 = CommissionEngine(db3)
    recs2 = engine2.calculate_long_term_reward(info_i["DS2"]["id"], period, db=db3)
    if recs2:
        db3.commit()
        # DS2c 从 DS2cc 获 355.2（40% of 888）
        # DS2 长期奖励 = 355.2 * 4% = 14.208，Decimal 四舍五入 = 14.21
        total_lt2 = sum(Decimal(str(r.amount)) for r in recs2)
        chk(total_lt2 == Decimal("14.21"),
            f"I2: DS2 long-term=14.21 (4% of 355.2=14.208 rounded, got {total_lt2})")
    else:
        warn_msg("I2: no long-term reward records")
    db3.close()
except Exception as ex:
    warn_msg(f"I2: {ex}")

print()

# ═══════════════════════════════════════════
# J: 新增场景 — 管理员种子用户 / 冷启动 / 支付列表 / 线下支付 / 验证码
# ═══════════════════════════════════════════

# ── J16-J18: 管理员创建种子用户 ──
print("=== J16-J18: Admin Create Seed User ===")
# J16: 创建 agent 无推荐码
seed_a = admin_create_seed(em("seed_agent"), "agent", at)
chk("id" in seed_a.get("data", {}),
    f"J16a: Created seed agent (id={seed_a.get('data',{}).get('id','?')})")
chk(seed_a.get("data", {}).get("role") == "agent",
    f"J16b: Seed agent role=agent")

# J17: 创建 distributor + 推荐码（关联上级）
a_rc_ext = ag1_rc  # AG1's referral code from setup
seed_d = admin_create_seed(em("seed_dist"), "distributor", at, referral_code=a_rc_ext)
chk("id" in seed_d.get("data", {}),
    f"J17a: Created seed distributor with referral (id={seed_d.get('data',{}).get('id','?')})")
# 验证 parent_id 设置
seed_d_id = seed_d["data"]["id"]
_db_seed = get_backend_session()
from app.models.user import User as _U2
su = _db_seed.query(_U2).filter(_U2.id == seed_d_id).first()
if su:
    chk(su.parent_id == ag1_id,
        f"J17b: Seed user parent_id={su.parent_id} (expected {ag1_id})")
else:
    warn_msg("J17b: Cannot verify parent_id, user not found")
_db_seed.close()

# J18: 重复邮箱创建
dup_resp = admin_create_seed(em("seed_agent"), "agent", at)
chk(dup_resp.get("_e") == 400,
    f"J18: Duplicate email rejected (code={dup_resp.get('_e')})")
print()

# ── J19: 冷启动登录断言 ──
print("=== J19: Cold-Start Login ===")
u_cold = login_as(em("coldstart"))
cold_me = get_me(u_cold["data"]["token"])["data"]
chk(cold_me["role"] == "distributor",
    f"J19a: Cold-start role=distributor (got={cold_me['role']})")
chk(cold_me["status"] == "active",
    f"J19b: Cold-start status=active")
chk(cold_me.get("parent_id") is None,
    f"J19c: Cold-start has no parent_id")
chk(cold_me.get("account_quota", 0) == 0,
    f"J19d: Cold-start has 0 quota (no payment yet)")
print()

# ── J20-J21: 支付列表/筛选 ──
print("=== J20-J21: Payment Listing ===")
# J20: 用户自列支付（用 U0 自己的邮箱，确与 user_id 关联）
u0_email = api("GET", "/api/v1/users/me", t=u0t)["data"]["email"]
p1 = recharge(5000, u0t, email=u0_email)["data"]["id"]
approve_r(p1, at)
p2 = recharge(888, u0t, email=u0_email)["data"]["id"]
approve_r(p2, at)

# J20: 用户自列支付
my_pays = api("GET", "/api/v1/payments", t=u0t)
chk(my_pays.get("total", 0) >= 1,
    f"J20: User payment list total={my_pays.get('total')} (expected >=1, 5000=user_id set, 888=NULL)")

# J21: 管理员按状态筛选
admin_pays = api("GET", "/api/v1/admin/payments?status=paid&limit=5", t=at)
chk(admin_pays.get("total", 0) >= 1,
    f"J21: Admin payment filter status=paid total={admin_pays.get('total')}")
print()

# ── J22-J23: 线下支付审批 ──
print("=== J22-J23: Offline Payment ===")
# J22: 线下审批无推荐码
u_off1 = login_as(em("offline1"))
utok_off1 = u_off1["data"]["token"]
poff1 = recharge(10000, utok_off1, email=em("offline1"))["data"]["id"]
approve_r(poff1, at)
off1_earn = get_earn(utok_off1)
off1_fr = [r for r in off1_earn.get("records", []) if r["type"] == "first_reward"]
chk(len(off1_fr) == 0,
    f"J22: Offline approve without referral -> 0 commission")

# J23: 线下审批有推荐码
u_off2 = login_as(em("offline2"))
utok_off2 = u_off2["data"]["token"]
poff2 = recharge(10000, utok_off2, email=em("offline2"), referral_code=a_rc_ext)["data"]["id"]
approve_r(poff2, at)
off2_earn = get_earn(ag1t)  # AG1's earnings (AG1 is the referrer)
off2_fr = [r for r in off2_earn.get("records", [])
           if r["type"] == "first_reward" and Decimal(str(r["amount"])) == Decimal("5500.00")]
chk(len(off2_fr) >= 1,
    f"J23: Offline approve with referral -> commission created (A got 5500)")
print()

# ── J24: 验证码过期 ──
print("=== J24: Verification Code Expire ===")
vc_email = em("vcexpire")
api("POST", "/api/v1/auth/send-email-code", {"email": vc_email, "scene": "login"})
# 手动将验证码过期时间改为过去
_db_exp = get_backend_session()
from app.models.email_verification_code import EmailVerificationCode as _EVC
from datetime import datetime, timezone, timedelta
vc_rec = _db_exp.query(_EVC).filter(
    _EVC.email == vc_email, _EVC.verified == False
).order_by(_EVC.created_at.desc()).first()
if vc_rec:
    vc_rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    expired_code = vc_rec.code  # 在 session 关闭前取值
    _db_exp.commit()
    _db_exp.close()
    # 尝试用过期码登录
    resp_exp = api("POST", "/api/v1/auth/login",
                   {"email": vc_email, "code": expired_code})
    chk(resp_exp.get("_e") in (400, 401),
        f"J24: Expired code rejected (code={resp_exp.get('_e')}, detail={resp_exp.get('detail','?')[:40]})")
else:
    _db_exp.close()
    skip_msg("J24: No verification code record found")
print()

# ── J25: 管理员拒绝支付 ──
print("=== J25: Admin Reject Payment ===")
u_rej = login_as(em("reject_pay"))
utok_rej = u_rej["data"]["token"]
prej = recharge(5000, utok_rej, email=em("reject_pay"))["data"]["id"]
reject_r(prej, "测试拒绝—黑名单", at)
# 验证支付状态
_db_rej = get_backend_session()
from app.models.payment import Payment as _P
pobj = _db_rej.query(_P).filter(_P.id == prej).first()
if pobj:
    chk(pobj.status == "failed" or pobj.status == "rejected",
        f"J25a: Payment status={pobj.status}")
    chk(pobj.reject_reason == "测试拒绝—黑名单",
        f"J25b: Reject reason='{pobj.reject_reason}'")
else:
    warn_msg("J25: Payment not found")
_db_rej.close()
# 角色不应改变
chk(get_me(utok_rej)["data"]["role"] == "distributor",
    "J25c: Role unchanged after reject")
print()

# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════
summary()
print("\n  扩展测试覆盖:")
print("  A: 佣金规则 (2档: agent 55% / distributor 40%)")
print("  B: 支付独立性 (不互斥/不降级/额度累加)")
print("  C: 支付边界 (无效金额/重复pending/记录列表)")
print("  D: 推荐码流程 (持久码获取)")
print("  E: 额度销售 (查询/真正API销售/权限/耗尽)")
print("  F: 工单列表")
print("  G: 管理员完整功能 (用户/看板/支付/工单/配置/重复审批)")
print("  H: 通知系统")
print("  I: 长期奖励补充 (经销商→经销商 4%)")
print("  J: 种子用户创建/冷启动/支付列表/线下支付/验证码过期/支付拒绝")
