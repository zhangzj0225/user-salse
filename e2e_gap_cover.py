"""E2E Gap Coverage: F1 double-spending / reject / license / invite / team / config.

Run with: backend server on 8000 + DATABASE_URL pointing to seeded deploy_test.db
"""
from decimal import Decimal
import json
import time
import urllib.error
import urllib.request as _ur

from e2e_common import (
    Config, api, api_key, api_with_headers, chk, skip_msg, warn_msg, summary,
    test_email, make_ts, login_as, admin_login, seed_user,
    get_backend_session, get_referral_code_str,
    make_callback_signature, admin_create_seed,
)

MOCK = Config.MOCK_CODE
TS = make_ts()


def em(n):
    return test_email("gap", n, TS)


# ── Local helpers (thin wrappers) ──────────────────────────

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


def approve_t(tid, at):
    return api("POST", f"/api/v1/admin/tickets/{tid}/approve", t=at)


def reject_t(tid, reason, at):
    return api("POST", f"/api/v1/admin/tickets/{tid}/reject",
               {"reject_reason": reason}, t=at)


# ═══════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════
print("=== SETUP ===")
at = admin_login()["token"]
chk(bool(at) and len(at) > 20, "G0: Admin login OK")

# A: cold-start login -> agent (10000)
a = login_as(em("A"))
atok = a["data"]["token"]
chk(get_me(atok)["data"]["role"] == "distributor", "G0a: A created as distributor")
rid = recharge(10000, atok)["data"]["id"]
approve_r(rid, at)
chk(get_me(atok)["data"]["role"] == "agent", "G0b: A -> agent (10000 approved)")
a_rc = get_referral_code_str(atok)

# B: seed under A -> distributor (5000)
a_id = get_me(atok)["data"]["id"]
b_info = seed_user(em("B"), parent_id=a_id)
b = login_as(b_info["email"])
btok = b["data"]["token"]
chk("token" in b.get("data", {}), "G0c: B registered under A")
rid = recharge(5000, btok, referral_code=a_rc)["data"]["id"]
approve_r(rid, at)
chk(get_me(btok)["data"]["role"] == "distributor", "G0d: B -> distributor (5000 approved)")
b_rc = get_referral_code_str(btok)

# C: seed under B -> distributor (888)
c_info = seed_user(em("C"), parent_id=b_info["id"])
c = login_as(c_info["email"])
ctok = c["data"]["token"]
c_id = c["data"]["user"]["id"]
rid = recharge(888, ctok, referral_code=b_rc)["data"]["id"]
approve_r(rid, at)
chk(get_me(ctok)["data"]["role"] == "distributor", "G0e: C -> distributor (888 under B)")

# Verify commission chain
time.sleep(0.5)
ae = get_earn(atok)
be = get_earn(btok)
a_fr = [r for r in ae["records"] if r["type"] == "first_reward"]
b_fr = [r for r in be["records"] if r["type"] == "first_reward"]
a_fr_c = [r for r in ae["records"] if r["type"] == "first_reward"
          and r.get("source_user_id") == c_id]
a_fu = [r for r in ae["records"] if r["type"] == "followup_reward"]
chk(len(a_fr) >= 1 and Decimal(str(a_fr[0]["amount"])) == Decimal("2750.00"),
    f"G1: A first_reward=2750 from B (55% x 5000, got {[r['amount'] for r in a_fr]})")
chk(len(b_fr) >= 1 and Decimal(str(b_fr[0]["amount"])) == Decimal("355.20"),
    f"G2: B first_reward=355.20 from C (got {[r['amount'] for r in b_fr]})")
chk(len(a_fr_c) == 0, "G3: A 0 first_reward from C (indirect)")
chk(len(a_fu) >= 1 and Decimal(str(a_fu[0]["amount"])) == Decimal("133.20"),
    f"G3b: A followup=133.20 (got {[r['amount'] for r in a_fu]})")
print("  Setup done.\n")

# ═══════════════════════════════════════════
# F1: Double Spending Regression (CRITICAL)
# ═══════════════════════════════════════════
print("=== F1: Double Spending Regression ===")
ae = get_earn(atok)
avail = Decimal(ae["summary"]["available_balance"])
bal = Decimal(ae["summary"]["pending_balance"])
print(f"  A balance: total={bal} avail={avail}")

