"""真实邮箱 E2E 测试 — Playwright 操控前端 + QQ 邮箱网页版自动读取验证码。

使用方式:
  1. 确保 QQ 邮箱已开启 SMTP 服务并获取授权码
  2. 确保后端已启动且 AUTH_MODE=email, SMTP 配置正确
  3. 确保前端已启动 (localhost:5173)
  4. 运行: python real_email_e2e.py

脚本流程:
  - Playwright 打开两个标签页：前端 + QQ 邮箱
  - 用户扫码登录 QQ 邮箱（人工交互）
  - 脚本自动在前端触发验证码发送
  - 脚本从 QQ 邮箱读取验证码邮件，提取 6 位数字
  - 自动填入前端表单完成登录/注册
"""
import asyncio
import json
import os
import re
import time

from playwright.async_api import async_playwright

from e2e_common import Config, api, make_ts, admin_login

# ── 配置 ──────────────────────────────────────────────────
REAL_EMAIL = "185215923@qq.com"
SENDER_EMAIL = "info_sys_noreply@163.com"
UI = Config.UI_BASE_URL
MAIL_URL = "https://mail.qq.com"
OUTPUT_DIR = Config.E2E_OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 验证码正则：邮件正文中的 6 位数字
CODE_PATTERN = re.compile(r"(?:验证码[是为：: ]*)(\d{6})", re.IGNORECASE)
CODE_FALLBACK_PATTERN = re.compile(r"\b(\d{6})\b")


# ── 结果收集 ──────────────────────────────────────────────
_results = []

def chk(ok, desc):
    tag = "PASS" if ok else "FAIL"
    _results.append(f"{tag}: {desc}")
    print(f"  {'  ' if ok else '*** '}{tag}: {desc}")

def summary():
    passed = sum(1 for r in _results if r.startswith("PASS"))
    failed = sum(1 for r in _results if r.startswith("FAIL"))
    print(f"\n{'=' * 60}")
    for r in _results:
        print(f"  {r}")
    print(f"\n  PASS={passed} FAIL={failed} TOTAL={len(_results)}")
    return passed, failed


# ── QQ 邮箱操作 ──────────────────────────────────────────

# QQ 邮箱账密登录凭据
QQ_MAIL_USER = os.environ.get("QQ_MAIL_USER", "185215923@qq.com")
QQ_MAIL_PASS = os.environ.get("QQ_MAIL_PASS", "zhang3.14zj")


async def qq_mail_login(mail_page, timeout=120):
    """自动通过账密登录 QQ 邮箱。

    QQ 邮箱登录表单在 iframe[name='ptlogin_iframe'] 中：
    - input[name='u'] — 账号
    - input[name='p'] — 密码
    - input[type='submit'] — 登录按钮
    - input[name='verifycode'] — 验证码（如出现需人工处理）
    """
    print(f"  [邮箱] 开始自动登录 QQ 邮箱: {QQ_MAIL_USER}")
    await mail_page.goto(MAIL_URL, wait_until="domcontentloaded")
    await mail_page.wait_for_timeout(3000)

    # 登录表单在 iframe[name='ptlogin_iframe'] 中
    login_frame = mail_page.frame(name="ptlogin_iframe")
    if not login_frame:
        # 尝试通过 URL 匹配
        for f in mail_page.frames:
            if "ptlogin2" in f.url or "xui.ptlogin" in f.url:
                login_frame = f
                break

    if not login_frame:
        print("  [ERROR] 未找到 ptlogin_iframe，页面结构可能已变化")
        return False

    print("  [邮箱] 找到登录 iframe")

    # 切换到"密码登录"模式（默认是二维码扫码登录）
    try:
        # "密码登录" 是一个文本链接
        switch_clicked = False
        for sel in ["a:has-text('密码登录')", "text=密码登录", "#switcher_plogin"]:
            try:
                elem = login_frame.locator(sel).first
                if await elem.is_visible(timeout=3000):
                    await elem.click()
                    await mail_page.wait_for_timeout(2000)
                    switch_clicked = True
                    print("  [邮箱] 点击'密码登录'切换")
                    break
            except Exception:
                continue
        if not switch_clicked:
            # 尝试 JavaScript 点击
            await login_frame.evaluate("document.querySelector('a:has-text(\"密码登录\")')?.click() || document.querySelectorAll('a').forEach(a => { if(a.textContent.includes('密码登录')) a.click() })")
            await mail_page.wait_for_timeout(2000)
            print("  [邮箱] 通过 JS 点击'密码登录'")
    except Exception as e:
        print(f"  [邮箱] 切换密码登录异常: {e}")

    # 填写账号
    try:
        await login_frame.fill("input[name='u']", QQ_MAIL_USER)
        print(f"  [邮箱] 填入账号: {QQ_MAIL_USER}")
    except Exception as e:
        print(f"  [邮箱] 填写账号失败: {e}")
        return False

    # 填写密码
    try:
        await login_frame.fill("input[name='p']", QQ_MAIL_PASS)
        print("  [邮箱] 填入密码: ******")
    except Exception as e:
        print(f"  [邮箱] 填写密码失败: {e}")
        return False

    await mail_page.wait_for_timeout(500)

    # 点击登录按钮
    try:
        await login_frame.click("input[type='submit']")
        print("  [邮箱] 点击登录按钮")
    except Exception as e:
        print(f"  [邮箱] 点击登录失败: {e}")
        return False

    # 等待登录完成 — 可能需要人工处理验证码
    print(f"  [等待] 等待登录完成（超时 {timeout} 秒）")
    print("  [提示] 如果出现验证码或安全验证，请手动完成")
    start = time.time()
    while time.time() - start < timeout:
        url = mail_page.url
        if "sid=" in url or "frame_html" in url or ("mail.qq.com" in url and "cgi-bin" in url):
            print("  [OK] 检测到 QQ 邮箱登录成功")
            await mail_page.wait_for_timeout(3000)
            return True
        try:
            content = await mail_page.content()
            if "收件箱" in content and ("写信" in content or "通信录" in content or "已收到" in content):
                print("  [OK] 检测到 QQ 邮箱收件箱页面")
                await mail_page.wait_for_timeout(2000)
                return True
        except Exception:
            pass
        await asyncio.sleep(2)
    print("  [TIMEOUT] QQ 邮箱登录超时")
    return False


