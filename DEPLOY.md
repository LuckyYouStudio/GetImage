# 部署与接入中转站

先判断你手上有什么权限，三条路选一条：

| 你能改什么 | 走哪条 | 效果 |
|---|---|---|
| 中转站服务器 / Caddy | **A. 同域名静态托管** | 最干净，一个文件 + 三行配置 |
| 只有 Sub2API 面板管理员后台 | **B. Cloudflare Worker + 面板自定义菜单** | 不碰服务器；面板侧边栏出现入口，用户点开即用，还能自动带上他自己的 Key |
| 什么都不能改 | 只能走 B，入口靠你自己发链接 | — |

为什么面板后台**自己**放不了这个页面：Sub2API 的 Markdown 自定义页会剥掉 `<script>`；首页 HTML 虽不净化但站点 CSP 禁止内联脚本；页面文件只能放服务器磁盘 `data/pages/`。三个口子都进不去一个需要跑 JS 的页面。CORS 白名单是配置文件项，后台也改不了。这不是本项目的限制，是 Sub2API 的设计。

---

## B. Cloudflare Worker + Sub2API 自定义菜单（面板管理员方案）

原理：Worker 既返回页面，又把 `/v1/*` 转发到 `img.the5288.com`。浏览器看来页面和接口同源，CORS 不再是问题。面板用 iframe 把 Worker 地址嵌进侧边栏，并会自动把这个地址加进自己的 CSP `frame-src`（Sub2API `GetFrameSrcOrigins`），所以不用动任何服务器配置。

需要：一个 Cloudflare 账号（免费版够用）。全程在网页上操作，不需要命令行。

### B1. 生成 Worker 脚本

仓库里已经带了构建好的 `dist/worker.js`。如果你改过 `index.html`，重新生成一次：

```bash
python deploy/build_worker.py
```

### B2. 在 Cloudflare 创建 Worker

1. 登录 Cloudflare → 左侧 **Workers & Pages** → **Create** → **Create Worker**
2. 名字随意（例如 `the5288-studio`），点 **Deploy**（先部署默认的 Hello World）
3. 点 **Edit code**，把编辑器里的内容**全部删掉**，粘贴 `dist/worker.js` 的全部内容，点 **Deploy**
4. 记下地址，形如 `https://the5288-studio.<你的子域>.workers.dev`，浏览器打开应能看到工作台页面，页脚显示「接口 the5288-studio.xxx.workers.dev」

可选：**Settings → Domains & Routes → Add → Custom domain**，绑一个自己的域名（需要域名 DNS 托管在 Cloudflare）。

### B3.（推荐）配置面板地址，启用自动取 Key

Worker → **Settings → Variables and Secrets → Add**：

| 名称 | 值 |
|---|---|
| `PANEL_ORIGIN` | 你的 Sub2API 面板地址，例如 `https://panel.example.com`（**不是** `img.the5288.com`，那只是网关） |

保存后 Worker 会把 `/api/v1/keys` 这一个接口转发到面板。面板 iframe 打开工作台时会带上用户的登录 token，页面用它取到用户自己的 API Key 并自动填好——用户**打开就能出图，不用去复制 Key**。

没配这个变量也能用，只是用户要手动去「API 密钥」页复制一次。

> 如果面板开启了「会话 IP / UA 绑定」，从 Worker 发出的请求 IP 会和用户不一致，自动取 Key 会失败（页面会静默回退到手动填写，不报错）。这种情况要么关掉该绑定，要么接受手动填 Key。

### B4. 在 Sub2API 面板加菜单入口

管理员后台 → **系统设置** → 找到 **「自定义菜单页面」** → **添加菜单项**：

| 字段 | 填什么 |
|---|---|
| 菜单名称 | `图像工作台`（或你喜欢的名字） |
| 页面 URL | B2 里的 Worker 地址，例如 `https://the5288-studio.xxx.workers.dev/` |
| 可见性 | 普通用户 |
| 隐藏"新窗口打开"按钮 | 建议**不勾**——新窗口里页面更大，而且同样能自动取 Key |
| 图标 | 可选，上传一个 SVG |

点页面底部 **保存**。刷新面板，侧边栏应出现新菜单，点开即是工作台。

### B5. 验证

1. 用一个**普通用户**账号登录面板，点新菜单
2. 页面加载后如果右下角弹出「已自动使用你的 API Key「xxx」」，说明 B3 生效；否则会弹设置框让用户填 Key
3. 生成一张图。页脚应显示「面板内嵌 · 接口 …workers.dev」

