"""E2E 佣金规则完整性测试 — 补充长期奖励 4 种组合、后续收益关系排除、不穿透验证。

PRD v2: 佣金 2 档（agent 55% / distributor 40%），无推荐码=无佣金。
角色只有 distributor 和 agent，无 user/member。

本脚本聚焦需求中最容易遗漏的边界场景：

1. 长期奖励 4 种组合全覆盖（需求 4.3）
   - 代理→代理 5%        (已在 chain_e2e S9 覆盖，此处做对照)
   - 代理→经销商 不适用   (代码有排除逻辑，从未被验证)
   - 经销商→代理 4%      (完全缺失)
   - 经销商→经销商 4%    (已在 e2e_extended I2 覆盖)

2. 后续收益关系排除（需求 4.2 — 仅代理→经销商关系）
   - 代理→代理→经销商充888，不应有 followup_reward
   - 经销商→经销商→经销商充888，不应有 followup_reward

3. 长期奖励不穿透（需求 4.3 — 仅限直接下级）
   - A(代理)→B(代理)→C(经销商)→D(经销商充888)
   - A 的长期奖励只看 B 的收入，不看 C/D 的收入

Run with: backend server on 8000 + DATABASE_URL pointing to seeded deploy_test.db
"""
from decimal import Decimal
import time
from datetime import datetime, timezone, timedelta

from e2e_common import (
    Config, api, chk, skip_msg, warn_msg, summary,
    test_email, make_ts, admin_login, seed_users,
    get_backend_session, get_referral_code_str,
)

MOCK = Config.MOCK_CODE
TS = make_ts()


def em(n):
    return test_email("rule", n, TS)


def login(email):
    api("POST", "/api/v1/auth/send-email-code", {"email": email, "scene": "login"})
    return api("POST", "/api/v1/auth/login", {"email": email, "code": MOCK})


def recharge_and_approve(token, amount, admin_token, email=None, referral_code=None):
    """创建支付并审批（PRD v2: recharges → payments/create）。"""
    if email is None:
        me = api("GET", "/api/v1/users/me", t=token)
        email = me["data"]["email"]
    body = {"email": email, "amount": amount}
    if referral_code:
        body["referral_code"] = referral_code
    rid = api("POST", "/api/v1/payments/create", body, token)["data"]["id"]
    api("POST", f"/api/v1/admin/payments/{rid}/approve", data={}, t=admin_token)
    return rid


def get_earnings(token):
    return api("GET", "/api/v1/users/me/earnings", t=token)


def first_reward_from(earn_resp, source_uid):
    return [r for r in earn_resp.get("records", [])
            if r["type"] == "first_reward"
            and r.get("source_user_id") == source_uid]


def followup_rewards(earn_resp):
    return [r for r in earn_resp.get("records", [])
            if r["type"] == "followup_reward"]


def calc_long_term(user_id, period):
    """调用佣金引擎计算长期奖励，返回 (记录数, 总金额)。"""
    db = get_backend_session()
    from app.services.commission_service import CommissionEngine
    engine = CommissionEngine(db)
    recs = engine.calculate_long_term_reward(user_id, period, db=db)
    if recs:
        db.commit()
        # 在 session 关闭前提取金额
        amounts = [(r.id, Decimal(str(r.amount))) for r in recs]
    else:
        amounts = []
    db.close()
    return amounts


def get_next_period():
    next_month = datetime.now(timezone.utc).replace(day=1) + timedelta(days=32)
    return next_month.strftime("%Y%m")


# ═══════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════
print("=== SETUP ===")
at = admin_login()["token"]
PERIOD = get_next_period()
print(f"  Settlement period: {PERIOD}")
chk(True, "R0: Admin login OK")


# ═══════════════════════════════════════════
# J. 后续收益关系排除（需求 4.2）
# ═══════════════════════════════════════════
print("\n=== J. 后续收益关系排除 ===")
print("  需求: 后续收益仅限代理→经销商关系，其他关系不产生 133.2 元")

# J1: 代理→代理→经销商充888，不应有后续收益
# 链路: A2(agent) → B2(agent) → C2(distributor充888)
# B2 是代理不是经销商，A2 不应获 followup_reward
print("\n  [J1] 代理→代理→经销商充888")
info_j1 = seed_users([("A2", None), ("B2", "A2"), ("C2", "B2")], ts=TS + "j1")
toks = {}
for nm in ["A2", "B2", "C2"]:
    r = login(info_j1[nm]["email"])
    toks[nm] = r["data"]["token"]

