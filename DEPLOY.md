# 部署与接入中转站

先判断你手上有什么权限，三条路选一条：

| 你能改什么 | 走哪条 | 效果 |
|---|---|---|
| 中转站服务器 / Caddy | **A. 放在 Sub2API 旁边，用自己的域名** | 推荐。零外部依赖，Sub2API 升级互不影响，自动取 Key 开箱即用 |
| 只有 Sub2API 面板管理员后台 | **B. Cloudflare Worker / B′. Vercel + 面板自定义菜单** | 不碰服务器；面板侧边栏出现入口，用户点开即用 |
| 什么都不能改 | 只能走 B，入口靠你自己发链接 | — |

无论哪条路，**工具都不进 Sub2API 的代码或容器**，面板侧只用它公开的"自定义菜单页面"功能挂一个入口。

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
| `PANEL_ORIGIN` | Sub2API 面板地址。**默认已是 `https://api.the5288.com`**，不改就不用配；换站点时再设 |

Worker 会把 `/api/v1/keys` 这一个接口转发到面板。面板 iframe 打开工作台时会带上用户的登录 token，页面用它拉取用户自己的全部 API 密钥——用户**打开就能出图，不用去复制 Key**。

用户往往有多个密钥（分属不同分组，价格和可用模型不同），页面按这个顺序决定用哪个：

1. 之前在本页选过的（按面板 user_id 记忆）→ 沿用
2. 只有一个可用密钥 → 直接用
3. 名称或分组名里带「生图 / 图片 / image / 绘 / 画」的 → 优先；唯一命中直接用
4. 仍不确定 → 先用命中的第一个保证能出图，同时弹出选择框（列出全部密钥的名称 · 分组 · 掩码）让用户切换，之后记住

页面底部常驻显示「密钥：xxx · 分组（更换）」，随时可以换。**建议给生图用的分组或密钥起名时带上"生图"二字**，用户就完全不用选。

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

## B′. 用 Vercel 代替 Cloudflare Worker

同样是"托管页面 + 转发 `/v1/*`"，只是跑在 Vercel 上。仓库里已经带好了 `vercel.json`、`api/proxy.js`、`.vercelignore`，**导入仓库即可，不用改任何东西**。

### 步骤

