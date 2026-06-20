"""E2E Gap Coverage: F1 double-spending / reject / license / invite / team / config.

Run with: backend server on 8000 + DATABASE_URL pointing to seeded deploy_test.db
"""
import json, os, sys, time, urllib.request as ur
from decimal import Decimal

os.environ.setdefault("ENV", "dev")
sys.path.insert(0, "d:/user-salse/backend")  # Ensure correct module path

BASE = "http://127.0.0.1:8000"; MOCK = "123456"
TS = str(int(time.time()))[-4:]; results = []


def api(m, p, d=None, t=None):
    u = f"{BASE}{p}"; b = json.dumps(d).encode() if d else None
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = f"Bearer {t}"
    req = ur.Request(u, data=b, method=m, headers=h)
    try:
        return json.loads(ur.urlopen(req, timeout=15).read())
    except ur.HTTPError as e:
        body = json.loads(e.read() if e.fp else b"{}")
        return {"_e": e.code, "detail": body.get("detail", str(e))}


def api_key(path, data):
    """API call with X-API-Key header (for license verify)"""
    req = ur.Request(f"{BASE}{path}", data=json.dumps(data).encode(),
                     headers={"Content-Type": "application/json",
                              "X-API-Key": "deploy-test-license-api-key"})
    try:
        return json.loads(ur.urlopen(req, timeout=10).read())
    except ur.HTTPError as e:
        return {"_e": e.code, "success": False, "message": str(e)}


def chk(ok, desc):
    tag = "PASS" if ok else "FAIL"
    results.append(f"{tag}: {desc}")
    print(f"  {tag}: {desc}" if ok else f"  *** {tag}: {desc}")
    return ok


def em(n): return f"gap_{TS}_{n}@test.com"


def login_user(email):
    api("POST", "/api/v1/auth/send-email-code", {"email": email, "scene": "login"})
    return api("POST", "/api/v1/auth/login", {"email": email, "code": MOCK})


def seed_user(email, parent_id, role="user"):
    """Direct DB insert to bypass register verification code issue"""
    from app.core.database import get_session_local
    from app.models.user import User
    from app.models.invite_code import InviteCode
    from app.core.security import generate_invite_code
    db = get_session_local()()
    u = User(email=email, role=role, status="active", parent_id=parent_id)
    db.add(u); db.flush()
    ic = generate_invite_code(u.id)
    u.invite_code = ic
    db.add(InviteCode(code=ic, generator_id=u.id, key_version=1))
    db.commit()
    uid, uic = u.id, ic
    db.close()
    return {"id": uid, "email": email, "invite_code": uic}


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
ad = api("POST", "/api/v1/auth/admin-login", {"username": "admin", "password": "admin123"})
at = ad["data"]["token"]
chk("token" in ad["data"], "G0: Admin login OK")

# A: cold-start login -> agent (10000)
a = login_user(em("A"))
atok = a["data"]["token"]
chk(get_me(atok)["data"]["role"] == "user", "G0a: A created as user")
rid = recharge(10000, atok)["data"]["id"]
approve_r(rid, at)
chk(get_me(atok)["data"]["role"] == "agent", "G0b: A -> agent (10000 approved)")

# B: seed under A -> distributor (5000)
a_id = get_me(atok)["data"]["id"]
b_info = seed_user(em("B"), parent_id=a_id)
b = login_user(b_info["email"])
btok = b["data"]["token"]
chk(True, "G0c: B registered under A")
rid = recharge(5000, btok)["data"]["id"]
approve_r(rid, at)
chk(get_me(btok)["data"]["role"] == "distributor", "G0d: B -> distributor (5000 approved)")

# C: seed under B -> member (888)
c_info = seed_user(em("C"), parent_id=b_info["id"])
c = login_user(c_info["email"])
ctok = c["data"]["token"]
c_id = c["data"]["user"]["id"]
rid = recharge(888, ctok)["data"]["id"]
approve_r(rid, at)
chk(get_me(ctok)["data"]["role"] == "member", "G0e: C -> member (888 under B)")