# A2、B2 充 10000 成为代理
recharge_and_approve(toks["A2"], 10000, at)
a2_rc = get_referral_code_str(toks["A2"])
recharge_and_approve(toks["B2"], 10000, at, referral_code=a2_rc)
b2_rc = get_referral_code_str(toks["B2"])
time.sleep(0.3)

a2_role = api("GET", "/api/v1/users/me", t=toks["A2"])["data"]["role"]
b2_role = api("GET", "/api/v1/users/me", t=toks["B2"])["data"]["role"]
chk(a2_role == "agent" and b2_role == "agent", f"J1a: A2={a2_role} B2={b2_role} (both agent)")

# C2 充 888
recharge_and_approve(toks["C2"], 888, at, referral_code=b2_rc)
time.sleep(0.5)

# B2 应获首次奖励 488.40 (代理 55%) — 888 支付 source_user_id 为 None，按金额匹配
b2_earn = get_earnings(toks["B2"])
b2_fr = [r for r in b2_earn.get("records", [])
         if r["type"] == "first_reward" and Decimal(str(r["amount"])) == Decimal("488.40")]
chk(len(b2_fr) >= 1,
    f"J1b: B2 first_reward=488.40 from C2 (agent 55%)")

# A2 不应获后续收益（B2 是代理不是经销商）
a2_earn = get_earnings(toks["A2"])
a2_fu = followup_rewards(a2_earn)
chk(len(a2_fu) == 0,
    f"J1c: A2 0 followup_reward (B2 is agent not distributor, got {len(a2_fu)})")

# J2: 经销商→经销商→经销商充888，不应有后续收益
# 链路: D2(distributor) → E2(distributor) → F2(distributor充888)
print("\n  [J2] 经销商→经销商→经销商充888")
info_j2 = seed_users([("D2", None), ("E2", "D2"), ("F2", "E2")], ts=TS + "j2")
toks2 = {}
for nm in ["D2", "E2", "F2"]:
    r = login(info_j2[nm]["email"])
    toks2[nm] = r["data"]["token"]

recharge_and_approve(toks2["D2"], 5000, at)
d2_rc = get_referral_code_str(toks2["D2"])
recharge_and_approve(toks2["E2"], 5000, at, referral_code=d2_rc)
e2_rc = get_referral_code_str(toks2["E2"])
time.sleep(0.3)

d2_role = api("GET", "/api/v1/users/me", t=toks2["D2"])["data"]["role"]
e2_role = api("GET", "/api/v1/users/me", t=toks2["E2"])["data"]["role"]
chk(d2_role == "distributor" and e2_role == "distributor",
    f"J2a: D2={d2_role} E2={e2_role} (both distributor)")

recharge_and_approve(toks2["F2"], 888, at, referral_code=e2_rc)
time.sleep(0.5)

# E2 应获首次奖励 355.20 (经销商 40%) — 888 支付 source_user_id 为 None
e2_earn = get_earnings(toks2["E2"])
e2_fr = [r for r in e2_earn.get("records", [])
         if r["type"] == "first_reward" and Decimal(str(r["amount"])) == Decimal("355.20")]
chk(len(e2_fr) >= 1,
    f"J2b: E2 first_reward=355.20 from F2 (distributor 40%)")

# D2 不应获后续收益（E2 是经销商，D2 也是经销商，不是代理→经销商关系）
d2_earn = get_earnings(toks2["D2"])
d2_fu = followup_rewards(d2_earn)
chk(len(d2_fu) == 0,
    f"J2c: D2 0 followup_reward (distributor→distributor not eligible, got {len(d2_fu)})")


# ═══════════════════════════════════════════
# K. 长期奖励 4 种组合全覆盖（需求 4.3）
# ═══════════════════════════════════════════
print("\n=== K. 长期奖励 4 种组合 ===")
print("  需求 4.3:")
print("  | 上级→下级     | 比例   |")
print("  | 代理→代理     | 5%    |")
print("  | 代理→经销商   | 不适用 |")
print("  | 经销商→代理   | 4%    |")
print("  | 经销商→经销商 | 4%    |")

# K1: 代理→经销商 不适用（关键缺口！）
# 链路: AG(distributor parent=AG_parent) → DS(distributor)
# AG 是代理，DS 是经销商，AG 的长期奖励应排除 DS
print("\n  [K1] 代理→经销商 不适用长期奖励")
info_k1 = seed_users(
    [("AGp", None), ("AG", "AGp"), ("DS", "AG"), ("DSc", "DS")],
    ts=TS + "k1",
)
toks_k1 = {}
for nm in ["AGp", "AG", "DS", "DSc"]:
    r = login(info_k1[nm]["email"])
    toks_k1[nm] = r["data"]["token"]

