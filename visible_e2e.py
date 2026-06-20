"""Visible Playwright E2E - the browser WILL pop up for you to watch!"""
import asyncio
import json
import os

from playwright.async_api import async_playwright

from e2e_common import (
    Config, api, make_ts, admin_login, login_as, register_user,
)

MOCK = Config.MOCK_CODE
UI = Config.UI_BASE_URL
TS = make_ts()

print("Getting distributor invite code from API...")
at = admin_login()["token"]

# Find a distributor
users = api("GET", "/api/v1/admin/users?role=distributor&limit=1", t=at)
if not users.get("data"):
    print("No distributor, seeding one...")
    r = login_as(f"e2e_dist_{TS}@test.com")
    dtok = r["data"]["token"]
    agents = api("GET", "/api/v1/admin/users?role=agent&limit=1", t=at)
    if agents.get("data"):
        a_email = agents["data"][0]["email"]
        r = login_as(a_email)
        atok = r["data"]["token"]
        ic = api("POST", "/api/v1/invite-codes", t=atok)["data"]["code"]
        r = register_user(f"e2e_dist_{TS}@test.com", ic)
        dtok = r["data"]["token"]
        rid = api("POST", "/api/v1/recharges", {"amount": 5000}, dtok)["data"]["id"]
        api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)
    bci = api("POST", "/api/v1/invite-codes", t=dtok)["data"]["code"]
else:
    d_email = users["data"][0]["email"]
    r = login_as(d_email)
    dtok = r["data"]["token"]
    bci = api("POST", "/api/v1/invite-codes", t=dtok)["data"]["code"]

print(f"Invite code obtained: {bci[:20]}...")


async def run():
    print("\n=== PLAYWRIGHT VISIBLE MODE ===")
    print("Watch the Chromium window that will open...\n")

    async with async_playwright() as p:
        br = await p.chromium.launch(headless=False, slow_mo=500)
        pg = await br.new_page()
        pg.set_default_timeout(60000)

        test_email = f"visible_e2e_{TS}@test.com"

        print("[1/6] Opening login page...")
        await pg.goto(f"{UI}/login")
        await pg.wait_for_timeout(2000)
        os.makedirs(Config.E2E_OUTPUT_DIR, exist_ok=True)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/v_01_login.png")

        print("[2/6] Switching to Register tab...")
        await pg.click('[data-node-key="register"]')
        await pg.wait_for_timeout(1000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/v_02_register.png")

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
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/v_03_filled.png")

        print("[6/6] Clicking Register...")
        await pg.locator("button[type='submit']:visible").click()
        await pg.wait_for_timeout(4000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/v_04_result.png")

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
print(f"\nDone! Screenshots saved to {Config.E2E_OUTPUT_DIR}/v_*.png")