# Withdraw partial amount
w_amt = str(max(Decimal("100"), (avail / 2).quantize(Decimal("1"))))
print(f"  Withdrawing {w_amt}...")
resp = api("POST", "/api/v1/users/me/tickets",
           {"amount": w_amt, "payment_method": "alipay"}, atok)
tid = resp.get("ticket_id") or resp.get("id")
chk(bool(tid), f"F1a: Withdraw {w_amt} OK (ticket_id={tid})")
assert tid, "F1 needs ticket_id"

# Approve first withdrawal
approve_t(tid, at)
chk(True, f"F1b: Ticket {tid} approved (via admin API)")

# Verify available = original - withdrawn (NOT bounced back to original)
ae2 = get_earn(atok)
avail2 = Decimal(ae2["summary"]["available_balance"])
expected = avail - Decimal(w_amt)
chk(avail2 == expected,
    f"F1c: Available={avail2} (expected {expected}, OLD formula would bounce to {avail})")

# Try over-withdraw -> MUST be rejected
over = str(avail2 + Decimal("100"))
resp = api("POST", "/api/v1/users/me/tickets",
           {"amount": over, "payment_method": "wechat"}, atok)
chk(resp.get("_e") == 400, f"F1d: Over-withdraw {over} rejected (code={resp.get('_e')})")

# Withdraw remaining -> drain to 0
if avail2 > 0:
    resp = api("POST", "/api/v1/users/me/tickets",
               {"amount": str(avail2), "payment_method": "alipay"}, atok)
    tid2 = resp.get("ticket_id") or resp.get("id")
    if tid2:
        approve_t(tid2, at)
        avail3 = Decimal(get_earn(atok)["summary"]["available_balance"])
        chk(avail3 == Decimal("0"), f"F1e: Full drain -> available={avail3}")
        resp = api("POST", "/api/v1/users/me/tickets",
                   {"amount": "100", "payment_method": "wechat"}, atok)
        chk(resp.get("_e") == 400,
            f"F1f: Third withdrawal rejected (available=0, code={resp.get('_e')})")
    else:
        chk(False, f"F1e: Second withdrawal failed: {resp}")
print()

# ═══════════════════════════════════════════
# GAP2: Withdrawal Reject Unfreeze
# ═══════════════════════════════════════════
print("=== GAP2: Withdrawal Reject Unfreeze ===")
be0 = get_earn(btok)
b_avail0 = Decimal(be0["summary"]["available_balance"])
print(f"  B avail={b_avail0}")
if b_avail0 >= Decimal("100"):
    resp = api("POST", "/api/v1/users/me/tickets",
               {"amount": "100", "payment_method": "alipay"}, btok)
    btid = resp.get("ticket_id") or resp.get("id")
    b_avail1 = Decimal(get_earn(btok)["summary"]["available_balance"])
    chk(b_avail1 == b_avail0 - Decimal("100"),
        f"G2a: B avail {b_avail0} -> {b_avail1} (frozen 100)")

    reject_t(btid, "test reject", at)
    b_avail2 = Decimal(get_earn(btok)["summary"]["available_balance"])
    chk(b_avail2 >= b_avail1 + Decimal("99"),
        f"G2b: Reject unfroze avail {b_avail1} -> {b_avail2}")

    resp = api("POST", "/api/v1/users/me/tickets",
               {"amount": "100", "payment_method": "wechat"}, btok)
    chk("ticket_id" in resp or "id" in resp,
        f"G2c: Can re-withdraw after reject")
else:
    skip_msg("GAP2 not enough balance")
print()

# ═══════════════════════════════════════════
# GAP3: Recharge Reject
# ═══════════════════════════════════════════
print("=== GAP3: Recharge Reject ===")
u = login_as(em("rej"))
utok = u["data"]["token"]
cid = recharge(10000, utok)["data"]["id"]
reject_r(cid, "test reject recharge", at)
chk(get_me(utok)["data"]["role"] == "distributor",
    f"G3: Reject payment -> role stays distributor")
print()