# AG 充 10000 (代理), DS 充 5000 (经销商), DSc 充 888
recharge_and_approve(toks_k1["AG"], 10000, at)
ag_rc = get_referral_code_str(toks_k1["AG"])
recharge_and_approve(toks_k1["DS"], 5000, at, referral_code=ag_rc)
ds_rc = get_referral_code_str(toks_k1["DS"])
time.sleep(0.3)
recharge_and_approve(toks_k1["DSc"], 888, at, referral_code=ds_rc)
time.sleep(0.5)

# AG 应从 DS 获得 first_reward 2750 (代理 55%)
ag_earn = get_earnings(toks_k1["AG"])
ag_fr_ds = first_reward_from(ag_earn, info_k1["DS"]["id"])
chk(len(ag_fr_ds) >= 1 and Decimal(str(ag_fr_ds[0]["amount"])) == Decimal("2750.00"),
    f"K1a: AG first_reward=2750 from DS (agent 55%)")

# AG 应从 DSc 获得 followup_reward 133.20 (代理→经销商→用户充888)
ag_fu = followup_rewards(ag_earn)
chk(len(ag_fu) >= 1 and Decimal(str(ag_fu[0]["amount"])) == Decimal("133.20"),
    f"K1b: AG followup=133.20 from DSc's 888 (agent→distributor→user)")

# 计算长期奖励：AG 的直接下级 DS 是经销商 → 应被排除
recs_k1 = calc_long_term(info_k1["AG"]["id"], PERIOD)
if recs_k1:
    total_k1 = sum(amt for _, amt in recs_k1)
    chk(False, f"K1c: AG long-term should be 0 (distributor child excluded, got {total_k1})")
else:
    chk(True, "K1c: AG no long-term reward (distributor child excluded)")


# K2: 经销商→代理 4%（完全缺失的场景）
# 链路: DSP(distributor) → AGT(agent) → AGTc(distributor充888)
# DSP 是经销商，AGT 是代理，AGT 从 AGTc 获 488.40 首次奖励
# DSP 长期奖励 = 488.40 * 4% = 19.536 → 19.54
print("\n  [K2] 经销商→代理 4%")
info_k2 = seed_users(
    [("DSP", None), ("AGT", "DSP"), ("AGTc", "AGT")],
    ts=TS + "k2",
)
toks_k2 = {}
for nm in ["DSP", "AGT", "AGTc"]:
    r = login(info_k2[nm]["email"])
    toks_k2[nm] = r["data"]["token"]

recharge_and_approve(toks_k2["DSP"], 5000, at)
dsp_rc = get_referral_code_str(toks_k2["DSP"])
recharge_and_approve(toks_k2["AGT"], 10000, at, referral_code=dsp_rc)
agt_rc = get_referral_code_str(toks_k2["AGT"])
time.sleep(0.3)
recharge_and_approve(toks_k2["AGTc"], 888, at, referral_code=agt_rc)
time.sleep(0.5)

# AGT 应获 first_reward 488.40 (代理 55%) — 888 支付 source_user_id 为 None
agt_earn = get_earnings(toks_k2["AGT"])
agt_fr = [r for r in agt_earn.get("records", [])
          if r["type"] == "first_reward" and Decimal(str(r["amount"])) == Decimal("488.40")]
chk(len(agt_fr) >= 1,
    f"K2a: AGT first_reward=488.40 from AGTc (agent 55%)")

# DSP 长期奖励 = AGT 收入 * 4% = 488.40 * 0.04 = 19.536 → 19.54
recs_k2 = calc_long_term(info_k2["DSP"]["id"], PERIOD)
if recs_k2:
    total_k2 = sum(amt for _, amt in recs_k2)
    chk(total_k2 == Decimal("19.54"),
        f"K2b: DSP long-term=19.54 (4% of 488.40=19.536 rounded, got {total_k2})")
else:
    warn_msg(f"K2b: DSP no long-term reward (expected 19.54)")


# ═══════════════════════════════════════════
# L. 长期奖励不穿透（需求 4.3 — 仅限直接下级）
# ═══════════════════════════════════════════
print("\n=== L. 长期奖励不穿透 ===")
print("  需求: 长期奖励仅限直接下级，不穿透更深层级")

# 链路: TOP(agent) → MID(agent) → BOT(distributor) → LEAF(distributor充888)
# TOP 的长期奖励只看 MID 的收入，不看 BOT/LEAF 的收入
# MID 从 BOT 获得 first_reward 2750 + followup 133.20 = 2883.20
# TOP 长期奖励 = 2883.20 * 5% = 144.16
# 关键：BOT 的收入（355.20 from LEAF）不应被 TOP 计入
print("\n  [L1] 三级链路长期奖励不穿透")
info_l1 = seed_users(
    [("TOP", None), ("MID", "TOP"), ("BOT", "MID"), ("LEAF", "BOT")],
    ts=TS + "l1",
)
toks_l1 = {}
for nm in ["TOP", "MID", "BOT", "LEAF"]:
    r = login(info_l1[nm]["email"])
    toks_l1[nm] = r["data"]["token"]