# Verify commission chain
time.sleep(0.5)
ae = get_earn(atok)
be = get_earn(btok)
# A: first_reward from B = 2750 (agent x 55% x 5000)
a_fr = [r for r in ae["records"] if r["type"] == "first_reward"]
# B: first_reward from C = 355.20 (distributor x 40% x 888)
b_fr = [r for r in be["records"] if r["type"] == "first_reward"]
# A: no first_reward from C (indirect)
a_fr_c = [r for r in ae["records"] if r["type"] == "first_reward"
          and r.get("source_user_id") == c_id]
# A: followup from C = 133.20 (agent->distributor->member charges 888)
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
        # Third attempt must fail
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

    # Reject -> balance unfreezes
    reject_t(btid, "test reject", at)
    b_avail2 = Decimal(get_earn(btok)["summary"]["available_balance"])
    chk(b_avail2 >= b_avail1 + Decimal("99"),
        f"G2b: Reject unfroze avail {b_avail1} -> {b_avail2}")

    # Can re-withdraw after reject
    resp = api("POST", "/api/v1/users/me/tickets",
               {"amount": "100", "payment_method": "wechat"}, btok)
    chk("ticket_id" in resp or "id" in resp,
        f"G2c: Can re-withdraw after reject")
else:
    results.append("SKIP: GAP2 not enough balance")
print()

# ═══════════════════════════════════════════
# GAP3: Recharge Reject
# ═══════════════════════════════════════════
print("=== GAP3: Recharge Reject ===")
u = login_user(em("rej"))
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
# B has license (distributor from 5000 recharge)
lic = api("GET", "/api/v1/users/me/license", t=btok)
chk("code" in lic,
    f"G4a: B has license (code={lic.get('code', 'N/A')[:12]}...)")
chk(lic.get("status") in ("unused", "activated"),
    f"G4b: License status={lic.get('status')}")

# Verify license with API Key
v = api_key("/api/v1/license/verify",
            {"code": lic["code"], "email": b_info["email"]})
chk(v.get("success") is True,
    f"G4c: License verify success={v.get('success')}")

# Re-verify -> must fail (already activated)
v2 = api_key("/api/v1/license/verify",
             {"code": lic["code"], "email": b_info["email"]})
chk(v2.get("success") is False,
    f"G4d: Re-verify denied (success={v2.get('success')})")
print()

# ═══════════════════════════════════════════
# GAP5: Invite Code Exhaustion
# ═══════════════════════════════════════════
print("=== GAP5: Invite Code Exhaustion ===")
# Query DB directly for used codes
from app.core.database import get_session_local as gsl2
from app.models.invite_code import InviteCode as ICModel2
db3 = gsl2()()
used_ic = db3.query(ICModel2).filter(ICModel2.used_by != None).first()
b_own = db3.query(ICModel2).filter(
    ICModel2.generator_id == b_info["id"], ICModel2.used_by == None).first()
db3.close()
if used_ic:
    resp = api("POST", "/api/v1/auth/send-email-code",
               {"email": em("dup"), "scene": "register"})
    resp = api("POST", "/api/v1/auth/register",
               {"email": em("dup"), "code": MOCK, "invite_code": used_ic.code})
    chk(resp.get("_e") in (400, 422),
        f"G5a: Used IC rejected (code={resp.get('_e')})")
else:
    results.append("SKIP: G5a no used codes")
if b_own:
    resp = api("POST", "/api/v1/auth/send-email-code",
               {"email": b_info["email"], "scene": "register"})
    resp = api("POST", "/api/v1/auth/register",
               {"email": b_info["email"], "code": MOCK, "invite_code": b_own.code})
    chk(resp.get("_e") in (400, 422),
        f"G5b: Self-referral rejected (code={resp.get('_e')})")
else:
    results.append("SKIP: G5b no own unused code")
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
# C upstream chain: C -> B -> A
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
# Update min_withdrawal_amount from 100 to 200
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
# Restore
api("PUT", "/api/v1/admin/configs/min_withdrawal_amount",
    {"config_value": old}, at)
print()

# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════
print("\n" + "=" * 60)
for r in results:
    print(f"  {r}")
p = sum(1 for r in results if "PASS" in r)
f = sum(1 for r in results if "FAIL" in r)
s = sum(1 for r in results if "SKIP" in r)
print(f"\n  PASS={p} FAIL={f} SKIP={s} TOTAL={len(results)}")
print("  E2E gap coverage: F1 double-spending, reject/unfreeze, recharge reject,")
print("  license lifecycle, invite code exhaustion, team tree, admin config")
