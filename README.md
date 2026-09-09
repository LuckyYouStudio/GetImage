# AI 图片生成器

调用 OpenAI 兼容图片接口（`https://img.the5288.com`）的跨平台文生图工具。Windows / macOS / Linux 通用。

```
getImage/
├─ 启动.bat     ← Windows 用户双击这个
├─ start.bat    同上（ASCII 文件名版本）
├─ start.sh     macOS / Linux 启动
├─ index.html   主界面（不要直接双击，见下方说明）
├─ proxy.py     本地启动器：静态服务 + API 转发（Python 3.7+，无第三方依赖）
└─ README.md
```

## 快速开始

> ⚠️ **不要直接双击 `index.html`** —— 那样打开会被浏览器的 CORS 策略拦死，什么都发不出去。

**Windows：** 双击 **`启动.bat`**
**macOS / Linux：** 终端里 `./start.sh`
**任意平台：** `python proxy.py`

黑窗口会留着（那是本地服务，关掉即停止），浏览器自动打开 `http://127.0.0.1:8788/`，然后：

1. 填 **API Key**（Base URL 已自动填好，不用管）
2. 点模型框旁的 **「拉取」** —— 会列出服务端实际支持的模型，挑一个图像模型；默认已填 `gpt-image-2`，也可手输其他模型名
3. 写提示词 → **生成图片**（或 `Ctrl` / `⌘` + `Enter`）

生成的图点一下放大，下方有「下载」和「复制提示词」。

## 为什么必须跑 `proxy.py`，不能直接双击 index.html

已实测确认：`img.the5288.com` 的 `OPTIONS` 预检请求返回 **403，且不下发任何 `Access-Control-Allow-*` 响应头**。而带 `Authorization` 头和 JSON body 的 POST 必然触发预检 —— 所以用 `file://` 直接打开页面，请求 100% 会被浏览器的同源策略拦掉。这是服务端的 CORS 配置问题，不是代码问题。

`proxy.py` 的解法是让页面和 API **走同一个源**：它在 `127.0.0.1:8788` 上既提供 `index.html`，又把 `/v1/*` 的请求转发到目标站，同源了自然就不存在跨域。

页面能识别自己是怎么被打开的：经代理打开时提示"不会被 CORS 拦截"，被 `file://` 直接打开时会明确提示去跑 `proxy.py`。

代理只做转发 + 补 CORS 头，**仅监听回环地址** `127.0.0.1`（外网访问不到），不读取也不存储 API Key —— Key 随请求头原样透传给目标服务。

常用参数：

8788 端口被占用时会自动往后顺延（8789、8790…最多试 12 个），不用手动处理。

```bash
python proxy.py --port 8899                        # 指定起始端口
python proxy.py --target https://other-relay.com   # 换中转站
python proxy.py --no-browser                       # 不自动开浏览器
```

## 请求格式

标准 OpenAI 格式，`POST {BaseURL}/v1/images/generations`：

```json
{
  "model": "gpt-image-2",
  "prompt": "...",
  "n": 1,
  "size": "1024x1024",
  "quality": "high"
}
```

- 认证：`Authorization: Bearer <API Key>`
- 返回的 `data[].b64_json` 和 `data[].url` 两种形式都能正确显示
- 选「自动（不传）」的参数不会出现在请求体里 —— 遇到「不支持该参数」类报错时，把对应项切回「不传」通常就能解决
- 错误信息同时兼容 OpenAI 的 `{"error":{"message"}}` 和该中转站的 `{"code","message"}` 两种格式
- Base URL 会自动规范化：去尾部斜杠、补 `/v1`、补 `https://`

## 自动化对接

要在脚本 / 服务里直接调这个接口，见 [API.md](API.md) —— 完整的 HTTP 协议、实测过的参数行为、错误格式，以及 curl / Python / Node / PowerShell 的可运行示例。

## 排错记录（实测结论）

**502 `Upstream access forbidden, please contact administrator`**
中转站会拦截 `User-Agent: Python-urllib/x.y`，而 Python 的 urllib 在请求头缺 UA 时会自动补上这个值 —— 于是经代理的请求全被拒。已修复：`proxy.py` 透传浏览器自己的 UA，非浏览器客户端回落到 `curl/8.4.0`（已验证可用）。改动见 `FALLBACK_UA`。

**502 `Upstream request failed`**
换模型。实测该中转站上 `gpt-image-1` 和 `gpt-image-1.5` 都返回这个错，只有 `gpt-image-2` 可用（单张约 50 秒）。

生成失败时页面会自动去核对 `/v1/models`，告诉你所选模型在不在服务端列表里 —— 能直接区分模型名写错和有权限问题。

## API Key 存在哪

浏览器 `localStorage`，**明文**，仅限本机本浏览器。不进 git，也不会发给除 Base URL 指向的服务之外的任何地方。

清除方式：开发者工具 Console 执行 `localStorage.removeItem('img-gen-config-v1')`，或换用无痕窗口。共享电脑上别存高额度的 Key。

## 已知限制

- 只做文生图。图生图 / 编辑（`/v1/images/edits`）、批量任务、历史归档均未实现。
- 若接口返回的是图片 `url` 而非 base64，点「下载」会新开标签页（跨域限制导致无法直接触发保存），需手动右键另存；返回 base64 的可直接保存。
- 生成结果只在当前页面会话中保留，刷新即清空。
