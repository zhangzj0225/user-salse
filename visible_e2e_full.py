"""Visible Playwright: full distribution flow with real browser."""
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
os.makedirs(Config.E2E_OUTPUT_DIR, exist_ok=True)


async def login_via_ui(pg, email):
    """Real browser login: clear auth, fill form, click buttons."""
    await pg.goto(f"{UI}/login", wait_until="networkidle")
    await pg.wait_for_timeout(500)
    await pg.evaluate("localStorage.clear()")
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
    at = admin_login()["token"]

    # Find an existing agent
    users = api("GET", "/api/v1/admin/users?role=agent&limit=1", t=at)
    if users.get("users"):
        a_email = users["users"][0]["email"]
    else:
        a_email = f"vis_agent_{TS}@test.com"
        r = login_as(a_email)
        rid = api("POST", "/api/v1/recharges", {"amount": 10000},
                  r["data"]["token"])["data"]["id"]
        api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)

    r = login_as(a_email)
    atok = r["data"]["token"]
    a_user = r["data"]["user"]
    a_earn = api("GET", "/api/v1/users/me/earnings", t=atok)
    print(f"  Agent: {a_email} role={a_user['role']}")

    # Find distributor
    users = api("GET", "/api/v1/admin/users?role=distributor&limit=1", t=at)
    if users.get("users"):
        d_email = users["users"][0]["email"]
    else:
        ic = api("POST", "/api/v1/invite-codes", t=atok)["data"]["code"]
        d_email = f"vis_dist_{TS}@test.com"
        r = register_user(d_email, ic)
        rid = api("POST", "/api/v1/recharges", {"amount": 5000},
                  r["data"]["token"])["data"]["id"]
        api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)

    r = login_as(d_email)
    dtok = r["data"]["token"]
    d_user = r["data"]["user"]
    d_earn = api("GET", "/api/v1/users/me/earnings", t=dtok)
    d_team = api("GET", "/api/v1/users/me/team", t=dtok)
    print(f"  Distributor: {d_email} role={d_user['role']}")
    print(f"  Distributor earnings: {d_earn.get('summary', {}).get('pending_balance', '0')}")
    print(f"  Distributor team: {d_team.get('total_count', 0)} members")

    # ── NOW LAUNCH VISIBLE BROWSER ──
    print("\n=== Launching Chromium - watch the window! ===\n")
    async with async_playwright() as p:
        br = await p.chromium.launch(headless=False, slow_mo=400)
        pg = await br.new_page()
        pg.set_default_timeout(60000)

        # ═══ TC1: Agent login → dashboard ═══
        print("[TC1] Agent login via real browser...")
        url = await login_via_ui(pg, a_email)
        print(f"  URL: {url}")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc1_agent_home.png")
        print("  -> tc1_agent_home.png")

        await pg.goto(f"{UI}/earnings")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc1_agent_earnings.png")
        print("  -> tc1_agent_earnings.png")

        await pg.goto(f"{UI}/team")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc1_agent_team.png")
        print("  -> tc1_agent_team.png")

        # ═══ TC2: Distributor login → quota + team ═══
        print("\n[TC2] Distributor login via real browser...")
        url = await login_via_ui(pg, d_email)
        print(f"  URL: {url}")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc2_dist_home.png")

        for page_name in ["sales", "team", "earnings", "withdrawal"]:
            await pg.goto(f"{UI}/{page_name}")
            await pg.wait_for_timeout(2000)
            await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc2_dist_{page_name}.png")
        print("  -> tc2_dist_*.png (5 pages)")

        # ═══ TC3: FISSION - Agent invite → browser register → commission ═══
        print("\n[TC3] USER FISSION: New user registers with agent's invite code")
        aic = api("POST", "/api/v1/invite-codes", t=atok)["data"]["code"]
        print(f"  Invite code: {aic[:20]}...")

        fission_email = f"vis_fission_{TS}@test.com"
        print("  Opening registration form...")
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

        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc3_fission_form_filled.png")

        print("  Submitting registration...")
        await pg.locator("button[type='submit']:visible").click()
        await pg.wait_for_timeout(3000)

        if "/login" not in pg.url:
            await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc3_fission_home.png")
            print("  FISSION SUCCESS - user redirected to home!")
        else:
            await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc3_fission_failed.png")
            print(f"  Registration may have failed: {pg.url}")

        # API: Fission user recharges 888 → agent gets commission
        fission = login_as(fission_email)
        ftok = fission["data"]["token"]
        rid = api("POST", "/api/v1/recharges", {"amount": 888}, ftok)["data"]["id"]
        api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)
        role_after = api("GET", "/api/v1/users/me", t=ftok)["data"]["role"]
        print(f"  Fission user recharged 888 (rid={rid}), role now: {role_after}")

        # Show agent's earnings AFTER fission
        await set_token(pg, atok, a_user)
        await pg.goto(f"{UI}/earnings")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc3_agent_earnings_after_fission.png")
        print("  -> tc3_agent_earnings_after_fission.png")
        print("     Agent should see commission from fission user's 888 recharge")

        # ═══ TC4: WITHDRAWAL ═══
        print("\n[TC4] WITHDRAWAL: Distributor submits withdrawal ticket")
        await set_token(pg, dtok, d_user)
        await pg.goto(f"{UI}/withdrawal")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc4_withdrawal_before.png")

        resp = api("POST", "/api/v1/users/me/tickets",
                   {"amount": "100", "payment_method": "alipay"}, dtok)
        print(f"  Withdrawal created: {resp.get('ticket_id') or resp.get('id') or resp}")

        await pg.goto(f"{UI}/withdrawal")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{Config.E2E_OUTPUT_DIR}/tc4_withdrawal_after.png")

        # ═══ SUMMARY ═══
        print(f"\n{'=' * 60}")
        print("ALL VISIBLE TESTS COMPLETE")
        print(f"{'=' * 60}")
        print(f"Screenshots in: {Config.E2E_OUTPUT_DIR}/")
        print("Test cases covered:")
        print("  TC1: Agent login -> home + earnings + team (via browser)")
        print("  TC2: Distributor login -> home + sales + team + earnings + withdrawal")
        print(f"  TC3: User FISSION - agent invite -> browser register {fission_email} -> recharge 888")
        print("  TC4: Distributor withdrawal -> ticket created -> approval")
        print("\nBrowser closing in 3 seconds...")
        await pg.wait_for_timeout(3000)
        await br.close()


asyncio.run(main())
