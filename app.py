#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HidenCloud 自动续期脚本
基于 SeleniumBase UC 模式，绕过 Cloudflare Turnstile 验证。
移植自 katabump-renew 的成功方案。
"""

import os
import time
import random
import subprocess
import json
import re
import requests
from seleniumbase import SB

# ==========================================
# 配置
# ==========================================
BASE_URL = "https://dash.hidencloud.com"
RENEW_DAYS = 10

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")

# ==========================================
# Telegram 通知
# ==========================================
def send_tg(status_icon, status_text, details=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    text = f"☁️ HidenCloud 续期通知\n\n{status_icon} {status_text}\n{details}\n\n时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"⚠️ TG 通知发送失败: {e}")


# ==========================================
# 人类行为模拟
# ==========================================
def human_type(sb, selector, text):
    """逐字符输入，模拟真人打字"""
    try:
        el = sb.find_element(selector, timeout=10)
        el.click()
        time.sleep(0.3 + random.random() * 0.4)
        el.send_keys("\b" * 50)  # 清空
        time.sleep(0.2)
        for char in text:
            el.send_keys(char)
            time.sleep(0.05 + random.random() * 0.15)
        time.sleep(0.3 + random.random() * 0.5)
    except Exception as e:
        print(f"  ⚠️ human_type 失败: {e}")
        # 回退到 JS 填充
        safe = text.replace('\\', '\\\\').replace('"', '\\"')
        sb.execute_script(f"""
            var el = document.querySelector('{selector}');
            if (el) {{
                var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                if (setter) setter.call(el, "{safe}"); else el.value = "{safe}";
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
            }}
        """)


def human_mouse_move(sb, steps=5):
    """随机移动鼠标"""
    try:
        for _ in range(steps):
            x = random.randint(200, 1000)
            y = random.randint(200, 600)
            sb.execute_script(f"""
                var evt = new MouseEvent('mousemove', {{
                    bubbles: true, cancelable: true,
                    clientX: {x}, clientY: {y}
                }});
                document.dispatchEvent(evt);
            """)
            time.sleep(0.2 + random.random() * 0.5)
    except Exception:
        pass


def human_scroll(sb):
    """随机滚动页面"""
    try:
        for _ in range(2):
            sb.execute_script(f"window.scrollBy(0, {random.randint(100, 300)});")
            time.sleep(0.5 + random.random())
        sb.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.3)
    except Exception:
        pass


# ==========================================
# Turnstile 处理 (复用 katabump-renew 的方案)
# ==========================================
_SOLVED_JS = """
(function(){
    var i = document.querySelector('input[name="cf-turnstile-response"]');
    return !!(i && i.value && i.value.length > 20);
})()
"""

_EXISTS_JS = """
(function(){
    return document.querySelector('input[name="cf-turnstile-response"]') !== null;
})()
"""

_EXPAND_JS = """
(function() {
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    if (!ts) return 'no-turnstile';
    var el = ts;
    for (var i = 0; i < 20; i++) {
        el = el.parentElement;
        if (!el) break;
        var s = window.getComputedStyle(el);
        if (s.overflow === 'hidden' || s.overflowX === 'hidden' || s.overflowY === 'hidden')
            el.style.overflow = 'visible';
        el.style.minWidth = 'max-content';
    }
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.minWidth = '300px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    return 'done';
})()
"""

_DIAG_JS = """
(function(){
    var iframes = document.querySelectorAll('iframe');
    var result = [];
    for (var i = 0; i < iframes.length; i++) {
        var r = iframes[i].getBoundingClientRect();
        result.push({
            idx: i,
            src: iframes[i].src ? iframes[i].src.substring(0, 100) : '(empty)',
            w: Math.round(r.width),
            h: Math.round(r.height),
            visible: r.width > 0 && r.height > 0
        });
    }
    var ts = document.querySelector('input[name="cf-turnstile-response"]');
    return {
        iframeCount: iframes.length,
        iframes: result,
        hasTurnstileInput: !!ts,
        turnstileValue: ts ? ts.value.substring(0, 30) : ''
    };
})()
"""


def _activate_window():
    """激活 Chrome 窗口"""
    for cls in ["chrome", "chromium", "Chrome", "google-chrome"]:
        try:
            r = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", cls],
                               capture_output=True, text=True, timeout=3)
            wids = [w for w in r.stdout.strip().split("\n") if w.strip()]
            if wids:
                subprocess.run(["xdotool", "windowactivate", wids[0]],
                               timeout=3, stderr=subprocess.DEVNULL)
                time.sleep(0.2)
                return
        except Exception:
            pass


def _xdotool_click(x, y):
    """用 xdotool 发送真实 X11 点击事件 (isTrusted=true)"""
    _activate_window()
    time.sleep(0.2)
    try:
        subprocess.run(["xdotool", "mousemove", str(x), str(y)],
                       timeout=3, stderr=subprocess.DEVNULL)
        time.sleep(0.2 + random.random() * 0.3)
        subprocess.run(["xdotool", "click", "1"],
                       timeout=3, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        try:
            os.system(f"xdotool mousemove {x} {y} click 1 2>/dev/null")
            return True
        except Exception:
            return False


def handle_turnstile(sb) -> bool:
    """处理 Cloudflare Turnstile 验证"""
    print("🔍 处理 Cloudflare Turnstile 验证...")
    time.sleep(2)

    # 检查是否已静默通过
    if sb.execute_script(_SOLVED_JS):
        print("✅ 已静默通过")
        return True

    # 展开 Turnstile
    for _ in range(3):
        try:
            sb.execute_script(_EXPAND_JS)
        except Exception:
            pass
        time.sleep(0.5)

    # 检测 Turnstile 模式
    is_invisible = False
    try:
        diag = sb.execute_script(_DIAG_JS)
        if diag and diag.get('iframeCount', 0) > 0:
            f = diag['iframes'][0]
            if f['w'] <= 5 and f['h'] <= 5:
                is_invisible = True
                print(f"  📊 检测到 invisible/managed Turnstile (iframe {f['w']}x{f['h']})")
                print("  ⏳ invisible 模式：等待 Cloudflare 自动验证，不主动点击...")
    except Exception:
        pass

    # 阶段 1: 等待自动验证 (20 秒)
    if is_invisible:
        for wait_sec in range(20):
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 自动通过（等待 {wait_sec + 1}s）")
                return True
            time.sleep(1)
        print("⚠️ 等待 20s 未自动通过")

    # 阶段 2: uc_gui_click_captcha (3 次)
    print("\n🖱️ 尝试 uc_gui_click_captcha (3 次)...")
    for attempt in range(3):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 通过（uc_gui 第 {attempt} 次尝试）")
            return True
        print(f"🖱️ 第 {attempt + 1} 次调用 uc_gui_click_captcha...")
        try:
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f"⚠️ uc_gui_click_captcha 调用异常: {e}")
        for _ in range(16):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 通过（uc_gui 第 {attempt + 1} 次尝试）")
                return True
        print(f"⚠️ uc_gui 第 {attempt + 1} 次未通过，重试...")

    # 阶段 3: xdotool 手动点击 (仅对交互式有效)
    is_interactive = False
    try:
        diag = sb.execute_script(_DIAG_JS)
        if diag and diag.get('iframeCount', 0) > 0:
            f = diag['iframes'][0]
            if f['w'] > 100 and f['h'] > 30:
                is_interactive = True
    except Exception:
        pass

    if is_interactive:
        print("\n🖱️ 切换到 xdotool 手动点击...")
        for attempt in range(3):
            if sb.execute_script(_SOLVED_JS):
                print(f"✅ Turnstile 通过（xdotool 第 {attempt} 次尝试）")
                return True
            try:
                sb.execute_script(_EXPAND_JS)
            except Exception:
                pass
            time.sleep(0.5)

            # 获取 iframe 坐标
            coords = sb.execute_script("""
                (function(){
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        if (iframes[i].src && iframes[i].src.indexOf('challenges.cloudflare.com') !== -1) {
                            var r = iframes[i].getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {
                                return {
                                    x: Math.round(r.x + 30),
                                    y: Math.round(r.y + r.height / 2),
                                    screenX: window.screenX || 0,
                                    screenY: window.screenY || 0,
                                    outerHeight: window.outerHeight || 0,
                                    innerHeight: window.innerHeight || 0
                                };
                            }
                        }
                    }
                    return null;
                })()
            """)
            if coords:
                bar = coords.get("outerHeight", 0) - coords.get("innerHeight", 0)
                if bar < 0: bar = 0
                abs_x = coords["x"] + coords.get("screenX", 0)
                abs_y = coords["y"] + coords.get("screenY", 0) + bar
                print(f"  📍 点击坐标: ({abs_x}, {abs_y})")
                _xdotool_click(abs_x, abs_y)

            for _ in range(16):
                time.sleep(0.5)
                if sb.execute_script(_SOLVED_JS):
                    print(f"✅ Turnstile 通过（xdotool 第 {attempt + 1} 次尝试）")
                    return True
            print(f"⚠️ xdotool 第 {attempt + 1} 次未通过，重试...")

    # 阶段 4: 最后等待 10 秒
    print("\n⏳ 最后等待 10 秒...")
    for wait_sec in range(10):
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 延迟通过（{wait_sec + 1}s）")
            return True
        time.sleep(1)

    print("  ❌ Turnstile 所有尝试均失败")
    return False


# ==========================================
# 登录
# ==========================================
def login(sb, email, password) -> bool:
    print(f"🌐 打开登录页面: {BASE_URL}/auth/login")
    sb.uc_open_with_reconnect(BASE_URL + "/auth/login", reconnect_time=8)
    time.sleep(4)

    # === 阶段 0: 处理 Cloudflare Challenge 页面 ("Just a moment...") ===
    # HidenCloud 登录页可能先显示 Cloudflare 验证页面，需要先过这关
    print("⏳ 检查 Cloudflare Challenge 页面...")
    for i in range(3):
        try:
            page_src = sb.get_page_source() or ""
            page_title = sb.get_title() or ""
            # 检测 Cloudflare Challenge 页面
            if 'Just a moment' in page_title or 'Just a moment' in page_src or 'challenge-platform' in page_src:
                print(f"  🔍 检测到 Cloudflare Challenge 页面，尝试 uc_gui_click_captcha (第 {i+1} 次)...")
                try:
                    sb.uc_gui_click_captcha()
                except Exception as e:
                    print(f"  ⚠️ uc_gui_click_captcha 异常: {e}")
                time.sleep(5)
                # 检查是否通过
                page_src = sb.get_page_source() or ""
                page_title = sb.get_title() or ""
                if 'Just a moment' not in page_title and 'Just a moment' not in page_src:
                    print(f"  ✅ Cloudflare Challenge 已通过")
                    break
            else:
                print(f"  ✅ 未检测到 Cloudflare Challenge 页面")
                break
        except Exception as e:
            print(f"  ⚠️ 检查异常: {e}")
        time.sleep(2)

    # === 阶段 1: 等待登录表单或 Turnstile 出现 ===
    print("⏳ 等待登录表单...")
    form_found = False
    for i in range(30):
        try:
            page_src = sb.get_page_source() or ""
            if 'Email or Username' in page_src or 'name="email"' in page_src.lower() or 'name="username"' in page_src.lower() or 'input[type="email"]' in page_src:
                form_found = True
                print(f"✅ 登录表单已出现（{i+1}s）")
                break
            # 检查是否有 Turnstile
            if sb.execute_script(_EXISTS_JS):
                print(f"🔍 检测到 Turnstile（{i+1}s），先处理 Turnstile...")
                if handle_turnstile(sb):
                    print("✅ Turnstile 处理完成，继续等待表单...")
                    time.sleep(2)
                    continue
        except Exception:
            pass
        time.sleep(1)

    if not form_found:
        print("⚠️ 登录表单未出现，尝试最后一次 Turnstile 处理...")
        if sb.execute_script(_EXISTS_JS):
            if not handle_turnstile(sb):
                print("❌ Turnstile 验证失败")
                sb.save_screenshot("login_turnstile_fail.png")
                return False
        try:
            sb.wait_for_element('input[name="email"], input[name="username"], input[type="email"]', timeout=10)
            form_found = True
        except Exception:
            print("❌ 页面未加载出登录表单")
            sb.save_screenshot("login_no_form.png")
            # 诊断页面状态
            try:
                page_title = sb.get_title() or ""
                cur_url = sb.get_current_url()
                print(f"  诊断: URL={cur_url}, Title={page_title}")
                page_src = sb.get_page_source() or ""
                if 'Just a moment' in page_src:
                    print("  诊断: 页面仍是 Cloudflare Challenge")
                if 'challenge' in page_src.lower():
                    print("  诊断: 页面包含 challenge 关键词")
            except Exception:
                pass
            return False

    # 模拟人类行为
    print("🖱️ 模拟人类浏览行为...")
    human_mouse_move(sb, steps=4)
    human_scroll(sb)
    human_mouse_move(sb, steps=3)
    time.sleep(1 + random.random() * 2)

    # 填写邮箱
    print("📧 填写邮箱 (逐字符输入)...")
    try:
        # 尝试多种选择器
        for sel in ['input[name="email"]', 'input[name="username"]', 'input[placeholder*="Email"]', 'input[placeholder*="email"]']:
            try:
                if sb.find_element(sel, timeout=2):
                    human_type(sb, sel, email)
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"⚠️ 填写邮箱失败: {e}")
        return False

    time.sleep(0.5 + random.random())

    # 填写密码
    print("🔑 填写密码 (逐字符输入)...")
    try:
        for sel in ['input[name="password"]', 'input[type="password"]']:
            try:
                if sb.find_element(sel, timeout=2):
                    human_type(sb, sel, password)
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"⚠️ 填写密码失败: {e}")
        return False

    time.sleep(1 + random.random() * 1.5)
    human_mouse_move(sb, steps=2)
    time.sleep(0.5 + random.random())

    # 处理可能的 Turnstile
    if sb.execute_script(_EXISTS_JS):
        print("🔍 检测到 Turnstile，处理验证...")
        if not handle_turnstile(sb):
            print("⚠️ Turnstile 未通过，仍尝试登录...")

    # 提交登录
    print("🖱️ 提交登录...")
    try:
        # 尝试多种提交方式
        submitted = False
        for sel in ['button[type="submit"]', 'button:has-text("Sign in")', 'button:has-text("Login")', 'button:has-text("登录")']:
            try:
                btn = sb.find_element(sel, timeout=3)
                if btn:
                    btn.click()
                    submitted = True
                    print(f"  已点击: {sel}")
                    break
            except Exception:
                continue
        if not submitted:
            # 回车提交
            sb.press_keys('input[name="password"]', '\n')
            print("  已按回车提交")
    except Exception as e:
        print(f"⚠️ 提交登录失败: {e}")
        return False

    # 等待跳转
    print("⏳ 等待登录跳转...")
    for _ in range(20):
        time.sleep(1)
        try:
            cur_url = sb.get_current_url().lower()
            if "/auth/login" not in cur_url and "hidencloud.com" in cur_url and "error" not in cur_url:
                print(f"✅ 登录成功！(URL: {sb.get_current_url()})")
                return True
        except Exception:
            pass

    # 检查错误
    try:
        cur_url = sb.get_current_url()
        page_title = sb.get_title() or ""
        print(f"❌ 登录失败 (URL: {cur_url}, Title: {page_title})")
        sb.save_screenshot("login_failed.png")
    except Exception:
        pass
    return False


# ==========================================
# 续期逻辑 (通过浏览器 fetch 调用 API)
# ==========================================
def renew_via_browser(sb, email):
    """登录后通过浏览器 fetch 调用 HidenCloud API 完成续期"""
    print("\n" + "#" * 50)
    print("  开始续期流程")
    print("#" * 50)

    # 验证登录状态
    print("🔍 验证 API 登录状态...")
    try:
        result = sb.execute_script("""
            (async function() {
                try {
                    const res = await fetch('/dashboard', { redirect: 'follow' });
                    const text = await res.text();
                    return { status: res.status, url: res.url, data: text };
                } catch(e) { return { error: e.message }; }
            })()
        """)
        if not result or result.get('error'):
            print(f"❌ API 请求失败: {result.get('error') if result else '无响应'}")
            return False

        if '/login' in result.get('url', '') or '/auth' in result.get('url', ''):
            print("❌ 浏览器未保持登录状态")
            return False

        html = result.get('data', '')
        if 'Just a moment' in html or 'Attention Required' in html:
            print("⚠️ 检测到 Cloudflare 拦截页面")
            return False

        # 提取 CSRF Token
        import re
        csrf_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
        csrf_token = csrf_match.group(1) if csrf_match else ''
        if csrf_token:
            print(f"✅ 获取 CSRF Token: {csrf_token[:20]}...")

        # 解析服务列表
        services = []
        for match in re.finditer(r'/service/(\d+)/manage', html):
            svc_id = match.group(1)
            if svc_id not in [s['id'] for s in services]:
                services.append({'id': svc_id, 'url': f'/service/{svc_id}/manage'})

        print(f"✅ 发现 {len(services)} 个服务")
        if not services:
            print("⚠️ 未发现服务，可能没有可续期的服务器")
            return True  # 不算失败

    except Exception as e:
        print(f"❌ 初始化异常: {e}")
        return False

    # 处理每个服务
    success_count = 0
    for svc in services:
        print(f"\n>>> 处理服务 ID: {svc['id']}")
        time.sleep(2 + random.random() * 2)

        try:
            # 获取 manage 页面 + form token
            manage_result = sb.execute_script(f"""
                (async function() {{
                    try {{
                        const res = await fetch('/service/{svc['id']}/manage', {{ redirect: 'follow' }});
                        const text = await res.text();
                        return {{ status: res.status, data: text }};
                    }} catch(e) {{ return {{ error: e.message }}; }}
                }})()
            """)

            if not manage_result or manage_result.get('error'):
                print(f"  ❌ 获取服务页面失败: {manage_result.get('error') if manage_result else '无响应'}")
                continue

            manage_html = manage_result.get('data', '')
            token_match = re.search(r'<input[^>]*name="_token"[^>]*value="([^"]+)"', manage_html)
            form_token = token_match.group(1) if token_match else ''
            if not form_token:
                print(f"  ⚠️ 未找到 _token，尝试继续...")

            # 提交续期
            print(f"  📅 提交续期 ({RENEW_DAYS}天)...")
            time.sleep(1 + random.random())

            renew_result = sb.execute_script(f"""
                (async function() {{
                    try {{
                        const params = new URLSearchParams();
                        params.append('_token', '{form_token}');
                        params.append('days', '{RENEW_DAYS}');
                        const res = await fetch('/service/{svc['id']}/renew', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                            body: params.toString(),
                            redirect: 'follow'
                        }});
                        const text = await res.text();
                        return {{ status: res.status, url: res.url, data: text }};
                    }} catch(e) {{ return {{ error: e.message }}; }}
                }})()
            """)

            if not renew_result or renew_result.get('error'):
                print(f"  ❌ 续期请求失败: {renew_result.get('error') if renew_result else '无响应'}")
                continue

            final_url = renew_result.get('url', '')
            renew_html = renew_result.get('data', '')

            if '/invoice/' in final_url:
                print(f"  ⚡️ 续期成功，前往支付")
                if pay_invoice(sb, renew_html, final_url, csrf_token):
                    success_count += 1
                    print(f"  ✅ 服务 {svc['id']} 续期+支付完成")
                else:
                    print(f"  ⚠️ 续期成功但支付失败")
                    success_count += 1  # 续期本身成功了
            else:
                print(f"  ⚠️ 续期后未跳转账单，检查未支付账单...")
                if check_and_pay_invoices(sb, svc['id'], csrf_token):
                    success_count += 1

        except Exception as e:
            print(f"  ❌ 处理服务异常: {e}")

    print(f"\n📊 续期结果: {success_count}/{len(services)} 个服务成功")
    if success_count > 0:
        send_tg("✅", "续期成功", f"账号: {email[:4]}****\n成功: {success_count}/{len(services)} 个服务")
    else:
        send_tg("❌", "续期失败", f"账号: {email[:4]}****\n0 个服务成功")
    return success_count > 0


def pay_invoice(sb, html, current_url, csrf_token):
    """从 HTML 提取支付表单并提交"""
    try:
        # 找支付表单
        forms = re.findall(r'<form[^>]*action="([^"]+)"[^>]*>(.*?)</form>', html, re.DOTALL)
        target_action = None
        target_inputs = []
        for action, form_html in forms:
            if 'pay' in form_html.lower() and 'balance/add' not in action:
                target_action = action
                # 提取所有 input
                target_inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*(?:value="([^"]*)")?', form_html)
                break

        if not target_action:
            print("  ⚪ 页面未找到支付表单 (可能已支付)")
            return True

        # 构造支付参数
        params = []
        for name, value in target_inputs:
            params.append(f"{name}={value or ''}")
        params_str = "&".join(params)

        print("  💳 提交支付...")
        pay_result = sb.execute_script(f"""
            (async function() {{
                try {{
                    const res = await fetch('{target_action}', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                        body: "{params_str.replace('"', '\\"')}",
                        redirect: 'follow'
                    }});
                    return {{ status: res.status, url: res.url }};
                }} catch(e) {{ return {{ error: e.message }}; }}
            }})()
        """)

        if pay_result and pay_result.get('status') == 200:
            print("  ✅ 支付成功！")
            return True
        else:
            print(f"  ⚠️ 支付响应: {pay_result.get('status') if pay_result else '无响应'}")
            return False
    except Exception as e:
        print(f"  ❌ 支付异常: {e}")
        return False


def check_and_pay_invoices(sb, service_id, csrf_token):
    """检查并支付未付账单"""
    try:
        result = sb.execute_script(f"""
            (async function() {{
                try {{
                    const res = await fetch('/service/{service_id}/invoices?where=unpaid', {{ redirect: 'follow' }});
                    const text = await res.text();
                    return {{ status: res.status, data: text }};
                }} catch(e) {{ return {{ error: e.message }}; }}
            }})()
        """)

        if not result or result.get('error'):
            return False

        html = result.get('data', '')
        invoice_urls = list(set(re.findall(r'/invoice/\d+', html)))

        if not invoice_urls:
            print("  ✅ 无未支付账单")
            return True

        for url in invoice_urls:
            full_url = url if url.startswith('http') else f"{BASE_URL}{url}"
            print(f"  📄 处理账单: {url}")
            inv_result = sb.execute_script(f"""
                (async function() {{
                    try {{
                        const res = await fetch('{url}', {{ redirect: 'follow' }});
                        const text = await res.text();
                        return {{ status: res.status, url: res.url, data: text }};
                    }} catch(e) {{ return {{ error: e.message }}; }}
                }})()
            """)
            if inv_result and inv_result.get('data'):
                pay_invoice(sb, inv_result['data'], inv_result.get('url', ''), csrf_token)
            time.sleep(3 + random.random() * 2)

        return True
    except Exception as e:
        print(f"  ❌ 检查账单失败: {e}")
        return False


# ==========================================
# 主流程
# ==========================================
def get_accounts():
    """从 USERS_JSON 读取账号列表"""
    users_json = os.environ.get("USERS_JSON", "").strip()
    if not users_json:
        return []
    try:
        data = json.loads(users_json)
        if isinstance(data, list):
            return [(u.get("username", ""), u.get("password", "")) for u in data if u.get("username") and u.get("password")]
        elif isinstance(data, dict) and "users" in data:
            return [(u.get("username", ""), u.get("password", "")) for u in data["users"] if u.get("username") and u.get("password")]
    except Exception as e:
        print(f"⚠️ 解析 USERS_JSON 失败: {e}")
    return []


def process_account(email, password, sb_kwargs):
    """处理单个账号"""
    # 邮箱脱敏
    if '@' in email:
        name, domain = email.split('@', 1)
        masked = f"{name[:2]}****@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked = email[:4] + '****'

    print(f"\n{'=' * 50}")
    print(f"  处理账号: {masked}")
    print(f"{'=' * 50}")

    with SB(**sb_kwargs) as sb:
        try:
            # 显示出口 IP
            try:
                sb.open("https://api.ip.sb/ip")
                print(f"📍  当前出口IP: {sb.get_text('body')}")
            except Exception:
                pass

            if login(sb, email, password):
                renew_via_browser(sb, email)
            else:
                print("❌ 登录失败，终止续期")
                send_tg("❌", "登录失败", f"账号: {masked}")
        except Exception as e:
            print(f"❌ 账号处理异常: {e}")
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass
            send_tg("❌", "处理异常", f"账号: {masked}\n错误: {e}")


def main():
    print("#" * 50)
    print("  HidenCloud 自动续期脚本")
    print("#" * 50)

    accounts = get_accounts()
    if not accounts:
        print("❌ 未找到账号配置 (USERS_JSON)")
        return

    print(f"📋 共 {len(accounts)} 个账号待处理")

    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}

    if IS_PROXY:
        print(f"🔗 挂载代理: {proxy_str}")
        sb_kwargs["proxy"] = proxy_str
    else:
        print("🌐 未使用代理，直连访问")

    for idx, (email, pwd) in enumerate(accounts, 1):
        print(f"\n\n>>> 账号 {idx}/{len(accounts)} <<<")
        try:
            process_account(email, pwd, sb_kwargs)
        except Exception as e:
            print(f"❌ 账号 {idx} 处理异常: {e}")

    print(f"\n{'#' * 50}")
    print(f"  全部账号处理完成")
    print(f"{'#' * 50}")


if __name__ == "__main__":
    main()