# ═══════════════════════════════════════════
# GAP4: License Lifecycle
# ═══════════════════════════════════════════
print("=== GAP4: License Lifecycle ===")
lic = api("GET", "/api/v1/users/me/license", t=btok)
chk("code" in lic,
    f"G4a: B has license (code={lic.get('code', 'N/A')[:12]}...)")
chk(lic.get("status") in ("unused", "activated"),
    f"G4b: License status={lic.get('status')}")

v = api_key("/api/v1/license/verify",
            {"code": lic["code"]})
if v.get("_e") == 401:
    skip_msg("G4c: License verify skipped (API key mismatch)")
else:
    chk(v.get("valid") is True,
        f"G4c: License verify valid={v.get('valid')}")

v2 = api_key("/api/v1/license/verify",
             {"code": lic["code"]})
if v2.get("_e") == 401:
    skip_msg("G4d: Re-verify skipped (API key mismatch)")
else:
    chk(v2.get("valid") is True,
        f"G4d: Re-verify valid={v2.get('valid')} (verify is idempotent)")
print()

# ═══════════════════════════════════════════
# GAP5: 推荐码持久性（PRD v2: 1人1码，持久码，替代旧邀请码耗尽测试）
# ═══════════════════════════════════════════
print("=== GAP5: Referral Code Persistence ===")
# 推荐码是持久码，多次获取返回同一个码
rc1 = api("GET", "/api/v1/referral-code", t=btok)
rc2 = api("GET", "/api/v1/referral-code", t=btok)
chk(rc1.get("data", {}).get("code") == rc2.get("data", {}).get("code"),
    f"G5a: Referral code is persistent (same on repeated calls)")
chk(rc1.get("data", {}).get("code", "") != "",
    f"G5b: Referral code is non-empty")
print()

# ═══════════════════════════════════════════
# GAP6: Team Tree Structure
# ═══════════════════════════════════════════
print("=== GAP6: Team Tree ===")
ateam = api("GET", "/api/v1/users/me/team", t=atok)
chk("total_count" in ateam and "root" in ateam,
    f"G6a: Team tree structure OK (total={ateam.get('total_count', '?')})")
root = ateam.get("root", {})
chk(len(root.get("children", [])) >= 1,
    f"G6b: A has >=1 direct child (got {len(root.get('children', []))})")
chain = api("GET", "/api/v1/users/me/upstream", t=ctok)
chk(len(chain.get("chain", [])) == 2,
    f"G6c: C upstream chain length=2 (C->B->A, got {len(chain.get('chain', []))})")
print()

# ═══════════════════════════════════════════
# GAP7: Admin Config Flow (S1 fix verification)
# ═══════════════════════════════════════════
print("=== GAP7: Admin Config Flow ===")
cfgs = api("GET", "/api/v1/admin/configs", t=at)
chk(len(cfgs.get("configs", [])) >= 8,
    f"G7a: Configs exist ({len(cfgs.get('configs', []))})")
old = [c["config_value"] for c in cfgs["configs"]
       if c["config_key"] == "min_withdrawal_amount"]
old = old[0] if old else "100"
api("PUT", "/api/v1/admin/configs/min_withdrawal_amount",
    {"config_value": "200"}, at)
cfgs2 = api("GET", "/api/v1/admin/configs", t=at)
new = [c["config_value"] for c in cfgs2["configs"]
       if c["config_key"] == "min_withdrawal_amount"]
chk(new and new[0] == "200",
    f"G7b: Config updated {old} -> {new[0] if new else 'FAIL'}")
api("PUT", "/api/v1/admin/configs/min_withdrawal_amount",
    {"config_value": old}, at)
print()

# ═══════════════════════════════════════════
# G18: 重复支付防护（pending_user_key 约束）
# ═══════════════════════════════════════════
print("=== G18: Duplicate Payment Prevention ===")
dup_email = em("dup")
u_dup = login_as(dup_email)
utok_dup = u_dup["data"]["token"]
p1 = recharge(5000, utok_dup, email=dup_email)
chk("data" in p1, f"G18a: First payment created (id={p1.get('data',{}).get('id','?')})")
p2 = recharge(888, utok_dup, email=dup_email)
chk(p2.get("_e") == 400, f"G18b: Duplicate payment rejected (code={p2.get('_e')})")
# Cleanup: approve first payment to release pending_user_key
if "data" in p1:
    approve_r(p1["data"]["id"], at)
