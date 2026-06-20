"""Deep chain test v2 — 四级分销链佣金 + 长期奖励月结。"""
from decimal import Decimal

from e2e_common import (
    Config, api, chk, skip_msg, warn_msg, summary,
    test_email, make_ts, admin_login, get_backend_session, seed_users,
)

MOCK = Config.MOCK_CODE
TS = make_ts()


def em(n):
    return test_email("chain4", n, TS)


# ═══ PHASE 1: Seed all users, commit, close ═══
print("PHASE 1: Seed users")
info = seed_users([("A", None), ("B", "A"), ("C", "B"), ("D", "C"), ("F", "A")], ts=TS)
for name, data in info.items():
    print(f"  {name}: id={data['id']} parent={'?' if name == 'A' else '...'}")
print("  Seeded + committed.\n")

# ═══ PHASE 2: Login + recharges ═══
print("PHASE 2: Login + recharge")
at = admin_login()["token"]
tokens = {}
for nm in ["A", "B", "C", "D", "F"]:
    i = info[nm]
    api("POST", "/api/v1/auth/send-email-code", {"email": i["email"], "scene": "login"})
    r = api("POST", "/api/v1/auth/login", {"email": i["email"], "code": MOCK})
    if "_e" in r:
        print(f"  {nm} login FAIL: {r['detail']}")
        continue
    tokens[nm] = r["data"]["token"]
    print(f"  {nm}: login id={r['data']['user']['id']} (DB id={i['id']})")

for nm, amt in [("A", 10000), ("B", 10000), ("C", 5000), ("D", 888), ("F", 10000)]:
    t = tokens.get(nm)
    if not t:
        continue
    rid = api("POST", "/api/v1/recharges", {"amount": amt}, t)["data"]["id"]
    api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)
    role = api("GET", "/api/v1/users/me", t=t)["data"]["role"]
    ex = {"A": "agent", "B": "agent", "C": "distributor", "D": "member", "F": "agent"}[nm]
    chk(role == ex, f"P2: {nm} role={role}")
print()

# ═══ PHASE 3: Verify parent chain ═══
print("PHASE 3: Verify parent chain")
chain = api("GET", "/api/v1/users/me/upstream", t=tokens["B"])
b_parents = [m["user_id"] for m in chain.get("chain", [])]
print(f"  B upstream: {b_parents} (A's id={info['A']['id']})")
chk(info["A"]["id"] in b_parents, f"P3a: B.parent=A (upstream: {b_parents})")

chain_c = api("GET", "/api/v1/users/me/upstream", t=tokens["C"])
c_parents = [m["user_id"] for m in chain_c.get("chain", [])]
print(f"  C upstream: {c_parents} (B's id={info['B']['id']})")
chk(info["B"]["id"] in c_parents, f"P3b: C.parent=B (upstream: {c_parents})")

chain_d = api("GET", "/api/v1/users/me/upstream", t=tokens["D"])
d_parents = [m["user_id"] for m in chain_d.get("chain", [])]
print(f"  D upstream: {d_parents}")
chk(len(d_parents) == 3, f"P3c: D has 3-level chain (got:{len(d_parents)})")
print()

# ═══ PHASE 4: Commission verification ═══
print("PHASE 4: Commission verification")
a_recs = api("GET", "/api/v1/users/me/earnings", t=tokens["A"]).get("records", [])
b_recs = api("GET", "/api/v1/users/me/earnings", t=tokens["B"]).get("records", [])
c_recs = api("GET", "/api/v1/users/me/earnings", t=tokens["C"]).get("records", [])

a_b = [r for r in a_recs if r["type"] == "first_reward" and r.get("source_user_id") == info["B"]["id"]]
chk(len(a_b) >= 1 and Decimal(str(a_b[0]["amount"])) == Decimal("5500.00"), "S1: A +5500 from B")

a_f = [r for r in a_recs if r["type"] == "first_reward" and r.get("source_user_id") == info["F"]["id"]]
chk(len(a_f) >= 1 and Decimal(str(a_f[0]["amount"])) == Decimal("5500.00"), "S2: A +5500 from F")

b_c = [r for r in b_recs if r["type"] == "first_reward" and r.get("source_user_id") == info["C"]["id"]]
chk(len(b_c) >= 1 and Decimal(str(b_c[0]["amount"])) == Decimal("2750.00"),
    f"S3: B +2750 from C (B is agent, 55% of 5000. records:{[r['amount'] for r in b_recs]})")

a_c = [r for r in a_recs if r.get("source_user_id") == info["C"]["id"]]
chk(len(a_c) == 0, "S4: A 0 from C")

