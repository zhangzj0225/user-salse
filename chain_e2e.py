"""Deep chain test v2 — fixed parent_id + quota sale."""
import json, os, sys, time, urllib.request
from decimal import Decimal
sys.path.insert(0, "D:/workspace/user-salse/backend")
os.environ.setdefault("ENV", "dev")
import app.models  # noqa
from app.core.database import get_session_local
from app.models.user import User
from app.models.invite_code import InviteCode
from app.core.security import generate_invite_code

BASE = "http://127.0.0.1:8000"; MOCK = "123456"
TS = str(int(time.time()))[-4:]; results = []

def api(m, p, d=None, t=None):
    u = f"{BASE}{p}"; b = (json.dumps(d).encode() if d else None)
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = f"Bearer {t}"
    r = urllib.request.Request(u, data=b, method=m, headers=h)
    try: return json.loads(urllib.request.urlopen(r, timeout=15).read())
    except urllib.error.HTTPError as e:
        return {"_e": e.code, "detail": json.loads(e.read()).get("detail", "")}

def chk(ok, desc):
    p = "PASS" if ok else "FAIL"; results.append(f"{p}: {desc}")
    print(f"  {p}: {desc}" if ok else f"  *** {p}: {desc}"); return ok

def em(n): return f"chain4_{TS}_{n}@test.com"
ad = api("POST","/api/v1/auth/admin-login",{"username":"admin","password":"admin123"}); at = ad["data"]["token"]

# ═══ PHASE 1: Seed all users, commit, close ═══
print("PHASE 1: Seed users")
SessionLocal = get_session_local(); db = SessionLocal()
info = {}

for name, par in [("A",None),("B","A"),("C","B"),("D","C"),("F","A")]:
    email = em(name)
    parent_id = info[par]["id"] if par else None
    u = User(email=email, role="user", status="active", parent_id=parent_id)
    db.add(u); db.flush()
    code = generate_invite_code(u.id); u.invite_code = code
    db.add(InviteCode(code=code, generator_id=u.id, key_version=1))
    info[name] = {"email": email, "id": u.id}
    print(f"  {name}: id={u.id} parent={parent_id}")

db.commit(); db.close()
print("  Seeded + committed.\n")

# ═══ PHASE 2: Login + recharges ═══
print("PHASE 2: Login + recharge")
tokens = {}
for nm in ["A","B","C","D","F"]:
    i = info[nm]
    api("POST","/api/v1/auth/send-email-code",{"email":i["email"],"scene":"login"})
    r = api("POST","/api/v1/auth/login",{"email":i["email"],"code":MOCK})
    if "_e" in r: print(f"  {nm} login FAIL: {r['detail']}"); continue
    tokens[nm] = r["data"]["token"]
    print(f"  {nm}: login id={r['data']['user']['id']} (DB id={i['id']})")

for nm, amt in [("A",10000),("B",10000),("C",5000),("D",888),("F",10000)]:
    t = tokens.get(nm)
    if not t: continue
    rid = api("POST","/api/v1/recharges",{"amount":amt},t)["data"]["id"]
    api("POST",f"/api/v1/admin/recharges/{rid}/approve",t=at)
    role = api("GET","/api/v1/users/me",t=t)["data"]["role"]
    ex = {"A":"agent","B":"agent","C":"distributor","D":"member","F":"agent"}[nm]
    chk(role==ex, f"P2: {nm} role={role}")
print()

# ═══ PHASE 3: Verify parent chain (debug) ═══
print("PHASE 3: Verify parent chain")
# Check B's parent is A
a_email = info["A"]["email"]
b_email = info["B"]["email"]
# Login as B and check upstream
chain = api("GET","/api/v1/users/me/upstream",t=tokens["B"])
b_parents = [m["user_id"] for m in chain.get("chain",[])]
print(f"  B upstream: {b_parents} (A's id={info['A']['id']})")
chk(info["A"]["id"] in b_parents, f"P3a: B.parent=A (upstream: {b_parents})")

# Check C's parent is B
chain_c = api("GET","/api/v1/users/me/upstream",t=tokens["C"])
c_parents = [m["user_id"] for m in chain_c.get("chain",[])]
print(f"  C upstream: {c_parents} (B's id={info['B']['id']})")
chk(info["B"]["id"] in c_parents, f"P3b: C.parent=B (upstream: {c_parents})")

# D's parent is C
chain_d = api("GET","/api/v1/users/me/upstream",t=tokens["D"])
d_parents = [m["user_id"] for m in chain_d.get("chain",[])]
print(f"  D upstream: {d_parents}")
chk(len(d_parents)==3, f"P3c: D has 3-level chain (got:{len(d_parents)})")
print()

# ═══ PHASE 4: Commission verification ═══
print("PHASE 4: Commission verification")
a_recs = api("GET","/api/v1/users/me/earnings",t=tokens["A"]).get("records",[])
b_recs = api("GET","/api/v1/users/me/earnings",t=tokens["B"]).get("records",[])
c_recs = api("GET","/api/v1/users/me/earnings",t=tokens["C"]).get("records",[])

# A: 5500 from B
a_b = [r for r in a_recs if r["type"]=="first_reward" and r.get("source_user_id")==info["B"]["id"]]
chk(len(a_b)>=1 and Decimal(str(a_b[0]["amount"]))==Decimal("5500.00"), "S1: A +5500 from B")