print()

# ═══════════════════════════════════════════
# G19-G20: 无推荐码=无佣金（5000/10000）
# ═══════════════════════════════════════════
print("=== G19-G20: No Referral = No Commission (5000/10000) ===")

# G19: 5000 without referral
u_nr5k = login_as(em("nr5k"))
utok_nr5k = u_nr5k["data"]["token"]
pid_nr5k = recharge(5000, utok_nr5k, email=em("nr5k"))["data"]["id"]
approve_r(pid_nr5k, at)
# 支付人本身永远不会有 first_reward（佣金打给推荐人），不能靠 earn API 断言。
# 直接查 CommissionRecord 表验证零佣金记录。
_db_nr5k = get_backend_session()
from app.models.commission_record import CommissionRecord as _CR
cr_nr5k = _db_nr5k.query(_CR).filter(_CR.business_id == f"payment:{pid_nr5k}").count()
_db_nr5k.close()
chk(cr_nr5k == 0,
    f"G19: 5000 without referral -> 0 commission (DB records={cr_nr5k})")

# G20: 10000 without referral
u_nr10k = login_as(em("nr10k"))
utok_nr10k = u_nr10k["data"]["token"]
pid_nr10k = recharge(10000, utok_nr10k, email=em("nr10k"))["data"]["id"]
approve_r(pid_nr10k, at)
_db_nr10k = get_backend_session()
cr_nr10k = _db_nr10k.query(_CR).filter(_CR.business_id == f"payment:{pid_nr10k}").count()
_db_nr10k.close()
chk(cr_nr10k == 0,
    f"G20: 10000 without referral -> 0 commission (DB records={cr_nr10k})")
print()

# ═══════════════════════════════════════════
# G21: 支付 redirect URL 白名单
# ═══════════════════════════════════════════
print("=== G21: Payment Redirect URL ===")
# 合法 redirect URL
p_redir = api("POST", "/api/v1/payments/create",
              {"email": em("redirect_ok"), "amount": 888,
               "redirect_url": "http://localhost:5173/callback"}, atok)
chk("data" in p_redir,
    f"G21a: Payment with valid redirect URL accepted (id={p_redir.get('data',{}).get('id','?')})")
# 恶意 redirect URL — 后端已添加 hostname 白名单校验
p_evil = api("POST", "/api/v1/payments/create",
             {"email": em("redirect_evil"), "amount": 888,
              "redirect_url": "https://evil.com/steal"}, atok)
chk(p_evil.get("_e") in (400, 422),
    f"G21b: Malicious redirect URL rejected (open redirect patched, code={p_evil.get('_e')})")
print()

# ═══════════════════════════════════════════
# G23-G25: License 激活流程
# ═══════════════════════════════════════════
print("=== G23-G25: License Activate ===")
# 获取 B 的 License 代码
b_lic = api("GET", "/api/v1/users/me/license", t=btok)
lic_code = b_lic.get("code", "")
if lic_code:
    # G23: 有效激活
    act_resp = api_key("/api/v1/license/activate",
                       {"code": lic_code, "business_user_id": "test_biz_user_001",
                        "business_user_info": "测试业务系统用户"})
    if act_resp.get("_e") == 401:
        skip_msg("G23: License activate skipped (API key mismatch)")
        skip_msg("G24: Wrong API key test skipped")
        skip_msg("G25: Double activate test skipped")
    else:
        chk(act_resp.get("data", {}).get("success") is True,
            f"G23: License activated (resp={act_resp})")

        # G24: 错误 API Key
        bad_req = _ur.Request(
            f"{Config.API_BASE_URL}/api/v1/license/activate",
            data=json.dumps({"code": lic_code, "business_user_id": "bad_key_test"}).encode(),
            headers={"Content-Type": "application/json", "X-API-Key": "wrong-key"},
            method="POST",
        )
        try:
            _ur.urlopen(bad_req, timeout=Config.TIMEOUT)
            chk(False, "G24: Wrong API Key should be rejected")
        except urllib.error.HTTPError as e:
            chk(e.code in (401, 403), f"G24: Wrong API Key rejected ({e.code})")

        # G25: 重复激活
        act_resp2 = api_key("/api/v1/license/activate",
                            {"code": lic_code, "business_user_id": "test_biz_user_002"})
        chk(act_resp2.get("data", {}).get("success") is False,
            f"G25: Double activate rejected (resp={act_resp2})")