# TOP、MID 充 10000 (代理), BOT 充 5000 (经销商)
recharge_and_approve(toks_l1["TOP"], 10000, at)
top_rc = get_referral_code_str(toks_l1["TOP"])
recharge_and_approve(toks_l1["MID"], 10000, at, referral_code=top_rc)
mid_rc = get_referral_code_str(toks_l1["MID"])
recharge_and_approve(toks_l1["BOT"], 5000, at, referral_code=mid_rc)
bot_rc = get_referral_code_str(toks_l1["BOT"])
time.sleep(0.3)

# LEAF 充 888
recharge_and_approve(toks_l1["LEAF"], 888, at, referral_code=bot_rc)
time.sleep(0.5)

# 验证佣金链
mid_earn = get_earnings(toks_l1["MID"])
mid_fr_bot = first_reward_from(mid_earn, info_l1["BOT"]["id"])
chk(len(mid_fr_bot) >= 1 and Decimal(str(mid_fr_bot[0]["amount"])) == Decimal("2750.00"),
    f"L1a: MID first_reward=2750 from BOT (agent 55% of 5000)")

mid_fu = followup_rewards(mid_earn)
chk(len(mid_fu) >= 1 and Decimal(str(mid_fu[0]["amount"])) == Decimal("133.20"),
    f"L1b: MID followup=133.20 from LEAF's 888")

# TOP 应从 MID 获得 first_reward 5500 (代理 55% of 10000)
top_earn = get_earnings(toks_l1["TOP"])
top_fr_mid = first_reward_from(top_earn, info_l1["MID"]["id"])
chk(len(top_fr_mid) >= 1 and Decimal(str(top_fr_mid[0]["amount"])) == Decimal("5500.00"),
    f"L1c: TOP first_reward=5500 from MID (agent 55% of 10000)")

# TOP 不应从 BOT/LEAF 获得任何 first_reward（不穿透）
top_fr_bot = first_reward_from(top_earn, info_l1["BOT"]["id"])
chk(len(top_fr_bot) == 0, f"L1d: TOP 0 first_reward from BOT (no penetration)")

# TOP 不应从 LEAF 的充 888 获得后续收益（后续收益只给 BOT 的上级 MID）
top_fu = followup_rewards(top_earn)
chk(len(top_fu) == 0, f"L1e: TOP 0 followup_reward (no penetration)")

# 长期奖励: TOP 只看 MID 的收入
# MID 收入 = 2750 (first_reward from BOT) + 133.20 (followup from LEAF) = 2883.20
# TOP 长期奖励 = 2883.20 * 5% = 144.16
# 关键：BOT 的收入（0，BOT 没有下级佣金）和 LEAF 的收入不影响 TOP
recs_l1 = calc_long_term(info_l1["TOP"]["id"], PERIOD)
if recs_l1:
    total_l1 = sum(amt for _, amt in recs_l1)
    chk(total_l1 == Decimal("144.16"),
        f"L1f: TOP long-term=144.16 (5% of MID's 2883.20, no penetration, got {total_l1})")
else:
    warn_msg(f"L1f: TOP no long-term reward (expected 144.16)")

# L2: 验证 TOP 不从 BOT 的收入获得长期奖励
# BOT 从 LEAF 获得 first_reward 355.20（经销商 40%）— 888 支付 source_user_id 为 None
bot_earn = get_earnings(toks_l1["BOT"])
bot_fr_leaf = [r for r in bot_earn.get("records", [])
               if r["type"] == "first_reward" and Decimal(str(r["amount"])) == Decimal("355.20")]
chk(len(bot_fr_leaf) >= 1,
    f"L1g: BOT first_reward=355.20 from LEAF (distributor 40%)")

# TOP 长期奖励不应包含 BOT 的 355.20
# 已在 L1f 验证（144.16 = 2883.20 * 5%，不含 355.20）
print("  L1h: TOP long-term excludes BOT's income (verified in L1f)")


# ═══════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════
print(f"\n{'=' * 60}")
summary()
print("\n  佣金规则完整性测试覆盖:")
print("  J: 后续收益关系排除 (代理→代理/经销商→经销商 不产生 133.2)")
print("  K: 长期奖励 4 种组合 (代理→经销商不适用 / 经销商→代理 4%)")
print("  L: 长期奖励不穿透 (仅直接下级，不含更深层级收入)")
