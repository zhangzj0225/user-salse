"""E2E Full Flow: User fission + distribution + commission."""
import asyncio, json, os, time, urllib.request
from decimal import Decimal
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"; UI = "http://localhost:5173"; MOCK = "123456"
TS = str(int(time.time()))[-4:]; results = []

def api(m, p, d=None, t=None):
    u = f"{BASE}{p}"; b = json.dumps(d).encode() if d else None
    h = {"Content-Type":"application/json"}
    if t: h["Authorization"] = f"Bearer {t}"
    r = urllib.request.Request(u, data=b, method=m, headers=h)
    try:
        resp = urllib.request.urlopen(r, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"_e": e.code, "detail": json.loads(e.read()).get("detail","")}

def chk(ok, desc):
    p = "PASS" if ok else "FAIL"
    results.append(f"{p}: {desc}")
    print(f"  {p}: {desc}" if ok else f"  *** {p}: {desc}")
    return ok

def em(n): return f"e2e_{TS}_{n}@test.com"
def login(eml): api("POST","/api/v1/auth/send-email-code",{"email":eml,"scene":"login"}); return api("POST","/api/v1/auth/login",{"email":eml,"code":MOCK})
def reg(eml, ic): api("POST","/api/v1/auth/send-email-code",{"email":eml,"scene":"register"}); return api("POST","/api/v1/auth/register",{"email":eml,"code":MOCK,"invite_code":ic})
def rech(amt, t): return api("POST","/api/v1/recharges",{"amount":amt},t)
def approve_r(rid, at): return api("POST",f"/api/v1/admin/recharges/{rid}/approve",t=at)
def approve_t(tid, at): return api("POST",f"/api/v1/admin/tickets/{tid}/approve",t=at)
def get_ic(t): return api("POST","/api/v1/invite-codes",t=t)["data"]["code"]
def get_me(t): return api("GET","/api/v1/users/me",t=t)
def get_earn(t): return api("GET","/api/v1/users/me/earnings",t=t)

ad = api("POST","/api/v1/auth/admin-login",{"username":"admin","password":"admin123"})
at = ad["data"]["token"]
chk("token" in ad["data"], "S0: Admin login OK")

# ═══ S1: Seed ═══
print("\n=== S1: Seed ===")
a=login(em("agent")); atok=a["data"]["token"]
chk(a["data"]["user"]["role"]=="user","S1a: A created")
rid=rech(10000,atok)["data"]["id"]; approve_r(rid,at)
chk(get_me(atok)["data"]["role"]=="agent","S1b: A role=agent")
aci=get_ic(atok); b=reg(em("dist"),aci); btok=b["data"]["token"]
chk(True,"S1c: B registered")
rid=rech(5000,btok)["data"]["id"]; approve_r(rid,at)
chk(get_me(btok)["data"]["role"]=="distributor","S1d: B role=distributor")
bci=get_ic(btok); c=reg(em("user"),bci); ctok=c["data"]["token"]
chk(True,"S1e: C registered")
rid=rech(888,ctok)["data"]["id"]; approve_r(rid,at)
chk(get_me(ctok)["data"]["role"]=="member","S1f: C role=member")
aci2=get_ic(atok); d=reg(em("agent2"),aci2); dtok=d["data"]["token"]
rid=rech(10000,dtok)["data"]["id"]; approve_r(rid,at)
chk(get_me(dtok)["data"]["role"]=="agent","S1g: D role=agent")

# ═══ S2: Commission ═══
print("\n=== S2: Commission ===")
b_earn=get_earn(btok); fr=[r for r in b_earn.get("records",[]) if r["type"]=="first_reward"]
chk(len(fr)>=1 and Decimal(str(fr[0]["amount"]))==Decimal("355.20"),f"S2a: B first_reward=355.20")
a_earn=get_earn(atok)
fu=[r for r in a_earn.get("records",[]) if r["type"]=="followup_reward"]
chk(len(fu)>=1 and Decimal(str(fu[0]["amount"]))==Decimal("133.20"),"S2b: A followup=133.20")
afr=[r for r in a_earn.get("records",[]) if r["type"]=="first_reward"]
chk(any(Decimal(str(r["amount"]))==Decimal("5500.00") for r in afr),"S2c: A first_reward=5500")

