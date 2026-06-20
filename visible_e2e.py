"""Visible Playwright E2E - the browser WILL pop up for you to watch!"""
import asyncio, json, os, time, urllib.request
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"
UI = "http://localhost:5173"
MOCK = "123456"
TS = str(int(time.time()))[-4:]

def api(m, p, d=None, t=None):
    u = f"{BASE}{p}"; b = json.dumps(d).encode() if d else None
    h = {"Content-Type": "application/json"}
    if t: h["Authorization"] = f"Bearer {t}"
    r = urllib.request.Request(u, data=b, method=m, headers=h)
    return json.loads(urllib.request.urlopen(r, timeout=15).read())

print("Getting distributor invite code from API...")
ad = api("POST", "/api/v1/auth/admin-login", {"username":"admin","password":"admin123"})
at = ad["data"]["token"]

# Find a distributor
users = api("GET", "/api/v1/admin/users?role=distributor&limit=1", t=at)
if not users.get("data"):
    # No distributor? Seed one quickly
    print("No distributor, seeding one...")
    r = api("POST","/api/v1/auth/send-email-code",{"email":f"e2e_dist_{TS}@test.com","scene":"login"})
    r = api("POST","/api/v1/auth/login",{"email":f"e2e_dist_{TS}@test.com","code":MOCK})
    dtok = r["data"]["token"]
    # Get invite code from agent
    agents = api("GET","/api/v1/admin/users?role=agent&limit=1",t=at)
    if agents.get("data"):
        a_email = agents["data"][0]["email"]
        # Login as agent to get token
        r = api("POST","/api/v1/auth/send-email-code",{"email":a_email,"scene":"login"})
        r = api("POST","/api/v1/auth/login",{"email":a_email,"code":MOCK})
        atok = r["data"]["token"]
        ic = api("POST","/api/v1/invite-codes",t=atok)["data"]["code"]
        # Register distributor
        r = api("POST","/api/v1/auth/send-email-code",{"email":f"e2e_dist_{TS}@test.com","scene":"register"})
        r = api("POST","/api/v1/auth/register",{"email":f"e2e_dist_{TS}@test.com","code":MOCK,"invite_code":ic})
        dtok = r["data"]["token"]
        # Recharge 5000
        rid = api("POST","/api/v1/recharges",{"amount":5000},dtok)["data"]["id"]
        api("POST",f"/api/v1/admin/recharges/{rid}/approve",t=at)
    bci = api("POST","/api/v1/invite-codes",t=dtok)["data"]["code"]
else:
    d_email = users["data"][0]["email"]
    r = api("POST","/api/v1/auth/send-email-code",{"email":d_email,"scene":"login"})
    r = api("POST","/api/v1/auth/login",{"email":d_email,"code":MOCK})
    dtok = r["data"]["token"]
    bci = api("POST","/api/v1/invite-codes",t=dtok)["data"]["code"]

print(f"Invite code obtained: {bci[:20]}...")

async def run():
    print("\n=== PLAYWRIGHT VISIBLE MODE ===")
    print("Watch the Chromium window that will open...\n")
    
    async with async_playwright() as p:
        # HEADLESS=FALSE -> you WILL see the browser!
        br = await p.chromium.launch(headless=False, slow_mo=500)
        pg = await br.new_page()
        pg.set_default_timeout(60000)
        
        test_email = f"visible_e2e_{TS}@test.com"
        
        print("[1/6] Opening login page...")
        await pg.goto(f"{UI}/login")
        await pg.wait_for_timeout(2000)
        os.makedirs("D:/workspace/user-salse/e2e_output", exist_ok=True)
        await pg.screenshot(path="D:/workspace/user-salse/e2e_output/v_01_login.png")
        
        print("[2/6] Switching to Register tab...")
        await pg.click('[data-node-key="register"]')
        await pg.wait_for_timeout(1000)
        await pg.screenshot(path="D:/workspace/user-salse/e2e_output/v_02_register.png")
        
        print("[3/6] Filling email...")
        await pg.locator("input[placeholder*='邮箱']:visible").fill(test_email)
        await pg.wait_for_timeout(500)
        
        print("[4/6] Clicking 'Get Code'...")
        await pg.locator("button:has-text('获取验证码'):visible").click()
        await pg.wait_for_timeout(3000)
        
        print("[5/6] Filling code + invite code...")
        await pg.locator("input[placeholder*='验证码']:visible").fill(MOCK)
        await pg.locator("input[placeholder*='邀请码']:visible").fill(bci)
        await pg.wait_for_timeout(1000)
        await pg.screenshot(path="D:/workspace/user-salse/e2e_output/v_03_filled.png")
        
        print("[6/6] Clicking Register...")
        await pg.locator("button[type='submit']:visible").click()
        await pg.wait_for_timeout(4000)
        await pg.screenshot(path="D:/workspace/user-salse/e2e_output/v_04_result.png")
        
        if "/login" not in pg.url:
            print("\n*** REGISTRATION SUCCESSFUL! ***")
            print(f"    User: {test_email}")
            print(f"    URL: {pg.url}")
        else:
            print(f"\n*** Registration may have failed - URL: {pg.url} ***")
        
        print("\nBrowser will close in 3 seconds...")
        await pg.wait_for_timeout(3000)
        await br.close()

asyncio.run(run())
print("\nDone! Screenshots saved to D:/workspace/user-salse/e2e_output/v_*.png")