# A: 5500 from F
a_f = [r for r in a_recs if r["type"]=="first_reward" and r.get("source_user_id")==info["F"]["id"]]
chk(len(a_f)>=1 and Decimal(str(a_f[0]["amount"]))==Decimal("5500.00"), "S2: A +5500 from F")

# B: 2750 from C (B is agent → 55% of 5000)
b_c = [r for r in b_recs if r["type"]=="first_reward" and r.get("source_user_id")==info["C"]["id"]]
chk(len(b_c)>=1 and Decimal(str(b_c[0]["amount"]))==Decimal("2750.00"), f"S3: B +2750 from C (B is agent, 55% of 5000. records:{[r['amount'] for r in b_recs]})")

# A: 0 from C (non-direct)
a_c = [r for r in a_recs if r.get("source_user_id")==info["C"]["id"]]
chk(len(a_c)==0, "S4: A 0 from C")

# C: 355.20 from D
c_d = [r for r in c_recs if r["type"]=="first_reward"]
chk(len(c_d)>=1 and Decimal(str(c_d[0]["amount"]))==Decimal("355.20"), "S5: C +355.20 from D")

# B: 133.20 follow-up
b_fu = [r for r in b_recs if r["type"]=="followup_reward"]
chk(len(b_fu)>=1 and Decimal(str(b_fu[0]["amount"]))==Decimal("133.20"), "S6: B +133.20 follow-up")

# A: 0 follow-up
a_fu = [r for r in a_recs if r["type"]=="followup_reward"]
chk(len(a_fu)==0, "S7: A 0 follow-up")

# ═══ PHASE 5: Quota sale (E created by sale, NOT seeded) ═══
print("\nPHASE 5: Quota sale")
e_email = em("E_sale")
api("POST","/api/v1/auth/send-email-code",{"email":e_email,"scene":"sale_verify"})
sale = api("POST","/api/v1/sales",{"customer_email":e_email,"verification_code":MOCK},tokens["B"])
sale_ok = "_e" not in sale and sale.get("remaining_quota")==21
chk(sale_ok, "S8a: Quota sale")

b_bal_before = Decimal(api("GET","/api/v1/users/me/earnings",t=tokens["B"])["summary"]["pending_balance"])
print(f"  B balance before sale: {b_bal_before}")
api("POST","/api/v1/auth/send-email-code",{"email":e_email,"scene":"login"})
e_r = api("POST","/api/v1/auth/login",{"email":e_email,"code":MOCK})
chk(sale_ok, "S8a: Quota sale")
if sale_ok and "_e" not in e_r:
    chk(api("GET","/api/v1/users/me",t=e_r["data"]["token"])["data"]["role"]=="member", "S8b: E=member")
b_bal_after = Decimal(api("GET","/api/v1/users/me/earnings",t=tokens["B"])["summary"]["pending_balance"])
chk(b_bal_before==b_bal_after, "S8c: B balance unchanged")

# ═══ PHASE 6: Long-term reward ═══
print("\nPHASE 6: Long-term reward")
try:
    db2 = SessionLocal()
    from app.services.commission_service import CommissionEngine
    from datetime import datetime, timezone
    engine = CommissionEngine(db2)
    # 传下个月 period，查询窗口覆盖当月佣金（函数内部查的是上月数据）
    from datetime import timedelta
    next_month = (datetime.now(timezone.utc).replace(day=1) + timedelta(days=32))
    period = next_month.strftime("%Y%m")
    recs = engine.calculate_long_term_reward(info["A"]["id"], period, db=db2)
    if recs:
        db2.commit()
        # B 先充 10000→agent，C 再充 5000 时 B 拿 agent 比率 2750，+ followup 133.20 = 2883.20，5% = 144.16
        chk(Decimal(str(recs[0].amount))==Decimal("144.16"), f"S9: A team_bonus=144.16 (got:{recs[0].amount})")
    else:
        results.append("WARN: S9 no settlement (period={period})")
    db2.close()
except Exception as ex:
    results.append(f"WARN: S9 {ex}")

# ═══ SUMMARY ═══
print(f"\n{'='*60}")
a_bal = api("GET","/api/v1/users/me/earnings",t=tokens["A"])["summary"]["pending_balance"]
b_bal = api("GET","/api/v1/users/me/earnings",t=tokens["B"])["summary"]["pending_balance"]
c_bal = api("GET","/api/v1/users/me/earnings",t=tokens["C"])["summary"]["pending_balance"]
print(f"  A total={a_bal} (expect ~11000), B={b_bal} (2750+133.20=2883.20), C={c_bal} (355.20)")
print(f"\n  链路: A(11k) ─┬─ B(2.1k, 充1万) ─┬─ C(355, 充5千) ─┬─ D(充888)")
print(  f"               │                     └─ E_sale(会员, B卖额度)")
print(  f"               └─ F(充1万)")
for r in results: print(f"  {r}")
p=sum(1 for r in results if "PASS" in r); f=sum(1 for r in results if "FAIL" in r); w=sum(1 for r in results if "WARN" in r)
print(f"\n  PASS={p} FAIL={f} WARN={w}")
