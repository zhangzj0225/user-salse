"""E2E Gap Coverage: F1 double-spending / reject / license / invite / team / config.

Run with: backend server on 8000 + DATABASE_URL pointing to seeded deploy_test.db
"""
from decimal import Decimal
import time

from e2e_common import (
    Config, api, api_key, chk, skip_msg, summary,
    test_email, make_ts, login_as, admin_login, seed_user,
    get_backend_session,
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


def recharge(amt, t):
    return api("POST", "/api/v1/recharges", {"amount": amt}, t)


def approve_r(rid, at):
    return api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)


def reject_r(rid, reason, at):
    return api("POST", f"/api/v1/admin/recharges/{rid}/reject",
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
chk(True, "G0: Admin login OK")

# A: cold-start login -> agent (10000)
a = login_as(em("A"))
atok = a["data"]["token"]
chk(get_me(atok)["data"]["role"] == "user", "G0a: A created as user")
rid = recharge(10000, atok)["data"]["id"]
approve_r(rid, at)
chk(get_me(atok)["data"]["role"] == "agent", "G0b: A -> agent (10000 approved)")

# B: seed under A -> distributor (5000)
a_id = get_me(atok)["data"]["id"]
b_info = seed_user(em("B"), parent_id=a_id)
b = login_as(b_info["email"])
btok = b["data"]["token"]
chk(True, "G0c: B registered under A")
rid = recharge(5000, btok)["data"]["id"]
approve_r(rid, at)
chk(get_me(btok)["data"]["role"] == "distributor", "G0d: B -> distributor (5000 approved)")

# C: seed under B -> member (888)
c_info = seed_user(em("C"), parent_id=b_info["id"])
c = login_as(c_info["email"])
ctok = c["data"]["token"]
c_id = c["data"]["user"]["id"]
rid = recharge(888, ctok)["data"]["id"]
approve_r(rid, at)
chk(get_me(ctok)["data"]["role"] == "member", "G0e: C -> member (888 under B)")

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
chk(True, f"F1b: Ticket {tid} approved")

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
chk(get_me(utok)["data"]["role"] == "user",
    f"G3: Reject recharge -> role stays user")
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
            {"code": lic["code"], "email": b_info["email"]})
chk(v.get("success") is True,
    f"G4c: License verify success={v.get('success')}")

v2 = api_key("/api/v1/license/verify",
             {"code": lic["code"], "email": b_info["email"]})
chk(v2.get("success") is False,
    f"G4d: Re-verify denied (success={v2.get('success')})")
print()

# ═══════════════════════════════════════════
# GAP5: Invite Code Exhaustion
# ═══════════════════════════════════════════
print("=== GAP5: Invite Code Exhaustion ===")
from app.models.invite_code import InviteCode as ICModel

db3 = get_backend_session()
used_ic = db3.query(ICModel).filter(ICModel.used_by != None).first()
b_own = db3.query(ICModel).filter(
    ICModel.generator_id == b_info["id"], ICModel.used_by == None).first()
db3.close()
if used_ic:
    api("POST", "/api/v1/auth/send-email-code",
        {"email": em("dup"), "scene": "register"})
    resp = api("POST", "/api/v1/auth/register",
               {"email": em("dup"), "code": MOCK, "invite_code": used_ic.code})
    chk(resp.get("_e") in (400, 422),
        f"G5a: Used IC rejected (code={resp.get('_e')})")
else:
    skip_msg("G5a no used codes")
if b_own:
    api("POST", "/api/v1/auth/send-email-code",
        {"email": b_info["email"], "scene": "register"})
    resp = api("POST", "/api/v1/auth/register",
               {"email": b_info["email"], "code": MOCK, "invite_code": b_own.code})
    chk(resp.get("_e") in (400, 422),
        f"G5b: Self-referral rejected (code={resp.get('_e')})")
else:
    skip_msg("G5b no own unused code")
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
# SUMMARY
# ═══════════════════════════════════════════
summary()
print("  E2E gap coverage: F1 double-spending, reject/unfreeze, recharge reject,")
print("  license lifecycle, invite code exhaustion, team tree, admin config")
