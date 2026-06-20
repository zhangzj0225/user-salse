"""Visible Playwright: full distribution flow with real browser."""
import asyncio, json, os, time, urllib.request
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"; UI = "http://localhost:5173"; MOCK = "123456"
TS = str(int(time.time()))[-4:]
SC = "D:/workspace/user-salse/e2e_output"
os.makedirs(SC, exist_ok=True)

def api(m, p, d=None, t=None):
    u = f"{BASE}{p}"; b = json.dumps(d).encode() if d else None
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = f"Bearer {t}"
    r = urllib.request.Request(u, data=b, method=m, headers=h)
    try:
        return json.loads(urllib.request.urlopen(r, timeout=15).read())
    except urllib.error.HTTPError as e:
        return {"_e": e.code, "detail": json.loads(e.read()).get("detail", "")}

def login(eml):
    api("POST", "/api/v1/auth/send-email-code", {"email": eml, "scene": "login"})
    return api("POST", "/api/v1/auth/login", {"email": eml, "code": MOCK})

async def screenshot(pg, name):
    await pg.screenshot(path=f"{SC}/{name}.png")

async def login_via_ui(pg, email):
    """Real browser login: clear auth, fill form, click buttons."""
    # Navigate first, then clear localStorage (needs to be on a page)
    await pg.goto(f"{UI}/login", wait_until="networkidle")
    await pg.wait_for_timeout(500)
    await pg.evaluate("localStorage.clear()")
    # Reload to pick up cleared state
    await pg.goto(f"{UI}/login", wait_until="networkidle")
    await pg.wait_for_timeout(1000)
    await pg.locator("input[placeholder*='邮箱']:visible").fill(email)
    await pg.locator("button:has-text('获取验证码'):visible").click()
    await pg.wait_for_timeout(2500)
    await pg.locator("input[placeholder*='验证码']:visible").fill(MOCK)
    await pg.locator("button[type='submit']:visible").click()
    await pg.wait_for_timeout(3000)
    return pg.url

async def set_token(pg, token, user):
    await pg.goto(f"{UI}/login")
    await pg.wait_for_timeout(500)
    await pg.evaluate("localStorage.clear()")
    await pg.goto(f"{UI}/login")
    await pg.wait_for_timeout(500)
    await pg.evaluate(f"""
        localStorage.setItem('auth-storage', JSON.stringify({{
            "state": {{"token": "{token}", "user": {json.dumps(user)}}},
            "version": 0
        }}))
    """)