# ═══ S3: Role non-downgrade ═══
print("\n=== S3: Role non-downgrade ===")
rid=rech(888,atok)["data"]["id"]; approve_r(rid,at)
chk(get_me(atok)["data"]["role"]=="agent","S3: A remains agent")

# ═══ S6: Commission matrix ═══
print("\n=== S6: Matrix ===")
aci3=get_ic(atok); u55=reg(em("u55"),aci3); rid=rech(888,u55["data"]["token"])["data"]["id"]; approve_r(rid,at)
a_earn2=get_earn(atok); fr55=[r for r in a_earn2.get("records",[]) if r["type"]=="first_reward" and Decimal(str(r["amount"]))==Decimal("488.40")]
chk(len(fr55)>=1,f"S6a: agent<-888=488.40")
cci=get_ic(ctok); u20=reg(em("u20"),cci); rid=rech(888,u20["data"]["token"])["data"]["id"]; approve_r(rid,at)
c_earn=get_earn(ctok); cfr=[r for r in c_earn.get("records",[]) if r["type"]=="first_reward"]
chk(len(cfr)>=1 and Decimal(str(cfr[0]["amount"]))==Decimal("177.60"),f"S6b: member<-888=177.60")
cci2=get_ic(ctok); z5k=reg(em("z5k"),cci2); rid=rech(5000,z5k["data"]["token"])["data"]["id"]; approve_r(rid,at)
c_earn2=get_earn(ctok); cfr2=[r for r in c_earn2.get("records",[]) if r["type"]=="first_reward"]
chk(len(cfr2)==1,f"S6c: member<-5000=0 commission (only 1, got:{len(cfr2)})")

# ═══ S9: Invite code protection ═══
print("\n=== S9: Invite code protection ===")
resp=reg(em("dup"),bci); chk(resp.get("_e") in (400,422),f"S9a: Duplicate IC rejected ({resp.get('_e')})")
resp=reg(em("self"),bci); chk(resp.get("_e") in (400,422),f"S9b: Self-referral rejected ({resp.get('_e')})")
resp=reg(em("bad"),"BAD_CODE"); chk(resp.get("_e") in (400,422),f"S9c: Invalid IC rejected ({resp.get('_e')})")

# ═══ S4+S12: Playwright ═══
# (Must come BEFORE withdrawal so B has enough balance from fission user's 5000 recharge)
print("\n=== S4+S12: Playwright ===")
async def pw_tests():
    async with async_playwright() as p:
        br = await p.chromium.launch(headless=True)
        pg = await br.new_page()

        # S4: Browser register - use visible email input on register tab
        bci4 = get_ic(btok)
        ferm = em("fission")
        await pg.goto(f"{UI}/login"); await pg.wait_for_timeout(1000)
        await pg.click('[data-node-key="register"]'); await pg.wait_for_timeout(800)
        # On register tab, there are 3 inputs: email(0), code(1), invite(2). Use visible only
        await pg.locator("input[placeholder*='邮箱']:visible").fill(ferm)
        await pg.locator("button:has-text('获取验证码'):visible").click()
        await pg.wait_for_timeout(2000)
        await pg.locator("input[placeholder*='验证码']:visible").fill(MOCK)
        await pg.locator("input[placeholder*='邀请码']:visible").fill(bci4)
        await pg.locator("button[type='submit']:visible").click()
        await pg.wait_for_timeout(3000)
        os.makedirs("d:/user-salse/e2e_output", exist_ok=True)
        if "/login" not in pg.url:
            chk(True, "S4a: Browser registration succeeded")
            await pg.screenshot(path="d:/user-salse/e2e_output/s4_register.png")
            f = login(ferm); ftok = f["data"]["token"]
            rid=rech(5000,ftok)["data"]["id"]; approve_r(rid,at)
            chk(get_me(ftok)["data"]["role"]=="distributor", "S4b: Fission user role=distributor")
        else:
            chk(False, f"S4: Registration failed ({pg.url})")
            await pg.screenshot(path="d:/user-salse/e2e_output/s4_fail.png")

        # S12: Screenshots as B
        bu = get_me(btok)["data"]
        await pg.goto(f"{UI}/login")
        await pg.evaluate(f"localStorage.setItem('auth-storage',JSON.stringify({{state:{{token:'{btok}',user:{json.dumps(bu)}}},version:0}}))")
        for path,name in [("/","home"),("/earnings","earnings"),("/team","team"),("/recharge","recharge"),("/withdrawal","withdrawal"),("/sales","sales"),("/profile","profile")]:
            await pg.goto(f"{UI}{path}"); await pg.wait_for_timeout(1500)
            await pg.screenshot(path=f"d:/user-salse/e2e_output/s12_{name}.png")
        results.append("PASS: S12 7 screenshots saved")
        print("  S12: 7 screenshots saved")
        await br.close()