出问题看这里：

| 现象 | 原因 |
|---|---|
| 面板里一片空白 | 页面 URL 填错，或 Worker 没部署成功。直接在新标签打开 URL 看能否访问 |
| 能打开但生成报「请求被浏览器拦截」 | Worker 脚本不完整（粘贴漏了），`/v1/*` 没被转发。重新粘贴 `dist/worker.js` |
| 生成报 502 `Upstream access forbidden` | 上游拦了 User-Agent。Worker 会透传浏览器 UA，正常不会遇到；若遇到说明中间还有别的代理改了 UA |
| 没有自动取 Key | `PANEL_ORIGIN` 没配或配成了网关地址；或面板开了 IP/UA 绑定 |

### 安全边界

- Worker **只**转发 `/v1/*` 到图片接口、`/api/v1/keys`（仅 GET）到面板，不是通用代理
- 面板登录 token 只在页面内存里用一次，用完立刻从地址栏抹掉，不写 localStorage
- 配了 `PANEL_ORIGIN` 后 Worker 会下发 `frame-ancestors 'self' <面板地址>`，别的站点无法 iframe 它
- 用户的 API Key 存在用户自己浏览器的 localStorage，Worker 不记录任何请求内容

---

## A. 同域名静态托管（有服务器权限时）

把 `index.html` 放到 `img.the5288.com` 下任意路径。页面启动时发现自己在 http(s) 且不是 localhost，就把接口地址设为 `location.origin`——同源，零跨域，零配置。

### 步骤

1. 服务器上建目录，如 `/srv/getimage/`，放入 `index.html`
2. Caddy 站点块加一段（中转站响应头里有 `Via: 1.1 Caddy`）：

```caddyfile
img.the5288.com {
    handle_path /studio/* {
        root * /srv/getimage
        file_server
        header Cache-Control "no-cache"
    }
    handle {
        reverse_proxy 127.0.0.1:3000   # 原有反代，按实际配置
    }
}
```

Nginx 等价：

```nginx
location /studio/ {
    alias /srv/getimage/;
    index index.html;
    add_header Cache-Control "no-cache";
}
```

3. 打开 `https://img.the5288.com/studio/`，页脚应显示「接口 img.the5288.com」

这条路同样可以再用 B4 的方法把地址加进面板菜单；如果也想自动取 Key，需要在 Caddy 里把 `/studio/api/v1/keys` 反代到面板——比 Worker 麻烦，一般直接让用户填一次 Key 就好。

### 页面和接口不同域名时

例如页面在 `tool.the5288.com`、接口在 `img.the5288.com`，需要接口侧下发 CORS 头（Sub2API 配置文件 `cors.allowed_origins`，或在 Caddy 层加）。**能同域就同域，或者直接用方案 B，都比开 CORS 省事。**

---

## 品牌与文案

集中在 `index.html` 开头的 `BRAND` 对象：

```javascript
const BRAND = {
  name: "the5288",              // 顶栏品牌名，也用作下载文件名前缀
  product: "图像工作台",
  company: "LuckyYou Studio",   // 页脚
  homepage: "",                 // 顶栏品牌名的跳转。留空 = 不可点
  keyUrl: "",                   // 用户去哪领 Key。留空 = 设置里不显示链接
  github: "",                   // 页脚 GitHub。留空 = 不显示
  apiHost: "https://img.the5288.com",   // 仅本地 file:// 模式下使用，不是链接
  defaultModel: "gpt-image-2",
  maxHistory: 120,              // 每个用户浏览器里最多保留多少张历史
};
```

三个链接默认全空，页面不带任何外部链接。配色在 `<style>` 开头的 `:root` 变量里。

改完 `index.html` 记得 `python deploy/build_worker.py` 重新生成 Worker。

## 数据与隐私

- **API Key**：用户浏览器 `localStorage`，明文，只在用户自己的设备上
- **历史图片**：用户浏览器 `IndexedDB`，默认最多 120 张（约 200 MB），超出自动淘汰最旧的，「设置」里可一键清除
- 页面无后端、无埋点、无外部资源；`<meta name="referrer" content="no-referrer">`

## 本地运行

`proxy.py` / `启动.bat` / `start.sh` 依然可用，适合部署前预览。要在本地也测试面板嵌入模式：

```bash
python proxy.py --panel https://panel.example.com
```

然后打开 `http://127.0.0.1:8788/?ui_mode=embedded&theme=dark&token=<你的面板登录 token>` 即可模拟面板 iframe 的行为。