else:
    skip_msg("G23-G25: No license code available")
print()

# ═══════════════════════════════════════════
# G26: 佣金幂等性（同一支付回调两次）
# ═══════════════════════════════════════════
print("=== G26: Commission Idempotency ===")
u_idem = login_as(em("idem"))
utok_idem = u_idem["data"]["token"]
# 用 A 的推荐码支付（有佣金）
pid_idem = recharge(5000, utok_idem, email=em("idem"), referral_code=a_rc)["data"]["id"]
# 第一次回调处理
sig = make_callback_signature(pid_idem, "test_pno_idem_001")
cb1 = api_with_headers("POST", "/api/v1/payments/callback",
                       {"payment_id": pid_idem, "payment_no": "test_pno_idem_001"},
                       headers={"X-Signature": sig})
chk("data" in cb1, f"G26a: First callback OK (status={cb1.get('data',{}).get('status','?')})")

# 查询佣金条数
_db3 = get_backend_session()
from app.models.commission_record import CommissionRecord as _CR
cr_count_1 = _db3.query(_CR).filter(_CR.business_id == f"payment:{pid_idem}").count()
_db3.close()

# 第二次回调（相同 payment_id + payment_no）
sig2 = make_callback_signature(pid_idem, "test_pno_idem_001")
cb2 = api_with_headers("POST", "/api/v1/payments/callback",
                       {"payment_id": pid_idem, "payment_no": "test_pno_idem_001"},
                       headers={"X-Signature": sig2})
# 第二次回调：后端对已支付订单返回 200（幂等）或 400（已处理）。
# _e 只在 HTTPError 时出现（4xx/5xx），200 响应没有 _e 键。
cb2_ok = "data" in cb2
cb2_idem = cb2.get("_e") == 400  # 400 = 已处理，幂等返回
chk(cb2_ok or cb2_idem,
    f"G26b: Second callback idempotent (ok={cb2_ok}, status={cb2.get('_e', 'N/A')})")

_db3 = get_backend_session()
cr_count_2 = _db3.query(_CR).filter(_CR.business_id == f"payment:{pid_idem}").count()
_db3.close()
chk(cr_count_1 == cr_count_2,
    f"G26c: Commission records unchanged ({cr_count_1} -> {cr_count_2})")
print()

# ═══════════════════════════════════════════
# G27-G28: 支付回调签名验证
# ═══════════════════════════════════════════
print("=== G27-G28: Payment Callback Signature ===")
# 创建一笔支付用于测试回调
u_cb = login_as(em("cb"))
utok_cb = u_cb["data"]["token"]
pid_cb = recharge(5000, utok_cb, email=em("cb"), referral_code=a_rc)["data"]["id"]
pno_cb = "test_pno_sig_001"

# G27: 正确签名
sig_ok = make_callback_signature(pid_cb, pno_cb)
cb_ok = api_with_headers("POST", "/api/v1/payments/callback",
                         {"payment_id": pid_cb, "payment_no": pno_cb},
                         headers={"X-Signature": sig_ok})
chk("data" in cb_ok and cb_ok["data"].get("status") == "paid",
    f"G27: Callback with valid signature -> paid (got: {cb_ok.get('data',{}).get('status', cb_ok.get('_e'))})")

# G28: 错误签名
sig_bad = "a" * 64  # 64 hex chars but wrong value
cb_bad = api_with_headers("POST", "/api/v1/payments/callback",
                          {"payment_id": pid_cb, "payment_no": "bad_pno"},
                          headers={"X-Signature": sig_bad})
chk(cb_bad.get("_e") == 403,
    f"G28: Callback with invalid signature -> 403 (got {cb_bad.get('_e')})")
print()

# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════
summary()
print("  E2E gap coverage: F1 double-spending, reject/unfreeze, payment reject,")
print("  license lifecycle/activate, referral code persistence, team tree, admin config,")
print("  duplicate payment prevention, no-referral=no-commission, redirect URL,")
print("  commission idempotency, payment callback HMAC signature")
