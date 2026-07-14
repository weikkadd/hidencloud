# HidenCloud 自动续期脚本

基于 **SeleniumBase UC 模式** 绕过 Cloudflare Turnstile 验证码，支持 sing-box 全协议代理、多账号、Telegram 通知、人类行为模拟。

## ✨ 特性

- 🤖 **SeleniumBase UC 模式** — 修补 Chrome 二进制，深度反检测，绕过 Cloudflare Turnstile
- 🖱️ **`uc_gui_click_captcha()`** — SeleniumBase 内置方法，通过 PyAutoGUI 发送真实 X11 鼠标事件（`isTrusted=true`）
- 👤 **人类行为模拟** — 逐字符输入、鼠标移动、页面滚动
- 🌐 **全协议代理** — VLESS / VMess / Trojan / Shadowsocks / SOCKS5 / TUIC / Hysteria2 / AnyTLS
- 👥 **多账号支持** — `USERS_JSON` 配置多个账号
- 💳 **自动续期 + 支付** — 续期后自动完成支付流程
- 📲 **Telegram 通知** — 续期结果推送
- ⏰ **定时任务** — 每 3 天自动运行

## 🚀 配置与使用

### 1. 配置 Secrets

在仓库 `Settings` → `Secrets and variables` → `Actions` 中添加：

| Secret 名称 | 必填 | 说明 |
|-------------|:---:|------|
| `USERS_JSON` | ✅ | JSON 数组：`[{"username":"email","password":"pwd"}]` |
| `PROXY_NODE` | ❌ | 代理链接（可选，建议住宅代理） |
| `TG_BOT_TOKEN` | ❌ | Telegram Bot Token |
| `TG_CHAT_ID` | ❌ | Telegram Chat ID |

**`USERS_JSON` 格式示例**（单账号）：
```json
[{"username":"your_email@example.com","password":"your_password"}]
```

**多账号示例**：
```json
[{"username":"email1@example.com","password":"pwd1"},{"username":"email2@example.com","password":"pwd2"}]
```

### 2. 代理格式（可选）

| 协议 | 示例 |
|------|------|
| VLESS | `vless://uuid@host:port?type=ws&security=tls&sni=...` |
| VMess | `vmess://eyJhZGQiOi...` |
| Trojan | `trojan://password@host:port?type=ws&sni=...` |
| TUIC | `tuic://uuid:password@host:port?sni=...` |
| Hysteria2 | `hysteria2://password@host:port?sni=...` |
| SOCKS5 | `socks5://user:pass@host:port` |

⚠️ Cloudflare Turnstile 对 IP 信誉有要求，机房 IP 可能过不了，建议用住宅代理。

### 3. 运行

- **定时运行**：每 3 天 UTC 10:00 自动触发
- **手动运行**：Actions → `HidenCloud 自动续期` → Run workflow

## 🛠️ 项目结构

| 文件 | 说明 |
|------|------|
| `app.py` | 主程序（Python + SeleniumBase） |
| `.github/workflows/renew1.yml` | GitHub Actions 工作流 |

## 🔧 工作原理

1. **启动浏览器** — SeleniumBase UC 模式
2. **打开登录页** — 等待 Cloudflare 验证
3. **模拟人类行为** — 鼠标移动 + 滚动
4. **逐字符输入** — 邮箱/密码
5. **Turnstile 验证** — 检测 invisible 模式，优先等待，失败后用 `uc_gui_click_captcha()` + xdotool
6. **登录提交** — 点击按钮或回车
7. **续期 API** — 通过浏览器 fetch 调用 `/service/{id}/renew`
8. **自动支付** — 解析账单页面，提交支付表单
9. **Telegram 通知** — 推送结果

## 📄 许可证

MIT License