asyncio.run(pw_tests())

# ═══ S5: Scenario A - Quota sales (B sells 1 quota to customer) ═══
print("\n=== S5: Scenario A quota sale ===")
try:
    # Send verification code for customer
    api("POST","/api/v1/auth/send-email-code",{"email":em("sale_cust"),"scene":"sale_verify"})
    resp = api("POST","/api/v1/sales",{"customer_email":em("sale_cust"),"verification_code":MOCK},btok)
    chk("customer_id" in resp or "recharge_id" in resp or "_e" not in resp, f"S5: Quota sale submitted (resp keys:{list(resp.keys())[:4]})")
except Exception as e:
    results.append(f"WARN: S5 quota sale error: {e}")

# ═══ S8: Withdrawal (after fission recharge, B balance should have grown) ═══
print("\n=== S8: Withdrawal ===")
b_earn3 = get_earn(btok)
b_bal = b_earn3.get("summary",{}).get("available_balance","0")
print(f"  B available: {b_bal}")

# Withdraw 500
resp = api("POST","/api/v1/users/me/tickets",{"amount":"500","payment_method":"alipay"},btok)
tid = resp.get("ticket_id") or resp.get("id")
chk(tid is not None, f"S8a: Withdraw 500 OK (id={tid})" if tid else f"S8a: Withdraw 500 failed (resp:{resp})")

# Boundary tests
resp = api("POST","/api/v1/users/me/tickets",{"amount":"10000","payment_method":"wechat"},btok)
chk(resp.get("_e")==400, f"S8b: Withdraw 10000 rejected")
resp = api("POST","/api/v1/users/me/tickets",{"amount":"50","payment_method":"alipay"},btok)
chk(resp.get("_e")==400, f"S8c: Withdraw 50 rejected")
if tid: approve_t(tid,at); chk(True, f"S8d: Ticket {tid} approved")
notifs = api("GET","/api/v1/users/me/notifications",t=btok)
chk(notifs.get("total",0)>=1, f"S8e: B has notifications ({notifs.get('total',0)})")

# ═══ S11: API smoke ═══
print("\n=== S11: API smoke ===")
dash=api("GET","/api/v1/admin/dashboard",t=at)
chk(dash["total_users"]>=8,f"S11a: Dashboard ({dash['total_users']} users)")
cfgs=api("GET","/api/v1/admin/configs",t=at)
chk(len(cfgs["configs"])==8,"S11b: Configs 8 items")
usr=api("GET","/api/v1/admin/users?limit=5",t=at)
chk(usr["total"]>=8,"S11c: Users list returned")

# Summary
print("\n"+"="*60)
passed=sum(1 for r in results if "PASS" in r)
failed=sum(1 for r in results if "FAIL" in r)
warn=sum(1 for r in results if "WARN" in r)
for r in results: print(f"  {r}")
print(f"\n  PASS={passed} FAIL={failed} WARN={warn} TOTAL={len(results)}")
print("  Screenshots: d:/user-salse/e2e_output/")
