/**
 * the5288 图像工作台 —— Vercel 托管层的转发函数
 *
 * 与 deploy/worker.src.js（Cloudflare 版）职责相同，只是运行在 Vercel Functions（Node.js）上：
 *   /v1/*, /v1beta/*  → 转发到图片接口（API_ORIGIN），让页面与接口同源
 *   /api/v1/keys      → 仅 GET，转发到 Sub2API 面板（PANEL_ORIGIN），供面板嵌入时自动取 Key
 *
 * 路由由 vercel.json 的 rewrites 完成，原始路径通过 ?p= 传进来；index.html 由 Vercel 作为静态文件直接服务。
 *
 * 配置：Vercel 项目 Settings → Environment Variables
 *   API_ORIGIN    默认 https://img.the5288.com
 *   PANEL_ORIGIN  可选，Sub2API 面板地址；不设则 /api/v1/keys 返回 404，页面回退到手动填 Key
 *
 * 平台限制（Vercel Functions）：请求体与响应体各 4.5 MB 上限；maxDuration 300s（vercel.json 已设）。
 */

const { Readable } = require("node:stream");

const API_ORIGIN = trimSlash(process.env.API_ORIGIN || "https://img.the5288.com");
// Sub2API 面板（5288API）。环境变量设为空字符串可关闭自动取 Key
const PANEL_ORIGIN = trimSlash(process.env.PANEL_ORIGIN !== undefined ? process.env.PANEL_ORIGIN : "https://api.the5288.com");
// 实测接口会拦截 Python-urllib 之类的 UA；浏览器 UA 原样透传，这里只是缺 UA 时的兜底
const FALLBACK_UA = process.env.FALLBACK_UA || "curl/8.4.0";

const FORWARD_REQ = new Set([
  "authorization", "content-type", "accept", "user-agent",
  "x-api-key", "openai-organization", "openai-project",
]);
// 上游若带 CORS 头一律去掉——同源部署不需要；也不回传会干扰 Node 流式输出的逐跳头
const STRIP_RESP = new Set([
  "access-control-allow-origin", "access-control-allow-credentials", "access-control-allow-headers",
  "access-control-allow-methods", "access-control-expose-headers",
  "transfer-encoding", "connection", "content-encoding", "content-length",
]);

module.exports = async function handler(req, res) {
  const url = new URL(req.url, "http://localhost");
  const path = url.searchParams.get("p") || "";
  url.searchParams.delete("p");
  const search = url.searchParams.toString() ? "?" + url.searchParams.toString() : "";

  let target;
  if (path.startsWith("/v1/") || path.startsWith("/v1beta/")) {
    target = API_ORIGIN + path + search;
  } else if (path === "/api/v1/keys") {
    if (!PANEL_ORIGIN) return json(res, 404, "PANEL_ORIGIN 未配置，自动取 Key 已关闭");
    if (req.method !== "GET") return json(res, 405, "method not allowed");
    target = PANEL_ORIGIN + path + search;
  } else {
    return json(res, 404, "not found");
  }

  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) {
    if (FORWARD_REQ.has(k.toLowerCase()) && v) headers[k] = Array.isArray(v) ? v.join(", ") : v;
  }
  if (!headers["user-agent"]) headers["user-agent"] = FALLBACK_UA;

  const hasBody = !(req.method === "GET" || req.method === "HEAD");
  let upstream;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await readBody(req) : undefined,
      redirect: "manual",
    });
  } catch (e) {
    return json(res, 502, "转发失败：" + (e && e.message ? e.message : String(e)));
  }

  res.statusCode = upstream.status;
  upstream.headers.forEach((v, k) => { if (!STRIP_RESP.has(k.toLowerCase())) res.setHeader(k, v); });
  res.setHeader("cache-control", "no-store");
  if (!upstream.body || req.method === "HEAD") return res.end();
  // 流式回传：不在内存里攒完整个 2–3 MB 的响应
  Readable.fromWeb(upstream.body).pipe(res);
};

function readBody(req) {
  // Vercel 对 JSON / 表单请求可能已把 req.body 解析好；multipart 与其他类型则保留原始流
  if (req.body !== undefined && req.body !== null) {
    if (Buffer.isBuffer(req.body)) return req.body;
    if (typeof req.body === "string") return Buffer.from(req.body);
    if (typeof req.body === "object") return Buffer.from(JSON.stringify(req.body));
  }
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function json(res, status, message) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.end(JSON.stringify({ error: { message, type: "vercel_proxy_error" } }));
}
function trimSlash(s) { return String(s || "").trim().replace(/\/+$/, ""); }