1. Vercel → **Add New → Project** → Import 这个 GitHub 仓库
2. **Framework Preset 选 `Other`**，Build Command / Output Directory 都留空 → **Deploy**
3. 得到 `https://xxx.vercel.app`，打开应看到工作台，页脚显示「接口 xxx.vercel.app」
4. （推荐）**Settings → Environment Variables** 加 `PANEL_ORIGIN` = 面板地址 → **Redeploy**，启用自动取 Key
5. 面板菜单配置同 [B4](#b4-在-sub2api-面板加菜单入口)

### Vercel 与 Cloudflare Worker 怎么选

| | Cloudflare Worker | Vercel |
|---|---|---|
| 部署方式 | 网页粘贴一个文件 | 导入 GitHub 仓库，之后 push 自动重新部署 |
| 出图等待（27–56 秒） | 无限制 | Hobby 计划函数 300 秒，够用 |
| 参考图上传 | 上限 100 MB | **函数请求体上限 4.5 MB**。页面会自动把大图压到 4 MB 以内，正常使用感知不到 |
| 返回的图片（2–3 MB） | 无限制 | 流式回传，不受 4.5 MB 限制 |
| 改了 index.html 之后 | 要重新跑 `build_worker.py` 再粘贴 | push 即生效 |
| 免费额度 | 10 万请求/天 | 100 GB 流量/月、函数按 CPU 时间计（等待上游不计费） |
| 国内访问 | `workers.dev` 域名时好时坏 | `vercel.app` 域名同样不稳定 |

**两者都建议绑一个自己的域名**，免费域名在国内的可达性都不可靠——你的用户如果主要在国内，这一条比其他所有差异都重要。

Vercel 更省事的地方是和 GitHub 联动：以后改代码 push 就自动上线。Cloudflare 更宽松的地方是没有 4.5 MB 这类限制。两个都免费，选顺手的。

### Vercel 上的转发是怎么做的

`vercel.json` 把 `/v1/*`、`/v1beta/*`、`/api/v1/keys` 三条路径 rewrite 到 `api/proxy.js`，原始路径通过 `?p=` 传入；函数用 Node 原生 `fetch` 转发并把响应**流式**写回。之所以不用 Vercel 的"外部 rewrite"直接代理到 `img.the5288.com`：官方文档没有写明外部 rewrite 的上游超时，而出图要 27–56 秒，不敢赌；函数的 300 秒是明确写在文档里的。

`.vercelignore` 把 `proxy.py`、文档、`dist/` 等排除在部署之外，避免它们被当静态文件公开。

---

## A. 部署在自己的服务器上（推荐）

### 原则：放在 Sub2API 旁边，不放进去

工具是一个静态 HTML，所有"接入"都在 **Caddy 这一层**完成：Caddy 负责提供页面、把 `/v1/*` 转到 Sub2API 后端。Sub2API 的代码、容器、数据库一概不碰。

这样做的直接好处是**升级互不影响**：

| 动作 | 影响范围 |
|---|---|
| Sub2API 升级（换镜像 / 换二进制） | 只动 Sub2API 自己。Caddyfile 和 `/srv/studio/` 不在它的管辖范围 |
| 工具升级 | `cd /srv/studio && git pull`，或者只覆盖 `index.html`。Sub2API 不用重启 |
| 面板里的菜单配置 | 存在 Sub2API 数据库的 `custom_menu_items` 里，随数据库一起保留 |

工具对 Sub2API 的依赖只有两处，都是它**公开设计**的特性，不是内部实现：

1. 自定义菜单以 iframe 打开外部 URL，并自动把该 URL 加进 CSP `frame-src`
2. iframe 地址附带 `token` / `user_id` / `theme`；工具据此调 `GET /api/v1/keys` 自动填 Key

即便某次升级改了 (2) 的接口结构，工具只会退回到"让用户手动填一次 Key"，功能不受影响。别把 HTML 塞进 Sub2API 的 `data/pages/` 靠图片接口回 `text/html`——那是副作用，不是承诺。

### A1. 独立子域名（推荐）

`studio.the5288.com` 专门给工具用，域名干净、和网关互不干扰。

**1. 放文件**

```bash
git clone https://github.com/LuckyYouStudio/GetImage.git /srv/studio
```

只有 `index.html` 会被服务，其余文件不会暴露（见下面 `file_server` 只指向单文件的写法）。

**2. Caddyfile 加一个站点块**

先在你现有的 Caddyfile 里找到 `img.the5288.com` 那段的 `reverse_proxy` 目标（形如 `reverse_proxy sub2api:8080` 或 `127.0.0.1:8080`），下面记作 `<后端>`：

```caddyfile
studio.the5288.com {
    encode zstd gzip

    # 图片接口：转给 Sub2API 后端，浏览器看来与页面同源
    handle /v1/* {
        reverse_proxy <后端>
    }
    handle /v1beta/* {
        reverse_proxy <后端>
    }

    # 面板嵌入时自动取 Key 用。只放行这一个接口，不要把整个 /api 开出去
    @keys {
        path /api/v1/keys
        method GET
    }
    handle @keys {
        reverse_proxy <后端>
    }

    # 其余一律回页面（带 query 的嵌入地址、任意子路径都能命中）
    handle {
        root * /srv/studio
        rewrite * /index.html
        file_server
        header Cache-Control "no-cache"
        header X-Content-Type-Options "nosniff"
        header Referrer-Policy "no-referrer"
    }
}
```

`rewrite * /index.html` 保证只有这一个文件会被服务，仓库里的 `proxy.py`、文档等都不会被访问到。

Docker Compose 部署的 Caddy 需要把目录挂进容器：

```yaml
services:
  caddy:
    volumes:
      - /srv/studio:/srv/studio:ro
```

**3. DNS**：`studio.the5288.com` 解析到这台服务器。Caddy 会自动签证书。

**4. 验证**：打开 `https://studio.the5288.com/`，页脚显示「接口 studio.the5288.com」。填 Key 生成一张。

**5. 面板入口**：按 [B4](#b4-在-sub2api-面板加菜单入口) 把 `https://studio.the5288.com/` 加进自定义菜单。因为 `/api/v1/keys` 已经在同一域名下反代到了后端，**自动取 Key 直接可用，不需要任何额外配置**。

### A2. 挂在网关域名的子路径下

不想加子域名时，也可以放在 `img.the5288.com/studio/`：

```caddyfile
img.the5288.com {
    handle_path /studio/* {
        root * /srv/studio
        rewrite * /index.html
        file_server
        header Cache-Control "no-cache"
    }
    @keys {
        path /api/v1/keys
        method GET
    }
    handle @keys {
        reverse_proxy <后端>
    }
    # ---- 原有的 /v1/* 反代保持不动 ----
}
```

页脚应显示「接口 img.the5288.com」。缺点是工具和网关共用域名，日志、限流、以后换域名都会牵扯在一起；A1 更清爽。

### Nginx 等价（A1）

```nginx
server {
    server_name studio.the5288.com;

    location /v1/     { proxy_pass http://<后端>; proxy_read_timeout 300s; }
    location /v1beta/ { proxy_pass http://<后端>; proxy_read_timeout 300s; }
    location = /api/v1/keys {
        limit_except GET { deny all; }
        proxy_pass http://<后端>;
    }
    location / {
        root /srv/studio;
        try_files /index.html =404;
        add_header Cache-Control "no-cache";
    }
}
```

`proxy_read_timeout` 一定要给够——出图 27–56 秒，Nginx 默认 60 秒太贴边。

### 以后怎么更新工具

```bash
cd /srv/studio && git pull
```

没有构建步骤，没有重启，刷新页面即生效。改品牌 / 文案在 `index.html` 开头的 `BRAND` 对象里，改完同样 `git pull` 或直接覆盖文件。

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
