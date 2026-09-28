# 部署到中转站域名下

目标形态：用户打开 `https://img.the5288.com/<某路径>/`，填自己的 Key 就能用。**不需要 proxy.py，不需要改服务端的 CORS。**

## 为什么放在同一域名下就够了

之前所有的跨域麻烦（OPTIONS 403、无 `Access-Control-Allow-*` 头）都源于页面和接口不同源。浏览器的同源策略只管**跨源**请求——页面在 `img.the5288.com` 上，接口也在 `img.the5288.com` 上，请求根本不经过 CORS 检查。

页面启动时会自动判断：`location.origin` 是 `http(s)` 且不是 localhost → 认为自己部署在接口域名下，接口地址默认取 `location.origin`。所以**文件原样放上去，零配置。**

## 部署步骤

只有一个文件需要部署：`index.html`。

### 1. 放置文件

在服务器上任选一个目录，例如 `/srv/getimage/`，把 `index.html` 放进去。

### 2. 反向代理加一条静态路由

中转站前面是 Caddy（响应头里有 `Via: 1.1 Caddy`）。在 `img.the5288.com` 的站点块里加：

```caddyfile
img.the5288.com {
    # ---- 新增：图像工作台静态页面 ----
    handle_path /studio/* {
        root * /srv/getimage
        file_server
        header Cache-Control "no-cache"
    }

    # ---- 原有的 API 反代保持不动 ----
    handle {
        reverse_proxy 127.0.0.1:3000   # 示意，按实际配置
    }
}
```

`/studio/` 可以换成任何路径。`handle_path` 会剥掉前缀再去找文件，所以 `/studio/` 会命中 `/srv/getimage/index.html`。

Nginx 等价写法：

```nginx
location /studio/ {
    alias /srv/getimage/;
    index index.html;
    add_header Cache-Control "no-cache";
}
```

### 3. 验证

打开 `https://img.the5288.com/studio/`，页脚应显示「接口 img.the5288.com」。填 Key，生成一张。

页脚显示的是页面对自己运行环境的判断——如果显示的不是这个，说明部署位置不对。

## 品牌与文案

所有可改的东西都集中在 `index.html` 的 `<script>` 开头的 `BRAND` 对象里：

```javascript
const BRAND = {
  name: "the5288",              // 顶栏品牌名，也用作下载文件名前缀
  product: "图像工作台",         // 顶栏产品名
  company: "LuckyYou Studio",   // 页脚
  homepage: "",                 // 顶栏品牌名的跳转。留空 = 不可点
  keyUrl: "",                   // 用户去哪领 Key。留空 = 设置里不显示链接
  github: "",                   // 页脚 GitHub。留空 = 不显示
  apiHost: "https://img.the5288.com",   // 仅本地 file:// 模式下使用，不是链接
  defaultModel: "gpt-image-2",
  maxHistory: 120,              // 每个用户浏览器里最多保留多少张历史
};
```

**建议填上 `keyUrl`**——指向中转站的控制台或购买页，新用户第一次打开就能顺着链接去拿 Key。

配色在 `<style>` 开头的 `:root` 变量里，取的是 the5288.com 的 `#1f6feb` 主色系。

## 如果页面和接口不在同一域名

例如页面放 `tool.the5288.com`，接口在 `img.the5288.com`——这就又是跨源了，需要接口侧返回 CORS 头。中转站的 Caddy 配置需要加：

```caddyfile
img.the5288.com {
    @preflight method OPTIONS
    handle @preflight {
        header Access-Control-Allow-Origin  "https://tool.the5288.com"
        header Access-Control-Allow-Methods "GET, POST, OPTIONS"
        header Access-Control-Allow-Headers "Authorization, Content-Type"
        header Access-Control-Max-Age       "86400"
        respond "" 204
    }
    header Access-Control-Allow-Origin "https://tool.the5288.com"
    # ...原有反代
}
```

然后用户在「设置 → 高级 → 接口地址」填 `https://img.the5288.com`。**能同域就同域，省掉这一整段。**

## 数据与隐私

- **API Key**：浏览器 `localStorage`，明文，只在用户自己的设备上。页面不会把 Key 发给接口以外的任何地方。
- **历史图片**：浏览器 `IndexedDB`，每张约 1–2 MB，默认最多 120 张（约 200 MB 上限），超出自动淘汰最旧的。用户可在「设置」里一键清除。
- 页面本身**没有任何后端、埋点或外部请求**——除了用户主动发起的接口调用。`<meta name="referrer" content="no-referrer">` 保证接口那边也看不到来源页。

## 本地运行方式保留

`proxy.py` / `启动.bat` / `start.sh` 依然可用，适合：

- 部署前本地预览
- 不方便部署时给个别用户单独用

本地模式下页面会自动识别（页脚显示「本地模式」），接口地址走 `127.0.0.1` 上的代理。