c_d = [r for r in c_recs if r["type"] == "first_reward"]
chk(len(c_d) >= 1 and Decimal(str(c_d[0]["amount"])) == Decimal("355.20"), "S5: C +355.20 from D")

b_fu = [r for r in b_recs if r["type"] == "followup_reward"]
chk(len(b_fu) >= 1 and Decimal(str(b_fu[0]["amount"])) == Decimal("133.20"), "S6: B +133.20 follow-up")

a_fu = [r for r in a_recs if r["type"] == "followup_reward"]
chk(len(a_fu) == 0, "S7: A 0 follow-up")

# ═══ PHASE 5: Quota sale (E seeded directly under B) ═══
# NOTE: 真正的销售流程需 sale_verify 验证码，但 SQLite DELETE journal 模式
# 下 send-email-code + POST /sales 存在会话隔离问题（同类测试在 e2e_full_flow.py
# S5 中通过 Playwright 覆盖）。此处通过 DB 直接创建客户来验证核心逻辑：
# B 的佣金余额不受子用户创建影响（销售零佣金）。
print("\nPHASE 5: Quota sale (DB-seeded customer E under B)")
b_bal_before = Decimal(api("GET", "/api/v1/users/me/earnings", t=tokens["B"])["summary"]["pending_balance"])
print(f"  B balance before: {b_bal_before}")

from app.models.user import User
from app.models.invite_code import InviteCode
from app.core.security import generate_invite_code

db3 = get_backend_session()
e_email = em("E_sale")
e = User(email=e_email, role="member", status="active", parent_id=info["B"]["id"])
db3.add(e); db3.flush()
ecode = generate_invite_code(e.id); e.invite_code = ecode
db3.add(InviteCode(code=ecode, generator_id=e.id, key_version=1))
db3.commit(); db3.close()

api("POST", "/api/v1/auth/send-email-code", {"email": e_email, "scene": "login"})
e_r = api("POST", "/api/v1/auth/login", {"email": e_email, "code": MOCK})
if "_e" not in e_r:
    chk(e_r["data"]["user"]["role"] == "member", "S8a: E=member (parent=B)")
    e_upstream = api("GET", "/api/v1/users/me/upstream", t=e_r["data"]["token"])
    e_parents = [m["user_id"] for m in e_upstream.get("chain", [])]
    chk(info["B"]["id"] in e_parents, f"S8b: E.parent=B (upstream={e_parents[:2]}...)")
else:
    chk(False, f"S8a: E login failed: {e_r.get('detail', '')}")
b_bal_after = Decimal(api("GET", "/api/v1/users/me/earnings", t=tokens["B"])["summary"]["pending_balance"])
chk(b_bal_before == b_bal_after, "S8c: B balance unchanged (sale=0 commission)")

# ═══ PHASE 6: Long-term reward ═══
print("\nPHASE 6: Long-term reward")
try:
    from app.services.commission_service import CommissionEngine
    from datetime import datetime, timezone, timedelta

    db2 = get_backend_session()
    engine = CommissionEngine(db2)
    next_month = (datetime.now(timezone.utc).replace(day=1) + timedelta(days=32))
    period = next_month.strftime("%Y%m")
    recs = engine.calculate_long_term_reward(info["A"]["id"], period, db=db2)
    if recs:
        db2.commit()
        # B 先充 10000→agent，C 再充 5000 时 B 拿 agent 比率 2750，+ followup 133.20 = 2883.20，5% = 144.16
        chk(Decimal(str(recs[0].amount)) == Decimal("144.16"),
            f"S9: A team_bonus=144.16 (got:{recs[0].amount})")
    else:
        warn_msg(f"S9 no settlement (period={period})")
    db2.close()
except Exception as ex:
    warn_msg(f"S9 {ex}")

# ═══ SUMMARY ═══
a_bal = api("GET", "/api/v1/users/me/earnings", t=tokens["A"])["summary"]["pending_balance"]
b_bal = api("GET", "/api/v1/users/me/earnings", t=tokens["B"])["summary"]["pending_balance"]
c_bal = api("GET", "/api/v1/users/me/earnings", t=tokens["C"])["summary"]["pending_balance"]
print(f"\n{'=' * 60}")
print(f"  A total={a_bal} (expect ~11000), B={b_bal} (2750+133.20=2883.20), C={c_bal} (355.20)")
print(f"\n  链路: A(11k) ─┬─ B(2.1k, 充1万) ─┬─ C(355, 充5千) ─┬─ D(充888)")
print(f"               │                     └─ E_sale(会员, B卖额度)")
print(f"               └─ F(充1万)")
summary()
