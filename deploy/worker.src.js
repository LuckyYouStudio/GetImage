/**
 * the5288 图像工作台 —— Cloudflare Worker 托管层（源码模板）
 *
 * 这个文件不能直接部署：占位符 __HTML__ 需要由 build_worker.py 替换成 index.html 的内容，
 * 生成 dist/worker.js 后再粘贴到 Cloudflare 控制台。
 *
 * 它做三件事：
 *   1. 任何 GET 请求 → 返回 index.html（页面）
 *   2. /v1/*         → 原样转发到图片接口（API_ORIGIN），让浏览器看来页面和接口同源，从而绕开
 *                      接口不下发 CORS 头的问题
 *   3. /api/v1/keys  → 转发到 Sub2API 面板（PANEL_ORIGIN），供面板 iframe 嵌入时用登录 token
 *                      自动取用户自己的 API Key。未配置 PANEL_ORIGIN 时该路径直接 404，页面会
 *                      静默回退到手动填 Key。只放行这一个面板接口，不做通用代理。
 *
 * 配置优先级：Cloudflare 环境变量（Settings → Variables）> 下面的 CONFIG 常量。
 */

const CONFIG = {
  API_ORIGIN: "https://img.the5288.com",
  PANEL_ORIGIN: "https://api.the5288.com",   // Sub2API 面板（5288API）。设为空字符串可关闭自动取 Key
  // 实测接口会拦截 Python-urllib 这类 UA；浏览器的 UA 会原样透传，这里只是缺 UA 时的兜底
  FALLBACK_UA: "curl/8.4.0",
};

const HTML = __HTML__;

// 只透传必要的请求头；Host / Origin / Referer / Cookie 之类带过去反而可能被上游拒绝
const FORWARD_REQ = new Set([
  "authorization", "content-type", "accept", "user-agent",
  "x-api-key", "openai-organization", "openai-project",
]);
// 上游若带了 CORS 头一律去掉——本 Worker 下页面与接口同源，不需要，留着反而扩大暴露面
const STRIP_RESP = ["access-control-allow-origin", "access-control-allow-credentials",
  "access-control-allow-headers", "access-control-allow-methods", "access-control-expose-headers"];

export default {
  async fetch(request, env) {
    const cfg = {
      apiOrigin: trimSlash((env && env.API_ORIGIN) || CONFIG.API_ORIGIN),
      panelOrigin: trimSlash((env && env.PANEL_ORIGIN !== undefined) ? env.PANEL_ORIGIN : CONFIG.PANEL_ORIGIN),
      ua: (env && env.FALLBACK_UA) || CONFIG.FALLBACK_UA,
    };
    const url = new URL(request.url);
    const path = url.pathname;

    if (path.startsWith("/v1/") || path.startsWith("/v1beta/")) {
      return proxy(request, cfg.apiOrigin + path + url.search, cfg);
    }

    if (path === "/api/v1/keys") {
      if (!cfg.panelOrigin) return json(404, "PANEL_ORIGIN 未配置，自动取 Key 已关闭");
      if (request.method !== "GET") return json(405, "method not allowed");
      return proxy(request, cfg.panelOrigin + path + url.search, cfg);
    }

    if (request.method === "GET" || request.method === "HEAD") {
      // 其余任何路径都回页面：部署在子路径、带 query（面板嵌入参数）都能命中
      const headers = {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-cache",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
      };
      // 配了面板地址就只允许面板 iframe 本页；没配则不限制（否则面板嵌不进来）
      if (cfg.panelOrigin) headers["content-security-policy"] = `frame-ancestors 'self' ${cfg.panelOrigin}`;
      return new Response(request.method === "HEAD" ? null : HTML, { status: 200, headers });
    }

    return json(404, "not found");
  },
};

async function proxy(request, target, cfg) {
  const headers = new Headers();
  for (const [k, v] of request.headers) if (FORWARD_REQ.has(k.toLowerCase())) headers.set(k, v);
  if (!headers.has("user-agent")) headers.set("user-agent", cfg.ua);

  const hasBody = !(request.method === "GET" || request.method === "HEAD");
  let upstream;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
    });
  } catch (e) {
    return json(502, "转发失败：" + (e && e.message ? e.message : String(e)));
  }

  const rh = new Headers(upstream.headers);
  STRIP_RESP.forEach((k) => rh.delete(k));
  rh.set("cache-control", "no-store");
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: rh });
}

function json(status, message) {
  return new Response(JSON.stringify({ error: { message, type: "worker_error" } }), {
    status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}
function trimSlash(s) { return String(s || "").trim().replace(/\/+$/, ""); }