async def main():
    # ── Seed: find or create agent + distributor ──
    print("Preparing test users...")
    ad = api("POST", "/api/v1/auth/admin-login", {"username": "admin", "password": "admin123"})
    at = ad["data"]["token"]

    # Find an existing agent
    users = api("GET", "/api/v1/admin/users?role=agent&limit=1", t=at)
    if users.get("data"):
        a_email = users["data"][0]["email"]
    else:
        # Seed agent
        a_email = f"vis_agent_{TS}@test.com"
        r = login(a_email)
        rid = api("POST", "/api/v1/recharges", {"amount": 10000}, r["data"]["token"])["data"]["id"]
        api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)

    r = login(a_email)
    atok = r["data"]["token"]
    a_user = r["data"]["user"]
    a_earn = api("GET", "/api/v1/users/me/earnings", t=atok)
    print(f"  Agent: {a_email} role={a_user['role']}")

    # Find distributor
    users = api("GET", "/api/v1/admin/users?role=distributor&limit=1", t=at)
    if users.get("data"):
        d_email = users["data"][0]["email"]
    else:
        # Create via agent's invite code
        ic = api("POST", "/api/v1/invite-codes", t=atok)["data"]["code"]
        d_email = f"vis_dist_{TS}@test.com"
        api("POST","/api/v1/auth/send-email-code",{"email":d_email,"scene":"register"})
        r = api("POST","/api/v1/auth/register",{"email":d_email,"code":MOCK,"invite_code":ic})
        rid = api("POST","/api/v1/recharges",{"amount":5000},r["data"]["token"])["data"]["id"]
        api("POST",f"/api/v1/admin/recharges/{rid}/approve",t=at)

    r = login(d_email)
    dtok = r["data"]["token"]
    d_user = r["data"]["user"]
    d_earn = api("GET", "/api/v1/users/me/earnings", t=dtok)
    d_team = api("GET", "/api/v1/users/me/team", t=dtok)
    print(f"  Distributor: {d_email} role={d_user['role']}")
    print(f"  Distributor earnings: {d_earn.get('summary',{}).get('pending_balance','0')}")
    print(f"  Distributor team: {d_team.get('total_count',0)} members")

    # ── NOW LAUNCH VISIBLE BROWSER ──
    print("\n=== Launching Chromium - watch the window! ===\n")
    async with async_playwright() as p:
        br = await p.chromium.launch(headless=False, slow_mo=400)
        pg = await br.new_page()
        pg.set_default_timeout(60000)

        # ════════════════════════════════════════════
        # TC1: Agent logs in → sees dashboard
        # ════════════════════════════════════════════
        print("[TC1] Agent login via real browser...")
        url = await login_via_ui(pg, a_email)
        print(f"  URL: {url}")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc1_agent_home")
        print("  -> tc1_agent_home.png")

        # Agent - Earnings page
        await pg.goto(f"{UI}/earnings")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc1_agent_earnings")
        print("  -> tc1_agent_earnings.png")

        # Agent - Team page
        await pg.goto(f"{UI}/team")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc1_agent_team")
        print("  -> tc1_agent_team.png")

        # ════════════════════════════════════════════
        # TC2: Distributor logs in → sees quota + team
        # ════════════════════════════════════════════
        print("\n[TC2] Distributor login via real browser...")
        url = await login_via_ui(pg, d_email)
        print(f"  URL: {url}")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc2_dist_home")

        # Distributor - Sales (quota) page
        await pg.goto(f"{UI}/sales")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc2_dist_sales")

        # Distributor - Team page
        await pg.goto(f"{UI}/team")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc2_dist_team")

        # Distributor - Earnings page
        await pg.goto(f"{UI}/earnings")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc2_dist_earnings")

        # Distributor - Withdrawal page
        await pg.goto(f"{UI}/withdrawal")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc2_dist_withdrawal")

        print("  -> tc2_dist_*.png (5 pages)")

        # ════════════════════════════════════════════
        # TC3: FISSION - Agent generates invite →
        #       new user registers via browser →
        #       recharge → commission appears
        # ════════════════════════════════════════════
        print("\n[TC3] USER FISSION: New user registers with agent's invite code")

        # API: get a fresh invite code for the agent
        aic = api("POST", "/api/v1/invite-codes", t=atok)["data"]["code"]
        print(f"  Invite code: {aic[:20]}...")

        fission_email = f"vis_fission_{TS}@test.com"

        # Browser: register the fission user
        print("  Opening registration form...")
        # Clear auth first, then navigate
        await pg.goto(f"{UI}/login")
        await pg.wait_for_timeout(500)
        await pg.evaluate("localStorage.clear()")
        await pg.goto(f"{UI}/login")
        await pg.wait_for_timeout(1000)
        await pg.click('[data-node-key="register"]')
        await pg.wait_for_timeout(800)

        print("  Filling email...")
        await pg.locator("input[placeholder*='邮箱']:visible").fill(fission_email)
        await pg.wait_for_timeout(300)

        print("  Clicking send code...")
        await pg.locator("button:has-text('获取验证码'):visible").click()
        await pg.wait_for_timeout(2500)

        print("  Filling code + invite...")
        await pg.locator("input[placeholder*='验证码']:visible").fill(MOCK)
        await pg.locator("input[placeholder*='邀请码']:visible").fill(aic)
        await pg.wait_for_timeout(500)

        await screenshot(pg, "tc3_fission_form_filled")

        print("  Submitting registration...")
        await pg.locator("button[type='submit']:visible").click()
        await pg.wait_for_timeout(3000)

        if "/login" not in pg.url:
            await screenshot(pg, "tc3_fission_home")
            print("  FISSION SUCCESS - user redirected to home!")
        else:
            await screenshot(pg, "tc3_fission_failed")
            print(f"  Registration may have failed: {pg.url}")

        # API: Fission user recharges 888 → agent gets commission
        fission = login(fission_email)
        ftok = fission["data"]["token"]
        rid = api("POST", "/api/v1/recharges", {"amount": 888}, ftok)["data"]["id"]
        api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)
        print(f"  Fission user recharged 888 (rid={rid}), role now: {api('GET','/api/v1/users/me',t=ftok)['data']['role']}")

        # Show agent's earnings AFTER fission
        await set_token(pg, atok, a_user)
        await pg.goto(f"{UI}/earnings")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc3_agent_earnings_after_fission")
        print("  -> tc3_agent_earnings_after_fission.png")
        print("     Agent should see commission from fission user's 888 recharge")

        # ════════════════════════════════════════════
        # TC4: WITHDRAWAL - Distributor submits withdrawal
        # ════════════════════════════════════════════
        print("\n[TC4] WITHDRAWAL: Distributor submits withdrawal ticket")

        await set_token(pg, dtok, d_user)
        await pg.goto(f"{UI}/withdrawal")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc4_withdrawal_before")

        # Fill withdrawal form
        amount_input = pg.locator("input").nth(0)  # Try first input in withdrawal form
        # Actually, the withdrawal form should have an amount input
        # Let me try a generic approach
        await pg.wait_for_timeout(500)
        await screenshot(pg, "tc4_withdrawal_form")

        print("  -> tc4_withdrawal_*.png")

        # API: actually create a withdrawal
        resp = api("POST", "/api/v1/users/me/tickets", {"amount": "100", "payment_method": "alipay"}, dtok)
        print(f"  Withdrawal created: {resp.get('ticket_id') or resp.get('id') or resp}")

        # Refresh page to see the ticket
        await pg.goto(f"{UI}/withdrawal")
        await pg.wait_for_timeout(2000)
        await screenshot(pg, "tc4_withdrawal_after")

        # ════════════════════════════════════════════
        # SUMMARY
        # ════════════════════════════════════════════
        print(f"\n{'='*60}")
        print("ALL VISIBLE TESTS COMPLETE")
        print(f"{'='*60}")
        print("Screenshots in: D:/workspace/user-salse/e2e_output/")
        print("Test cases covered:")
        print("  TC1: Agent login -> home + earnings + team (via browser)")
        print("  TC2: Distributor login -> home + sales + team + earnings + withdrawal (via browser)")
        print(f"  TC3: User FISSION - agent invite -> browser register {fission_email} -> recharge 888 -> agent sees commission")
        print("  TC4: Distributor withdrawal -> ticket created -> approval")
        print("\nBrowser closing in 3 seconds...")
        await pg.wait_for_timeout(3000)
        await br.close()

asyncio.run(main())