async def fetch_verification_code(mail_page, timeout=90, known_codes=None):
    """从 QQ 邮箱收件箱轮询读取验证码。

    策略：
    1. 刷新收件箱（点击"收件箱"或刷新按钮）
    2. 查找含"验证码"或"足球舆情"关键词的邮件
    3. 点击打开邮件
    4. 从邮件正文中正则提取 6 位数字验证码
    5. 排除 known_codes 中的旧验证码
    """
    if known_codes is None:
        known_codes = set()
    print(f"  [邮箱] 等待验证码邮件到达（超时 {timeout} 秒，排除旧码: {known_codes}）...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            # 刷新页面（重新加载收件箱）
            await mail_page.reload(wait_until="domcontentloaded")
            await mail_page.wait_for_timeout(2000)

            # 策略 1：直接在主页面查找邮件列表
            code = await _try_find_code_in_page(mail_page, known_codes)
            if code:
                print(f"  [邮箱] 从主页面提取到验证码: {code}")
                return code

            # 策略 2：遍历 iframe 查找
            code = await _try_find_code_in_iframes(mail_page, known_codes)
            if code:
                print(f"  [邮箱] 从 iframe 提取到验证码: {code}")
                return code

        except Exception as e:
            print(f"  [邮箱] 轮询异常: {e}")

        await asyncio.sleep(3)

    print("  [TIMEOUT] 等待验证码邮件超时")
    return None


async def _try_find_code_in_page(page, known_codes=None):
    """在主页面 DOM 中查找验证码邮件并提取验证码。"""
    if known_codes is None:
        known_codes = set()
    try:
        content = await page.content()

        # 先检查页面是否有邮件相关内容
        if "验证码" not in content and "足球舆情" not in content:
            return None

        # 尝试查找邮件链接/标题
        # QQ 邮箱新版邮件列表可能有多种选择器
        selectors = [
            "a:has-text('验证码')",
            "a:has-text('足球舆情')",
            "span:has-text('验证码')",
            "td:has-text('验证码')",
            "[title*='验证码']",
            "[title*='足球舆情']",
        ]

        for sel in selectors:
            try:
                elem = page.locator(sel).first
                if await elem.is_visible(timeout=2000):
                    await elem.click()
                    await page.wait_for_timeout(2000)
                    code = await _extract_code_from_mail_content(page)
                    if code and code not in known_codes:
                        return code
            except Exception:
                continue

        # 尝试直接从页面文本提取（排除旧验证码）
        code = _extract_code_from_text(content)
        if code and code not in known_codes:
            return code
    except Exception:
        return None


async def _try_find_code_in_iframes(page, known_codes=None):
    """遍历 iframe 查找验证码邮件。"""
    if known_codes is None:
        known_codes = set()
    try:
        frames = page.frames
        for frame in frames:
            try:
                content = await frame.content()
                if "验证码" not in content and "足球舆情" not in content:
                    continue

                # 在 iframe 中查找邮件链接
                selectors = [
                    "a:has-text('验证码')",
                    "a:has-text('足球舆情')",
                    "[title*='验证码']",
                    "[title*='足球舆情']",
                ]
                for sel in selectors:
                    try:
                        elem = frame.locator(sel).first
                        if await elem.is_visible(timeout=2000):
                            await elem.click()
                            await page.wait_for_timeout(2000)
                            # 点击后可能在同 iframe 或新 frame 显示内容
                            code = await _extract_code_from_mail_content(frame)
                            if code and code not in known_codes:
                                return code
                            # 也检查所有 frames
                            for f2 in page.frames:
                                code = await _extract_code_from_mail_content(f2)
                                if code and code not in known_codes:
                                    return code
                    except Exception:
                        continue

                # 直接从 iframe 文本提取
                code = _extract_code_from_text(content)
                if code and code not in known_codes:
                    return code
            except Exception:
                continue
    except Exception:
        pass
    return None


async def _extract_code_from_mail_content(context):
    """从邮件内容区域提取 6 位验证码。"""
    try:
        # 尝试多种邮件正文选择器
        body_selectors = [
            ".mail_content",
            ".readmail_content",
            "#mailContent",
            ".qmbox",
            "div[class*='content']",
            "div[class*='body']",
        ]
        for sel in body_selectors:
            try:
                elem = context.locator(sel).first
                if await elem.is_visible(timeout=2000):
                    text = await elem.inner_text()
                    code = _extract_code_from_text(text)
                    if code:
                        return code
            except Exception:
                continue

        # 兜底：从整个上下文文本提取
        text = await context.inner_text("body") if hasattr(context, 'inner_text') else ""
        return _extract_code_from_text(text)
    except Exception:
        return None


def _extract_code_from_text(text):
    """从文本中提取 6 位验证码。"""
    if not text:
        return None
    # 先尝试带上下文的匹配
    m = CODE_PATTERN.search(text)
    if m:
        return m.group(1)
    # 兜底：查找独立的 6 位数字（排除过长数字如时间戳）
    for m in CODE_FALLBACK_PATTERN.finditer(text):
        num = m.group(1)
        # 排除明显不是验证码的数字（如 202606 之类的年月）
        if not num.startswith("2026") and not num.startswith("2025"):
            return num
    return None


# ── 前端操作 ──────────────────────────────────────────────

async def fill_and_send_code(frontend_page, email, scene="login"):
    """在前端填写邮箱并点击获取验证码。"""
    await frontend_page.goto(f"{UI}/login", wait_until="networkidle")
    await frontend_page.wait_for_timeout(500)
    await frontend_page.evaluate("localStorage.clear()")
    await frontend_page.goto(f"{UI}/login", wait_until="networkidle")
    await frontend_page.wait_for_timeout(1000)

    # 如果是注册场景，切换到注册 Tab
    if scene == "register":
        await frontend_page.click('[data-node-key="register"]')
        await frontend_page.wait_for_timeout(800)

    # 填邮箱
    await frontend_page.locator("input[placeholder*='邮箱']:visible").fill(email)
    await frontend_page.wait_for_timeout(300)

    # 点获取验证码
    await frontend_page.locator("button:has-text('获取验证码'):visible").click()
    await frontend_page.wait_for_timeout(1000)


async def fill_code_and_submit(frontend_page, code, scene="login", invite_code=None):
    """在前端填入验证码并提交。"""
    # 填验证码
    await frontend_page.locator("input[placeholder*='验证码']:visible").fill(code)
    await frontend_page.wait_for_timeout(300)

    # 注册场景需填邀请码
    if scene == "register" and invite_code:
        await frontend_page.locator("input[placeholder*='邀请码']:visible").fill(invite_code)
        await frontend_page.wait_for_timeout(300)

    # 截图
    ts = make_ts()
    await frontend_page.screenshot(path=f"{OUTPUT_DIR}/real_{scene}_form_filled.png")

    # 提交
    await frontend_page.locator("button[type='submit']:visible").click()
    await frontend_page.wait_for_timeout(3000)


async def set_token(pg, token, user):
    """直接注入 token 到 localStorage（快速切换用户）。"""
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


# ── 主测试流程 ────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  真实邮箱 E2E 测试")
    print(f"  测试邮箱: {REAL_EMAIL}")
    print(f"  前端地址: {UI}")
    print(f"  收件邮箱: {MAIL_URL}")
    print("=" * 60)

    # 检查后端是否在运行
    try:
        health = api("GET", "/health")
        if health.get("status") != "ok":
            print("  [ERROR] 后端未运行，请先启动后端")
            return
    except Exception:
        print("  [ERROR] 后端未运行，请先启动后端")
        return

    print("  [OK] 后端运行正常")

    # 管理员登录
    at = admin_login()["token"]
    print("  [OK] 管理员登录成功")

    async with async_playwright() as p:
        br = await p.chromium.launch(headless=False, slow_mo=400)

        # ═══ Tab1: 先打开前端登录页 ═══
        pg = await br.new_page()
        pg.set_default_timeout(60000)
        await pg.goto(f"{UI}/login", wait_until="networkidle")
        print("  [OK] 前端标签页已打开")

        # ═══ Tab2: 打开 QQ 邮箱 ═══
        print("\n--- Step 1: 打开 QQ 邮箱 ---")
        mail_page = await br.new_page()
        await mail_page.goto(MAIL_URL, wait_until="domcontentloaded")
        print("  [提示] 浏览器已打开 QQ 邮箱，请扫码登录")

        logged_in = await qq_mail_login(mail_page, timeout=120)
        if not logged_in:
            chk(False, "QQ 邮箱登录失败/超时")
            await br.close()
            summary()
            return
        chk(True, "QQ 邮箱登录成功")

        # ═══ TC1: 真实邮箱登录 ═══
        print("\n--- TC1: 真实邮箱登录 ---")
        print("  [自动] 2 秒后开始登录测试...")
        await asyncio.sleep(2)

        # 切到前端标签页
        await pg.bring_to_front()
        await pg.goto(f"{UI}/login", wait_until="networkidle")
        await pg.wait_for_timeout(500)
        await pg.evaluate("localStorage.clear()")
        await pg.goto(f"{UI}/login", wait_until="networkidle")
        await pg.wait_for_timeout(1000)

        # 填邮箱并点获取验证码
        await pg.locator("input[placeholder*='邮箱']:visible").fill(REAL_EMAIL)
        await pg.wait_for_timeout(300)

        # 发送前先收集 QQ 邮箱中已有的旧验证码（避免提取到旧邮件的码）
        print("  [邮箱] 收集旧验证码...")
        old_codes = set()
        try:
            old_code = await _try_find_code_in_page(mail_page)
            if old_code:
                old_codes.add(old_code)
                print(f"  [邮箱] 已知旧验证码: {old_code}")
            old_code2 = await _try_find_code_in_iframes(mail_page)
            if old_code2 and old_code2 not in old_codes:
                old_codes.add(old_code2)
                print(f"  [邮箱] 已知旧验证码(iframe): {old_code2}")
        except Exception:
            pass
        if not old_codes:
            print("  [邮箱] 未找到旧验证码邮件")

        await pg.locator("button:has-text('获取验证码'):visible").click()
        print("  [前端] 已点击获取验证码，等待邮件...")
        await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc1_code_sent.png")

        # 从 QQ 邮箱读取验证码（排除旧码）
        code = await fetch_verification_code(mail_page, timeout=90, known_codes=old_codes)
        if not code:
            chk(False, "TC1: 从邮箱获取验证码失败")
            await br.close()
            summary()
            return
        chk(True, f"TC1a: 从邮箱获取验证码: {code}")

        # 切回前端标签页，填入验证码并提交
        await pg.bring_to_front()
        await pg.locator("input[placeholder*='验证码']:visible").fill(code)
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc1_form_filled.png")
        await pg.locator("button[type='submit']:visible").click()
        await pg.wait_for_timeout(3000)

        # 验证登录成功
        if "/login" not in pg.url:
            chk(True, f"TC1b: 登录成功，跳转到 {pg.url}")
            await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc1_home.png")
        else:
            chk(False, f"TC1b: 登录失败，仍在登录页")

        # ═══ TC2: 浏览收益/团队页 ═══
        print("\n--- TC2: 浏览收益/团队页 ---")
        try:
            await pg.goto(f"{UI}/earnings", wait_until="networkidle")
            await pg.wait_for_timeout(2000)
            await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc2_earnings.png")
            chk(True, "TC2a: 收益页加载成功")
        except Exception as e:
            chk(False, f"TC2a: 收益页加载失败: {e}")

        try:
            await pg.goto(f"{UI}/team", wait_until="networkidle")
            await pg.wait_for_timeout(2000)
            await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc2_team.png")
            chk(True, "TC2b: 团队页加载成功")
        except Exception as e:
            chk(False, f"TC2b: 团队页加载失败: {e}")

        # ═══ TC3: 充值 + 管理员审核 ═══
        print("\n--- TC3: 充值 + 管理员审核 ---")
        print("  [自动] 2 秒后开始充值测试...")
        await asyncio.sleep(2)

        # 获取当前用户 token（从 localStorage）
        try:
            auth_data = await pg.evaluate("""
                () => {
                    const raw = localStorage.getItem('auth-storage');
                    if (raw) return JSON.parse(raw);
                    return null;
                }
            """)
            user_token = auth_data["state"]["token"] if auth_data else None
            user_info = auth_data["state"]["user"] if auth_data else None
        except Exception:
            user_token = None
            user_info = None

        if user_token:
            # 提交充值
            resp = api("POST", "/api/v1/recharges", {"amount": 888}, user_token)
            if resp.get("data"):
                rid = resp["data"]["id"]
                chk(True, f"TC3a: 充值申请提交成功 (id={rid})")

                # 管理员审核
                api("POST", f"/api/v1/admin/recharges/{rid}/approve", t=at)
                role = api("GET", "/api/v1/users/me", t=user_token)["data"]["role"]
                chk(role == "member", f"TC3b: 充值审核通过，角色={role}")

                # 刷新前端
                await pg.goto(f"{UI}/", wait_until="networkidle")
                await pg.wait_for_timeout(2000)
                await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc3_after_recharge.png")
            else:
                chk(False, f"TC3a: 充值申请失败: {resp}")
        else:
            chk(False, "TC3: 无法获取用户 token")

        # ═══ TC4: 真实邮箱注册（如果用户已有账号则跳过） ═══
        print("\n--- TC4: 真实邮箱注册测试 ---")
        print("  [提示] 此测试需要一个新的邮箱地址")
        print(f"  [提示] 当前测试邮箱 {REAL_EMAIL} 可能已注册")
        do_register = os.environ.get("E2E_DO_REGISTER", "n").strip().lower()

        if do_register == "y":
            # 需要一个邀请码
            # 先用管理员找一个已有代理
            users = api("GET", "/api/v1/admin/users?role=agent&limit=1", t=at)
            if users.get("users"):
                agent_email = users["users"][0]["email"]
                agent_login = api("POST", "/api/v1/auth/send-email-code",
                                  {"email": agent_email, "scene": "login"})
                # mock 模式下直接登录获取 token
                agent_resp = api("POST", "/api/v1/auth/login",
                                 {"email": agent_email, "code": "123456"})
                if agent_resp.get("data"):
                    agent_token = agent_resp["data"]["token"]
                    ic_resp = api("POST", "/api/v1/invite-codes", t=agent_token)
                    if ic_resp.get("data"):
                        invite_code = ic_resp["data"]["code"]
                        print(f"  [OK] 获取邀请码: {invite_code[:20]}...")

                        # 在前端注册
                        await fill_and_send_code(pg, REAL_EMAIL, scene="register")
                        # 填邀请码（在发送验证码之后）
                        await pg.locator("input[placeholder*='邀请码']:visible").fill(invite_code)
                        await pg.wait_for_timeout(500)

                        # 等待验证码邮件
                        code2 = await fetch_verification_code(mail_page, timeout=90)
                        if code2:
                            chk(True, f"TC4a: 注册验证码获取: {code2}")
                            await fill_code_and_submit(pg, code2, scene="register")

                            if "/login" not in pg.url:
                                chk(True, "TC4b: 注册成功")
                                await pg.screenshot(path=f"{OUTPUT_DIR}/real_tc4_registered.png")
                            else:
                                chk(False, "TC4b: 注册失败（邮箱可能已注册）")
                        else:
                            chk(False, "TC4a: 注册验证码获取失败")
                    else:
                        print("  [SKIP] 无法生成邀请码")
                else:
                    print("  [SKIP] 代理登录失败，无法生成邀请码")
            else:
                print("  [SKIP] 系统中无代理用户")
        else:
            print("  [SKIP] 跳过注册测试")

        # ═══ 总结 ═══
        print(f"\n{'=' * 60}")
        print("  测试完成，浏览器将在 5 秒后关闭...")
        print(f"  截图保存: {OUTPUT_DIR}/")
        await pg.wait_for_timeout(5000)
        await br.close()

    summary()
    print("\n  真实邮箱 E2E 测试覆盖:")
    print("  TC1: 真实邮箱登录（QQ 邮箱验证码自动读取）")
    print("  TC2: 登录后浏览收益/团队页")
    print("  TC3: 充值 + 管理员审核")
    print("  TC4: 真实邮箱注册（可选）")


if __name__ == "__main__":
    asyncio.run(main())
